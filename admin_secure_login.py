import os
import sys
import threading
import traceback
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from admin_supabase import AdminSupabaseClient, friendly_auth_error
from admin_window_utils import center_window


COLOR_BG = "#F4F7FB"
COLOR_CARD = "#FFFFFF"
COLOR_BORDER = "#D9E2EF"
COLOR_PRIMARY = "#2563EB"
COLOR_PRIMARY_HOVER = "#1D4ED8"
COLOR_SUCCESS = "#059669"
COLOR_SUCCESS_HOVER = "#047857"
COLOR_TEXT = "#0F172A"
COLOR_MUTED = "#64748B"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


def _fatal_error(exc_type, exc_value, exc_traceback):
    details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        base_dir = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__)
        log_path = os.path.join(base_dir, "log_erro_gerador.txt")
        with open(log_path, "w", encoding="utf-8") as file:
            file.write(details)
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Falha no Gerador Administrativo",
            "O gerador não pôde ser aberto. Os detalhes foram salvos em "
            f"{log_path}.",
        )
        root.destroy()
    except Exception:
        pass


class SecureLoginApp(ctk.CTk):
    def __init__(self, enroll_only=False):
        super().__init__()
        self.title("Assistente PRO — Gerador Admin 2.0 (Prévia)")
        self.geometry("520x620")
        self.configure(fg_color=COLOR_BG)
        self.resizable(False, False)
        self.auth_client = AdminSupabaseClient()
        self.enroll_only = bool(enroll_only)
        self.pending_session = None
        self.pending_factor_id = ""

        card = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        card.pack(fill="both", expand=True, padx=30, pady=30)
        ctk.CTkLabel(card, text="🔐", width=64, height=64, corner_radius=18,
                     fg_color="#DBEAFE", text_color=COLOR_PRIMARY,
                     font=ctk.CTkFont(size=32)).pack(pady=(30, 12))
        ctk.CTkLabel(
            card,
            text="Acesso ao Gerador Admin",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack()
        ctk.CTkLabel(
            card,
            text="Gerencie clientes, licenças e versões com segurança.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_MUTED,
        ).pack(pady=(2, 20))

        entry_style = dict(
            width=340,
            height=44,
            justify="left",
            fg_color="#FFFFFF",
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
        )
        ctk.CTkLabel(card, text="E-mail administrativo", width=340, anchor="w",
                     text_color=COLOR_MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(pady=(2, 4))
        self.entry_email = ctk.CTkEntry(
            card, placeholder_text="nome@empresa.com", **entry_style
        )
        self.entry_email.pack(pady=(0, 12))
        ctk.CTkLabel(card, text="Senha", width=340, anchor="w",
                     text_color=COLOR_MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(pady=(0, 4))
        self.entry_password = ctk.CTkEntry(
            card, show="*", placeholder_text="Digite sua senha", **entry_style
        )
        self.entry_password.pack(pady=(0, 12))
        self.entry_code = ctk.CTkEntry(
            card,
            placeholder_text="Código de 6 dígitos",
            font=ctk.CTkFont(size=16),
            **entry_style,
        )
        self.status = ctk.CTkLabel(
            card,
            text="🔒  Sua senha não é armazenada neste computador.",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_MUTED,
            fg_color="#F8FAFC",
            corner_radius=8,
            width=340,
            height=36,
        )
        self.after(20, lambda: center_window(self, 520, 620))
        self.status.pack(pady=(0, 12))
        self.login_button = ctk.CTkButton(
            card,
            text="Entrar com segurança",
            width=340,
            height=44,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.login,
        )
        self.login_button.pack(pady=(0, 20))
        self.entry_email.focus()
        self.bind("<Return>", self.login)

    def login(self, _event=None):
        if self.pending_session and self.pending_factor_id:
            self._verify_code()
            return
        email = self.entry_email.get().strip()
        password = self.entry_password.get()
        if not email or not password:
            messagebox.showwarning(
                "Dados obrigatórios", "Informe seu e-mail e senha.", parent=self
            )
            return
        self._busy(True, "Validando identidade...")

        def work():
            try:
                session = self.auth_client.sign_in(email, password)
                factors = self.auth_client.verified_totp_factors(session.access_token)
                self.after(0, lambda: self._after_password(session, factors))
            except Exception as error:
                self.after(0, lambda current=error: self._show_error(current))

        threading.Thread(target=work, daemon=True).start()

    def _after_password(self, session, factors):
        self.pending_session = session
        if factors:
            self.pending_factor_id = str(factors[0].get("id") or "")
            self.entry_email.configure(state="disabled")
            self.entry_password.configure(state="disabled")
            self.entry_code.pack(pady=(0, 12), before=self.status)
            self.entry_code.focus()
            self.login_button.configure(text="Validar código MFA")
            self._busy(False, "Digite o código do aplicativo autenticador.")
            return
        self._start_mfa_enrollment()

    def _start_mfa_enrollment(self):
        self._busy(True, "Preparando seu autenticador...")

        def work():
            try:
                enrollment = self.auth_client.enroll_totp(
                    self.pending_session.access_token
                )
                self.after(0, lambda: self._show_mfa_enrollment(enrollment))
            except Exception as error:
                self.after(0, lambda current=error: self._show_error(current))

        threading.Thread(target=work, daemon=True).start()

    def _show_mfa_enrollment(self, enrollment):
        import qrcode
        from PIL import Image

        totp = enrollment.get("totp") or {}
        self.pending_factor_id = str(enrollment.get("id") or "")
        uri = str(totp.get("uri") or "")
        secret = str(totp.get("secret") or "")
        if not self.pending_factor_id or not uri:
            self._show_error(RuntimeError("O servidor não retornou o QR Code do MFA."))
            return

        qr = qrcode.make(uri).convert("RGB").resize(
            (220, 220), Image.Resampling.NEAREST
        )
        self._qr_image = ctk.CTkImage(
            light_image=qr, dark_image=qr, size=(220, 220)
        )
        window = ctk.CTkToplevel(self)
        window.title("Ativar verificação em duas etapas")
        window.geometry("520x640")
        window.resizable(False, False)
        window.configure(fg_color=COLOR_BG)
        window.grab_set()
        window.protocol("WM_DELETE_WINDOW", lambda: None)
        window.after(20, lambda: center_window(window, 520, 640, self))

        ctk.CTkLabel(
            window,
            text="Proteja seu acesso",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(pady=(22, 4))
        ctk.CTkLabel(
            window,
            text="Leia o QR Code com Google Authenticator, Microsoft Authenticator\n"
            "ou outro aplicativo compatível.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_MUTED,
            justify="center",
        ).pack(pady=(0, 10))
        ctk.CTkLabel(window, image=self._qr_image, text="").pack(pady=5)
        ctk.CTkLabel(
            window,
            text="Chave manual (guarde em local seguro):",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_MUTED,
        ).pack(pady=(8, 2))
        secret_entry = ctk.CTkEntry(window, width=400, height=36, justify="center")
        secret_entry.insert(0, secret)
        secret_entry.configure(state="readonly")
        secret_entry.pack()
        code_entry = ctk.CTkEntry(
            window,
            width=260,
            height=44,
            justify="center",
            placeholder_text="Código de 6 dígitos",
            font=ctk.CTkFont(size=17),
        )
        code_entry.pack(pady=16)

        def confirm(_event=None):
            code = code_entry.get().strip().replace(" ", "")
            if len(code) != 6 or not code.isdigit():
                messagebox.showwarning(
                    "Código inválido",
                    "Digite os seis números exibidos no autenticador.",
                    parent=window,
                )
                return
            confirm_button.configure(state="disabled", text="VALIDANDO...")

            def work():
                try:
                    session = self.auth_client.challenge_and_verify(
                        self.pending_session.access_token,
                        self.pending_factor_id,
                        code,
                    )
                    self.after(0, lambda: self._finish_access(session, window))
                except Exception as error:
                    def failed(current=error):
                        confirm_button.configure(
                            state="normal", text="Ativar e entrar"
                        )
                        messagebox.showerror(
                            "Falha na verificação",
                            friendly_auth_error(current),
                            parent=window,
                        )
                    self.after(0, failed)

            threading.Thread(target=work, daemon=True).start()

        confirm_button = ctk.CTkButton(
            window,
            text="Ativar e entrar",
            width=260,
            height=42,
            command=confirm,
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        confirm_button.pack()
        code_entry.bind("<Return>", confirm)
        code_entry.focus()
        self._busy(False, "Conclua o cadastro no aplicativo autenticador.")

    def _verify_code(self):
        code = self.entry_code.get().strip().replace(" ", "")
        if len(code) != 6 or not code.isdigit():
            messagebox.showwarning(
                "Código inválido", "Digite os seis números do autenticador.", parent=self
            )
            return
        self._busy(True, "Confirmando o segundo fator...")

        def work():
            try:
                session = self.auth_client.challenge_and_verify(
                    self.pending_session.access_token, self.pending_factor_id, code
                )
                self.after(0, lambda: self._finish_access(session))
            except Exception as error:
                self.after(
                    0, lambda current=error: self._show_error(current, keep_mfa=True)
                )

        threading.Thread(target=work, daemon=True).start()

    def _finish_access(self, session, mfa_window=None):
        if self.enroll_only:
            if mfa_window is not None:
                mfa_window.grab_release()
                mfa_window.destroy()
            self._show_enrollment_success()
            return
        self._busy(True, "Confirmando permissão administrativa...")

        def work():
            try:
                self.auth_client.confirm_admin_access(session.access_token)
                self.after(0, lambda: self._open_panel(session, mfa_window))
            except Exception as error:
                self.after(
                    0, lambda current=error: self._show_error(current, keep_mfa=True)
                )

        threading.Thread(target=work, daemon=True).start()

    def _show_enrollment_success(self):
        """Keep the confirmation visible until the administrator acknowledges it."""
        self._busy(False, "Verificação em duas etapas ativada com sucesso.")
        window = ctk.CTkToplevel(self)
        window.title("MFA ativado")
        window.geometry("470x330")
        window.resizable(False, False)
        window.configure(fg_color=COLOR_BG)
        window.transient(self)
        window.protocol("WM_DELETE_WINDOW", self.destroy)
        window.after(20, lambda: center_window(window, 470, 330, self))

        card = ctk.CTkFrame(
            window,
            fg_color=COLOR_CARD,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        card.pack(fill="both", expand=True, padx=24, pady=24)
        ctk.CTkLabel(
            card,
            text="✓",
            width=58,
            height=58,
            corner_radius=29,
            fg_color=COLOR_SUCCESS,
            text_color="white",
            font=ctk.CTkFont(size=30, weight="bold"),
        ).pack(pady=(28, 12))
        ctk.CTkLabel(
            card,
            text="MFA ativado com sucesso",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack()
        ctk.CTkLabel(
            card,
            text="Seu acesso administrativo agora está protegido.\n\n"
            "Clique em Concluir para fechar esta etapa.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_MUTED,
            justify="center",
        ).pack(pady=(10, 20))
        ctk.CTkButton(
            card,
            text="Concluir",
            width=280,
            height=42,
            command=self.destroy,
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack()

        def show_modal():
            window.lift()
            window.focus_force()
            window.grab_set()

        window.after(50, show_modal)

    def _open_panel(self, session, mfa_window=None):
        if mfa_window is not None:
            mfa_window.grab_release()
            mfa_window.destroy()
        self.destroy()
        from supabase_admin_app import SupabaseAdminApp
        SupabaseAdminApp(session).mainloop()

    def _busy(self, busy, message):
        self.status.configure(
            text=message, text_color=COLOR_PRIMARY if busy else COLOR_MUTED
        )
        self.login_button.configure(state="disabled" if busy else "normal")

    def _show_error(self, error, keep_mfa=False):
        self._busy(False, "Não foi possível concluir o acesso.")
        messagebox.showerror(
            "Acesso não autorizado", friendly_auth_error(error), parent=self
        )
        if keep_mfa:
            self.entry_code.delete(0, tk.END)
            self.entry_code.focus()
        else:
            self.pending_session = None
            self.pending_factor_id = ""


def run():
    sys.excepthook = _fatal_error
    SecureLoginApp(enroll_only="--enroll-only" in sys.argv).mainloop()
