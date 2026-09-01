from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QMessageBox
from PyQt6.QtCore import Qt
from src.core.license_manager import LicenseManager
from src.core.updater import Updater

class AboutScreen(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sobre o Sistema")
        self.setFixedSize(420, 360)
        self.setStyleSheet("background-color: white;")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Logo ou Título
        lbl_titulo = QLabel("SaaS Assistente PRO")
        lbl_titulo.setStyleSheet("font-size: 20px; font-weight: bold; color: #1E293B;")
        lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_titulo)
        
        # Inicialização e variáveis
        from src.version import __version__
        self.current_version = __version__
        self.updater = Updater(self.current_version)
        
        # Versão Atual
        lbl_versao = QLabel(f"Versão Instalada: {self.current_version}")
        lbl_versao.setStyleSheet("font-size: 14px; color: #64748B;")
        lbl_versao.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_versao)
        
        self.lbl_status = QLabel("Checando atualizações...")
        self.lbl_status.setStyleSheet("font-size: 13px; color: #3B82F6;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)
        
        # Botão de Atualizar
        self.btn_atualizar = QPushButton("⬇  Baixar e Atualizar Automaticamente")
        self.btn_atualizar.setStyleSheet("""
            QPushButton {
                background-color: #22C55E; color: white; font-weight: bold; font-size: 14px;
                border: none; border-radius: 6px; padding: 10px;
            }
            QPushButton:hover { background-color: #16A34A; }
            QPushButton:disabled { background-color: #94A3B8; }
        """)
        self.btn_atualizar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_atualizar.setEnabled(False)
        self.btn_atualizar.clicked.connect(self.iniciar_atualizacao)
        layout.addWidget(self.btn_atualizar)
        
        # Botão Termos de Uso
        btn_termos = QPushButton("📄 Termos de Uso e Licença")
        btn_termos.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9; color: #475569; font-weight: 600; font-size: 12px;
                border: 1px solid #CBD5E1; border-radius: 6px; padding: 8px;
            }
            QPushButton:hover { background-color: #E2E8F0; color: #1E293B; }
        """)
        btn_termos.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_termos.clicked.connect(self.abrir_termos)
        layout.addWidget(btn_termos)
        
        # Desenvolvedor
        lbl_dev = QLabel("Desenvolvido para Gestão de Qualidade")
        lbl_dev.setStyleSheet("font-size: 11px; color: #94A3B8; margin-top: 10px;")
        lbl_dev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_dev)
        
        self.checar_nuvem()

    def abrir_termos(self):
        from src.ui.screens.terms_dialog import TermsDialog
        dialog = TermsDialog(self, apenas_leitura=True)
        dialog.exec()

    def checar_nuvem(self):
        try:
            manager = LicenseManager()
            resposta = manager.secure_backend.license_status(self.current_version)
            sistema = dict(resposta.get("system") or {})
            dados = {
                "versao_atual": sistema.get("current_version"),
                "url_download": sistema.get("installer_url"),
                "installer_sha256": sistema.get("installer_sha256"),
            }
                
            if not dados:
                self.lbl_status.setText("Não foi possível checar atualizações.")
                return
                
            self.versao_nuvem = dados.get("versao_atual") or dados.get("versao_recente", "1.0.0")
            self.link_download = dados.get("link_download") or dados.get("url_download", "")
            self.installer_sha256 = str(dados.get("installer_sha256") or "")
            
            updater = Updater(self.current_version)
            if updater._versao_maior(self.versao_nuvem, self.current_version):
                self.lbl_status.setText(f"🚀 Nova versão ({self.versao_nuvem}) disponível!")
                self.btn_atualizar.setEnabled(True)
            else:
                self.lbl_status.setText("✅ Seu sistema está na versão mais recente.")
                self.lbl_status.setStyleSheet("font-size: 13px; color: #22C55E;")
        except Exception as e:
            self.lbl_status.setText("Erro de conexão com o servidor.")

    def iniciar_atualizacao(self):
        self.btn_atualizar.setEnabled(False)
        self.btn_atualizar.setText("Preparando atualização segura...")
        self.lbl_status.setText("O instalador será validado antes de qualquer alteração.")
        self.updater = Updater(self.current_version)
        started = self.updater.executar_atualizacao(
            self.link_download, self.versao_nuvem, self, self.installer_sha256
        )
        if not started:
            self.btn_atualizar.setText("⬇  Baixar e Atualizar Automaticamente")
            self.btn_atualizar.setEnabled(True)
