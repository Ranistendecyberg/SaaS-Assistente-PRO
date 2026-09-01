"""Painel administrativo exclusivo do Supabase.

Este módulo não contém URL, leitura ou escrita do Firebase. Todas as mutações
passam pela Edge Function administrativa e exigem a sessão MFA em memória.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import threading
import tkinter as tk
import urllib.request
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote
from tkinter import filedialog, messagebox, simpledialog, ttk

import customtkinter as ctk

from admin_supabase import AdminSession, AdminSupabaseClient, friendly_auth_error


BG = "#0B0F17"
CARD = "#161F30"
BORDER = "#24324D"
TEXT = "#F8FAFC"
MUTED = "#94A3B8"
PRIMARY = "#4F46E5"
SUCCESS = "#10B981"
DANGER = "#EF4444"
WARNING = "#F59E0B"


def _relation(value):
    if isinstance(value, list):
        return value[0] if value else {}
    return value if isinstance(value, dict) else {}


def _display_date(value):
    if not value:
        return "—"
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return str(value)


def _iso_end_of_day(value):
    parsed = dt.datetime.strptime(value.strip(), "%d/%m/%Y")
    return parsed.replace(hour=22, minute=0, second=0).astimezone().isoformat()


def _parse_monthly_price(value):
    """Valor monetário finito com até dois decimais (formato BR ou decimal)."""
    text = str(value).strip().removeprefix("R$").strip()
    if "," in text:
        if not re.fullmatch(r"(?:\d+|\d{1,3}(?:\.\d{3})+),\d{1,2}", text):
            raise ValueError("Mensalidade inválida")
        text = text.replace(".", "").replace(",", ".")
    elif not re.fullmatch(r"\d+(?:\.\d{1,2})?", text):
        raise ValueError("Mensalidade inválida")
    try:
        price = Decimal(text)
    except InvalidOperation as error:
        raise ValueError("Mensalidade inválida") from error
    if not price.is_finite() or not Decimal("0") <= price <= Decimal("99999999.99"):
        raise ValueError("Mensalidade inválida")
    return float(price)


_REPORT_ID_PATTERN = re.compile(r"00O[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?")


def _normalize_report_id(value):
    """Aceita ID ou URL do myHonda e devolve somente o ID Salesforce."""
    raw = unquote(str(value or "").strip())
    if not raw:
        return ""

    # Também tolera um link colado no formato Markdown: [texto](https://...).
    markdown = re.fullmatch(r"\[[^\]]*\]\((https://[^)]+)\)", raw, flags=re.IGNORECASE)
    if markdown:
        raw = markdown.group(1).strip()

    if _REPORT_ID_PATTERN.fullmatch(raw):
        return raw

    if raw.lower().startswith("https://"):
        match = _REPORT_ID_PATTERN.search(raw)
        if match:
            return match.group(0)

    raise ValueError(
        "Informe somente o ID do relatório (ex.: 00OVP000008YZJh) "
        "ou cole o link completo do myHonda."
    )


class SupabaseAdminApp(ctk.CTk):
    def __init__(self, session: AdminSession):
        super().__init__()
        self.session = session
        self.client = AdminSupabaseClient(timeout=35)
        self.installations = {}
        self.keys = {}
        self.system = {}
        self.client_sort_column = "company"
        self.client_sort_reverse = False
        self.title("SaaS Assistente PRO — Administração Supabase")
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = min(1480, int(screen_w * .94)), min(900, int(screen_h * .90))
        self.geometry(f"{width}x{height}+{max(0, (screen_w-width)//2)}+{max(0, (screen_h-height)//2)}")
        self.minsize(1080, 680)
        self.configure(fg_color=BG)
        self._configure_tree_style()
        self._build()
        self._kpi_columns = 4
        self.bind("<Configure>", self._responsive_layout)
        self.after(0, lambda: self.state("zoomed"))
        self.after(150, self.refresh_all)

    def _configure_tree_style(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Secure.Treeview", background="#121A29", foreground=TEXT,
                        fieldbackground="#121A29", rowheight=36, borderwidth=0,
                        font=("Segoe UI", 10))
        style.configure("Secure.Treeview.Heading", background="#1E293B", foreground=MUTED,
                        relief="flat", font=("Segoe UI", 10, "bold"))
        style.map("Secure.Treeview", background=[("selected", PRIMARY)], foreground=[("selected", "white")])

    def _build(self):
        shell = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        shell.pack(fill="both", expand=True)
        sidebar = ctk.CTkFrame(shell, width=250, fg_color="#101827", corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=24, pady=(34, 38))
        ctk.CTkLabel(brand, text="⚡", text_color=TEXT,
                     font=ctk.CTkFont(size=28, weight="bold")).pack(side="left", padx=(0, 12))
        title_box = ctk.CTkFrame(brand, fg_color="transparent")
        title_box.pack(side="left")
        ctk.CTkLabel(title_box, text="ASSISTENTE PRO", text_color=TEXT,
                     font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_box, text="ADMIN CONSOLE · SUPABASE", text_color="#38BDF8",
                     font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", pady=(3, 0))

        self.nav_buttons = {}
        for key, label in [
            ("clients", "▦  Clientes & Máquinas"),
            ("system", "🚀  Distribuição & Preços"),
            ("keys", "🔑  Gerador de Licenças"),
            ("audit", "◉  Diagnósticos & Logs"),
        ]:
            button = ctk.CTkButton(
                sidebar, text=label, anchor="w", height=52, corner_radius=9,
                fg_color="transparent", hover_color="#1E293B", text_color=MUTED,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda page=key: self._show_page(page),
            )
            button.pack(fill="x", padx=14, pady=5)
            self.nav_buttons[key] = button
        ctk.CTkLabel(sidebar, text="🔐 MFA ativo\nOperações registradas em auditoria",
                     text_color="#64748B", justify="left",
                     font=ctk.CTkFont(size=11)).pack(side="bottom", anchor="w", padx=26, pady=25)

        main = ctk.CTkFrame(shell, fg_color=BG, corner_radius=0)
        main.pack(side="left", fill="both", expand=True)
        header = ctk.CTkFrame(main, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(22, 12))
        header_titles = ctk.CTkFrame(header, fg_color="transparent")
        header_titles.pack(side="left")
        self.page_title = ctk.CTkLabel(header_titles, text="Clientes & Máquinas", text_color=TEXT,
                                      font=ctk.CTkFont(size=24, weight="bold"))
        self.page_title.pack(anchor="w")
        self.page_subtitle = ctk.CTkLabel(
            header_titles, text="Visão consolidada das instalações e licenças",
            text_color=MUTED, font=ctk.CTkFont(size=11),
        )
        self.page_subtitle.pack(anchor="w", pady=(1, 0))
        self.status = ctk.CTkLabel(header, text="Conectando ao Supabase...", text_color=WARNING,
                                   fg_color=CARD, corner_radius=14, height=30, padx=13)
        self.status.pack(side="right", padx=12)
        ctk.CTkButton(header, text="↻  Atualizar dados", width=150, height=38,
                      command=self.refresh_all, fg_color=PRIMARY).pack(side="right")

        self.kpi_frame = ctk.CTkFrame(main, fg_color="transparent")
        self.kpi_frame.pack(fill="x", padx=30, pady=(0, 14))
        for column in range(4):
            self.kpi_frame.grid_columnconfigure(column, weight=1, uniform="kpi")
        self.kpi_labels = {}
        self.kpi_cards = []
        for key, title, icon in [
            ("machines", "MÁQUINAS INSTALADAS", "▣"),
            ("online", "ONLINE AGORA", "◉"),
            ("price", "PREÇO PADRÃO GLOBAL", "＄"),
            ("version", "VERSÃO EM PRODUÇÃO", "🚀"),
        ]:
            card = ctk.CTkFrame(self.kpi_frame, width=145, fg_color=CARD, border_width=1,
                                border_color=BORDER, corner_radius=13)
            card.grid(row=0, column=len(self.kpi_labels), sticky="ew", padx=6)
            self.kpi_cards.append(card)
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=18, pady=(15, 0))
            ctk.CTkLabel(top, text=title, text_color="#7890B8",
                         font=ctk.CTkFont(size=10, weight="bold")).pack(side="left")
            ctk.CTkLabel(top, text=icon, text_color=TEXT).pack(side="right")
            value = ctk.CTkLabel(card, text="—", text_color=TEXT,
                                 font=ctk.CTkFont(size=24, weight="bold"))
            value.pack(anchor="w", padx=18, pady=(8, 1))
            sub = ctk.CTkLabel(card, text="Sincronizando...", text_color="#8EA6CC",
                               font=ctk.CTkFont(size=11))
            sub.pack(anchor="w", padx=18, pady=(0, 15))
            self.kpi_labels[key] = (value, sub)

        self.content = ctk.CTkFrame(main, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=30, pady=(0, 20))
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self.tab_clients = ctk.CTkFrame(self.content, fg_color="transparent")
        self.tab_keys = ctk.CTkFrame(self.content, fg_color="transparent")
        self.tab_system = ctk.CTkFrame(self.content, fg_color="transparent")
        self.tab_audit = ctk.CTkFrame(self.content, fg_color="transparent")
        self.pages = {"clients": self.tab_clients, "keys": self.tab_keys,
                      "system": self.tab_system, "audit": self.tab_audit}
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")
        self._build_clients()
        self._build_keys()
        self._build_system()
        self._build_audit()
        self._show_page("clients")

    def _responsive_layout(self, event):
        if event.widget is not self or not hasattr(self, "kpi_cards"):
            return
        columns = 2 if event.width < 1180 else 4
        if columns == getattr(self, "_kpi_columns", None):
            return
        self._kpi_columns = columns
        for index in range(4):
            self.kpi_frame.grid_columnconfigure(index, weight=1 if index < columns else 0)
        for index, card in enumerate(self.kpi_cards):
            card.grid_configure(row=index // columns, column=index % columns,
                                pady=6 if columns == 2 else 0)

    def _show_page(self, key):
        titles = {
            "clients": ("Clientes & Máquinas", "Visão consolidada das instalações e licenças"),
            "system": ("Distribuição & Preços", "Controle de versões, atualizações e comunicação"),
            "keys": ("Gerador de Licenças", "Criação e rastreabilidade de chaves temporárias"),
            "audit": ("Diagnósticos & Logs", "Investigação remota com dados protegidos"),
        }
        self.pages[key].tkraise()
        self.page_title.configure(text=titles[key][0])
        self.page_subtitle.configure(text=titles[key][1])
        for page_key, button in self.nav_buttons.items():
            selected = page_key == key
            button.configure(fg_color=PRIMARY if selected else "transparent",
                             text_color="white" if selected else MUTED)

    def _toolbar_button(self, parent, text, command, color=PRIMARY):
        return ctk.CTkButton(parent, text=text, command=command, height=36,
                             fg_color=color, font=ctk.CTkFont(size=12, weight="bold"))

    def _build_clients(self):
        self.tab_clients.grid_columnconfigure(0, weight=1)
        self.tab_clients.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(self.tab_clients, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(10, 12))
        toolbar.grid_columnconfigure(1, weight=1)
        self.client_filter = ctk.CTkComboBox(
            toolbar, width=130, height=36,
            values=["Todos", "Online", "Offline", "Vencendo", "Expirados", "Bloqueados"],
            command=lambda _value: self._render_installations(),
        )
        self.client_filter.set("Todos")
        self.client_filter.grid(row=0, column=0, padx=(0, 8))
        self.client_search = ctk.CTkEntry(toolbar, placeholder_text="Buscar concessionária ou computador...",
                                          height=36)
        self.client_search.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.client_search.bind("<KeyRelease>", lambda _event: self._render_installations())
        edit_button = self._toolbar_button(toolbar, "Editar licença", self.edit_license)
        edit_button.configure(width=115)
        edit_button.grid(row=0, column=2, padx=4)
        self.client_actions_button = self._toolbar_button(toolbar, "Mais ações  ⋮", self._open_actions_button, "#334155")
        self.client_actions_button.configure(width=125)
        self.client_actions_button.grid(row=0, column=3, padx=(4, 0))

        frame = ctk.CTkFrame(self.tab_clients, fg_color=CARD, border_width=1, border_color=BORDER)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        columns = ("status", "hardware", "company", "manager", "phone", "days", "license", "price", "version")
        self.client_tree = ttk.Treeview(frame, columns=columns, show="headings", style="Secure.Treeview")
        headings = {
            "status": "STATUS", "hardware": "ID / CHASSI", "company": "CONCESSIONÁRIA",
            "manager": "RESPONSÁVEL", "phone": "CONTATO", "days": "DIAS REST.",
            "license": "LICENÇA", "price": "MENSALIDADE", "version": "VERSÃO",
        }
        widths = {"status": 80, "hardware": 165, "company": 155, "manager": 135,
                  "phone": 100, "days": 68, "license": 76, "price": 92, "version": 65}
        for column in columns:
            self.client_tree.heading(column, text=headings[column],
                                     command=lambda selected=column: self._sort_clients(selected))
            self.client_tree.column(column, width=widths[column], anchor="w" if column == "company" else "center")
        self.client_tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        scroll = ctk.CTkScrollbar(frame, command=self.client_tree.yview)
        scroll.grid(row=0, column=1, sticky="ns", padx=(0, 10), pady=10)
        horizontal = ctk.CTkScrollbar(frame, orientation="horizontal", command=self.client_tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.client_tree.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        self.client_tree.bind("<Double-1>", lambda _event: self.edit_license())
        self.client_tree.bind("<Button-3>", self._open_client_menu)
        self.client_tree.tag_configure("blocked", foreground="#FCA5A5")
        self.client_tree.tag_configure("expired", foreground="#FBBF24")
        self.client_tree.tag_configure("online", foreground="#6EE7B7")

        self.client_menu = tk.Menu(self, tearoff=0, bg="#1E293B", fg="white",
                                   activebackground=PRIMARY, activeforeground="white")
        self.client_menu.add_command(label="✎  Editar licença completa", command=self.edit_license)
        self.client_menu.add_command(label="＄  Definir mensalidade individual", command=self.set_monthly_price)
        self.client_menu.add_command(label="🔗  Configurar links dos relatórios", command=self.configure_report_links)
        self.client_menu.add_command(label="📣  Configurar aviso individual", command=self.set_individual_notice)
        self.client_menu.add_separator()
        self.client_menu.add_command(label="🔑  Gerar código de migração", command=self.issue_claim)
        self.client_menu.add_command(label="◉  Auditar eventos desta máquina", command=self.audit_selected)
        self.client_menu.add_command(label="⛔  Bloquear / Desbloquear", command=self.toggle_installation)
        self.client_menu.add_separator()
        self.client_menu.add_command(label="🌐  Configurar comunicado geral", command=lambda: self._show_page("system"))
        self.client_menu.add_command(label="🗑  Excluir cadastro definitivamente", command=self.delete_installation)

        footer = ctk.CTkFrame(self.tab_clients, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.client_count = ctk.CTkLabel(footer, text="0 registros", text_color=MUTED,
                                         font=ctk.CTkFont(size=11, weight="bold"))
        self.client_count.pack(side="left")
        ctk.CTkLabel(footer, text="Duplo clique: editar  ·  Botão direito: menu completo",
                     text_color="#64748B", font=ctk.CTkFont(size=11)).pack(side="right")

    def _build_keys(self):
        self.tab_keys.grid_columnconfigure(1, weight=1)
        self.tab_keys.grid_rowconfigure(0, weight=1)
        form = ctk.CTkFrame(self.tab_keys, width=355, fg_color=CARD, border_width=1,
                            border_color=BORDER, corner_radius=14)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 12), pady=10)
        form.grid_propagate(False)
        ctk.CTkLabel(form, text="✦  Nova licença", text_color=TEXT,
                     font=ctk.CTkFont(size=19, weight="bold")).pack(anchor="w", padx=25, pady=(24, 3))
        ctk.CTkLabel(form, text="Escolha a concessionária e o benefício.", text_color=MUTED,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=25, pady=(0, 15))
        self.key_company = ctk.CTkComboBox(form, values=["Selecione uma concessionária"], width=290)
        self.key_company.pack(pady=7)
        self.key_type = ctk.CTkComboBox(
            form, values=["Adicionar Dias", "Mensagens Extras", "Data Vencimento"], width=290,
            command=lambda _value: self._update_key_input(),
        )
        self.key_type.set("Adicionar Dias")
        self.key_type.pack(pady=7)
        self.key_value = ctk.CTkEntry(form, width=290, placeholder_text="30 ou DD/MM/AAAA")
        self.key_value.insert(0, "30")
        self.key_value.pack(pady=7)
        self.key_hint = ctk.CTkLabel(form, text="Acrescenta dias ao vencimento atual.", text_color="#7DD3FC",
                                     font=ctk.CTkFont(size=10))
        self.key_hint.pack(anchor="w", padx=25, pady=(0, 2))
        self._toolbar_button(form, "Gerar chave (válida 24h)", self.create_key, SUCCESS).pack(pady=16)
        ctk.CTkLabel(form, text="A chave completa aparece uma única vez\ne é copiada automaticamente.",
                     text_color=MUTED, justify="center").pack(pady=5)

        table = ctk.CTkFrame(self.tab_keys, fg_color=CARD, border_width=1,
                             border_color=BORDER, corner_radius=14)
        table.grid(row=0, column=1, sticky="nsew", pady=10)
        table.grid_rowconfigure(1, weight=1)
        table.grid_columnconfigure(0, weight=1)
        self._toolbar_button(table, "Revogar chave selecionada", self.revoke_key, DANGER).grid(
            row=0, column=0, sticky="e", padx=12, pady=10)
        columns = ("prefix", "company", "type", "value", "until", "status", "created")
        self.key_tree = ttk.Treeview(table, columns=columns, show="headings", style="Secure.Treeview")
        labels = ["PREFIXO", "CONCESSIONÁRIA", "TIPO", "VALOR", "UTILIZAR ATÉ", "STATUS", "CRIADA EM"]
        for column, label in zip(columns, labels):
            self.key_tree.heading(column, text=label)
            self.key_tree.column(column, width=130, anchor="center")
        self.key_tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

    def _update_key_input(self):
        choice = self.key_type.get()
        descriptions = {
            "Adicionar Dias": ("30", "Acrescenta dias ao vencimento atual."),
            "Mensagens Extras": ("100", "Adiciona mensagens sem alterar a validade."),
            "Data Vencimento": (dt.datetime.now().strftime("%d/%m/%Y"), "Mantém sempre a data de vencimento mais distante."),
        }
        value, hint = descriptions.get(choice, ("", ""))
        self.key_value.delete(0, "end")
        self.key_value.insert(0, value)
        self.key_hint.configure(text=hint)

    def _build_system(self):
        self.tab_system.grid_columnconfigure(0, weight=1)
        self.tab_system.grid_rowconfigure(0, weight=1)
        self.system_scroll = ctk.CTkScrollableFrame(self.tab_system, fg_color="transparent")
        self.system_scroll.grid(row=0, column=0, sticky="nsew")
        self.system_scroll.grid_columnconfigure((0, 1), weight=1, uniform="system-card")
        release = ctk.CTkFrame(self.system_scroll, fg_color=CARD, border_width=1,
                               border_color=BORDER, corner_radius=14)
        release.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(4, 10))
        pricing = ctk.CTkFrame(self.system_scroll, fg_color=CARD, border_width=1,
                               border_color=BORDER, corner_radius=14)
        pricing.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(4, 10))
        ctk.CTkLabel(release, text="🚀  Centro de Distribuição OTA", text_color=TEXT,
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=26, pady=(22, 3))
        ctk.CTkLabel(release, text="Publique uma versão verificável para todos os computadores.",
                     text_color=MUTED, font=ctk.CTkFont(size=11)).pack(anchor="w", padx=26, pady=(0, 14))
        self.system_entries = {}
        fields = [
            ("current_version", "Versão em produção"), ("minimum_version", "Versão mínima permitida"),
            ("installer_url", "Link HTTPS do instalador"), ("installer_sha256", "Assinatura SHA-256"),
        ]
        for key, label in fields:
            ctk.CTkLabel(release, text=label, anchor="w", text_color=MUTED,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(fill="x", padx=26, pady=(7, 2))
            entry = ctk.CTkEntry(release, height=38)
            entry.pack(fill="x", padx=26)
            entry.bind("<KeyRelease>", lambda _event: self._update_release_readiness())
            self.system_entries[key] = entry
        release_actions = ctk.CTkFrame(release, fg_color="transparent")
        release_actions.pack(fill="x", padx=26, pady=12)
        self._toolbar_button(release_actions, "Selecionar EXE e calcular SHA", self.select_installer_file).pack(side="left", padx=(0, 6))
        self._toolbar_button(release_actions, "Testar link", self.test_installer_url, "#0EA5E9").pack(side="left")
        self.force_update = ctk.CTkSwitch(release, text="Exigir atualização antes de continuar")
        self.force_update.pack(anchor="w", padx=26, pady=(0, 18))
        self.release_readiness = ctk.CTkLabel(
            release, text="○ Verificando configuração...", anchor="w",
            fg_color="#0F172A", corner_radius=8, text_color=MUTED, height=34, padx=12,
        )
        self.release_readiness.pack(fill="x", padx=26, pady=(0, 20))

        ctk.CTkLabel(pricing, text="＄  Preços & Comunicação", text_color=TEXT,
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=26, pady=(22, 3))
        ctk.CTkLabel(pricing, text="Defina o valor padrão e os avisos exibidos aos clientes.",
                     text_color=MUTED, font=ctk.CTkFont(size=11)).pack(anchor="w", padx=26, pady=(0, 14))
        for key, label in [("default_monthly_price", "Mensalidade padrão (R$)"),
                           ("global_notice", "Comunicado geral"),
                           ("maintenance_message", "Mensagem de manutenção")]:
            ctk.CTkLabel(pricing, text=label, anchor="w", text_color=MUTED,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(fill="x", padx=26, pady=(9, 2))
            entry = ctk.CTkEntry(pricing, height=38)
            entry.pack(fill="x", padx=26)
            self.system_entries[key] = entry
            if key == "default_monthly_price":
                self.price_save_button = self._toolbar_button(
                    pricing, "Salvar mensalidade", self.save_monthly_price, SUCCESS,
                )
                self.price_save_button.pack(anchor="w", padx=26, pady=(10, 4))
                self.price_feedback = ctk.CTkLabel(
                    pricing, text="Salva apenas o preço padrão. Mensalidades individuais são preservadas.",
                    text_color=MUTED, font=ctk.CTkFont(size=11),
                    justify="left", anchor="w", wraplength=350,
                )
                self.price_feedback.pack(fill="x", padx=26, pady=(0, 6))
        self.maintenance = ctk.CTkSwitch(pricing, text="Ativar modo manutenção")
        self.maintenance.pack(anchor="w", padx=26, pady=18)

        publish = ctk.CTkFrame(self.tab_system, fg_color=CARD, border_width=1,
                               border_color=BORDER, corner_radius=14)
        publish.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.publish_button = self._toolbar_button(
            publish, "✓  VALIDAR E PUBLICAR CONFIGURAÇÕES", self.save_system, SUCCESS,
        )
        self.publish_button.pack(fill="x", padx=28, pady=12)

    def _build_audit(self):
        toolbar = ctk.CTkFrame(self.tab_audit, fg_color="transparent")
        toolbar.pack(fill="x", pady=(10, 8))
        self.audit_hardware = ctk.CTkEntry(toolbar, width=330, placeholder_text="Computador (vazio = todos)")
        self.audit_hardware.pack(side="left", padx=(0, 8))
        self._toolbar_button(toolbar, "Consultar eventos", self.load_telemetry).pack(side="left")
        self.audit_text = ctk.CTkTextbox(self.tab_audit, fg_color=CARD, text_color=TEXT,
                                         border_width=1, border_color=BORDER, font=("Consolas", 11))
        self.audit_text.pack(fill="both", expand=True, pady=(0, 10))

    def _run(self, operation, on_success, busy="Processando...", on_error=None):
        self.status.configure(text=busy, text_color=WARNING)
        def worker():
            try:
                result = operation()
                self.after(0, lambda: (self.status.configure(text="● Supabase conectado", text_color=SUCCESS), on_success(result)))
            except Exception as error:
                self.after(0, lambda e=error: (on_error or self._show_error)(e))
        threading.Thread(target=worker, daemon=True).start()

    def _request(self, action, **payload):
        return self.client.admin_request(self.session.access_token, action, **payload)

    def _show_error(self, error):
        self.status.configure(text="Falha na operação", text_color=DANGER)
        messagebox.showerror("Operação não concluída", friendly_auth_error(error), parent=self)

    def refresh_all(self):
        def operation():
            return {
                "installations": self._request("list_installations").get("installations", []),
                "keys": self._request("list_keys").get("keys", []),
                "system": self._request("get_system_config").get("system", {}),
            }
        self._run(operation, self._accept_refresh, "Sincronizando dados seguros...")

    def _accept_refresh(self, result):
        self.installations = {str(item.get("hardware_id")): item for item in result["installations"]}
        self.keys = {str(item.get("id")): item for item in result["keys"]}
        self.system = result["system"]
        self._render_installations()
        self._render_keys()
        self._render_system()
        self._render_kpis()
        companies = sorted({str(_relation(item.get("companies")).get("name") or "")
                            for item in self.installations.values()} - {""})
        self.key_company.configure(values=companies or ["Sem concessionárias"])
        if companies and self.key_company.get() not in companies:
            self.key_company.set(companies[0])

    @staticmethod
    def _is_online(item):
        try:
            seen = dt.datetime.fromisoformat(str(item.get("last_seen_at") or "").replace("Z", "+00:00"))
            return (dt.datetime.now(dt.timezone.utc) - seen.astimezone(dt.timezone.utc)).total_seconds() <= 300
        except (TypeError, ValueError):
            return False

    def _render_kpis(self):
        items = list(self.installations.values())
        active = sum(1 for item in items if item.get("status") == "active")
        trials = sum(1 for item in items if _relation(item.get("licenses")).get("license_type") == "trial")
        online = sum(1 for item in items if self._is_online(item))
        price = float(self.system.get("default_monthly_price") or 0)
        version = str(self.system.get("current_version") or "0.0.0")
        self.kpi_labels["machines"][0].configure(text=str(len(items)))
        self.kpi_labels["machines"][1].configure(text=f"{active} ativas  ·  {trials} trial")
        self.kpi_labels["online"][0].configure(text=str(online))
        self.kpi_labels["online"][1].configure(text="Ativas nos últimos 5 minutos")
        self.kpi_labels["price"][0].configure(text=f"R$ {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        self.kpi_labels["price"][1].configure(text="Mensalidade padrão")
        self.kpi_labels["version"][0].configure(text=f"v{version.lstrip('v')}")
        self.kpi_labels["version"][1].configure(text="Distribuição OTA segura")

    def _render_installations(self):
        for row in self.client_tree.get_children():
            self.client_tree.delete(row)
        search = self.client_search.get().strip().lower()
        selected_filter = self.client_filter.get() if hasattr(self, "client_filter") else "Todos"
        displayed = 0
        for hardware, item in self.installations.items():
            company = _relation(item.get("companies"))
            license_data = _relation(item.get("licenses"))
            company_name = str(company.get("name") or "Sem empresa")
            if search and search not in f"{hardware} {company_name}".lower():
                continue
            price = license_data.get("monthly_price")
            try:
                expiry = dt.datetime.fromisoformat(str(license_data.get("expires_at")).replace("Z", "+00:00"))
                days = max(0, (expiry.astimezone() - dt.datetime.now().astimezone()).days + 1)
            except (TypeError, ValueError):
                days = 0
            online = self._is_online(item)
            blocked = item.get("status") in {"blocked", "revoked"}
            matches_filter = {
                "Todos": True,
                "Online": online,
                "Offline": not online,
                "Vencendo": 1 <= days <= 7 and not blocked,
                "Expirados": days == 0 and not blocked,
                "Bloqueados": blocked,
            }.get(selected_filter, True)
            if not matches_filter:
                continue
            status_text = "● ONLINE" if online else "○ OFFLINE"
            tag = "blocked" if blocked else "expired" if days == 0 else "online" if online else ""
            self.client_tree.insert("", "end", iid=hardware, values=(
                status_text, hardware, company_name, company.get("manager_name") or "—",
                company.get("phone") or "—", days, str(license_data.get("status") or "—").upper(),
                f"R$ {float(price):.2f}" if price is not None else "Padrão",
                item.get("app_version") or "—",
            ), tags=(tag,) if tag else ())
            displayed += 1
        self.client_count.configure(text=f"{displayed} de {len(self.installations)} registros")
        self._sort_clients(self.client_sort_column, preserve_direction=True)

    def _sort_clients(self, column, preserve_direction=False):
        if not preserve_direction:
            if self.client_sort_column == column:
                self.client_sort_reverse = not self.client_sort_reverse
            else:
                self.client_sort_column = column
                self.client_sort_reverse = False
        rows = []
        numeric_columns = {"days"}
        for item_id in self.client_tree.get_children(""):
            value = self.client_tree.set(item_id, column)
            if column in numeric_columns:
                try:
                    value = int(value)
                except ValueError:
                    value = -1
            else:
                value = str(value).casefold()
            rows.append((value, item_id))
        for position, (_value, item_id) in enumerate(sorted(rows, reverse=self.client_sort_reverse)):
            self.client_tree.move(item_id, "", position)

    def _open_actions_button(self):
        if not self._selected_hardware():
            return
        x = self.client_actions_button.winfo_rootx()
        y = self.client_actions_button.winfo_rooty() + self.client_actions_button.winfo_height() + 4
        self.client_menu.tk_popup(x, y)

    def _selected_hardware(self):
        selected = self.client_tree.selection()
        if not selected:
            messagebox.showwarning("Seleção necessária", "Selecione uma concessionária na tabela.", parent=self)
            return ""
        return str(selected[0])

    def _open_client_menu(self, event):
        row = self.client_tree.identify_row(event.y)
        if not row:
            return
        self.client_tree.selection_set(row)
        self.client_tree.focus(row)
        self.client_menu.tk_popup(event.x_root, event.y_root)

    def set_monthly_price(self):
        hardware = self._selected_hardware()
        if not hardware:
            return
        current = _relation(self.installations[hardware].get("licenses")).get("monthly_price")
        value = simpledialog.askstring(
            "Mensalidade individual",
            "Informe o valor mensal. Deixe vazio para voltar ao preço padrão:",
            initialvalue="" if current is None else str(current), parent=self,
        )
        if value is None:
            return
        try:
            price = None if not value.strip() else float(value.replace(",", "."))
            if price is not None and price < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Valor inválido", "Informe um valor monetário válido.", parent=self)
            return
        self._run(lambda: self._request("update_license", hardware_id=hardware, monthly_price=price),
                  lambda _result: self.refresh_all(), "Atualizando mensalidade...")

    def set_individual_notice(self):
        hardware = self._selected_hardware()
        if not hardware:
            return
        current = str(_relation(self.installations[hardware].get("licenses")).get("adjustment_notice") or "")
        notice = simpledialog.askstring("Aviso individual", "Mensagem exibida somente nesta máquina:",
                                        initialvalue=current, parent=self)
        if notice is None:
            return
        self._run(lambda: self._request("update_license", hardware_id=hardware,
                                       adjustment_notice=notice.strip()),
                  lambda _result: self.refresh_all(), "Salvando aviso individual...")

    def configure_report_links(self):
        """Edita somente os links do myHonda, em uma janela compacta e persistente."""
        hardware = self._selected_hardware()
        if not hardware:
            return

        item = self.installations[hardware]
        license_data = _relation(item.get("licenses"))
        company = _relation(item.get("companies")).get("name") or hardware
        current_links = license_data.get("report_links") or {}
        link_fields = [
            ("auditor_tsi", "Relatório auditor TSI"),
            ("auditor_ssi", "Relatório auditor SSI"),
            ("fila_tsi", "Fila TSI"),
            ("fila_ssi", "Fila SSI"),
        ]

        modal = ctk.CTkToplevel(self)
        modal.title(f"Links dos relatórios — {company}")
        modal.geometry("680x490")
        modal.minsize(580, 440)
        modal.configure(fg_color=BG)
        modal.transient(self)
        modal.grab_set()
        modal.grid_columnconfigure(0, weight=1)
        modal.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(modal, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(22, 10))
        ctk.CTkLabel(
            header, text="Links dos relatórios myHonda", text_color=TEXT,
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            header, text=f"Configuração individual: {company}", text_color=MUTED,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", pady=(3, 0))
        ctk.CTkLabel(
            header,
            text="Informe o ID 00O... ou cole o link completo. O Gerador salvará somente o ID.",
            text_color="#38BDF8", font=ctk.CTkFont(size=11),
        ).pack(anchor="w", pady=(5, 0))

        form = ctk.CTkScrollableFrame(
            modal, fg_color=CARD, border_width=1, border_color=BORDER,
        )
        form.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 12))
        form.grid_columnconfigure(0, weight=1)
        entries = {}
        initial_values = {}
        for row, (key, label) in enumerate(link_fields):
            value = str(current_links.get(key) or "").strip()
            initial_values[key] = value
            try:
                display_value = _normalize_report_id(value)
            except ValueError:
                display_value = value
            ctk.CTkLabel(form, text=label, text_color=MUTED).grid(
                row=row * 2, column=0, sticky="w", padx=18, pady=(12, 3)
            )
            entry = ctk.CTkEntry(form, height=38, placeholder_text="Ex.: 00OVP000008YZJh")
            entry.insert(0, display_value)
            entry.grid(row=row * 2 + 1, column=0, sticky="ew", padx=18, pady=(0, 5))
            entries[key] = entry

        footer = ctk.CTkFrame(modal, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 22))
        footer.grid_columnconfigure(0, weight=1)
        saving = {"active": False}

        def values():
            return {key: entries[key].get().strip() for key, _label in link_fields}

        def changed():
            return values() != initial_values

        def finish_save(_result):
            saving["active"] = False
            modal.destroy()
            self.refresh_all()

        def save():
            if saving["active"]:
                return
            raw_links = values()
            try:
                report_links = {
                    key: _normalize_report_id(raw_links[key]) for key, _label in link_fields
                }
            except ValueError as error:
                messagebox.showwarning(
                    "ID de relatório inválido", str(error),
                    parent=modal,
                )
                return
            saving["active"] = True
            save_button.configure(state="disabled", text="Salvando...")
            self._run(
                lambda: self._request(
                    "update_license", hardware_id=hardware, report_links=report_links
                ),
                finish_save,
                "Salvando links dos relatórios...",
            )

        def close_window():
            if saving["active"]:
                return
            if not changed():
                modal.destroy()
                return
            decision = messagebox.askyesnocancel(
                "Alterações não salvas",
                "Os links foram alterados. Deseja salvar antes de fechar?",
                parent=modal,
            )
            if decision is True:
                save()
            elif decision is False:
                modal.destroy()

        cancel_button = self._toolbar_button(footer, "Cancelar", close_window, "#334155")
        cancel_button.configure(width=130)
        cancel_button.grid(row=0, column=1, padx=(0, 8))
        save_button = self._toolbar_button(footer, "Salvar links", save, SUCCESS)
        save_button.configure(width=155)
        save_button.grid(row=0, column=2)
        modal.protocol("WM_DELETE_WINDOW", close_window)
        entries["auditor_tsi"].focus_set()

    def audit_selected(self):
        hardware = self._selected_hardware()
        if not hardware:
            return
        self._show_page("audit")
        self.audit_hardware.delete(0, "end")
        self.audit_hardware.insert(0, hardware)
        self.load_telemetry()

    def delete_installation(self):
        hardware = self._selected_hardware()
        if not hardware:
            return
        typed = simpledialog.askstring(
            "Exclusão definitiva",
            "Esta ação apaga licença, consumo, diagnósticos e vínculo do computador.\n\n"
            f"Para confirmar, digite exatamente:\n{hardware}", parent=self,
        )
        if typed != hardware:
            if typed is not None:
                messagebox.showwarning("Exclusão cancelada", "A identificação digitada não confere.", parent=self)
            return
        self._run(lambda: self._request("delete_installation", hardware_id=hardware, confirmation=typed),
                  lambda _result: self.refresh_all(), "Excluindo cadastro...")

    def edit_license(self):
        hardware = self._selected_hardware()
        if not hardware:
            return
        item = self.installations[hardware]
        license_data = _relation(item.get("licenses"))
        company = _relation(item.get("companies")).get("name") or hardware
        modal = ctk.CTkToplevel(self)
        modal.title(f"Licença — {company}")
        modal.geometry("650x720")
        modal.minsize(560, 520)
        modal.configure(fg_color=BG)
        modal.transient(self)
        modal.grab_set()
        modal.grid_columnconfigure(0, weight=1)
        modal.grid_rowconfigure(1, weight=1)
        entries = {}
        fields = [
            ("expires_at", "Vencimento (DD/MM/AAAA)", _display_date(license_data.get("expires_at"))[:10]),
            ("extra_messages", "Mensagens extras", str(license_data.get("extra_messages") or 0)),
            ("monthly_price", "Mensalidade (vazio = padrão)", "" if license_data.get("monthly_price") is None else str(license_data.get("monthly_price"))),
            ("adjustment_notice", "Aviso individual", str(license_data.get("adjustment_notice") or "")),
        ]
        header = ctk.CTkFrame(modal, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=35, pady=(22, 10))
        ctk.CTkLabel(header, text=str(company), text_color=TEXT,
                     font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(
            header, text="Ajuste os dados da licença e confirme no botão Salvar alterações.",
            text_color=MUTED, font=ctk.CTkFont(size=11),
        ).pack(anchor="w", pady=(3, 0))

        form = ctk.CTkScrollableFrame(
            modal, fg_color=CARD, border_width=1, border_color=BORDER,
        )
        form.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 12))
        form.grid_columnconfigure(0, weight=1)
        for key, label, value in fields:
            ctk.CTkLabel(form, text=label, text_color=MUTED).pack(anchor="w", padx=18, pady=(10, 3))
            entry = ctk.CTkEntry(form, height=36)
            entry.insert(0, value)
            entry.pack(fill="x", padx=18)
            entries[key] = entry
        links = license_data.get("report_links") or {}
        for key, label in [("auditor_tsi", "Relatório auditor TSI"), ("auditor_ssi", "Relatório auditor SSI"),
                           ("fila_tsi", "Fila TSI"), ("fila_ssi", "Fila SSI")]:
            ctk.CTkLabel(form, text=label, text_color=MUTED).pack(anchor="w", padx=18, pady=(10, 3))
            entry = ctk.CTkEntry(form, height=34, placeholder_text="ID 00O... ou link do myHonda")
            stored_value = str(links.get(key) or "")
            try:
                stored_value = _normalize_report_id(stored_value)
            except ValueError:
                pass
            entry.insert(0, stored_value)
            entry.pack(fill="x", padx=18)
            entries[key] = entry
        diagnostic = ctk.CTkSwitch(form, text="Diagnóstico detalhado por 24 horas")
        diagnostic.pack(pady=16)
        diagnostic_until_value = license_data.get("detailed_diagnostics_until")
        try:
            diagnostic_until = dt.datetime.fromisoformat(
                str(diagnostic_until_value).replace("Z", "+00:00")
            )
            if diagnostic_until > dt.datetime.now().astimezone():
                diagnostic.select()
        except (TypeError, ValueError):
            pass

        initial_values = {key: entry.get() for key, entry in entries.items()}
        initial_diagnostic = bool(diagnostic.get())
        saving = {"active": False}

        footer = ctk.CTkFrame(modal, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 22))
        footer.grid_columnconfigure(0, weight=1)

        def save():
            if saving["active"]:
                return
            try:
                expiry = _iso_end_of_day(entries["expires_at"].get())
                extra = int(entries["extra_messages"].get())
                if extra < 0:
                    raise ValueError
                price_text = entries["monthly_price"].get().strip()
                price = None if not price_text else _parse_monthly_price(price_text)
            except ValueError:
                messagebox.showwarning("Dados inválidos", "Revise a data, as mensagens e a mensalidade.", parent=modal)
                return
            try:
                report_links = {
                    key: _normalize_report_id(entries[key].get())
                    for key in ("auditor_tsi", "auditor_ssi", "fila_tsi", "fila_ssi")
                }
            except ValueError as error:
                messagebox.showwarning("ID de relatório inválido", str(error), parent=modal)
                return
            diagnostic_until = ((dt.datetime.now().astimezone() + dt.timedelta(hours=24)).isoformat()
                                if diagnostic.get() else None)
            payload = dict(hardware_id=hardware, expires_at=expiry, status="active",
                           license_type="subscription", extra_messages=extra, monthly_price=price,
                           adjustment_notice=entries["adjustment_notice"].get().strip(),
                           report_links=report_links, detailed_diagnostics_until=diagnostic_until)
            saving["active"] = True
            save_button.configure(state="disabled", text="Salvando...")
            self._run(lambda: self._request("update_license", **payload),
                      lambda _result: (modal.destroy(), self.refresh_all()), "Atualizando licença...")

        def changed():
            return (any(entries[key].get() != value for key, value in initial_values.items())
                    or bool(diagnostic.get()) != initial_diagnostic)

        def close_window():
            if saving["active"]:
                return
            if not changed():
                modal.destroy()
                return
            decision = messagebox.askyesnocancel(
                "Alterações não salvas",
                "A licença foi alterada. Deseja salvar antes de fechar?",
                parent=modal,
            )
            if decision is True:
                save()
            elif decision is False:
                modal.destroy()

        cancel_button = self._toolbar_button(footer, "Cancelar", close_window, "#334155")
        cancel_button.configure(width=130)
        cancel_button.grid(row=0, column=1, padx=(0, 8))
        save_button = self._toolbar_button(footer, "Salvar alterações", save, SUCCESS)
        save_button.configure(width=170)
        save_button.grid(row=0, column=2)
        modal.protocol("WM_DELETE_WINDOW", close_window)
        entries["expires_at"].focus_set()

    def issue_claim(self):
        hardware = self._selected_hardware()
        if not hardware:
            return
        if self.installations[hardware].get("status") == "active":
            messagebox.showinfo("Já migrado", "Este computador já está ativo no Supabase.", parent=self)
            return
        if not messagebox.askyesno("Código de migração", "Gerar um novo código válido por 30 dias?", parent=self):
            return
        def accepted(result):
            code = str(result.get("claim_code") or "")
            self.clipboard_clear(); self.clipboard_append(code); self.update()
            messagebox.showinfo("Código copiado", f"{code}\n\nO código foi copiado e é válido por 30 dias.", parent=self)
        self._run(lambda: self.client.issue_migration_claim(self.session.access_token, hardware), accepted,
                  "Gerando código individual...")

    def toggle_installation(self):
        hardware = self._selected_hardware()
        if not hardware:
            return
        current = self.installations[hardware].get("status")
        target = "blocked" if current == "active" else "active"
        if messagebox.askyesno("Alterar acesso", f"Definir esta instalação como {target}?", parent=self):
            self._run(lambda: self._request("set_installation_status", hardware_id=hardware, status=target),
                      lambda _result: self.refresh_all(), "Alterando acesso...")

    def _render_keys(self):
        for row in self.key_tree.get_children():
            self.key_tree.delete(row)
        for key_id, item in self.keys.items():
            kind = item.get("key_type")
            value = item.get("days_to_add") if kind == "days" else item.get("messages_to_add") if kind == "messages" else _display_date(item.get("fixed_expiry"))[:10]
            self.key_tree.insert("", "end", iid=key_id, values=(item.get("code_prefix"), item.get("intended_company") or "—",
                                 kind, value, _display_date(item.get("usable_until")), item.get("status"), _display_date(item.get("created_at"))))

    def create_key(self):
        company = self.key_company.get().strip()
        choice = self.key_type.get()
        value = self.key_value.get().strip()
        payload = {"intended_company": company}
        try:
            if choice == "Adicionar Dias": payload.update(key_type="days", days_to_add=int(value))
            elif choice == "Mensagens Extras": payload.update(key_type="messages", messages_to_add=int(value))
            else: payload.update(key_type="fixed_expiry", fixed_expiry=_iso_end_of_day(value))
        except ValueError:
            messagebox.showwarning("Valor inválido", "Use um número positivo ou uma data DD/MM/AAAA.", parent=self)
            return
        def accepted(result):
            code = str(result.get("code") or "")
            self.clipboard_clear(); self.clipboard_append(code); self.update()
            messagebox.showinfo("Chave gerada", f"{code}\n\nCopiada. Utilize em até 24 horas.", parent=self)
            self.refresh_all()
        self._run(lambda: self._request("create_key", **payload), accepted, "Gerando chave segura...")

    def revoke_key(self):
        selected = self.key_tree.selection()
        if not selected:
            messagebox.showwarning("Seleção necessária", "Selecione uma chave.", parent=self); return
        key_id = str(selected[0])
        key = self.keys.get(key_id) or {}
        status = str(key.get("status") or "").lower()
        if status == "used":
            messagebox.showinfo(
                "Chave já utilizada",
                "Esta chave já foi utilizada e o benefício foi aplicado.\n\n"
                "Para corrigir dias, mensagens ou vencimento, selecione a máquina em "
                "Clientes & Máquinas e use Editar licença.",
                parent=self,
            )
            return
        if status in {"revoked", "expired"}:
            messagebox.showinfo(
                "Chave indisponível",
                "Esta chave já está revogada ou expirada e não pode mais ser utilizada.",
                parent=self,
            )
            return
        if messagebox.askyesno("Revogar chave", "Esta operação impede definitivamente o uso da chave. Continuar?", parent=self):
            self._run(lambda: self._request("revoke_key", key_id=key_id),
                      lambda _result: self.refresh_all(), "Revogando chave...")

    def _render_system(self):
        for key, entry in self.system_entries.items():
            if key == "default_monthly_price":
                previous = getattr(self, "_last_rendered_price_text", None)
                if previous is not None and entry.get() != previous:
                    continue  # Atualizar dados não deve apagar uma mensalidade em edição.
            entry.delete(0, "end")
            value = self.system.get(key)
            entry.insert(0, "" if value is None else str(value))
            if key == "default_monthly_price":
                self._last_rendered_price_text = entry.get()
        self.force_update.select() if self.system.get("update_required") else self.force_update.deselect()
        self.maintenance.select() if self.system.get("maintenance_mode") else self.maintenance.deselect()
        self._update_release_readiness()

    def _update_release_readiness(self):
        if not hasattr(self, "release_readiness"):
            return
        url = self.system_entries.get("installer_url").get().strip() if self.system_entries.get("installer_url") else ""
        checksum = self.system_entries.get("installer_sha256").get().strip().lower() if self.system_entries.get("installer_sha256") else ""
        version = self.system_entries.get("current_version").get().strip() if self.system_entries.get("current_version") else ""
        version_ok = bool(version) and all(part.isdigit() for part in version.lower().lstrip("v").split("."))
        sha_ok = len(checksum) == 64 and all(char in "0123456789abcdef" for char in checksum)
        if version_ok and url.lower().startswith("https://") and sha_ok:
            self.release_readiness.configure(text="● Publicação segura pronta para validação", text_color=SUCCESS)
        elif not url and not checksum:
            self.release_readiness.configure(text="○ Nenhum instalador novo preparado", text_color=MUTED)
        else:
            self.release_readiness.configure(text="● Publicação incompleta: confira link HTTPS e SHA-256", text_color=WARNING)

    def select_installer_file(self):
        path = filedialog.askopenfilename(
            parent=self, title="Selecione o instalador publicado",
            filetypes=[("Instalador Windows", "*.exe"), ("Todos os arquivos", "*.*")],
        )
        if not path:
            return
        self.status.configure(text="Calculando assinatura do instalador...", text_color=WARNING)
        def work():
            try:
                digest = hashlib.sha256()
                with open(path, "rb") as file:
                    for block in iter(lambda: file.read(1024 * 1024), b""):
                        digest.update(block)
                checksum = digest.hexdigest()
                def accepted():
                    entry = self.system_entries["installer_sha256"]
                    entry.delete(0, "end"); entry.insert(0, checksum)
                    self.status.configure(text=f"● SHA calculado: {os.path.basename(path)}", text_color=SUCCESS)
                    self._update_release_readiness()
                self.after(0, accepted)
            except Exception as error:
                self.after(0, lambda current=error: self._show_error(current))
        threading.Thread(target=work, daemon=True).start()

    def test_installer_url(self):
        url = self.system_entries["installer_url"].get().strip()
        if not url.lower().startswith("https://"):
            messagebox.showwarning("Link inseguro", "O instalador precisa usar um endereço HTTPS.", parent=self)
            return
        def operation():
            request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "SaaS-Admin/2.0"})
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    return {"status": response.status, "size": response.headers.get("Content-Length")}
            except Exception:
                request = urllib.request.Request(url, headers={"User-Agent": "SaaS-Admin/2.0", "Range": "bytes=0-0"})
                with urllib.request.urlopen(request, timeout=20) as response:
                    return {"status": response.status, "size": response.headers.get("Content-Range") or response.headers.get("Content-Length")}
        self._run(operation, lambda result: messagebox.showinfo(
            "Link validado", f"O servidor respondeu HTTP {result['status']}.\nTamanho informado: {result.get('size') or 'não informado'}.", parent=self
        ), "Testando endereço do instalador...")

    def save_monthly_price(self):
        if getattr(self, "_price_saving", False):
            return
        entry = self.system_entries["default_monthly_price"]
        submitted_text = entry.get()
        try:
            price = _parse_monthly_price(submitted_text)
        except ValueError:
            messagebox.showwarning(
                "Valor inválido", "Informe um valor não negativo, como 300 ou 300,00.", parent=self,
            )
            return
        self._price_saving = True
        self.price_save_button.configure(state="disabled", text="Salvando...")
        self.publish_button.configure(state="disabled")
        self.price_feedback.configure(text="Aguardando confirmação do Supabase...", text_color=WARNING)

        def finish():
            self._price_saving = False
            self.price_save_button.configure(state="normal", text="Salvar mensalidade")
            self.publish_button.configure(state="normal")

        def operation():
            result = self._request("update_system_config", default_monthly_price=price)
            saved = (result.get("system") or {}).get("default_monthly_price")
            if not result.get("ok") or saved is None or _parse_monthly_price(saved) != price:
                raise RuntimeError("O servidor não confirmou o preço solicitado.")
            return result

        def accepted(_result):
            finish()
            self.system["default_monthly_price"] = price
            formatted = f"{price:.2f}".replace(".", ",")
            if entry.get() == submitted_text:
                entry.delete(0, "end")
                entry.insert(0, formatted)
            self._last_rendered_price_text = formatted
            self._render_kpis()
            self.price_feedback.configure(
                text=f"✓ Mensalidade padrão de R$ {formatted} salva no Supabase.", text_color=SUCCESS,
            )

        def failed(error):
            finish()
            self.price_feedback.configure(
                text="Não foi possível confirmar o salvamento. O valor digitado foi preservado.",
                text_color=DANGER,
            )
            self._show_error(error)

        self._run(operation, accepted, "Salvando mensalidade padrão...", on_error=failed)

    def save_system(self):
        if getattr(self, "_price_saving", False):
            return
        try:
            price = _parse_monthly_price(self.system_entries["default_monthly_price"].get())
        except ValueError:
            messagebox.showwarning("Valor inválido", "Informe uma mensalidade válida.", parent=self); return
        payload = {key: entry.get().strip() for key, entry in self.system_entries.items()}
        version = payload.get("current_version", "").lower().lstrip("v")
        minimum = payload.get("minimum_version", "").lower().lstrip("v")
        checksum = payload.get("installer_sha256", "").lower()
        url = payload.get("installer_url", "")
        if not version or not minimum or any(not part.isdigit() for part in version.split(".")) or any(not part.isdigit() for part in minimum.split(".")):
            messagebox.showwarning("Versão inválida", "Use versões numéricas, por exemplo 1.9.1.", parent=self); return
        if url and not url.lower().startswith("https://"):
            messagebox.showwarning("Link inseguro", "O link do instalador precisa usar HTTPS.", parent=self); return
        if url and (len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum)):
            messagebox.showwarning("Assinatura obrigatória", "Selecione o EXE para calcular a assinatura SHA-256 antes de publicar.", parent=self); return
        if checksum and not url:
            messagebox.showwarning("Link obrigatório", "Existe uma assinatura SHA-256, mas o link do instalador está vazio.", parent=self); return
        if self._version_tuple(minimum) > self._version_tuple(version):
            messagebox.showwarning("Versão mínima inválida", "A versão mínima não pode ser superior à versão em produção.", parent=self); return
        if self.force_update.get() and not url:
            messagebox.showwarning("Atualização incompleta", "Para exigir atualização, publique primeiro o link HTTPS e a assinatura do instalador.", parent=self); return
        if self.maintenance.get() and not payload.get("maintenance_message"):
            messagebox.showwarning("Mensagem necessária", "Informe a mensagem que será exibida durante a manutenção.", parent=self); return
        if (self.force_update.get() or self.maintenance.get()) and not messagebox.askyesno(
            "Confirmar publicação",
            "Esta configuração pode impedir temporariamente o uso do sistema nos clientes.\n\nDeseja publicar agora?",
            parent=self,
        ):
            return
        payload["current_version"] = version
        payload["minimum_version"] = minimum
        payload["installer_sha256"] = checksum
        payload["default_monthly_price"] = price
        payload["update_required"] = bool(self.force_update.get())
        payload["maintenance_mode"] = bool(self.maintenance.get())
        submitted_price_text = self.system_entries["default_monthly_price"].get()

        def accepted(_result):
            if self.system_entries["default_monthly_price"].get() == submitted_price_text:
                self._last_rendered_price_text = submitted_price_text
            messagebox.showinfo("Salvo", "Configuração atualizada no Supabase.", parent=self)
            self.refresh_all()

        self._run(lambda: self._request("update_system_config", **payload),
                  accepted,
                  "Salvando configuração...")

    @staticmethod
    def _version_tuple(value):
        return tuple(int(part) for part in str(value).lower().lstrip("v").split("."))

    def load_telemetry(self):
        hardware = self.audit_hardware.get().strip()
        def accepted(result):
            self.audit_text.delete("1.0", "end")
            for event in result.get("events", []):
                installation = _relation(event.get("installations"))
                company = _relation(installation.get("companies")).get("name") or "—"
                self.audit_text.insert("end", f"{_display_date(event.get('occurred_at'))} | {event.get('level')} | {company} | {installation.get('hardware_id')}\n")
                self.audit_text.insert("end", f"  {event.get('component')}.{event.get('event_name')}  {event.get('details') or {}}\n\n")
        self._run(lambda: self._request("list_telemetry", hardware_id=hardware), accepted, "Consultando diagnóstico...")
