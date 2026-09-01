from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QHBoxLayout, QFrame
)
from PyQt6.QtCore import Qt
from src.core.license_manager import LicenseManager

class RegistrationScreen(QDialog):
    def __init__(self, parent=None, is_update=False):
        super().__init__(parent)
        self.is_update = is_update
        self.setWindowTitle("Bem-vindo ao Assistente PRO!" if not is_update else "Atualizar Cadastro")
        self.setFixedSize(450, 550)
        # Remove close button to force registration
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.lm = LicenseManager()
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #F8FAFC;
            }
            QLabel {
                color: #1E293B;
            }
            QLineEdit {
                padding: 10px;
                min-height: 40px;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                background-color: white;
                font-size: 14px;
                color: #0F172A;
            }
            QLineEdit:focus {
                border: 2px solid #2563EB;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        # Header
        lbl_title = QLabel("🚀 Vamos Começar?" if not self.is_update else "⚙️ Atualize seu Cadastro")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #0F172A;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        texto_desc = (
            "Para liberar seus 2 dias de Teste Grátis,\nprecisamos apenas conhecer você melhor."
            if not self.is_update else
            "Para continuar utilizando o sistema,\nprecisamos que você preencha seus dados de contato."
        )
        lbl_desc = QLabel(texto_desc)
        lbl_desc.setStyleSheet("font-size: 14px; color: #475569;")
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_desc)

        layout.addSpacing(10)

        # Form
        lbl_concessionaria = QLabel("Nome da Concessionária (Grupo):")
        lbl_concessionaria.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_concessionaria)
        self.inp_concessionaria = QLineEdit()
        self.inp_concessionaria.setPlaceholderText("Ex: Grupo Auto Motors")
        layout.addWidget(self.inp_concessionaria)

        lbl_gestor = QLabel("Nome do Responsável:")
        lbl_gestor.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_gestor)
        self.inp_gestor = QLineEdit()
        self.inp_gestor.setPlaceholderText("Ex: Carlos Silva")
        layout.addWidget(self.inp_gestor)

        lbl_telefone = QLabel("WhatsApp com DDD:")
        lbl_telefone.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_telefone)
        self.inp_telefone = QLineEdit()
        self.inp_telefone.setPlaceholderText("Ex: 86999999999")
        layout.addWidget(self.inp_telefone)

        layout.addSpacing(20)

        # Submit Button
        self.btn_submit = QPushButton("Iniciar Meu Teste Grátis" if not self.is_update else "Salvar Dados e Continuar")
        self.btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                padding: 10px;
                min-height: 45px;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        self.btn_submit.clicked.connect(self.registrar)
        layout.addWidget(self.btn_submit)
        
        # Exit Button
        self.btn_exit = QPushButton("Sair do Sistema")
        self.btn_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_exit.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #64748B;
                font-size: 14px;
                border: none;
                margin-top: 10px;
            }
            QPushButton:hover {
                color: #EF4444;
                text-decoration: underline;
            }
        """)
        self.btn_exit.clicked.connect(self.reject)
        layout.addWidget(self.btn_exit)

    def registrar(self):
        concessionaria = self.inp_concessionaria.text().strip()
        gestor = self.inp_gestor.text().strip()
        telefone = self.inp_telefone.text().strip()

        if not concessionaria or not gestor or not telefone:
            QMessageBox.warning(self, "Atenção", "Por favor, preencha todos os campos para continuar.")
            return

        # Simple phone validation
        telefone_digits = ''.join(filter(str.isdigit, telefone))
        if len(telefone_digits) < 10:
            QMessageBox.warning(self, "Atenção", "Por favor, insira um número de WhatsApp válido com DDD.")
            return

        self.btn_submit.setEnabled(False)
        self.btn_submit.setText("Registrando...")

        try:
            if self.is_update:
                self.lm.atualizar_dados_cliente(concessionaria, gestor, telefone_digits)
                QMessageBox.information(
                    self, 
                    "Sucesso", 
                    "Dados atualizados com sucesso!"
                )
            else:
                self.lm.registrar_nova_licenca(concessionaria, gestor, telefone_digits)
                QMessageBox.information(
                    self, 
                    "Sucesso", 
                    "Cadastro concluído! Aproveite seus 2 dias de teste gratuito."
                )
            self.accept()
            self.close()
            self.deleteLater()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Ocorreu um erro ao registrar: {str(e)}")
            self.btn_submit.setEnabled(True)
            self.btn_submit.setText("Iniciar Meu Teste Grátis")
