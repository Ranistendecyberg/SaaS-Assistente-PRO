from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QLabel, QPushButton
from PyQt6.QtCore import Qt
from src.ui.screens.dashboard_screen import DashboardScreen
from src.ui.screens.dashboard_ssi_screen import DashboardSSIScreen
from src.ui.screens.dashboard_comparativo_screen import DashboardComparativoScreen
from src.ui.dashboard_error_guard import record_dashboard_error

class DashboardTabsScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.dashboard_tsi = None
        self.dashboard_ssi = None
        self.dashboard_comparativo = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { 
                border: none; 
                background: transparent; 
            }
            QTabWidget::tab-bar {
                alignment: center;
            }
            QTabBar::tab { 
                background: transparent; 
                color: #64748B; 
                padding: 8px 16px; 
                font-weight: 700; 
                font-size: 13px; 
                border: none;
                border-bottom: 3px solid transparent;
                margin: 2px 4px;
                border-radius: 5px;
            }
            QTabBar::tab:hover {
                background: #F1F5F9;
                color: #3B82F6;
            }
            QTabBar::tab:selected { 
                color: #2563EB; 
                border-bottom: 3px solid #2563EB; 
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)
        
        # Cria abas vazias com layouts (Lazy Load containers)
        self.tab_tsi = QWidget()
        self.layout_tsi = QVBoxLayout(self.tab_tsi)
        self.layout_tsi.setContentsMargins(0, 0, 0, 0)
        
        self.tab_ssi = QWidget()
        self.layout_ssi = QVBoxLayout(self.tab_ssi)
        self.layout_ssi.setContentsMargins(0, 0, 0, 0)

        self.tab_comparativo = QWidget()
        self.layout_comparativo = QVBoxLayout(self.tab_comparativo)
        self.layout_comparativo.setContentsMargins(0, 0, 0, 0)
        
        self.tabs.addTab(self.tab_tsi, "🔧 Painel de Resultados TSI")
        self.tabs.addTab(self.tab_ssi, "🛵 Painel de Resultados SSI")
        self.tabs.addTab(self.tab_comparativo, "📊 Relatório Gerencial Geral")
        
        self.tabs.currentChanged.connect(self.on_tab_changed)
        layout.addWidget(self.tabs)
        
    def showEvent(self, event):
        super().showEvent(event)
        # Ao abrir essa tela pela primeira vez, carrega a aba ativa (TSI)
        if self.dashboard_tsi is None:
            self.on_tab_changed(self.tabs.currentIndex())
        
    def on_tab_changed(self, index):
        tabs = {
            0: ("dashboard_tsi", self.layout_tsi, DashboardScreen),
            1: ("dashboard_ssi", self.layout_ssi, DashboardSSIScreen),
            2: ("dashboard_comparativo", self.layout_comparativo, DashboardComparativoScreen),
        }
        tab = tabs.get(index)
        if tab is None:
            return

        attribute, layout, screen_class = tab
        try:
            screen = getattr(self, attribute)
            if screen is None:
                screen = screen_class()
                layout.addWidget(screen)
                setattr(self, attribute, screen)
            else:
                screen.carregar_dados()
        except Exception as error:
            diagnostic_id = record_dashboard_error(
                type(self).__name__, f"criar_aba_{index}", error,
            )
            self._show_tab_error(layout, index, diagnostic_id)

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_tab_error(self, layout, index, diagnostic_id):
        self._clear_layout(layout)
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message = QLabel(
            "Não foi possível abrir este painel. O restante do sistema continua disponível.\n"
            f"Código de diagnóstico: {diagnostic_id}"
        )
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setWordWrap(True)
        panel_layout.addWidget(message)
        retry = QPushButton("Tentar carregar novamente")
        retry.clicked.connect(lambda _checked=False, tab_index=index: self.on_tab_changed(tab_index))
        panel_layout.addWidget(retry, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(panel)
