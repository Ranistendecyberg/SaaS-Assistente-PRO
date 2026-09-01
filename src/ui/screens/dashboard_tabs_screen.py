from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PyQt6.QtCore import Qt
from src.ui.screens.dashboard_screen import DashboardScreen
from src.ui.screens.dashboard_ssi_screen import DashboardSSIScreen
from src.ui.screens.dashboard_comparativo_screen import DashboardComparativoScreen

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
        if index == 0:
            if self.dashboard_tsi is None:
                self.dashboard_tsi = DashboardScreen()
                self.layout_tsi.addWidget(self.dashboard_tsi)
            else:
                self.dashboard_tsi.carregar_dados()
                
        elif index == 1:
            if self.dashboard_ssi is None:
                self.dashboard_ssi = DashboardSSIScreen()
                self.layout_ssi.addWidget(self.dashboard_ssi)
            else:
                self.dashboard_ssi.carregar_dados()

        elif index == 2:
            if self.dashboard_comparativo is None:
                self.dashboard_comparativo = DashboardComparativoScreen()
                self.layout_comparativo.addWidget(self.dashboard_comparativo)
            else:
                self.dashboard_comparativo.carregar_dados()
