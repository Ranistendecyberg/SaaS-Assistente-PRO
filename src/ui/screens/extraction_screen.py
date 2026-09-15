import os
import re
import unicodedata
import urllib.parse
from bs4 import BeautifulSoup
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QListWidget, QListWidgetItem, QPushButton, 
    QFrame, QStackedWidget, QTabWidget, QLineEdit,
    QMessageBox, QComboBox, QFileDialog, QTextEdit, QInputDialog
)
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
# import pandas as pd deferred
from src.core.database import DatabaseManager
from src.core.telemetry import TelemetryClient, anonymous_id, record_event
from src.core.developer_access import DeveloperAccessGuard


def _normalizar_texto_busca(valor):
    """Compara nomes sem depender de maiúsculas, espaços ou acentos."""
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    sem_acentos = "".join(
        char for char in texto if not unicodedata.combining(char)
    )
    return " ".join(sem_acentos.casefold().split())

class ExtractionScreen(QWidget):
    sig_dispatch_whatsapp = pyqtSignal(str, str)
    sig_check_whatsapp_login = pyqtSignal()
    sig_request_tab_change = pyqtSignal(int)
    sig_iniciar_conversa_individual = pyqtSignal(str, str, str, str, dict)

    def __init__(self):
        super().__init__()
        
        self.fila_extraida = []
        self.fila_disparo = []
        self._conversation_generation = 0
        self._pending_conversation_generation = None
        self._ssi_generation = 0
        self._active_ssi_generation = None
        self._ssi_extracting_generation = None
        
        self.ssi_pronto = False
        self.tsi_pronto = False
        self.iniciou_carregamento = False
        self.is_full_history = False
        # Estado dos relatórios antes/depois da aplicação dos filtros. O robô
        # só extrai quando detecta mudança real e estabilização da nova tabela.
        self.tsi_relatorio_baseline = None
        self.tsi_relatorio_ultima_assinatura = None
        self.tsi_relatorio_estavel = 0
        self.tsi_relatorio_em_transicao = False
        self.tsi_relatorio_token = None
        self.ssi_relatorio_baseline = None
        self.ssi_relatorio_ultima_assinatura = None
        self.ssi_relatorio_estavel = 0
        self.ssi_relatorio_em_transicao = False
        
        self.os_respondidas_tsi = set()
        
        self.verificador_timer = QTimer(self)
        self.verificador_timer.timeout.connect(self.checar_tabelas_prontas)
        
        self.timer_ssi_ficha = QTimer(self)
        self.timer_ssi_ficha.timeout.connect(self.checar_ssi_ficha)
        
        # self.timer_auditor removido conforme regra de atualizacao manual
        
        self.db_manager = DatabaseManager()
        self.historico_tsi = self.db_manager.load_all_records()
        
        # Iniciar as OS respondidas com base no histórico
        self.os_respondidas_tsi = set()
        for rec in self.historico_tsi:
            os_val = str(rec.get('Ordens de Serviço: OS', '')).strip()
            if os_val:
                os_val = os_val.split('-')[1] if '-' in os_val else os_val
                self.os_respondidas_tsi.add(os_val)
        
        self.setup_ui()
        self.atualizar_combo_templates()
        self.setup_dev_mode_shortcut()
        self.setup_web_engine()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # --- CABEÇALHO E STATUS (Nomenclatura Premium) ---
        header_layout = QHBoxLayout()
        titulos_layout = QVBoxLayout()
        lbl_titulo = QLabel("Envios Pesquisas SSI & TSI via WhatsApp")
        lbl_titulo.setStyleSheet("color: #1E293B; font-size: 24px; font-weight: 800; border: none;")
        titulos_layout.addWidget(lbl_titulo)
        
        # Split header into two rows to prevent overflow
        header_row1 = QHBoxLayout()
        header_row1.addLayout(titulos_layout)
        header_row1.addStretch()
        
        header_row2 = QHBoxLayout()
        header_row2.addStretch()
        
        self.status_honda = QLabel("🟡 Aguardando Login myHonda...")
        self.status_honda.setStyleSheet("background-color: white; color: #F59E0B; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0;")
        
        self.status_auditor_tsi = QLabel("📡 Auditor TSI: Buscando...")
        self.status_auditor_tsi.setStyleSheet("background-color: white; color: #F59E0B; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0; margin-left: 10px;")

        self.status_auditor_ssi = QLabel("📡 Auditor SSI: Buscando...")
        self.status_auditor_ssi.setStyleSheet("background-color: white; color: #F59E0B; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0; margin-left: 10px;")
        
        self.btn_sincronizar = QPushButton("🔄 Atualizar myHonda")
        self.btn_sincronizar.setStyleSheet("background-color: #2563EB; color: white; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; margin-left: 10px;")
        self.btn_sincronizar.clicked.connect(self.forcar_sincronizacao_normal)
        self.btn_sincronizar.setEnabled(False)
        
        self.btn_sincronizar_ano = QPushButton("📥 Histórico Anual")
        self.btn_sincronizar_ano.setStyleSheet("background-color: #10B981; color: white; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; margin-left: 5px;")
        self.btn_sincronizar_ano.clicked.connect(self.forcar_historico_completo)
        self.btn_sincronizar_ano.setEnabled(False)
        
        header_row2.addWidget(self.status_honda)
        header_row2.addWidget(self.status_auditor_tsi)
        header_row2.addWidget(self.status_auditor_ssi)
        header_row2.addWidget(self.btn_sincronizar)
        header_row2.addWidget(self.btn_sincronizar_ano)
        
        header_main = QVBoxLayout()
        header_main.setContentsMargins(0, 0, 0, 10)
        header_main.addLayout(header_row1)
        header_main.addLayout(header_row2)
        
        layout.addLayout(header_main)
        
        # --- PAINEL DE CONTROLES (Automático) ---
        painel_ia = QFrame()
        painel_ia.setStyleSheet("background-color: #FFFFFF; border-radius: 10px; border: 1px solid #E2E8F0;")
        layout_ia = QHBoxLayout(painel_ia)
        layout_ia.setContentsMargins(25, 20, 25, 20)
        layout_ia.setSpacing(20)
        
        combo_layout = QVBoxLayout()
        lbl_filtro = QLabel("Selecione tipo Pesquisa:")
        lbl_filtro.setStyleSheet("color: #1E293B; font-weight: bold; font-size: 13px; border: none;")
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(["Pesquisas SSI (Vendas)", "Pesquisas TSI (Oficina)"])
        self.combo_tipo.setFixedHeight(40)
        self.combo_tipo.setFixedWidth(280)
        self.combo_tipo.setStyleSheet("background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 5px; padding-left: 10px; color: #1E293B; font-weight: bold;")
        self.combo_tipo.currentIndexChanged.connect(self.filtrar_lista) 
        combo_layout.addWidget(lbl_filtro)
        combo_layout.addWidget(self.combo_tipo)
        combo_layout.addStretch()
        layout_ia.addLayout(combo_layout, stretch=1)
        
        # Controles de Disparo e Atendimento Individual
        self.btn_conversar = QPushButton("💬 Conversar com o Destacado")
        self.btn_conversar.setFixedSize(220, 45)
        self.btn_conversar.setEnabled(False)
        self.btn_conversar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_conversar.setToolTip(
            "Abre somente a linha destacada em azul; não envia mensagem automaticamente."
        )
        self.btn_conversar.setStyleSheet("""
            QPushButton { background-color: #2563EB; color: white; font-weight: bold; border-radius: 6px; font-size: 13px; border-bottom: 4px solid #1D4ED8; }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:pressed { margin-top: 4px; border-bottom: none; }
            QPushButton:disabled { background-color: #94A3B8; border-bottom: 4px solid #64748B; }
        """)
        self.btn_conversar.clicked.connect(self.iniciar_conversa_individual)

        self.btn_dispatch = QPushButton("▶ Enviar Pesquisa Selecionada")
        self.btn_dispatch.setFixedSize(220, 45)
        self.btn_dispatch.setEnabled(False) # Habilita só quando a lista extrair
        self.btn_dispatch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dispatch.setStyleSheet("""
            QPushButton { background-color: #10B981; color: white; font-weight: bold; border-radius: 6px; font-size: 14px; border-bottom: 4px solid #059669; }
            QPushButton:hover { background-color: #059669; }
            QPushButton:pressed { margin-top: 4px; border-bottom: none; }
            QPushButton:disabled { background-color: #94A3B8; border-bottom: 4px solid #64748B; }
        """)
        self.btn_dispatch.clicked.connect(self.iniciar_disparo)
        
        layout_ia.addWidget(self.btn_conversar, alignment=Qt.AlignmentFlag.AlignBottom)
        layout_ia.addWidget(self.btn_dispatch, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(painel_ia)
        
        # --- ÁREA DE TRABALHO ---
        area_trabalho_layout = QHBoxLayout()
        area_trabalho_layout.setSpacing(20)
        
        # 1. Painel Fila de Disparo (Esquerda)
        painel_fila = QFrame()
        painel_fila.setStyleSheet("background-color: #FFFFFF; border-radius: 10px; border: 1px solid #E2E8F0;")
        layout_fila = QVBoxLayout(painel_fila)
        layout_fila.setContentsMargins(1, 1, 1, 1)
        layout_fila.setSpacing(5)
        
        self.lbl_fila = QLabel("  Fila de Disparo (0 Registros)")
        self.lbl_fila.setStyleSheet("color: #64748B; font-weight: bold; padding: 10px; border-bottom: 1px solid #E2E8F0;")
        layout_fila.addWidget(self.lbl_fila)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Buscar cliente por nome...")
        self.search_box.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                padding: 8px;
                font-size: 13px;
                margin: 5px 10px;
                selection-background-color: #2563EB;
                selection-color: #FFFFFF;
            }
            QLineEdit:focus {
                border: 2px solid #2563EB;
            }
        """)
        self.search_box.textChanged.connect(self.filtrar_lista)
        layout_fila.addWidget(self.search_box)

        self.selection_hint = QLabel("● Linha azul: conversa   ☑ Marcados: envio em lote")
        self.selection_hint.setStyleSheet(
            "color: #1E40AF; background: #EFF6FF; border: 1px solid #BFDBFE; "
            "border-radius: 5px; padding: 6px 10px; margin: 0 10px 4px 10px; "
            "font-size: 11px; font-weight: 600;"
        )
        layout_fila.addWidget(self.selection_hint)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget { border: none; padding: 5px; font-size: 13px; color: #1E293B; outline: none; }
            QListWidget::item { padding: 7px 8px; margin: 2px 4px; border: 2px solid transparent; border-radius: 6px; }
            QListWidget::item:hover { background: #F1F5F9; border-color: #CBD5E1; }
            QListWidget::item:selected,
            QListWidget::item:selected:!active {
                background: #2563EB;
                color: #FFFFFF;
                border: 2px solid #1D4ED8;
                font-weight: 700;
            }
            QScrollBar:vertical { width: 14px; background: #F1F5F9; border-radius: 7px; }
            QScrollBar::handle:vertical { background: #CBD5E1; min-height: 20px; border-radius: 7px; }
        """)
        self.list_widget.itemChanged.connect(self.ao_alterar_selecao_unica)
        layout_fila.addWidget(self.list_widget)
        area_trabalho_layout.addWidget(painel_fila, stretch=1)
        
        # 2. Painel Dinâmico da Direita (myHonda / Editor)
        painel_nav = QFrame()
        painel_nav.setStyleSheet("background-color: #FFFFFF; border-radius: 10px; border: 1px solid #E2E8F0;")
        layout_nav = QVBoxLayout(painel_nav)
        layout_nav.setContentsMargins(1, 1, 1, 1)
        
        header_nav = QHBoxLayout()
        self.lbl_nav_titulo = QLabel("  Visão do myHonda (Faça o Login para iniciar automação)")
        self.lbl_nav_titulo.setStyleSheet("color: #64748B; font-weight: bold; padding: 10px;")
        header_nav.addWidget(self.lbl_nav_titulo)
        header_nav.addStretch()
        layout_nav.addLayout(header_nav)
        
        linha_sep = QFrame()
        linha_sep.setFrameShape(QFrame.Shape.HLine)
        linha_sep.setStyleSheet("color: #E2E8F0;")
        layout_nav.addWidget(linha_sep)
        
        # STACKED WIDGET
        self.stack_direita = QStackedWidget()
        
        # Página 0: Tela de Login Limpa do myHonda (Sem abas de relatórios para o usuário)
        self.container_login = QWidget()
        self.login_layout = QVBoxLayout(self.container_login)
        self.login_layout.setContentsMargins(0, 0, 0, 0)
        self.stack_direita.addWidget(self.container_login)
        
        # Página 1: Editor de Mensagens e Modelos Pré-definidos
        container_editor = QWidget()
        layout_editor = QVBoxLayout(container_editor)
        layout_editor.setContentsMargins(15, 15, 15, 15)
        layout_editor.setSpacing(10)
        
        # 1. Barra Superior de Modelos / Templates
        frame_templates = QFrame()
        frame_templates.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 5px;")
        layout_tpl = QHBoxLayout(frame_templates)
        layout_tpl.setContentsMargins(10, 8, 10, 8)
        layout_tpl.setSpacing(8)
        
        lbl_tpl = QLabel("📋 Modelo:")
        lbl_tpl.setStyleSheet("font-weight: bold; color: #1E293B; font-size: 13px; border: none;")
        layout_tpl.addWidget(lbl_tpl)
        
        self.combo_templates = QComboBox()
        self.combo_templates.setFixedHeight(34)
        self.combo_templates.setStyleSheet("""
            QComboBox {
                background-color: white;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                padding-left: 8px;
                color: #0F172A;
                font-weight: bold;
                font-size: 12px;
                min-width: 180px;
            }
        """)
        self.combo_templates.currentIndexChanged.connect(self.on_template_alterado)
        layout_tpl.addWidget(self.combo_templates, stretch=1)
        
        self.btn_salvar_novo_tpl = QPushButton("➕ Salvar Novo")
        self.btn_salvar_novo_tpl.setFixedHeight(34)
        self.btn_salvar_novo_tpl.setStyleSheet("""
            QPushButton { background-color: #2563EB; color: white; font-weight: bold; font-size: 11px; padding: 0 10px; border-radius: 5px; }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.btn_salvar_novo_tpl.setToolTip("Salva o texto atual como um novo modelo com título personalizado")
        self.btn_salvar_novo_tpl.clicked.connect(self.salvar_novo_template)
        layout_tpl.addWidget(self.btn_salvar_novo_tpl)
        
        self.btn_atualizar_tpl = QPushButton("💾 Salvar")
        self.btn_atualizar_tpl.setFixedHeight(34)
        self.btn_atualizar_tpl.setStyleSheet("""
            QPushButton { background-color: #059669; color: white; font-weight: bold; font-size: 11px; padding: 0 10px; border-radius: 5px; }
            QPushButton:hover { background-color: #047857; }
        """)
        self.btn_atualizar_tpl.setToolTip("Atualiza o modelo selecionado com as alterações feitas no texto")
        self.btn_atualizar_tpl.clicked.connect(self.salvar_alteracoes_template)
        layout_tpl.addWidget(self.btn_atualizar_tpl)
        
        self.btn_excluir_tpl = QPushButton("🗑️")
        self.btn_excluir_tpl.setFixedSize(34, 34)
        self.btn_excluir_tpl.setStyleSheet("""
            QPushButton { background-color: #EF4444; color: white; font-weight: bold; font-size: 12px; border-radius: 5px; }
            QPushButton:hover { background-color: #DC2626; }
        """)
        self.btn_excluir_tpl.setToolTip("Excluir o modelo selecionado")
        self.btn_excluir_tpl.clicked.connect(self.excluir_template_atual)
        layout_tpl.addWidget(self.btn_excluir_tpl)
        
        layout_editor.addWidget(frame_templates)
        
        # 2. Barra de Variáveis Rápidas
        bar_tags = QHBoxLayout()
        lbl_tags = QLabel("Variáveis:")
        lbl_tags.setStyleSheet("color: #64748B; font-size: 12px; font-weight: bold;")
        bar_tags.addWidget(lbl_tags)
        
        btn_tag_nome = QPushButton("+ [NOME]")
        btn_tag_nome.setFixedHeight(26)
        btn_tag_nome.setStyleSheet("background-color: #EEF2FF; color: #4F46E5; border: 1px solid #C7D2FE; font-weight: bold; font-size: 11px; border-radius: 4px; padding: 0 8px;")
        btn_tag_nome.clicked.connect(lambda: self.inserir_tag_variavel("[NOME]"))
        bar_tags.addWidget(btn_tag_nome)
        
        btn_tag_link = QPushButton("+ [LINK]")
        btn_tag_link.setFixedHeight(26)
        btn_tag_link.setStyleSheet("background-color: #ECFDF5; color: #059669; border: 1px solid #A7F3D0; font-weight: bold; font-size: 11px; border-radius: 4px; padding: 0 8px;")
        btn_tag_link.clicked.connect(lambda: self.inserir_tag_variavel("[LINK]"))
        bar_tags.addWidget(btn_tag_link)
        
        bar_tags.addStretch()
        layout_editor.addLayout(bar_tags)
        
        # 3. Editor de Mensagem
        self.editor_mensagem = QTextEdit()
        self.editor_mensagem.setStyleSheet("""
            QTextEdit {
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                font-size: 14px;
                padding: 12px;
                color: #1E293B;
                background-color: #FFFFFF;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border: 1px solid #3B82F6;
            }
        """)
        layout_editor.addWidget(self.editor_mensagem)
        
        lbl_dica = QLabel("💡 As variáveis [NOME] e [LINK] são preenchidas dinamicamente para cada cliente na hora do disparo.")
        lbl_dica.setStyleSheet("color: #64748B; font-size: 11px; font-style: italic;")
        layout_editor.addWidget(lbl_dica)
        
        self.stack_direita.addWidget(container_editor)
        
        # Página 2: Modo Desenvolvedor / Inspeção de Robôs (Acessível via Ctrl+Shift+D)
        container_dev = QWidget()
        dev_layout = QVBoxLayout(container_dev)
        dev_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs_navegadores = QTabWidget()
        self.tabs_navegadores.setStyleSheet("""
            QTabBar::tab {
                background: #F1F5F9;
                color: #475569;
                padding: 8px 14px;
                font-weight: bold;
                font-size: 11px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
                color: #2563EB;
                border-bottom: 2px solid #2563EB;
            }
        """)
        dev_layout.addWidget(self.tabs_navegadores)
        self.stack_direita.addWidget(container_dev)
        
        layout_nav.addWidget(self.stack_direita)
        area_trabalho_layout.addWidget(painel_nav, stretch=2)
        
        layout.addLayout(area_trabalho_layout, stretch=1)

    def setup_web_engine(self):
        import os
        from src.core.paths import get_base_dir
        storage_path = os.path.join(get_base_dir(), "app_data", "salesforce")
        self.profile = QWebEngineProfile("SalesforceProfile", self)
        self.profile.setPersistentStoragePath(storage_path)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # 1. Navegador de Login do myHonda (Exibido limpo na Página 0 sem abas para o usuário)
        self.nav_login = QWebEngineView()
        self.nav_login.setPage(QWebEnginePage(self.profile, self.nav_login))
        self.nav_login.setUrl(QUrl("https://myhonda.my.site.com/concessionaria/login"))
        self.nav_login.urlChanged.connect(self.verificar_login_honda)
        self.login_layout.addWidget(self.nav_login)
        
        # 2. Navegadores dos Robôs e Relatórios
        self.nav_auditor_tsi = QWebEngineView()
        self.nav_auditor_tsi.setPage(QWebEnginePage(self.profile, self.nav_auditor_tsi))
        
        self.nav_auditor_ssi = QWebEngineView()
        self.nav_auditor_ssi.setPage(QWebEnginePage(self.profile, self.nav_auditor_ssi))

        self.nav_tsi_oculto = QWebEngineView()
        self.nav_tsi_oculto.setPage(QWebEnginePage(self.profile, self.nav_tsi_oculto))

        self.nav_ssi_oculto = QWebEngineView()
        self.nav_ssi_oculto.setPage(QWebEnginePage(self.profile, self.nav_ssi_oculto))
        
        # Abas disponíveis apenas no Modo Desenvolvedor (Página 2)
        self.tabs_navegadores.addTab(self.nav_auditor_tsi, "📊 Respostas TSI")
        self.tabs_navegadores.addTab(self.nav_auditor_ssi, "📊 Respostas SSI")
        self.tabs_navegadores.addTab(self.nav_tsi_oculto, "🚀 Disparo TSI")
        self.tabs_navegadores.addTab(self.nav_ssi_oculto, "🚀 Disparo SSI")


    def iniciar_recuperacao(self, tipo):
        if tipo == 'TSI':
            self.timer_polling_auditor.stop()
            self.status_auditor_tsi.setText("⚠️ TSI: Instabilidade detectada. Recuperando em 60s...")
            self.status_auditor_tsi.setStyleSheet("background-color: white; color: #F59E0B; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0; margin-left: 10px;")
            self.contador_rec_tsi = 60
            self.timer_rec_tsi = QTimer(self)
            self.timer_rec_tsi.timeout.connect(lambda: self.atualizar_contagem_rec('TSI'))
            self.timer_rec_tsi.start(1000)
        else:
            self.timer_polling_auditor_ssi.stop()
            self.status_auditor_ssi.setText("⚠️ SSI: Instabilidade detectada. Recuperando em 60s...")
            self.status_auditor_ssi.setStyleSheet("background-color: white; color: #F59E0B; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0; margin-left: 10px;")
            self.contador_rec_ssi = 60
            self.timer_rec_ssi = QTimer(self)
            self.timer_rec_ssi.timeout.connect(lambda: self.atualizar_contagem_rec('SSI'))
            self.timer_rec_ssi.start(1000)

    def atualizar_contagem_rec(self, tipo):
        if tipo == 'TSI':
            self.contador_rec_tsi -= 1
            if self.contador_rec_tsi <= 0:
                self.timer_rec_tsi.stop()
                self.status_auditor_tsi.setText("🔄 TSI: Reiniciando extração...")
                self.status_auditor_tsi.setStyleSheet("background-color: white; color: #2563EB; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0; margin-left: 10px;")
                self.nav_auditor_tsi.reload()
                self.tentativas_auditor_tsi = 0
                self.tsi_filtros_aplicados = False
                self.timer_polling_auditor.start(3000)
            else:
                self.status_auditor_tsi.setText(f"⚠️ TSI: Instabilidade detectada. Recuperando em {self.contador_rec_tsi}s...")
        else:
            self.contador_rec_ssi -= 1
            if self.contador_rec_ssi <= 0:
                self.timer_rec_ssi.stop()
                self.status_auditor_ssi.setText("🔄 SSI: Reiniciando extração...")
                self.status_auditor_ssi.setStyleSheet("background-color: white; color: #2563EB; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0; margin-left: 10px;")
                self.nav_auditor_ssi.reload()
                self.tentativas_auditor_ssi = 0
                self.ssi_filtros_aplicados = False
                self.timer_polling_auditor_ssi.start(3000)
            else:
                self.status_auditor_ssi.setText(f"⚠️ SSI: Instabilidade detectada. Recuperando em {self.contador_rec_ssi}s...")

    def verificar_login_honda(self, qurl):
        url = qurl.toString().lower()
        if ("home" in url or "leads" in url or "recent" in url or "/s/" in url) and not self.iniciou_carregamento:
            record_event("myhonda", "LOGIN_CONFIRMED")
            self.iniciou_carregamento = True
            self.status_honda.setText("🟡 myHonda: Autenticado. Preparando relatórios...")
            # Após 1 segundo de folga do login, inicializa sincronização
            QTimer.singleShot(1000, self.iniciar_sincronizacao_automatica)

    def get_templates_path(self):
        from src.core.paths import get_base_dir
        return os.path.join(get_base_dir(), "app_data", "templates_mensagens.json")

    def carregar_templates(self):
        path = self.get_templates_path()
        templates_padrao = [
            {
                "id": "padrao",
                "titulo": "Mensagem Padrão (Pesquisa de Satisfação)",
                "mensagem": "Olá *[NOME]*, tudo bem?\nAgradecemos a sua visita à nossa concessionária. Para continuarmos a melhorar, gostaríamos de ouvir a sua opinião:\n\n[LINK]"
            },
            {
                "id": "sorteio",
                "titulo": "Campanha Sorteio de Revisão",
                "mensagem": "Olá *[NOME]*, tudo bem?\nParticipe da nossa rápida pesquisa de satisfação e concorra a um sorteio exclusivo na sua próxima revisão!\n\nClique no link abaixo para avaliar:\n[LINK]"
            },
            {
                "id": "pos_venda",
                "titulo": "Agradecimento Pós-Vendas Oficina",
                "mensagem": "Olá *[NOME]*, esperamos que sua motocicleta esteja excelente!\nSua avaliação sobre o atendimento na nossa oficina é fundamental para nossa equipe:\n\n[LINK]\nMuito obrigado pela preferência!"
            }
        ]
        
        if not os.path.exists(path):
            try:
                import json
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(templates_padrao, f, ensure_ascii=False, indent=2)
                return templates_padrao
            except Exception:
                return templates_padrao
        else:
            try:
                import json
                with open(path, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    return dados if isinstance(dados, list) and dados else templates_padrao
            except Exception:
                return templates_padrao

    def salvar_templates_arquivo(self, templates):
        path = self.get_templates_path()
        try:
            import json
            with open(path, "w", encoding="utf-8") as f:
                json.dump(templates, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar modelos: {e}")
            return False

    def atualizar_combo_templates(self, selecionar_id=None):
        self._is_updating_templates = True
        self.combo_templates.clear()
        self.lista_templates = self.carregar_templates()
        
        target_idx = 0
        for i, tpl in enumerate(self.lista_templates):
            self.combo_templates.addItem(tpl.get("titulo", "Sem Título"), tpl.get("id"))
            if selecionar_id and tpl.get("id") == selecionar_id:
                target_idx = i
                
        self._is_updating_templates = False
        if self.lista_templates:
            self.combo_templates.setCurrentIndex(target_idx)
            self.editor_mensagem.setText(self.lista_templates[target_idx].get("mensagem", ""))

    def on_template_alterado(self, index):
        if getattr(self, '_is_updating_templates', False) or index < 0 or not hasattr(self, 'lista_templates') or index >= len(self.lista_templates):
            return
        tpl = self.lista_templates[index]
        self.editor_mensagem.setText(tpl.get("mensagem", ""))

    def salvar_novo_template(self):
        nome, ok = QInputDialog.getText(self, "Novo Modelo de Mensagem", "Digite o título/nome para este modelo:")
        if ok and nome.strip():
            nome = nome.strip()
            import uuid
            novo_id = str(uuid.uuid4())[:8]
            novo_tpl = {
                "id": novo_id,
                "titulo": nome,
                "mensagem": self.editor_mensagem.toPlainText()
            }
            self.lista_templates.append(novo_tpl)
            if self.salvar_templates_arquivo(self.lista_templates):
                self.atualizar_combo_templates(selecionar_id=novo_id)
                QMessageBox.information(self, "Sucesso", f"Modelo '{nome}' salvo com sucesso!")

    def salvar_alteracoes_template(self):
        idx = self.combo_templates.currentIndex()
        if idx < 0 or not hasattr(self, 'lista_templates') or idx >= len(self.lista_templates):
            return
        tpl = self.lista_templates[idx]
        tpl["mensagem"] = self.editor_mensagem.toPlainText()
        if self.salvar_templates_arquivo(self.lista_templates):
            QMessageBox.information(self, "Sucesso", f"Alterações no modelo '{tpl.get('titulo')}' salvas com sucesso!")

    def excluir_template_atual(self):
        idx = self.combo_templates.currentIndex()
        if idx < 0 or not hasattr(self, 'lista_templates') or idx >= len(self.lista_templates):
            return
        if len(self.lista_templates) <= 1:
            QMessageBox.warning(self, "Aviso", "É necessário manter pelo menos um modelo no sistema.")
            return
        tpl = self.lista_templates[idx]
        conf = QMessageBox.question(
            self, "Excluir Modelo", 
            f"Tem certeza que deseja excluir o modelo '{tpl.get('titulo')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if conf == QMessageBox.StandardButton.Yes:
            self.lista_templates.pop(idx)
            self.salvar_templates_arquivo(self.lista_templates)
            self.atualizar_combo_templates()
            QMessageBox.information(self, "Sucesso", "Modelo excluído com sucesso!")

    def inserir_tag_variavel(self, tag):
        cursor = self.editor_mensagem.textCursor()
        cursor.insertText(tag)
        self.editor_mensagem.setFocus()

    def setup_dev_mode_shortcut(self):
        self.dev_shortcut = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        self.dev_shortcut.activated.connect(self.abrir_modo_desenvolvedor)

    def abrir_modo_desenvolvedor(self):
        if self.stack_direita.currentIndex() == 2:
            novo_idx = 1 if getattr(self, 'iniciou_carregamento', False) else 0
            self.stack_direita.setCurrentIndex(novo_idx)
            titulo = "  ✉️ Editor de Mensagem e Disparo WhatsApp" if novo_idx == 1 else "  🔐 Visão do myHonda (Faça o Login para Iniciar automação)"
            self.lbl_nav_titulo.setText(titulo)
            QMessageBox.information(self, "Modo Desenvolvedor", "Modo desenvolvedor ocultado.")
            return

        autorizado, motivo = DeveloperAccessGuard.authorization_status(force=True)
        if not autorizado:
            texto = (
                "Não foi possível confirmar a autorização no servidor. Verifique a internet e tente novamente."
                if motivo == "DIAGNOSTIC_AUTHORIZATION_UNAVAILABLE" else
                "Autorize o diagnóstico por 24 horas neste computador pelo Gerador Admin antes de continuar."
            )
            QMessageBox.warning(self, "Acesso protegido", texto)
            return
        bloqueio = DeveloperAccessGuard.remaining_lock_seconds()
        if bloqueio:
            QMessageBox.warning(self, "Acesso temporariamente bloqueado", f"Aguarde {bloqueio // 60 + 1} minuto(s) para tentar novamente.")
            return
        senha, ok = QInputDialog.getText(
            self, "Modo Desenvolvedor / Master", 
            "Digite a senha de administrador:", 
            QLineEdit.EchoMode.Password
        )
        if ok:
            acesso, resultado = DeveloperAccessGuard.verify_password(senha)
            if acesso:
                self.stack_direita.setCurrentIndex(2)
                self.lbl_nav_titulo.setText("  🔧 [MODO DEV ATIVO] Modo: VISÍVEL (Abas de Robôs e Relatórios)")
                QMessageBox.information(self, "Modo Desenvolvedor", "Modo desenvolvedor autorizado temporariamente para este computador.")
            else:
                mensagem = "Acesso bloqueado por 15 minutos após tentativas incorretas." if resultado == "LOCKED" else "Senha incorreta. As tentativas são limitadas."
                QMessageBox.warning(self, "Acesso Negado", mensagem)

    def iniciar_sincronizacao_automatica(self):
        # 1. Transição para Modo Fantasma: Oculta navegadores e exibe Editor de Mensagens
        self.lbl_nav_titulo.setText("  ✉️ Editor de Mensagem e Disparo WhatsApp")
        self.stack_direita.setCurrentIndex(1) # Oculta os robôs e exibe o Editor de Mensagens!
        
        self.status_honda.setText("🟢 myHonda: Sincronizando dados...")
        
        # Checa se o computador é novo para forçar filtro de 'Ano atual' na fila
        self.precisa_filtro_fila_tsi = len(self.historico_tsi) < 50
        historico_ssi = self.db_manager.load_ssi_records()
        self.precisa_filtro_fila_ssi = len(historico_ssi) < 500
        
        # 2. Inicia o disparo dos relatórios invisíveis
        id_fila_ssi = "00O4M000004CsIi"
        id_fila_tsi = "00O4M000004n3W1"
        id_auditor_tsi = "00OVP000003I7cP"
        id_auditor_ssi = "00OKk000000JHzc"
        
        try:
            from src.core.paths import get_base_dir
            import json, os
            caminho_links = os.path.join(get_base_dir(), "app_data", "license_links.json")
            if os.path.exists(caminho_links):
                with open(caminho_links, "r", encoding="utf-8") as f:
                    links = json.load(f)
                if links.get("fila_ssi"): id_fila_ssi = links.get("fila_ssi")
                if links.get("fila_tsi"): id_fila_tsi = links.get("fila_tsi")
                if links.get("auditor_tsi"): id_auditor_tsi = links.get("auditor_tsi")
                if links.get("auditor_ssi"): id_auditor_ssi = links.get("auditor_ssi")
        except Exception as e:
            print("Erro lendo links customizados:", e)
            
        self.nav_ssi_oculto.setUrl(QUrl(f"https://myhonda.my.site.com/concessionaria/{id_fila_ssi}"))
        self.nav_tsi_oculto.setUrl(QUrl(f"https://myhonda.my.site.com/concessionaria/{id_fila_tsi}"))
        
        self.nav_auditor_tsi.setUrl(QUrl(f"https://myhonda.my.site.com/concessionaria/{id_auditor_tsi}"))
        self.nav_auditor_ssi.setUrl(QUrl(f"https://myhonda.my.site.com/concessionaria/{id_auditor_ssi}"))
        
        # Mantém dentro das abas sem jogar para fora do monitor
        pass
        
        # Timer de Polling do Auditor (Tenta achar a tabela a cada 3 segundos em vez de esperar 10s fixo)
        self.tsi_filtros_aplicados = False
        self.timer_polling_auditor = QTimer(self)
        self.timer_polling_auditor.timeout.connect(self.extrair_dados_auditor)
        self.timer_polling_auditor.start(3000)
        
        self.ssi_filtros_aplicados = False
        self.timer_polling_auditor_ssi = QTimer(self)
        self.timer_polling_auditor_ssi.timeout.connect(self.extrair_dados_auditor_ssi)
        self.timer_polling_auditor_ssi.start(3000)
        
        self.ssi_pronto = False
        self.tsi_pronto = False
        self.tentativas_verificacao = 0
        self.verificador_timer.start(3000)

    def checar_tabelas_prontas(self):
        self.tentativas_verificacao += 1
        
        script_filtros = """
        (function() {
            try {
                function selectOptionByText(selectTag, textMatch) {
                    for (let i = 0; i < selectTag.options.length; i++) {
                        if (selectTag.options[i].text.includes(textMatch)) {
                            selectTag.selectedIndex = i;
                            let event = new Event('change', { bubbles: true });
                            selectTag.dispatchEvent(event);
                            return true;
                        }
                    }
                    return false;
                }

                let selects = document.querySelectorAll('select');
                let changedAny = false;
                if (selects.length < 2) return "PAGINA_CARREGANDO";
                
                for (let i = 0; i < selects.length; i++) {
                    if (selectOptionByText(selects[i], 'Todos os tempos') || 
                        selectOptionByText(selects[i], 'Este ano') || 
                        selectOptionByText(selects[i], 'Ano atual') || 
                        selectOptionByText(selects[i], 'Sempre')) {
                        changedAny = true;
                        break;
                    }
                }
                
                if (changedAny) {
                    let allBtns = document.querySelectorAll('input[type="submit"], input[type="button"], button, input.btn');
                    for (let i = 0; i < allBtns.length; i++) {
                        let btn = allBtns[i];
                        let text = (btn.value || btn.innerText || btn.title || "").toLowerCase();
                        if (text.includes('executar')) {
                            btn.click();
                            return "FILTROS_APLICADOS_E_BOTAO_CLICADO";
                        }
                    }
                    return "FILTROS_APLICADOS_MAS_BOTAO_NAO_ENCONTRADO";
                }
                return "JA_CONFIGURADO_OU_NAO_ENCONTRADO";
            } catch(e) { return "ERRO: " + e; }
        })();
        """
                
        script_check = r"""
            (function() {
                function verificarDoc(doc) {
                    if (!doc || !doc.body) return false;
                    
                    let rows = doc.querySelectorAll('tr.even, tr.odd, tr[class*="dataRow"]');
                    if (rows.length > 0) return true;
                    
                    let links = doc.querySelectorAll('a[href*="/"]');
                    for (let a of links) {
                        let href = a.getAttribute('href') || '';
                        if (href.match(/\/([a-zA-Z0-9]{15,18})/i) && !href.includes('00O')) {
                            return true;
                        }
                    }
                    
                    let text = doc.body.innerText || '';
                    if (text.includes('Nenhum registro') || text.includes('No records found') || text.includes('0 registro') || text.includes('Total: 0')) {
                        return true;
                    }
                    
                    return false;
                }
                
                if (verificarDoc(document)) return true;
                
                var frames = document.querySelectorAll('iframe');
                for (var i = 0; i < frames.length; i++) {
                    try { 
                        if (verificarDoc(frames[i].contentDocument || frames[i].contentWindow.document)) return true; 
                    } catch(e) {}
                }
                return false;
            })();
        """
        
        if self.precisa_filtro_fila_ssi == True:
            self.nav_ssi_oculto.page().runJavaScript(script_filtros, self.resultado_filtro_fila_ssi)
        elif self.precisa_filtro_fila_ssi == False and not self.ssi_pronto:
            self.nav_ssi_oculto.page().runJavaScript(script_check, self.resultado_check_ssi)
        
        if self.precisa_filtro_fila_tsi == True:
            self.nav_tsi_oculto.page().runJavaScript(script_filtros, self.resultado_filtro_fila_tsi)
        elif self.precisa_filtro_fila_tsi == False and not self.tsi_pronto:
            self.nav_tsi_oculto.page().runJavaScript(script_check, self.resultado_check_tsi)
            
    def resultado_filtro_fila_ssi(self, res):
        if not res or "PAGINA_CARREGANDO" in str(res):
            return
        self.precisa_filtro_fila_ssi = False

    def resultado_filtro_fila_tsi(self, res):
        if not res or "PAGINA_CARREGANDO" in str(res):
            return
        self.precisa_filtro_fila_tsi = False
            
    def resultado_check_ssi(self, pronto):
        if pronto: self.ssi_pronto = True
        self.validar_ambos_prontos()
        
    def resultado_check_tsi(self, pronto):
        if pronto: self.tsi_pronto = True
        self.validar_ambos_prontos()

    def validar_ambos_prontos(self):
        if self.ssi_pronto and self.tsi_pronto:
            self.verificador_timer.stop()
            self.status_honda.setText("🟢 myHonda: Bases Prontas. Gerando Lista...")
            self.status_honda.setStyleSheet("background-color: white; color: #16A34A; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0;")
            
            # Inicia o Auditor de Respostas
            self.extrair_dados_auditor()
            
            # Inicia a Auto-Extração
            self.fila_extraida = []
            self.extrair_ssi_primeiro()

    # --- FUNÇÕES DE AUTO-EXTRAÇÃO EM CADEIA ---
    def extrair_ssi_primeiro(self):
        script = """
            (function() {
                var htmlFinal = document.documentElement.outerHTML;
                var frames = document.querySelectorAll('iframe');
                for (var i = 0; i < frames.length; i++) {
                    try {
                        var doc = frames[i].contentDocument || frames[i].contentWindow.document;
                        if (doc) htmlFinal += doc.documentElement.outerHTML;
                    } catch(e) { } 
                }
                return htmlFinal;
            })();
        """
        self.nav_ssi_oculto.page().runJavaScript(script, lambda html: self.processar_html_extraido(html, "SSI"))
        
    def extrair_tsi_segundo(self):
        script = """
            (function() {
                var htmlFinal = document.documentElement.outerHTML;
                var frames = document.querySelectorAll('iframe');
                for (var i = 0; i < frames.length; i++) {
                    try {
                        var doc = frames[i].contentDocument || frames[i].contentWindow.document;
                        if (doc) htmlFinal += doc.documentElement.outerHTML;
                    } catch(e) { } 
                }
                return htmlFinal;
            })();
        """
        self.nav_tsi_oculto.page().runJavaScript(script, lambda html: self.processar_html_extraido(html, "TSI"))

    def processar_html_extraido(self, html_content, tipo):
        if not html_content:
            if tipo == "SSI": self.extrair_tsi_segundo()
            else: self.finalizar_auto_extracao()
            return
            
        soup = BeautifulSoup(html_content, "html.parser")
        sent_surveys = self.db_manager.load_sent_surveys()
            
        linhas = soup.find_all("tr", class_=["even", "odd"])
        
        # Termos de cabeçalhos/banners/filtros do myHonda para ignorar estritamente
        TERMOS_IGNORAR_NOME = [
            "CONCESSIONARIA", "CONCESSIONÁRIA", "ALTERADO", "INTERFACE", "MYHONDA", 
            "RELATÓRIO", "TOTAL", "SUBTOTAL", "NENHUM REGISTRO", "EXIBINDO", "DESCONHECIDO",
            "GERADO EM", "CONFIDENCIAL", "DATA/HORA", "FILTRO", "PARÂMETROS"
        ]

        idx_coluna_cliente = -1
        # Procura índice da coluna Cliente
        for linha in linhas[:10]:
            celulas = linha.find_all(["th", "td"])
            for idx, celula in enumerate(celulas):
                if celula.get_text(strip=True).upper() == "CLIENTE":
                    idx_coluna_cliente = idx
                    break
            if idx_coluna_cliente != -1:
                break
        
        for linha in linhas:
            texto_linha = linha.get_text(separator="  ", strip=True)
            texto_linha_upper = texto_linha.upper().replace(" ", "")
            
            # Filtro anti-banner do Salesforce/myHonda
            if any(termo in texto_linha_upper for termo in ["CONCESSIONARIAALTERADO", "ALTERADOPARA", "MYHONDAINTERFACE"]):
                continue

            links = linha.find_all("a")
            id_encontrado = None
            url_ficha = None
            posse_text_bruto = ""
            
            for a in links:
                href = a.get("href", "")
                match = re.search(r'/([a-zA-Z0-9]{15,18})(?:\?|/|$)', href)
                if match and not match.group(1).startswith("00O"):
                    id_encontrado = match.group(1)
                    url_ficha = href
                    posse_text_bruto = a.get_text(strip=True)
                    break
                    
            if id_encontrado and not any(cli['id'] == id_encontrado for cli in self.fila_extraida):
                nome_cliente = "N/D"
                telefone_cliente = "S/N"
                os_cliente = ""
                
                # Extrai sequências que parecem telefone (agora suportando o 55 do Brasil colado)
                fones_encontrados = re.findall(r'(?:\+?55\s*)?\(?\d{2}\)?\s*(?:9\s*)?\d{4}[-\s]?\d{4}', texto_linha)
                melhor_fone = None
                
                for f in fones_encontrados:
                    nums = re.sub(r'\D', '', f)
                    
                    # Se o número veio com o 55 do Brasil (13 dígitos celular, 12 dígitos fixo), remove o 55
                    if (len(nums) == 13 or len(nums) == 12) and nums.startswith('55'):
                        nums = nums[2:]
                    
                    # Se o cara digitou 0 na frente do DDD (ex: 011), arranca o zero
                    if len(nums) == 12 and nums.startswith('0'):
                        nums = nums[1:]
                    elif len(nums) == 11 and nums.startswith('0'):
                        # Se tem 11 dígitos e começa com 0 (ex: 0144122408), é lixo (DDD não pode ser 01)
                        # ou é um fixo com zero na frente (ex: 011 4122 4080 -> 11).
                        nums = nums[1:]
                        
                    # Validar regras estritas do Brasil
                    if len(nums) == 11:
                        # Celular: DDD válido (11 a 99) e começa com 9
                        ddd = int(nums[0:2])
                        if 11 <= ddd <= 99 and nums[2] == '9':
                            melhor_fone = nums
                            break # Achou um celular perfeito
                    elif len(nums) == 10 and not melhor_fone:
                        # Fixo: DDD válido (11 a 99) e começa de 2 a 8
                        ddd = int(nums[0:2])
                        if 11 <= ddd <= 99 and nums[2] in '2345678':
                            melhor_fone = nums # Salva o fixo como fallback
                        
                if melhor_fone:
                    telefone_cliente = melhor_fone
                match_os_regex = re.search(r'\b\d{5,8}-\d{5,8}\b', texto_linha)
                
                # Regras Estritas do Cliente para OS / Posse
                if tipo == "SSI":
                    # Relação de posse: Parte antes do traço
                    if '-' in posse_text_bruto:
                        os_cliente = posse_text_bruto.split('-')[0]
                    else:
                        os_cliente = posse_text_bruto if posse_text_bruto else "Sem Posse"
                elif tipo == "TSI":
                    # O.S.: Parte depois do traço
                    if '-' in posse_text_bruto:
                        os_cliente = posse_text_bruto.split('-')[1]
                    else:
                        os_cliente = posse_text_bruto if posse_text_bruto else "Sem OS"
                        if match_os_regex and '-' in match_os_regex.group(0):
                             os_cliente = match_os_regex.group(0).split('-')[1]
                
                celulas = linha.find_all(['td', 'th'])
                if idx_coluna_cliente != -1 and idx_coluna_cliente < len(celulas):
                    nome_cru = celulas[idx_coluna_cliente].get_text(strip=True).upper()
                    if len(nome_cru) > 2:
                        nome_cliente = nome_cru
                else:
                    for idx, celula in enumerate(celulas):
                        if celula.find('a', href=re.compile(id_encontrado)):
                            for proxima_celula in celulas[idx+1:]:
                                txt = proxima_celula.get_text(strip=True).upper()
                                if len(txt) > 3 and not re.search(r'\d', txt):
                                    if "HONDA" not in txt and "SOL NASCENTE" not in txt:
                                        nome_cliente = txt
                                        break
                            break
                
                nome_cliente = re.sub(r'(?i)^CLIENTE:\s*', '', nome_cliente).strip()
                
                # Validação contra banners e nomes inválidos
                if any(termo in nome_cliente.upper() for termo in TERMOS_IGNORAR_NOME):
                    nome_cliente = "N/D"

                if nome_cliente != "N/D" and len(nome_cliente) > 2 and re.search(r'[A-Za-z]', nome_cliente):
                    ja_enviado = id_encontrado in sent_surveys
                    self.fila_extraida.append({
                        "tipo": tipo,
                        "id": id_encontrado, 
                        "cliente": nome_cliente,
                        "telefone": telefone_cliente,
                        "os": os_cliente,
                        "os_full": posse_text_bruto,
                        "url_ficha": url_ficha,
                        "enviado": ja_enviado
                    })

        if tipo == "SSI":
            self.extrair_tsi_segundo()
        else:
            self.finalizar_auto_extracao()

    def finalizar_auto_extracao(self):
        # Salva o mapeamento O.S. / Posse -> Cliente e Telefone para cruzamento no Dashboard e Relatórios
        if hasattr(self, 'db_manager') and self.fila_extraida:
            self.db_manager.save_leads_mapping(self.fila_extraida)

        self.status_honda.setText("🟢 myHonda: Listas Geradas com Sucesso!")
        self.btn_dispatch.setEnabled(True)
        if hasattr(self, 'btn_conversar'):
            self.btn_conversar.setEnabled(True)
        self.btn_sincronizar.setEnabled(True)
        self.btn_sincronizar.setText("🔄 Atualizar myHonda")
        if hasattr(self, 'btn_sincronizar_ano'):
            self.btn_sincronizar_ano.setEnabled(True)
            self.btn_sincronizar_ano.setText("📥 Histórico Anual")
        self.atualizar_lista_ui()

    # --- O AUDITOR DE RESPOSTAS (EVITA DUPLICIDADE) ---
    def recarregar_auditor(self):
        pass # Mantido por compatibilidade se algo chamar
        
    def forcar_sincronizacao_normal(self):
        self.is_full_history = False
        self.forcar_sincronizacao()
        
    def forcar_historico_completo(self):
        self.is_full_history = True
        self.forcar_sincronizacao()

    def forcar_sincronizacao(self):
        if not self.iniciou_carregamento:
            record_event("synchronization", "SYNC_BLOCKED_NOT_LOGGED", "WARN")
            return
        record_event(
            "synchronization", "SYNC_STARTED",
            mode="annual" if getattr(self, 'is_full_history', False) else "current",
        )
        self.btn_sincronizar.setEnabled(False)
        if hasattr(self, 'btn_sincronizar_ano'):
            self.btn_sincronizar_ano.setEnabled(False)
            
        if getattr(self, 'is_full_history', False):
            if hasattr(self, 'btn_sincronizar_ano'):
                self.btn_sincronizar_ano.setText("⏳ Extraindo Ano...")
            self.btn_sincronizar.setText("🔄 Atualizar myHonda")
        else:
            self.btn_sincronizar.setText("⏳ Atualizando...")
            if hasattr(self, 'btn_sincronizar_ano'):
                self.btn_sincronizar_ano.setText("📥 Histórico Anual")
        
        self.status_honda.setText("⏳ myHonda: Sincronizando dados...")
        self.status_honda.setStyleSheet("background-color: white; color: #F59E0B; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0;")
        
        self.status_auditor_tsi.setText("📡 Auditor TSI: Buscando...")
        self.status_auditor_tsi.setStyleSheet("background-color: white; color: #F59E0B; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0; margin-left: 10px;")
        
        self.status_auditor_ssi.setText("📡 Auditor SSI: Buscando...")
        self.status_auditor_ssi.setStyleSheet("background-color: white; color: #F59E0B; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0; margin-left: 10px;")
        
        self.list_widget.clear()
        self.tentativas_auditor_tsi = 0
        self.tentativas_auditor_ssi = 0
        
        self.nav_ssi_oculto.reload()
        self.nav_tsi_oculto.reload()
        self.nav_auditor_tsi.reload()
        self.nav_auditor_ssi.reload()
        
        self.ssi_pronto = False
        self.tsi_pronto = False
        self.ssi_filtros_aplicados = False
        self.tsi_filtros_aplicados = False
        self.tsi_relatorio_baseline = None
        self.tsi_relatorio_ultima_assinatura = None
        self.tsi_relatorio_estavel = 0
        self.tsi_relatorio_em_transicao = False
        self.ssi_relatorio_baseline = None
        self.ssi_relatorio_ultima_assinatura = None
        self.ssi_relatorio_estavel = 0
        self.ssi_relatorio_em_transicao = False
        
        if hasattr(self, 'timer_polling_auditor'):
            self.timer_polling_auditor.start(3000)
        
        if hasattr(self, 'timer_polling_auditor_ssi'):
            self.timer_polling_auditor_ssi.start(3000)
            
        self.verificador_timer.start(3000)

    def extrair_dados_auditor(self):
        if not hasattr(self, 'tentativas_auditor_tsi'): self.tentativas_auditor_tsi = 0
        self.tentativas_auditor_tsi += 1
        
        # O histórico anual não possui timeout fixo: o Salesforce pode levar
        # vários minutos. A conclusão é determinada pelo estado do DOM.
        if not getattr(self, 'is_full_history', False) and self.tentativas_auditor_tsi > 200:
            self.timer_polling_auditor.stop()
            self.status_auditor_tsi.setText("⚠️ TSI: Relatório com Instabilidade (Timeout)")
            self.status_auditor_tsi.setStyleSheet("background-color: white; color: #EF4444; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0; margin-left: 10px;")
            return

        # Fluxo normal: o relatório já abre pronto no formato padrão. Não há
        # filtro nem transição a aguardar; captura o HTML até o parser encontrar
        # a tabela.
        if not getattr(self, 'is_full_history', False):
            self.nav_auditor_tsi.page().runJavaScript(
                self._script_html_completo(),
                self.processar_html_auditor
            )
            return

        if not getattr(self, 'tsi_filtros_aplicados', False):
            script_filtros_tsi = """
            (function() {
                try {
                    function selectOptionByText(selectTag, textMatch) {
                        for (let i = 0; i < selectTag.options.length; i++) {
                            let opt = selectTag.options[i];
                            let optText = (opt.text || opt.innerText || '').trim();
                            if (optText.toLowerCase().includes(textMatch.toLowerCase())) {
                                selectTag.selectedIndex = i;
                                let event = new Event('change', { bubbles: true });
                                selectTag.dispatchEvent(event);
                                return true;
                            }
                        }
                        return false;
                    }

                    function getDocs() {
                        let docs = [];
                        function visit(doc) {
                            if (!doc || docs.includes(doc)) return;
                            docs.push(doc);
                            for (let frame of doc.querySelectorAll('iframe')) {
                                try { visit(frame.contentDocument || frame.contentWindow.document); } catch(e) {}
                            }
                        }
                        visit(document);
                        return docs;
                    }

                    function getReportSignature(docs) {
                        let rows = [];
                        for (let doc of docs) {
                            rows = rows.concat(Array.from(doc.querySelectorAll('tr.even, tr.odd, tr.dataRow')));
                        }
                        let sample = rows.slice(0, 2).concat(rows.slice(-2))
                            .map(r => (r.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 240))
                            .join('|');
                        return rows.length + ':' + sample;
                    }
                    
                    let docs = getDocs();
                    let baseline = getReportSignature(docs);
                    let reportToken = 'saas-' + Date.now().toString(36) + '-' +
                        Math.random().toString(36).slice(2);

                    function markReportRun(doc) {
                        if (doc && doc.documentElement) {
                            doc.documentElement.setAttribute('data-saas-report-run', reportToken);
                        }
                    }

                    // O relatório clássico do Salesforce expõe o intervalo
                    // pelo campo colDt_q. No histórico anual precisamos usar o
                    // valor exato "cury" (AC atual). Procurar apenas pelo texto em
                    // todos os <select> podia selecionar "AC atual e anterior" ou
                    // outro filtro sem relação com a data do relatório.
                    if (FULL_HISTORY_FLAG) {
                        for (let doc of docs) {
                            let intervalSelect = doc.querySelector(
                                'select#colDt_q, select[name="colDt_q"]'
                            );
                            if (!intervalSelect) continue;

                            let annualOption = Array.from(intervalSelect.options)
                                .find(opt => String(opt.value || '').toLowerCase() === 'cury');
                            if (!annualOption) continue;

                            intervalSelect.value = annualOption.value;
                            intervalSelect.dispatchEvent(new Event('change', { bubbles: true }));

                            // Defesa adicional para páginas em que o manipulador
                            // inline do Salesforce não é executado pelo evento.
                            let year = new Date().getFullYear();
                            let startInput = doc.querySelector('#colDt_s, input[name="colDt_s"]');
                            let endInput = doc.querySelector('#colDt_e, input[name="colDt_e"]');
                            if (startInput) startInput.value = '01/01/' + year;
                            if (endInput) endInput.value = '31/12/' + year;

                            let reportForm = intervalSelect.form || doc.querySelector(
                                'form#report, form[name="report"]'
                            );
                            let runButton = reportForm && reportForm.querySelector(
                                'input[name="run"], button[name="run"], input[title*="Executar relat"]'
                            );
                            if (runButton) {
                                markReportRun(doc);
                                runButton.click();
                                return "FILTROS_APLICADOS_E_BOTAO_CLICADO|||" + baseline + "|||" + reportToken;
                            }
                            return "FILTROS_APLICADOS_MAS_BOTAO_NAO_ENCONTRADO|||" + baseline + "|||" + reportToken;
                        }
                    }

                    let changedAny = false;
                    let targetDoc = null;
                    let targetSelect = null;
                    for (let doc of docs) {
                        let selects = doc.querySelectorAll('select');
                        for (let i = 0; i < selects.length; i++) {
                        let isFullHistory = FULL_HISTORY_FLAG;
                        if (isFullHistory) {
                            if (selectOptionByText(selects[i], 'Todos os tempos') || 
                                selectOptionByText(selects[i], 'Sempre') || 
                                selectOptionByText(selects[i], 'Todo o período') || 
                                selectOptionByText(selects[i], 'Todo o periodo') || 
                                selectOptionByText(selects[i], 'Este ano') || 
                                selectOptionByText(selects[i], 'Ano atual') || 
                                selectOptionByText(selects[i], 'AC atual e anterior') ||
                                selectOptionByText(selects[i], 'AC atual')) {
                                changedAny = true;
                                targetDoc = doc;
                                targetSelect = selects[i];
                                break;
                            }
                        } else {
                            var today = new Date();
                            if (today.getDate() <= 3) {
                                if (selectOptionByText(selects[i], 'Mês atual e anterior') || 
                                    selectOptionByText(selects[i], 'Mes atual e anterior') ||
                                    selectOptionByText(selects[i], 'Este mês e anterior')) {
                                    changedAny = true;
                                    targetDoc = doc;
                                    targetSelect = selects[i];
                                    break;
                                }
                            } else {
                                if (selectOptionByText(selects[i], 'Este mês') || 
                                    selectOptionByText(selects[i], 'Mês atual') || 
                                    selectOptionByText(selects[i], 'Este ms') || 
                                    selectOptionByText(selects[i], 'Ms atual')) {
                                    changedAny = true;
                                    targetDoc = doc;
                                    targetSelect = selects[i];
                                    break;
                                }
                            }
                        }
                        if (changedAny) break;
                    }
                    if (changedAny) break;
                    }
                    
                    if (changedAny) {
                        let allBtns = (targetDoc || document).querySelectorAll('input[type="submit"], input[type="button"], button, input.btn');
                        for (let i = 0; i < allBtns.length; i++) {
                            let btn = allBtns[i];
                            let text = (btn.value || btn.innerText || btn.title || "").toLowerCase();
                            if (text.includes('executar') || text.includes('aplicar') || text.includes('run') || text.includes('refresh') || text.includes('atualizar')) {
                                markReportRun(targetDoc || document);
                                btn.click();
                                return "FILTROS_APLICADOS_E_BOTAO_CLICADO|||" + baseline + "|||" + reportToken;
                            }
                        }
                        return "FILTROS_APLICADOS_MAS_BOTAO_NAO_ENCONTRADO|||" + baseline + "|||" + reportToken;
                    }
                    if (FULL_HISTORY_FLAG) return "FILTRO_ANUAL_NAO_ENCONTRADO";
                    return "JA_CONFIGURADO_OU_NAO_ENCONTRADO";
                } catch(e) { return "ERRO: " + e; }
            })();
            """
            is_full = "true" if getattr(self, 'is_full_history', False) else "false"
            script_filtros_tsi = script_filtros_tsi.replace('FULL_HISTORY_FLAG', is_full)
            self.nav_auditor_tsi.page().runJavaScript(script_filtros_tsi, self.resultado_filtros_tsi)
        else:
            self.nav_auditor_tsi.page().runJavaScript(
                self._script_estado_relatorio(),
                self.resultado_estado_relatorio_tsi
            )

    def resultado_filtros_tsi(self, res):
        if not res or "PAGINA_CARREGANDO" in str(res):
            return 
        if "FILTRO_ANUAL_NAO_ENCONTRADO" in str(res):
            record_event("tsi_auditor", "ANNUAL_FILTER_NOT_FOUND", "WARN")
            self.status_auditor_tsi.setText("⏳ TSI: Aguardando os filtros do relatório anual...")
            return
            
        if "FILTROS_APLICADOS_E_BOTAO_CLICADO" in str(res):
            record_event("tsi_auditor", "ANNUAL_FILTER_EXECUTED")
            self._iniciar_monitor_relatorio("TSI", res, aguardar_mudanca=True)
        elif "FILTROS_APLICADOS_MAS_BOTAO_NAO_ENCONTRADO" in str(res):
            self._iniciar_monitor_relatorio("TSI", res, aguardar_mudanca=True)
        elif "JA_CONFIGURADO_OU_NAO_ENCONTRADO" in str(res):
            self._iniciar_monitor_relatorio("TSI", res, aguardar_mudanca=False)

    def liberar_extracao_tsi(self):
        self.tsi_filtros_aplicados = True
        self.timer_polling_auditor.start(3000)

    @staticmethod
    def _script_estado_relatorio():
        """JavaScript que observa carregamento, quantidade e assinatura da tabela."""
        return r"""
            (function() {
                function visivel(el) {
                    if (!el) return false;
                    let st = window.getComputedStyle(el);
                    let rc = el.getBoundingClientRect();
                    return st.display !== 'none' && st.visibility !== 'hidden' &&
                           st.opacity !== '0' && rc.width > 0 && rc.height > 0;
                }
                function coletar(doc) {
                    if (!doc || !doc.body) return {
                        rows: [], loading: false, empty: false,
                        statusPresent: false, completed: false
                    };
                    let rows = Array.from(doc.querySelectorAll('tr.even, tr.odd, tr.dataRow'));
                    let loading = Array.from(doc.querySelectorAll(
                        '.loading, .waiting, .spinner, [class*="loading"], [class*="spinner"], [aria-busy="true"]'
                    )).some(visivel);
                    let texto = (doc.body.innerText || '').toLowerCase();
                    loading = loading || texto.includes('aguarde enquanto o relatório') ||
                              texto.includes('relatório está sendo executado') ||
                              texto.includes('report is running') ||
                              texto.includes('carregando relatório');
                    let empty = texto.includes('nenhum registro') ||
                                texto.includes('no records found') ||
                                texto.includes('0 registros') ||
                                texto.includes('grand totals (0');
                    // O SSI expõe um estado oficial no topo do relatório. Ele é
                    // mais confiável que inferir a conclusão apenas pela tabela,
                    // pois a página pode manter o intervalo como "Personalizado".
                    let statusEl = doc.querySelector('.progressIndicator #status, #status');
                    let statusText = statusEl ? (statusEl.innerText || statusEl.textContent || '') : '';
                    let statusNormalizado = statusText.toLowerCase().normalize('NFD')
                        .replace(/[\u0300-\u036f]/g, '').trim();
                    let completed = statusNormalizado.includes('concluido') ||
                                    statusNormalizado.includes('completed');
                    return {
                        rows: rows,
                        loading: loading,
                        empty: empty,
                        statusPresent: Boolean(statusEl),
                        completed: completed
                    };
                }

                let docs = [document];
                for (let frame of document.querySelectorAll('iframe')) {
                    try {
                        let doc = frame.contentDocument || frame.contentWindow.document;
                        if (doc) docs.push(doc);
                    } catch(e) {}
                }

                let allRows = [];
                let loading = false;
                let empty = false;
                let statusPresent = false;
                let completed = false;
                let interval = '';
                let runMarkers = [];
                for (let doc of docs) {
                    let estado = coletar(doc);
                    allRows = allRows.concat(estado.rows);
                    loading = loading || estado.loading;
                    empty = empty || estado.empty;
                    statusPresent = statusPresent || estado.statusPresent;
                    completed = completed || estado.completed;
                    let intervalSelect = doc.querySelector(
                        'select#colDt_q, select[name="colDt_q"]'
                    );
                    if (intervalSelect && intervalSelect.value) {
                        interval = String(intervalSelect.value);
                    }
                    if (doc.documentElement) {
                        let marker = doc.documentElement.getAttribute('data-saas-report-run');
                        if (marker) runMarkers.push(marker);
                    }
                }
                let amostra = allRows.slice(0, 2).concat(allRows.slice(-2))
                    .map(r => (r.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 240))
                    .join('|');
                return {
                    loading: loading,
                    empty: empty,
                    statusPresent: statusPresent,
                    completed: completed,
                    rows: allRows.length,
                    signature: allRows.length + ':' + amostra,
                    interval: interval,
                    runMarkers: runMarkers
                };
            })();
        """

    def _iniciar_monitor_relatorio(self, tipo, resultado_filtro, aguardar_mudanca):
        partes = str(resultado_filtro or '').split("|||", 2)
        baseline = partes[1] if len(partes) > 1 else None
        token = partes[2] if len(partes) > 2 else None
        prefixo = tipo.lower()
        setattr(self, f"{prefixo}_relatorio_baseline", baseline)
        setattr(self, f"{prefixo}_relatorio_ultima_assinatura", None)
        setattr(self, f"{prefixo}_relatorio_estavel", 0)
        setattr(self, f"{prefixo}_relatorio_em_transicao", not aguardar_mudanca)
        setattr(self, f"{prefixo}_relatorio_token", token)
        setattr(self, f"{prefixo}_filtros_aplicados", True)

        status = self.status_auditor_tsi if tipo == "TSI" else self.status_auditor_ssi
        status.setText(f"⏳ {tipo}: Filtro aplicado. Aguardando conclusão do relatório...")
        timer = self.timer_polling_auditor if tipo == "TSI" else self.timer_polling_auditor_ssi
        if not timer.isActive():
            timer.start(3000)

    def _avaliar_estado_relatorio(self, tipo, estado):
        if not isinstance(estado, dict):
            return False

        prefixo = tipo.lower()
        assinatura = str(estado.get("signature", ""))
        linhas = int(estado.get("rows", 0) or 0)
        carregando = bool(estado.get("loading", False))
        vazio = bool(estado.get("empty", False))
        status_presente = bool(estado.get("statusPresent", False))
        concluido = bool(estado.get("completed", False))
        intervalo = str(estado.get("interval", ""))
        marcadores = [str(valor) for valor in (estado.get("runMarkers") or [])]
        baseline = getattr(self, f"{prefixo}_relatorio_baseline", None)
        token = getattr(self, f"{prefixo}_relatorio_token", None)
        em_transicao = getattr(self, f"{prefixo}_relatorio_em_transicao", False)
        ultima = getattr(self, f"{prefixo}_relatorio_ultima_assinatura", None)

        navegacao_concluida = bool(token and token not in marcadores)
        if carregando or (baseline is not None and assinatura != baseline) or navegacao_concluida:
            em_transicao = True
            setattr(self, f"{prefixo}_relatorio_em_transicao", True)

        intervalo_anual_incorreto = (
            tipo == "TSI"
            and
            getattr(self, 'is_full_history', False)
            and intervalo
            and intervalo != "cury"
        )
        ssi_ainda_processando = tipo == "SSI" and status_presente and not concluido
        if (
            carregando
            or intervalo_anual_incorreto
            or ssi_ainda_processando
            or (linhas == 0 and not vazio)
            or not em_transicao
        ):
            setattr(self, f"{prefixo}_relatorio_estavel", 0)
            return False

        estavel = getattr(self, f"{prefixo}_relatorio_estavel", 0)
        estavel = estavel + 1 if assinatura == ultima else 1
        setattr(self, f"{prefixo}_relatorio_ultima_assinatura", assinatura)
        setattr(self, f"{prefixo}_relatorio_estavel", estavel)
        return estavel >= 2

    @staticmethod
    def _script_html_completo():
        return """
            (function() {
                var htmlFinal = document.documentElement.outerHTML;
                var frames = document.querySelectorAll('iframe');
                for (var i = 0; i < frames.length; i++) {
                    try {
                        var doc = frames[i].contentDocument || frames[i].contentWindow.document;
                        if (doc) htmlFinal += doc.documentElement.outerHTML;
                    } catch(e) {}
                }
                return htmlFinal;
            })();
        """

    def resultado_estado_relatorio_tsi(self, estado):
        if self._avaliar_estado_relatorio("TSI", estado):
            self.timer_polling_auditor.stop()
            self.status_auditor_tsi.setText("📥 TSI: Relatório concluído. Importando dados...")
            self.nav_auditor_tsi.page().runJavaScript(
                self._script_html_completo(),
                self.processar_html_auditor
            )
        else:
            minutos = self.tentativas_auditor_tsi * 3 // 60
            segundos = self.tentativas_auditor_tsi * 3 % 60
            self.status_auditor_tsi.setText(
                f"⏳ TSI: Relatório em processamento ({minutos:02d}:{segundos:02d})..."
            )

    def processar_html_auditor(self, html_source):
        if "WAITING_FOR_REFRESH" in html_source:
            return
        sucesso_extracao = False
        import os
        from src.core.paths import get_base_dir
        log_path = os.path.join(get_base_dir(), "app_data", "auditor_debug.txt")
        
        try:
            soup = BeautifulSoup(html_source, "html.parser")
            novos_registros_totais = []
            
            # Procura cabeçalho da tabela do TSI
            header_row = soup.find("tr", class_="headerRow")
            headers = []
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
            
            # Se não achou headerRow clássico, tenta achar qualquer tr com 'Ordens de Serviço' ou 'Data de Resposta'
            if not headers:
                for tr in soup.find_all("tr"):
                    txt = tr.get_text(separator=" ", strip=True).lower()
                    if "ordens de servi" in txt or "data de resposta" in txt:
                        headers = [th.get_text(strip=True) for th in tr.find_all(["th", "td"])]
                        if len(headers) >= 3:
                            break
            
            if headers:
                current_loja = "Desconhecida"
                linhas_all = soup.find_all("tr")
                
                for linha in linhas_all:
                    texto_linha = linha.get_text(separator=" ", strip=True)
                    
                    # Detecta agrupamento de loja no TSI: "Código concessionária: 1717379"
                    if "concessionária:" in texto_linha.lower():
                        match = re.search(r'concessionária:\s*(\d+)', texto_linha, re.IGNORECASE)
                        if match:
                            current_loja = match.group(1)
                            
                    classes = linha.get("class", [])
                    celulas = [td.get_text(strip=True) for td in linha.find_all(["td", "th"])]
                    
                    if len(celulas) == len(headers):
                        registro = dict(zip(headers, celulas))
                        
                        clean_row = {}
                        for k, v in registro.items():
                            k_str = str(k).strip()
                            v_str = str(v).strip()
                            if 'ordens de servi' in k_str.lower():
                                clean_row['Ordens de Serviço: OS'] = v_str
                            elif 'código concessionária' in k_str.lower():
                                clean_row['Código concessionária'] = v_str
                            else:
                                clean_row[k_str] = v_str
                        
                        if current_loja != "Desconhecida" and 'Código concessionária' not in clean_row:
                            clean_row['Código concessionária'] = current_loja
                            
                        # Validar se a linha é realmente um dado (contém OS no formato \d+-\d+ ou dígitos)
                        os_val = str(clean_row.get('Ordens de Serviço: OS', '')).strip()
                        if os_val and re.search(r'\d+-\d+', os_val):
                            # O relatório MyHonda é a fonte principal. A fila
                            # auxilia somente quando o relatório não trouxe o
                            # campo; nunca sobrescreve um cliente já informado.
                            lead = self.db_manager.find_lead(os_val, os_val.split('-')[-1], tipo="TSI")
                            if lead:
                                nome = str(lead.get("cliente", "")).strip()
                                telefone = str(lead.get("telefone", "")).strip()
                                cliente_atual = str(clean_row.get("Cliente", "")).strip()
                                telefone_atual = str(clean_row.get("Telefone", "")).strip()
                                invalidos = ("", "N/D", "S/N", "N/A", "NONE", "-", "NAN")
                                if cliente_atual.upper() in invalidos and nome.upper() not in invalidos:
                                    clean_row["Cliente"] = nome
                                if telefone_atual.upper() in invalidos and telefone.upper() not in invalidos:
                                    clean_row["Telefone"] = telefone
                            novos_registros_totais.append(clean_row)
            
            if novos_registros_totais:
                self.db_manager.save_records(novos_registros_totais)
                record_event("tsi_auditor", "REPORT_IMPORTED", records=len(novos_registros_totais))
                self.historico_tsi = self.db_manager.load_all_records()
                
                self.os_respondidas_tsi.clear()
                for cli in self.historico_tsi:
                    os_real = cli.get('Ordens de Serviço: OS', '')
                    if os_real:
                        os_real = os_real.split('-')[1] if '-' in os_real else os_real
                        self.os_respondidas_tsi.add(os_real)
                
                sucesso_extracao = True
                self.timer_polling_auditor.stop() # Tabela encontrada, para o polling
                from datetime import datetime
                cur_mes_ano = f"/{datetime.now().month:02d}/{datetime.now().year}"
                qtd_mes_atual = sum(1 for cli in self.historico_tsi if cur_mes_ano in str(cli.get('Data de Resposta', '')))
                if getattr(self, 'is_full_history', False):
                    meses_importados = {
                        str(cli.get('Data de Resposta', ''))[3:10]
                        for cli in novos_registros_totais
                        if re.search(r'\d{2}/\d{2}/\d{4}', str(cli.get('Data de Resposta', '')))
                    }
                    self.status_auditor_tsi.setText(
                        f"✅ TSI: histórico anual importado "
                        f"({len(novos_registros_totais)} respostas em {len(meses_importados)} meses)"
                    )
                else:
                    self.status_auditor_tsi.setText(f"✅ TSI: {qtd_mes_atual} Respostas")
                self.status_auditor_tsi.setStyleSheet("background-color: white; color: #16A34A; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0; margin-left: 10px;")
            else:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"TSI Parser: headers={headers}, linhas={len(soup.find_all('tr'))}\n")
                    
        except Exception as e:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"Erro no parser TSI: {str(e)}\n")
        
        if sucesso_extracao:
            self.atualizar_lista_ui()
        elif getattr(self, 'tsi_filtros_aplicados', False) and not self.timer_polling_auditor.isActive():
            # O DOM pode ter mudado entre a confirmação de estabilidade e a
            # captura do HTML. Retoma a observação sem reiniciar o relatório.
            self.tsi_relatorio_estavel = 0
            self.timer_polling_auditor.start(3000)

    def extrair_dados_auditor_ssi(self):
        if not hasattr(self, 'tentativas_auditor_ssi'): self.tentativas_auditor_ssi = 0
        self.tentativas_auditor_ssi += 1
        
        if not getattr(self, 'is_full_history', False) and self.tentativas_auditor_ssi > 200:
            self.timer_polling_auditor_ssi.stop()
            self.status_auditor_ssi.setText("⚠️ SSI: Relatório com Instabilidade (Timeout)")
            self.status_auditor_ssi.setStyleSheet("background-color: white; color: #EF4444; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0; margin-left: 10px;")
            return

        # Mesmo princípio do TSI: no fluxo normal o SSI é apenas aberto e
        # extraído. A observação de mudança é exclusiva do Histórico Anual.
        if not getattr(self, 'is_full_history', False):
            self.nav_auditor_ssi.page().runJavaScript(
                self._script_html_completo(),
                self.processar_html_auditor_ssi
            )
            return

        if not self.ssi_filtros_aplicados:
            script_filtros = """
            (function() {
                try {
                    function selectOptionByText(selectTag, textMatch) {
                        for (let i = 0; i < selectTag.options.length; i++) {
                            let opt = selectTag.options[i];
                            let optText = (opt.text || opt.innerText || '').trim();
                            if (optText.toLowerCase().includes(textMatch.toLowerCase())) {
                                selectTag.selectedIndex = i;
                                let event = new Event('change', { bubbles: true });
                                selectTag.dispatchEvent(event);
                                return true;
                            }
                        }
                        return false;
                    }

                    function getDocs() {
                        let docs = [];
                        function visit(doc) {
                            if (!doc || docs.includes(doc)) return;
                            docs.push(doc);
                            for (let frame of doc.querySelectorAll('iframe')) {
                                try { visit(frame.contentDocument || frame.contentWindow.document); } catch(e) {}
                            }
                        }
                        visit(document);
                        return docs;
                    }

                    function getReportSignature(docs) {
                        let rows = [];
                        for (let doc of docs) {
                            rows = rows.concat(Array.from(doc.querySelectorAll('tr.even, tr.odd, tr.dataRow')));
                        }
                        let sample = rows.slice(0, 2).concat(rows.slice(-2))
                            .map(r => (r.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 240))
                            .join('|');
                        return rows.length + ':' + sample;
                    }
                    
                    let docs = getDocs();
                    let targetDoc = docs.reduce(function(best, doc) {
                        return doc.querySelectorAll('select').length > best.querySelectorAll('select').length ? doc : best;
                    }, document);
                    let selects = targetDoc.querySelectorAll('select');
                    let baseline = getReportSignature(docs);
                    let reportToken = 'saas-' + Date.now().toString(36) + '-' +
                        Math.random().toString(36).slice(2);
                    let changedAny = false;

                    function markReportRun(doc) {
                        if (doc && doc.documentElement) {
                            doc.documentElement.setAttribute('data-saas-report-run', reportToken);
                        }
                    }
                    
                    if (selects.length >= 3) {
                        if (selectOptionByText(selects[0], 'Concessionária de vendas: Número da conta') || 
                            selectOptionByText(selects[0], 'Concessionária de vendas: Nome da conta') ||
                            selectOptionByText(selects[0], 'Concessionaria de vendas: Numero da conta')) {
                            changedAny = true;
                        }
                        
                        if (selectOptionByText(selects[1], 'Todos os relações de posses') || 
                            selectOptionByText(selects[1], 'Todas as relações de posses') ||
                            selectOptionByText(selects[1], 'Todas as relacoes de posses') ||
                            selectOptionByText(selects[1], 'Todos os relacoes de posses')) {
                            changedAny = true;
                        }
                        
                        if (selectOptionByText(selects[2], 'Data de resposta SSI 2W')) {
                            changedAny = true;
                        }
                    }
                    
                    for (let i = 0; i < selects.length; i++) {
                        let isFullHistory = FULL_HISTORY_FLAG;
                        if (isFullHistory) {
                            if (selectOptionByText(selects[i], 'Todos os tempos') || 
                                selectOptionByText(selects[i], 'Sempre') || 
                                selectOptionByText(selects[i], 'Todo o período') || 
                                selectOptionByText(selects[i], 'Todo o periodo') || 
                                selectOptionByText(selects[i], 'Este ano') || 
                                selectOptionByText(selects[i], 'Ano atual') || 
                                selectOptionByText(selects[i], 'AC atual e anterior') ||
                                selectOptionByText(selects[i], 'AC atual')) {
                                changedAny = true;
                                break;
                            }
                        } else {
                            var today = new Date();
                            if (today.getDate() <= 3) {
                                if (selectOptionByText(selects[i], 'Mês atual e anterior') || 
                                    selectOptionByText(selects[i], 'Mes atual e anterior') ||
                                    selectOptionByText(selects[i], 'Este mês e anterior')) {
                                    changedAny = true;
                                    break;
                                }
                            } else {
                                if (selectOptionByText(selects[i], 'Este mês') || 
                                    selectOptionByText(selects[i], 'Mês atual') || 
                                    selectOptionByText(selects[i], 'Este ms') || 
                                    selectOptionByText(selects[i], 'Ms atual')) {
                                    changedAny = true;
                                    break;
                                }
                            }
                        }
                    }
                    
                    if (changedAny) {
                        let allBtns = targetDoc.querySelectorAll('input[type="submit"], input[type="button"], button, input.btn');
                        for (let i = 0; i < allBtns.length; i++) {
                            let btn = allBtns[i];
                            let text = (btn.value || btn.innerText || btn.title || "").toLowerCase();
                            if (text.includes('executar') || text.includes('aplicar') || text.includes('run') || text.includes('refresh') || text.includes('atualizar')) {
                                markReportRun(targetDoc);
                                btn.click();
                                return "FILTROS_APLICADOS_E_BOTAO_CLICADO|||" + baseline + "|||" + reportToken;
                            }
                        }
                        return "FILTROS_APLICADOS_MAS_BOTAO_NAO_ENCONTRADO|||" + baseline + "|||" + reportToken;
                    }
                    if (FULL_HISTORY_FLAG) return "FILTRO_ANUAL_NAO_ENCONTRADO";
                    return "JA_CONFIGURADO_OU_NAO_ENCONTRADO";
                } catch(e) { return "ERRO: " + e; }
            })();
            """
            
            is_full = "true" if getattr(self, 'is_full_history', False) else "false"
            script_filtros = script_filtros.replace('FULL_HISTORY_FLAG', is_full)
            
            self.nav_auditor_ssi.page().runJavaScript(script_filtros, self.resultado_filtros_ssi)
        else:
            self.nav_auditor_ssi.page().runJavaScript(
                self._script_estado_relatorio(),
                self.resultado_estado_relatorio_ssi
            )

    def resultado_filtros_ssi(self, res):
        if not res or "PAGINA_CARREGANDO" in str(res):
            return # Ignora e espera o próximo tick do polling
        if "FILTRO_ANUAL_NAO_ENCONTRADO" in str(res):
            record_event("ssi_auditor", "ANNUAL_FILTER_NOT_FOUND", "WARN")
            self.status_auditor_ssi.setText("⏳ SSI: Aguardando os filtros do relatório anual...")
            return
            
        if "FILTROS_APLICADOS_E_BOTAO_CLICADO" in str(res):
            record_event("ssi_auditor", "ANNUAL_FILTER_EXECUTED")
            self._iniciar_monitor_relatorio("SSI", res, aguardar_mudanca=True)
        elif "FILTROS_APLICADOS_MAS_BOTAO_NAO_ENCONTRADO" in str(res):
            self._iniciar_monitor_relatorio("SSI", res, aguardar_mudanca=True)
        elif "JA_CONFIGURADO_OU_NAO_ENCONTRADO" in str(res):
            self._iniciar_monitor_relatorio("SSI", res, aguardar_mudanca=False)

    def liberar_extracao_ssi(self):
        self.ssi_filtros_aplicados = True
        self.timer_polling_auditor_ssi.start(3000)

    def resultado_estado_relatorio_ssi(self, estado):
        if self._avaliar_estado_relatorio("SSI", estado):
            self.timer_polling_auditor_ssi.stop()
            self.status_auditor_ssi.setText("📥 SSI: Relatório concluído. Importando dados...")
            self.nav_auditor_ssi.page().runJavaScript(
                self._script_html_completo(),
                self.processar_html_auditor_ssi
            )
        else:
            minutos = self.tentativas_auditor_ssi * 3 // 60
            segundos = self.tentativas_auditor_ssi * 3 % 60
            self.status_auditor_ssi.setText(
                f"⏳ SSI: Relatório em processamento ({minutos:02d}:{segundos:02d})..."
            )

    def processar_html_auditor_ssi(self, html_source):
        if "WAITING_FOR_REFRESH" in html_source:
            return
        try:
            soup = BeautifulSoup(html_source, "html.parser")
            novos_registros = []
            linhas_all = soup.find_all("tr")
            header_row = soup.find("tr", class_="headerRow")
            
            if not header_row:
                if not self.timer_polling_auditor_ssi.isActive():
                    self.ssi_relatorio_estavel = 0
                    self.timer_polling_auditor_ssi.start(3000)
                return # Tabela não carregou ainda
                
            headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
            current_loja = "Desconhecida"
            
            for linha in linhas_all:
                texto_linha = linha.get_text(separator=" ", strip=True)
                
                if "Concessionária de vendas: Número da conta:" in texto_linha:
                    match = re.search(r'Número da conta:\s*(\d+)', texto_linha)
                    if match:
                        current_loja = match.group(1)
                
                classes = linha.get("class", [])
                if "even" in classes or "odd" in classes:
                    celulas = []
                    for td in linha.find_all(["td", "th"]):
                        valor = td.get_text(strip=True)
                        if not valor:
                            imagem = td.find("img")
                            if imagem:
                                descricao = str(imagem.get("title") or imagem.get("alt") or "").strip()
                                valor = "Sim" if descricao.lower() in ("selecionado", "checked", "marcado") else descricao
                        celulas.append(valor)
                    if len(celulas) == len(headers):
                        registro = dict(zip(headers, celulas))
                        if current_loja != "Desconhecida" or "Concessionária de vendas: Número da conta" not in registro:
                            registro["Concessionária de vendas: Número da conta"] = current_loja
                            
                        # Limpeza leve para compatibilidade
                        clean_reg = {}
                        for k, v in registro.items():
                            k_str = str(k).strip()
                            v_str = str(v).strip()
                            clean_reg[k_str] = v_str
                            
                        novos_registros.append(clean_reg)
            
            if header_row:
                self.timer_polling_auditor_ssi.stop()
            if novos_registros:
                self.db_manager.save_ssi_records(novos_registros)
                record_event("ssi_auditor", "REPORT_IMPORTED", records=len(novos_registros))
                historico_ssi = self.db_manager.load_ssi_records()
                from datetime import datetime
                cur_mes_ano = f"/{datetime.now().month:02d}/{datetime.now().year}"
                qtd_mes_atual = sum(1 for cli in historico_ssi if cur_mes_ano in str(cli.get('Data de resposta SSI 2W', '')) or cur_mes_ano in str(cli.get('Data de Resposta', '')))
                if getattr(self, 'is_full_history', False):
                    meses_importados = set()
                    for cli in novos_registros:
                        data = str(
                            cli.get('Data de resposta SSI 2W', '')
                            or cli.get('Data de Resposta', '')
                        )
                        match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', data)
                        if match_data:
                            meses_importados.add(f"{match_data.group(2)}/{match_data.group(3)}")
                    self.status_auditor_ssi.setText(
                        f"✅ SSI: histórico anual importado "
                        f"({len(novos_registros)} respostas em {len(meses_importados)} meses)"
                    )
                else:
                    self.status_auditor_ssi.setText(f"✅ SSI: {qtd_mes_atual} Respostas")
                self.status_auditor_ssi.setStyleSheet("background-color: white; color: #16A34A; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0; margin-left: 10px;")
        except Exception as e:
            if not self.timer_polling_auditor_ssi.isActive():
                self.ssi_relatorio_estavel = 0
                self.timer_polling_auditor_ssi.start(3000)

    # --- UI DA LISTA E DISPARO ---
    def atualizar_lista_ui(self):
        # Salva o estado atual das checkboxes na memória antes de limpar a tela
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            idx = item.data(Qt.ItemDataRole.UserRole)
            if idx is not None and idx < len(self.fila_extraida):
                self.fila_extraida[idx]['selecionado'] = (item.checkState() == Qt.CheckState.Checked)

        sinais_bloqueados = self.list_widget.blockSignals(True)
        self.list_widget.clear()
        texto_busca = _normalizar_texto_busca(self.search_box.text())
        tipo_filtro = "SSI" if self.combo_tipo.currentIndex() == 0 else "TSI"
        
        # Primeiro, filtramos os itens que devem aparecer na tela mantendo o indice original
        itens_para_exibir = []
        for i, item in enumerate(self.fila_extraida):
            if item.get("tipo") != tipo_filtro:
                continue
                
            cliente = str(item.get("cliente") or "Desconhecido")
            if texto_busca and texto_busca not in _normalizar_texto_busca(cliente):
                continue
                
            itens_para_exibir.append((i, item))
            
        # Agora ordenamos os itens:
        # 1. Os "Enviados" vão para o final
        # 2. Os "Selecionados" sobem para o topo
        itens_para_exibir.sort(key=lambda x: (
            x[1].get("enviado", False),
            not x[1].get("selecionado", False)
        ))
        
        visiveis = 0
        for i, item in itens_para_exibir:
            cliente = str(item.get("cliente") or "Desconhecido")
            info_extra = str(item.get("os") or "")
            status_prefix = ""
            flags = (Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
                     | Qt.ItemFlag.ItemIsSelectable)
            is_checked = Qt.CheckState.Unchecked
            
            # 1. Checa se o usuário já disparou para esse cara nesta sessão
            if item.get("enviado", False):
                status_prefix = "✅ "
                flags = Qt.ItemFlag.NoItemFlags # Trava checkbox
            # 2. Checa se o Auditor achou resposta dele no Dashboard (TSI)
            elif tipo_filtro == "TSI" and info_extra in self.os_respondidas_tsi:
                status_prefix = "🔒 Já Respondida - "
                flags = Qt.ItemFlag.NoItemFlags
                
            display_text = f"{status_prefix}{cliente} - {info_extra}"

            
            list_item = QListWidgetItem(display_text)
            list_item.setData(Qt.ItemDataRole.UserRole, i)
            list_item.setFlags(flags)
            if flags == Qt.ItemFlag.NoItemFlags:
                # Cor mais clarinha para desabilitados
                list_item.setForeground(Qt.GlobalColor.gray)
                if item.get("enviado", False) or (tipo_filtro == "TSI" and info_extra in self.os_respondidas_tsi):
                    list_item.setCheckState(Qt.CheckState.Checked)
                else:
                    list_item.setCheckState(Qt.CheckState.Unchecked)
            else:
                is_checked = Qt.CheckState.Checked if item.get("selecionado", False) else Qt.CheckState.Unchecked
                list_item.setCheckState(is_checked)
                
            self.list_widget.addItem(list_item)
            visiveis += 1

        self.list_widget.blockSignals(sinais_bloqueados)
        self.lbl_fila.setText(f"  Fila de Disparo ({visiveis} Registros)")
        self._atualizar_resumo_selecao()
        
    def filtrar_lista(self, _texto=None):
        """Atualiza imediatamente a fila ao receber o texto do QLineEdit."""
        self.atualizar_lista_ui()
        
    def ao_alterar_selecao_unica(self, item_alterado):
        """Marca clientes; a licença é revalidada antes de iniciar o lote."""
        idx_alterado = item_alterado.data(Qt.ItemDataRole.UserRole)
        if idx_alterado is None or idx_alterado >= len(self.fila_extraida):
            return

        marcado = item_alterado.checkState() == Qt.CheckState.Checked
        if not marcado:
            self.fila_extraida[idx_alterado]['selecionado'] = False
            self._atualizar_resumo_selecao()
            return

        self.fila_extraida[idx_alterado]['selecionado'] = True
        self._atualizar_resumo_selecao()

    def _atualizar_resumo_selecao(self):
        quantidade = sum(
            1 for item in self.fila_extraida
            if item.get('selecionado', False) and not item.get('enviado', False)
        )
        if hasattr(self, 'selection_hint'):
            sufixo = f"   •   {quantidade} marcado(s)" if quantidade else ""
            self.selection_hint.setText(
                f"● Linha azul: conversa   ☑ Marcados: envio em lote{sufixo}"
            )
        if hasattr(self, 'btn_dispatch') and self.btn_dispatch.isEnabled():
            self.btn_dispatch.setText(
                f"▶ Enviar {quantidade} pesquisa(s)" if quantidade
                else "▶ Enviar Pesquisa Selecionada"
            )

    def iniciar_disparo(self):
        # Inicializa lista de rastreio de clientes com problemas de envio
        self.clientes_nao_enviados = []
        
        # Salva o estado atual das checkboxes na tela
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            idx = item.data(Qt.ItemDataRole.UserRole)
            self.fila_extraida[idx]['selecionado'] = (item.checkState() == Qt.CheckState.Checked)

        self.fila_disparo = []
        for i, item in enumerate(self.fila_extraida):
            if item.get("selecionado", False) and not item.get("enviado", False):
                self.fila_disparo.append(i) # Armazena o index original
                
        if not self.fila_disparo:
            QMessageBox.warning(self, "Aviso", "Selecione pelo menos um cliente válido para enviar.")
            return

        from src.core.license_manager import LicenseManager
        dados = LicenseManager().validar_licenca()
        limite_lote = max(1, int(dados.get('limite_lote') or 1))
        if dados.get('status') not in {'ativa', 'trial'}:
            self.fila_disparo = []
            QMessageBox.warning(self, "Licença", "Não foi possível autorizar envios para esta máquina.")
            return
        if len(self.fila_disparo) > limite_lote:
            self.fila_disparo = []
            QMessageBox.warning(
                self,
                "Limite por lote",
                f"Esta máquina permite até {limite_lote} cliente(s) por lote. Reduza a seleção."
            )
            return

        if len(self.fila_disparo) > 1:
            nomes = [
                str(self.fila_extraida[idx].get('cliente') or 'Cliente')
                for idx in self.fila_disparo[:5]
            ]
            restantes = len(self.fila_disparo) - len(nomes)
            resumo = "\n".join(f"• {nome}" for nome in nomes)
            if restantes:
                resumo += f"\n• e mais {restantes} cliente(s)"
            resposta = QMessageBox.question(
                self,
                "Confirmar envio em lote",
                f"Você selecionou {len(self.fila_disparo)} clientes:\n\n{resumo}\n\n"
                "As mensagens serão enviadas uma por vez. Deseja continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if resposta != QMessageBox.StandardButton.Yes:
                self.fila_disparo = []
                self._atualizar_resumo_selecao()
                return
            
        self.btn_dispatch.setEnabled(False)
        self.btn_dispatch.setText("⏳ Verificando WhatsApp...")
        
        # Pede para a tela do WhatsApp verificar se o usuário escaneou o QR Code
        self.sig_check_whatsapp_login.emit()
        
    def on_login_status_result(self, is_logged_in):
        if not is_logged_in:
            self.btn_dispatch.setEnabled(True)
            self._atualizar_resumo_selecao()
            QMessageBox.critical(
                self, 
                "WhatsApp Não Conectado", 
                "Você precisa conectar o WhatsApp antes de disparar as mensagens!\n\n"
                "1. Vá até a aba 'Motor WhatsApp' no menu lateral.\n"
                "2. Escaneie o QR Code com o seu celular.\n"
                "3. Aguarde suas conversas carregarem e volte aqui para disparar."
            )
            return
            
        self.btn_dispatch.setText("⏳ Enviando pesquisa...")
        self.sig_request_tab_change.emit(1) # Força a interface a pular para o Motor WhatsApp
        self.processar_proximo_disparo()

    def processar_proximo_disparo(self):
        if not self.fila_disparo:
            self.btn_dispatch.setEnabled(True)
            self.status_honda.setText("🟢 Disparo Finalizado!")
            self.atualizar_lista_ui()
            
            # Exibe resumo de clientes que não puderam ser contatados
            if hasattr(self, 'clientes_nao_enviados') and self.clientes_nao_enviados:
                from src.ui.screens.resumo_disparo_dialog import ResumoDisparoDialog
                ResumoDisparoDialog.exibir_se_houver(self, self.clientes_nao_enviados)
                self.clientes_nao_enviados = []
            return
            
        from src.core.license_manager import LicenseManager
        lm = LicenseManager()
        pode_enviar, motivo, reserva_id = lm.reservar_envio()
        
        if not pode_enviar:
            self.btn_dispatch.setEnabled(True)
            self._atualizar_resumo_selecao()
            self.status_honda.setText("🔴 Disparo Interrompido (Limite atingido)")
            QMessageBox.warning(self, "Limite Atingido", motivo)
            self.atualizar_lista_ui()
            return

        self.reserva_envio_atual = reserva_id
            
        self.indice_atual_disparo = self.fila_disparo.pop(0)
        self.item_atual = self.fila_extraida[self.indice_atual_disparo]
        tipo = self.item_atual.get('tipo')
        cliente = self.item_atual.get('cliente', '')
        
        self.status_honda.setText(f"🔄 Processando {cliente} ({tipo})...")
        
        from src.core.medallia_builder import MedalliaBuilder
        
        texto_base = self.editor_mensagem.toPlainText()
        texto_base = texto_base.replace("[NOME]", cliente.title())
        
        if tipo == 'TSI':
            fone = re.sub(r'\D', '', self.item_atual.get('telefone', ''))
            while fone.startswith('0'):
                fone = fone[1:]
                
            if not fone or len(fone) < 10:
                if not hasattr(self, 'clientes_nao_enviados'):
                    self.clientes_nao_enviados = []
                self.clientes_nao_enviados.append({
                    'cliente': cliente,
                    'tipo': 'TSI',
                    'telefone': self.item_atual.get('telefone', 'S/N') or 'S/N',
                    'motivo': 'Sem celular cadastrado no myHonda'
                })
                lm.liberar_reserva_envio(self.reserva_envio_atual)
                self.reserva_envio_atual = ""
                QTimer.singleShot(400, self.processar_proximo_disparo)
                return
                
            if not fone.startswith('55'):
                fone = '55' + fone
                
            link_bruto = MedalliaBuilder.build_tsi_link(self.item_atual.get('id', ''))
            link = MedalliaBuilder.encrypt_link(link_bruto)
            texto_final = texto_base.replace("[LINK]", link)
            self.sig_dispatch_whatsapp.emit(fone, texto_final)
            
        elif tipo == 'SSI':
            url_ficha = self.item_atual.get('url_ficha')
            if url_ficha:
                self._begin_ssi_lookup()
                url_completa = "https://myhonda.my.site.com" + url_ficha if url_ficha.startswith("/") else url_ficha
                record_event(
                    "ssi_dispatch", "CONTACT_PAGE_OPEN_STARTED",
                    survey_ref=anonymous_id(self.item_atual.get('id', '')),
                    target_domain=QUrl(url_completa).host(),
                )
                self.nav_ssi_oculto.setUrl(QUrl(url_completa))
                self.tentativas = 0
                self.timer_ssi_ficha.start(2000)
            else:
                if not hasattr(self, 'clientes_nao_enviados'):
                    self.clientes_nao_enviados = []
                self.clientes_nao_enviados.append({
                    'cliente': cliente,
                    'tipo': 'SSI',
                    'telefone': 'S/N',
                    'motivo': 'Ficha sem link de contato'
                })
                self.on_whatsapp_message_sent(False)

    def checar_ssi_ficha(self):
        generation = getattr(self, '_active_ssi_generation', None)
        if generation is None:
            self.timer_ssi_ficha.stop()
            return
        self.tentativas += 1
        if self.tentativas in (1, 5, 10) and TelemetryClient.instance().is_detailed_enabled():
            record_event(
                "ssi_dispatch", "CONTACT_PAGE_PROBE",
                survey_ref=anonymous_id(getattr(self, 'item_atual', {}).get('id', '')),
                attempts=self.tentativas,
                final_domain=self.nav_ssi_oculto.url().host(),
                login_redirect="login" in self.nav_ssi_oculto.url().toString().lower(),
            )
        if self.tentativas > 10:
            self._invalidate_ssi_lookup()
            if getattr(self, 'modo_conversa_individual', False):
                self.modo_conversa_individual = False
                self.status_honda.setText("⚠️ Tempo esgotado na ficha.")
                QMessageBox.warning(self, "Timeout", "Tempo esgotado ao abrir a ficha do cliente no myHonda.")
                return
                
            if not hasattr(self, 'clientes_nao_enviados'):
                self.clientes_nao_enviados = []
            self.clientes_nao_enviados.append({
                'cliente': self.item_atual.get('cliente', 'Desconhecido'),
                'tipo': 'SSI',
                'telefone': 'S/N',
                'motivo': 'Tempo esgotado ao abrir ficha no myHonda'
            })
            record_event(
                "ssi_dispatch", "CONTACT_PAGE_TIMEOUT", "ERROR",
                survey_ref=anonymous_id(self.item_atual.get('id', '')),
                attempts=self.tentativas,
                elapsed_ms=self.tentativas * 2000,
                final_domain=self.nav_ssi_oculto.url().host(),
                login_redirect="login" in self.nav_ssi_oculto.url().toString().lower(),
            )
            self.on_whatsapp_message_sent(False)
            return
            
        js_check = """
        (function(){ 
            return document.querySelectorAll('td.labelCol, th.labelCol, td[class*="labelCol"]').length > 0 || 
                   (document.body && (document.body.innerText.includes('Dados para Contato') || document.body.innerText.includes('Celular'))); 
        })();
        """
        self.nav_ssi_oculto.page().runJavaScript(
            js_check,
            lambda pronto, token=generation: self.callback_ssi_ficha_pronto(pronto, token),
        )

    def callback_ssi_ficha_pronto(self, pronto, generation=None):
        active_generation = getattr(self, '_active_ssi_generation', None)
        if generation is None:
            generation = active_generation
        if generation is None or generation != active_generation:
            return
        if pronto:
            if getattr(self, '_ssi_extracting_generation', None) == generation:
                return
            self._ssi_extracting_generation = generation
            record_event(
                "ssi_dispatch", "CONTACT_PAGE_READY",
                survey_ref=anonymous_id(getattr(self, 'item_atual', {}).get('id', '')),
                attempts=self.tentativas,
                elapsed_ms=self.tentativas * 2000,
            )
            self.timer_ssi_ficha.stop()
            js_extract = """
            (function() {
                let extracted = {celular: '', modelo: ''};
                
                let allCells = document.querySelectorAll('td, th');
                for (let i = 0; i < allCells.length; i++) {
                    let cell = allCells[i];
                    let text = (cell.innerText || '').trim().toLowerCase();
                    
                    // Modelo do Veículo (ex: POP110I ES, BROS 160, etc.)
                    if (text === 'modelo' || text === 'modelo:' || text.startsWith('modelo ')) {
                        let next = cell.nextElementSibling;
                        if (next) {
                            let val = (next.innerText || '').trim();
                            if (val) extracted.modelo = val;
                        }
                    } else if (!extracted.modelo && (text === 'produto / veículo' || text === 'produto' || text.startsWith('produto:'))) {
                        let next = cell.nextElementSibling;
                        if (next) {
                            let val = (next.innerText || '').trim();
                            if (val) extracted.modelo = val;
                        }
                    }
                    
                    // Celular / Telefone
                    if (text.includes('celular') || text.includes('telefone') || text.includes('fone') || text.includes('contato')) {
                        let next = cell.nextElementSibling;
                        if (next) {
                            let val = (next.innerText || '').trim();
                            let nums = val.replace(/\\D/g, '');
                            if (nums.length >= 10) {
                                if (!extracted.celular || nums.length === 11 || nums.length === 13) {
                                    extracted.celular = val;
                                }
                            }
                        }
                    }
                }
                
                // Fallback: varre todo o texto da página se não achou celular
                if (!extracted.celular) {
                    let pageText = document.body ? document.body.innerText : '';
                    let fones = pageText.match(/(?:\\+?55\\s*)?\\(?\\d{2}\\)?\\s*(?:9\\s*)?\\d{4}[-\\s]?\\d{4}/g);
                    if (fones && fones.length > 0) {
                        extracted.celular = fones[0].trim();
                    }
                }
                
                return extracted;
            })();
            """
            self.nav_ssi_oculto.page().runJavaScript(
                js_extract,
                lambda result, token=generation:
                    self.on_ssi_ficha_extraida(result, token),
            )

    def on_ssi_ficha_extraida(self, result, ssi_generation=None):
        if ssi_generation is not None and (
            ssi_generation != getattr(self, '_active_ssi_generation', None)
            or ssi_generation != getattr(self, '_ssi_extracting_generation', None)
        ):
            return
        if ssi_generation is not None:
            self._active_ssi_generation = None
            self._ssi_extracting_generation = None
        if getattr(self, 'modo_conversa_individual', False):
            self.modo_conversa_individual = False
            if result:
                from src.core.medallia_builder import MedalliaBuilder
                modelo = result.get('modelo', 'HONDA') or 'HONDA'
                self.item_conversa_individual['modelo'] = modelo
                
                fone_cru = result.get('celular', '')
                if not fone_cru or fone_cru == 'S/N':
                    fone_cru = self.item_conversa_individual.get('telefone', '')
                    
                celular = re.sub(r'\D', '', fone_cru)
                while celular.startswith('0'):
                    celular = celular[1:]
                    
                if not celular or len(celular) < 10:
                    self.status_honda.setText("⚠️ Celular não encontrado na ficha.")
                    QMessageBox.warning(self, "Sem Celular", f"Não foi encontrado número de celular na ficha do cliente {self.item_conversa_individual.get('cliente', '')}.")
                    return
                    
                if not celular.startswith('55'):
                    celular = '55' + celular
                    
                self.item_conversa_individual['telefone'] = celular
                
                link_bruto = MedalliaBuilder.build_ssi_link(self.item_conversa_individual.get('id', ''), modelo, "160")
                link = MedalliaBuilder.encrypt_link(link_bruto)
                texto_base = self.editor_mensagem.toPlainText()
                texto_base = texto_base.replace("[NOME]", self.item_conversa_individual.get('cliente', '').title())
                texto_final = texto_base.replace("[LINK]", link)
                
                self._mostrar_conversa_iniciada(
                    self.item_conversa_individual.get('cliente', '')
                )
                self.sig_iniciar_conversa_individual.emit(celular, self.item_conversa_individual.get('cliente', ''), link, texto_final, self.item_conversa_individual)
                self.sig_request_tab_change.emit(1)
            else:
                self.status_honda.setText("⚠️ Falha ao abrir ficha.")
                QMessageBox.warning(self, "Erro", "Não foi possível carregar a ficha do cliente no myHonda.")
            return

        if result:
            from src.core.medallia_builder import MedalliaBuilder
            modelo = result.get('modelo', 'HONDA') or 'HONDA'
            
            link_bruto = MedalliaBuilder.build_ssi_link(self.item_atual.get('id', ''), modelo, "160")
            link = MedalliaBuilder.encrypt_link(link_bruto)
            texto_base = self.editor_mensagem.toPlainText()
            texto_base = texto_base.replace("[NOME]", self.item_atual.get('cliente', '').title())
            texto_final = texto_base.replace("[LINK]", link)
            
            fone_cru = result.get('celular', '')
            if not fone_cru or fone_cru == 'S/N': 
                fone_cru = self.item_atual.get('telefone', '')
                
            celular = re.sub(r'\D', '', fone_cru)
            while celular.startswith('0'):
                celular = celular[1:]
                
            if not celular or len(celular) < 10:
                record_event(
                    "ssi_dispatch", "CONTACT_PHONE_NOT_FOUND", "WARN",
                    survey_ref=anonymous_id(self.item_atual.get('id', '')),
                    model_found=bool(modelo and modelo != 'HONDA'),
                )
                if not hasattr(self, 'clientes_nao_enviados'):
                    self.clientes_nao_enviados = []
                self.clientes_nao_enviados.append({
                    'cliente': self.item_atual.get('cliente', 'Desconhecido'),
                    'tipo': 'SSI',
                    'telefone': fone_cru or 'S/N',
                    'motivo': 'Sem celular na Ficha do myHonda'
                })
                self.on_whatsapp_message_sent(False)
                return
                
            if not celular.startswith('55'):
                celular = '55' + celular
                
            self.item_atual['telefone'] = celular
            if 0 <= self.indice_atual_disparo < len(self.fila_extraida):
                self.fila_extraida[self.indice_atual_disparo]['telefone'] = celular
            
            self.sig_dispatch_whatsapp.emit(celular, texto_final)
        else:
            if not hasattr(self, 'clientes_nao_enviados'):
                self.clientes_nao_enviados = []
            self.clientes_nao_enviados.append({
                'cliente': self.item_atual.get('cliente', 'Desconhecido'),
                'tipo': 'SSI',
                'telefone': 'S/N',
                'motivo': 'Não foi possível extrair dados da Ficha'
            })
            self.on_whatsapp_message_sent(False)

    def iniciar_conversa_individual(self):
        """Abre o chat no WhatsApp Web para conversar individualmente com o cliente selecionado."""
        # Uma busca SSI anterior não pode substituir o cliente escolhido agora.
        self._invalidate_ssi_lookup()
        self._conversation_generation = getattr(self, '_conversation_generation', 0) + 1
        self._pending_conversation_generation = None
        self.modo_conversa_individual = False
        # A linha destacada indica explicitamente o destinatário da conversa.
        item_selecionado = self.list_widget.currentItem()
        target_idx = None
        
        if item_selecionado:
            target_idx = item_selecionado.data(Qt.ItemDataRole.UserRole)
        else:
            # Se não clicou na linha, procura o primeiro marcado
            for i in range(self.list_widget.count()):
                it = self.list_widget.item(i)
                if it.checkState() == Qt.CheckState.Checked:
                    target_idx = it.data(Qt.ItemDataRole.UserRole)
                    break
                    
        if target_idx is None or target_idx < 0 or target_idx >= len(self.fila_extraida):
            QMessageBox.warning(self, "Aviso", "Por favor, clique em um cliente na lista para conversar.")
            return
            
        cli_data = self.fila_extraida[target_idx]
        cliente = cli_data.get('cliente', 'Cliente')
        tipo = cli_data.get('tipo', 'TSI')
        
        from src.core.medallia_builder import MedalliaBuilder
        
        texto_base = self.editor_mensagem.toPlainText()
        texto_base = texto_base.replace("[NOME]", cliente.title())
        
        if tipo == 'TSI':
            fone = re.sub(r'\D', '', cli_data.get('telefone', ''))
            while fone.startswith('0'):
                fone = fone[1:]
                
            if not fone or len(fone) < 10:
                QMessageBox.warning(self, "Telefone Não Encontrado", f"O cliente {cliente} não possui celular válido cadastrado no myHonda.")
                return
                
            if not fone.startswith('55'):
                fone = '55' + fone
                
            link_bruto = MedalliaBuilder.build_tsi_link(cli_data.get('id', ''))
            link = MedalliaBuilder.encrypt_link(link_bruto)
            texto_final = texto_base.replace("[LINK]", link)
            
            # Abre a conversa no WhatsApp Web sem enviar a mensagem
            self._mostrar_conversa_iniciada(cliente)
            self.sig_iniciar_conversa_individual.emit(fone, cliente, link, texto_final, cli_data)
            self.sig_request_tab_change.emit(1) # Pula para a aba do WhatsApp
            
        elif tipo == 'SSI':
            fone_cru = cli_data.get('telefone', '')
            fone = re.sub(r'\D', '', fone_cru)
            while fone.startswith('0'):
                fone = fone[1:]
                
            if fone and len(fone) >= 10:
                if not fone.startswith('55'):
                    fone = '55' + fone
                modelo = cli_data.get('modelo', 'HONDA') or 'HONDA'
                link_bruto = MedalliaBuilder.build_ssi_link(cli_data.get('id', ''), modelo, "160")
                link = MedalliaBuilder.encrypt_link(link_bruto)
                texto_final = texto_base.replace("[LINK]", link)
                
                self._mostrar_conversa_iniciada(cliente)
                self.sig_iniciar_conversa_individual.emit(fone, cliente, link, texto_final, cli_data)
                self.sig_request_tab_change.emit(1)
            else:
                # Precisa buscar na ficha do SSI primeiro
                url_ficha = cli_data.get('url_ficha')
                if not url_ficha:
                    QMessageBox.warning(self, "Ficha Não Disponível", f"Não há link de ficha para o cliente {cliente}.")
                    return
                    
                self.modo_conversa_individual = True
                self._pending_conversation_generation = self._conversation_generation
                self.item_conversa_individual = cli_data
                self.status_honda.setText(f"🔍 Abrindo ficha de {cliente} no myHonda para obter contato...")
                self.status_honda.setStyleSheet("background-color: white; color: #2563EB; padding: 8px 15px; border-radius: 15px; font-weight: bold; font-size: 12px; border: 1px solid #E2E8F0;")
                
                url_completa = "https://myhonda.my.site.com" + url_ficha if url_ficha.startswith("/") else url_ficha
                self._begin_ssi_lookup()
                self.nav_ssi_oculto.setUrl(QUrl(url_completa))
                self.tentativas = 0
                self.timer_ssi_ficha.start(2000)

    def _begin_ssi_lookup(self):
        self._ssi_generation = getattr(self, '_ssi_generation', 0) + 1
        self._active_ssi_generation = self._ssi_generation
        self._ssi_extracting_generation = None
        return self._active_ssi_generation

    def _invalidate_ssi_lookup(self):
        self._ssi_generation = getattr(self, '_ssi_generation', 0) + 1
        self._active_ssi_generation = None
        self._ssi_extracting_generation = None
        if hasattr(self, 'timer_ssi_ficha'):
            self.timer_ssi_ficha.stop()

    def _mostrar_conversa_iniciada(self, cliente):
        nome = str(cliente or "Cliente").strip() or "Cliente"
        self.status_honda.setText(f"💬 Conversa iniciada com {nome}")
        self.status_honda.setStyleSheet(
            "background-color: #EFF6FF; color: #1D4ED8; padding: 8px 15px; "
            "border-radius: 15px; font-weight: bold; font-size: 12px; "
            "border: 1px solid #93C5FD;"
        )

    def on_link_individual_enviado(self, item_data):
        """Chamado quando o link individual foi enviado com sucesso pela tela do WhatsApp."""
        if not item_data:
            return
        item_id = item_data.get('id')
        # Marca como enviado na lista em memória
        for cli in self.fila_extraida:
            if cli.get('id') == item_id:
                cli['enviado'] = True
                break
                
        # Salva no banco de dados local
        if item_id:
            self.db_manager.mark_survey_as_sent(item_id)
            
        # Registra consumo de licença e auditoria
        try:
            from src.core.license_manager import LicenseManager
            lm = LicenseManager()
            lm.registrar_envio()
            
            tipo = item_data.get('tipo', 'Desconhecido')
            cliente = item_data.get('cliente', 'Desconhecido')
            telefone = item_data.get('telefone', '')
            lm.registrar_log_auditoria(telefone, tipo, cliente)
        except Exception as e:
            print(f"Erro ao registrar auditoria individual: {e}")
            
        self.atualizar_lista_ui()

    def on_whatsapp_message_sent(self, success):
        record_event(
            "dispatch", "MESSAGE_CONFIRMED" if success else "MESSAGE_FAILED",
            "INFO" if success else "WARN",
            survey_ref=anonymous_id(getattr(self, 'item_atual', {}).get('id', '')),
            survey_type=getattr(self, 'item_atual', {}).get('tipo', 'desconhecido'),
        )
        reservation_id = getattr(self, 'reserva_envio_atual', '')
        self.reserva_envio_atual = ""
        from src.core.license_manager import LicenseManager
        reservation_manager = LicenseManager()
        if success:
            item = self.fila_extraida[self.indice_atual_disparo]
            item['enviado'] = True
            self.db_manager.mark_survey_as_sent(item.get('id', ''))

            confirmed, confirmation_message = reservation_manager.confirmar_envio(reservation_id)
            if not confirmed:
                record_event(
                    "dispatch", "MESSAGE_QUOTA_CONFIRMATION_PENDING", "ERROR",
                    survey_ref=anonymous_id(item.get('id', '')),
                )
                self.status_honda.setText(f"⚠️ {confirmation_message}")
            
            # Confirma a reserva já contabilizada e registra a auditoria.
            try:
                # Auditoria na Nuvem
                tipo = item.get('tipo', 'Desconhecido')
                cliente = item.get('cliente', 'Desconhecido')
                telefone = item.get('telefone', '')
                if not telefone or telefone == 'S/N':
                    telefone = getattr(self, 'item_atual', {}).get('telefone', '000000000')
                reservation_manager.registrar_log_auditoria(telefone, tipo, cliente)
            except: pass
            
            self.atualizar_lista_ui() # Atualiza na tela imediatamente que foi enviado
        else:
            released, release_message = reservation_manager.liberar_reserva_envio(reservation_id)
            if not released:
                record_event(
                    "dispatch", "MESSAGE_QUOTA_RELEASE_PENDING", "ERROR",
                    survey_ref=anonymous_id(getattr(self, 'item_atual', {}).get('id', '')),
                )
                self.status_honda.setText(f"⚠️ {release_message}")
            if not hasattr(self, 'clientes_nao_enviados'):
                self.clientes_nao_enviados = []
            cur_cli = self.item_atual.get('cliente', 'Desconhecido')
            cur_tipo = self.item_atual.get('tipo', 'Desconhecido')
            if not any(c.get('cliente') == cur_cli and c.get('tipo') == cur_tipo for c in self.clientes_nao_enviados):
                self.clientes_nao_enviados.append({
                    'cliente': cur_cli,
                    'tipo': cur_tipo,
                    'telefone': self.item_atual.get('telefone', 'S/N') or 'S/N',
                    'motivo': 'Número Inválido / Não cadastrado no WhatsApp'
                })
            
        import random
        # Anti-Ban Jitter humanizado entre 6.5s e 11.5s
        delay_ms = random.randint(6500, 11500) if success else 1500
        QTimer.singleShot(delay_ms, self.processar_proximo_disparo)
