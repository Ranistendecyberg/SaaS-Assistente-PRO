from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QLabel
from PyQt6.QtCore import Qt, QTimer
from src.ui.components.sidebar import Sidebar
from src.ui.lazy_screen import LazyScreen

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
                
        # Configuração da Janela
        from src.version import __version__
        self.setWindowTitle(f"SaaS Assistente PRO - V{__version__}")
        self.resize(1100, 700)
        
        # Widget Central com fundo cinza claro
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #F8FAFC;")
        self.setCentralWidget(central_widget)
        
        # Layout Principal Horizontal
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Instanciar Sidebar
        self.sidebar = Sidebar()
        main_layout.addWidget(self.sidebar)
        
        # Área Principal (Pilha de Telas)
        self.stack = QStackedWidget()
        self.setup_screens()
        main_layout.addWidget(self.stack)
        
        # Conectar Sidebar ao Stack
        self.sidebar.navigation_requested.connect(self.handle_navigation)
        self._active_sidebar_route = 6
        
        # Iniciar Heartbeat (Batimento de Online) — usa singleton do LicenseManager
        from src.core.license_manager import LicenseManager
        self.lm = LicenseManager.get_instance()
        self.lm.enviar_heartbeat(True) # Pulso de abertura
        
        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.timeout.connect(lambda: self.lm.enviar_heartbeat(True))
        self.heartbeat_timer.start(180000) # Pulso a cada 3 minutos
        
        # Checagem de Comunicados / Avisos de Reajuste da Administração
        QTimer.singleShot(1200, self.checar_comunicado_admin)
        
    def checar_comunicado_admin(self):
        """Verifica se há avisos ou comunicados no Firebase para esta máquina e exibe o popup."""
        import threading
        def _buscar():
            try:
                msg = self.lm.obter_aviso_reajuste()
                if msg and msg.strip():
                    from src.ui.screens.comunicado_dialog import ComunicadoDialog
                    QTimer.singleShot(0, lambda: ComunicadoDialog.exibir_se_houver(self, msg))
            except Exception as e:
                print("Erro ao checar comunicado:", e)
                
        threading.Thread(target=_buscar, daemon=True).start()
        
    def closeEvent(self, event):
        try:
            self.lm.enviar_heartbeat(False) # Pulso de fechamento
        except: pass
        event.accept()

    def handle_navigation(self, index):
        if index == 4:
            self.abrir_tela_licenca(modo="pix")
            # Voltar o foco da sidebar para a aba anterior
            self.sidebar.set_active_button(self._active_sidebar_route)
        elif index == 5:
            self.abrir_tela_licenca(modo="chave")
            self.sidebar.set_active_button(self._active_sidebar_route)
        elif index == 8:
            self.abrir_tela_sobre()
            self.sidebar.set_active_button(self._active_sidebar_route)
        elif index == 9:
            self.stack.setCurrentIndex(8)
            self._active_sidebar_route = 9
        else:
            self.stack.setCurrentIndex(index)
            self._active_sidebar_route = index
            
    def force_tab_change(self, index):
        self.sidebar.handle_nav_click(index)
            
    def abrir_tela_licenca(self, modo):
        from src.ui.screens.license_screen import LicenseScreen
        from PyQt6.QtWidgets import QDialog
        
        dialog = LicenseScreen(self, modo=modo)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Se ele ativou com sucesso, atualizamos a sidebar
            self.sidebar.buscar_status_licenca()
            
    def abrir_tela_sobre(self):
        from src.ui.screens.about_screen import AboutScreen
        dialog = AboutScreen(self)
        dialog.exec()
        
    def setup_screens(self):
        """Configura as rotas do QStackedWidget.

        Telas pesadas (ExtractionScreen, WhatsAppScreen, DashboardTabsScreen,
        CompanyAccountScreen) são envolvidas em LazyScreen e instanciadas
        somente na primeira navegação do usuário para aquela rota, reduzindo
        o tempo de inicialização do aplicativo.

        Sinais entre ExtractionScreen e WhatsAppScreen são conectados via
        callbacks on_ready(), que são chamados imediatamente após cada tela
        ser instanciada, independentemente da ordem de navegação.
        """
        from src.ui.screens.extraction_screen import ExtractionScreen
        from src.ui.screens.whatsapp_screen import WhatsAppScreen
        from src.ui.screens.dashboard_tabs_screen import DashboardTabsScreen
        from src.ui.screens.config_screen import ConfigScreen
        from src.ui.screens.tutorial_screen import TutorialScreen
        from src.ui.screens.suggestions_screen import SuggestionsScreen
        from src.ui.screens.company_account_screen import CompanyAccountScreen

        # --- Índice 0: Extração e Disparo (lazy) ---
        self._lazy_extraction = LazyScreen(ExtractionScreen)
        self.stack.addWidget(self._lazy_extraction)

        # --- Índice 1: Motor WhatsApp (lazy) ---
        self._lazy_whatsapp = LazyScreen(WhatsAppScreen)
        self.stack.addWidget(self._lazy_whatsapp)

        # Cada callback tenta efetuar uma única conexão bidirecional. O fluxo
        # anterior conectava metade dos sinais duas vezes, dependendo da ordem
        # em que as telas eram abertas.
        self._runtime_screens_connected = False
        self._lazy_extraction.on_ready(
            lambda _screen: self._connect_runtime_screens_if_ready()
        )
        self._lazy_whatsapp.on_ready(
            lambda _screen: self._connect_runtime_screens_if_ready()
        )

        # --- Índice 2: Dashboard (lazy) ---
        self._lazy_dashboard = LazyScreen(DashboardTabsScreen)
        self.stack.addWidget(self._lazy_dashboard)

        # --- Índice 3: Configuração de Lojas (instanciação imediata — leve) ---
        screen4 = ConfigScreen()
        self.stack.addWidget(screen4)

        # --- Índice 4: Dummy para PIX ---
        self.stack.addWidget(QWidget())

        # --- Índice 5: Dummy para Licença ---
        self.stack.addWidget(QWidget())

        # --- Índice 6: Tutorial (instanciação imediata — tela inicial) ---
        screen_tutorial = TutorialScreen()
        self.stack.addWidget(screen_tutorial)

        # --- Índice 7: Sugestões de Melhorias (leve — instanciação imediata) ---
        screen_sugestoes = SuggestionsScreen()
        self.stack.addWidget(screen_sugestoes)

        # --- Índice 8: Conta Empresarial (lazy) ---
        self._lazy_company = LazyScreen(CompanyAccountScreen)
        self.stack.addWidget(self._lazy_company)
        # Mantém referência compatível com código externo que acessa company_account_screen
        # O atributo agora é o LazyScreen; screen() retorna a instância real quando existir.
        self.company_account_screen = self._lazy_company

        # Tela inicial: Tutorial
        self.stack.setCurrentIndex(6)

    def _connect_runtime_screens_if_ready(self):
        """Conecta Extração e WhatsApp uma vez, quando ambos estiverem prontos."""
        if getattr(self, "_runtime_screens_connected", False):
            return False
        extraction_screen = self._lazy_extraction.screen()
        whatsapp_screen = self._lazy_whatsapp.screen()
        if extraction_screen is None or whatsapp_screen is None:
            return False

        extraction_screen.sig_dispatch_whatsapp.connect(whatsapp_screen.send_message)
        extraction_screen.sig_request_tab_change.connect(self.force_tab_change)
        extraction_screen.sig_check_whatsapp_login.connect(whatsapp_screen.check_login_status)
        extraction_screen.sig_iniciar_conversa_individual.connect(whatsapp_screen.abrir_conversa_cliente)
        whatsapp_screen.sig_message_sent.connect(extraction_screen.on_whatsapp_message_sent)
        whatsapp_screen.sig_login_status_result.connect(extraction_screen.on_login_status_result)
        whatsapp_screen.sig_link_individual_enviado.connect(extraction_screen.on_link_individual_enviado)
        self._runtime_screens_connected = True
        return True
