from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QLabel
from PyQt6.QtCore import Qt, QTimer
from src.ui.components.sidebar import Sidebar
from src.ui.screens.extraction_screen import ExtractionScreen
from src.ui.screens.dashboard_tabs_screen import DashboardTabsScreen

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
        
        # Iniciar Heartbeat (Batimento de Online)
        from src.core.license_manager import LicenseManager
        self.lm = LicenseManager()
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
            self.sidebar.set_active_button(self.stack.currentIndex())
        elif index == 5:
            self.abrir_tela_licenca(modo="chave")
            self.sidebar.set_active_button(self.stack.currentIndex())
        elif index == 8:
            self.abrir_tela_sobre()
            self.sidebar.set_active_button(self.stack.currentIndex())
        else:
            self.stack.setCurrentIndex(index)
            
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
        # Tela 1: Extração e Disparo (Agora completa)
        screen1 = ExtractionScreen()
        self.stack.addWidget(screen1)
        
        # Tela 2: Motor WhatsApp (Agora real)
        from src.ui.screens.whatsapp_screen import WhatsAppScreen
        screen2 = WhatsAppScreen()
        self.stack.addWidget(screen2)
        
        # Tela 3: Dashboard
        from src.ui.screens.dashboard_tabs_screen import DashboardTabsScreen
        screen3 = DashboardTabsScreen()
        self.stack.addWidget(screen3)
        
        # Tela 4: Configuração de Lojas
        from src.ui.screens.config_screen import ConfigScreen
        screen4 = ConfigScreen()
        self.stack.addWidget(screen4)
        
        # Tela 5 (Index 4): Dummy para PIX
        self.stack.addWidget(QWidget())
        
        # Tela 6 (Index 5): Dummy para Licença
        self.stack.addWidget(QWidget())
        
        # Tela 7 (Index 6): Tutorial
        from src.ui.screens.tutorial_screen import TutorialScreen
        screen_tutorial = TutorialScreen()
        self.stack.addWidget(screen_tutorial)
        
        # Tela 8 (Index 7): Sugestões de Melhorias
        from src.ui.screens.suggestions_screen import SuggestionsScreen
        screen_sugestoes = SuggestionsScreen()
        self.stack.addWidget(screen_sugestoes)
        
        # Set Tutorial as initial screen
        self.stack.setCurrentIndex(6)
        
        # --- ROTEAMENTO DE SINAIS ENTRE TELAS ---
        # Quando Extração pedir envio, aciona método send_message no WhatsApp
        screen1.sig_dispatch_whatsapp.connect(screen2.send_message)
        # Pular para a tela do WhatsApp automaticamente
        screen1.sig_request_tab_change.connect(self.force_tab_change)
        # Quando WhatsApp terminar, avisa a Extração para processar o próximo
        screen2.sig_message_sent.connect(screen1.on_whatsapp_message_sent)
        # Rota de verificação de login ANTES de começar os disparos
        screen1.sig_check_whatsapp_login.connect(screen2.check_login_status)
        screen2.sig_login_status_result.connect(screen1.on_login_status_result)
        # Fluxo de Conversa Individual e Envio de Link sob demanda
        screen1.sig_iniciar_conversa_individual.connect(screen2.abrir_conversa_cliente)
        screen2.sig_link_individual_enviado.connect(screen1.on_link_individual_enviado)
