from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QFrame, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)

from src.core.license_manager import LicenseManager
from src.core.supabase_desktop import friendly_desktop_error


class NewInstallationScreen(QDialog):
    """Cadastra um computador novo e libera o período de avaliação."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = LicenseManager()
        self.setWindowTitle("Cadastro do SaaS Assistente PRO")
        self.setFixedSize(560, 570)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint
        )
        self._build_ui()

    @staticmethod
    def _field(placeholder):
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        return field

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog { background: #F8FAFC; }
            QFrame { background: white; border: 1px solid #DCE5F0; border-radius: 14px; }
            QLabel { border: none; color: #334155; }
            QLineEdit { min-height: 44px; padding: 0 14px; border: 1px solid #CBD5E1;
                        border-radius: 8px; background: white; color: #0F172A; font-size: 14px; }
            QLineEdit:focus { border: 2px solid #2563EB; }
            QPushButton { min-height: 46px; border-radius: 8px; font-size: 14px; font-weight: 700; }
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        card = QFrame()
        outer.addWidget(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 26, 32, 26)
        layout.setSpacing(12)

        title = QLabel("Bem-vindo ao SaaS Assistente PRO")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 23px; font-weight: 800; color: #0F172A;")
        layout.addWidget(title)
        description = QLabel(
            "Faça o cadastro da concessionária para liberar automaticamente "
            "o período de avaliação por 2 dias."
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setStyleSheet("color: #64748B; font-size: 13px;")
        layout.addWidget(description)

        hardware = QLabel(f"Identificação: {self.manager.get_hardware_id()}")
        hardware.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        hardware.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hardware.setStyleSheet("color: #94A3B8; font-size: 11px;")
        layout.addWidget(hardware)

        self.company = self._field("Nome da concessionária")
        self.manager_name = self._field("Nome do responsável")
        self.phone = self._field("WhatsApp com DDD")
        for field in (self.company, self.manager_name, self.phone):
            layout.addWidget(field)
        self.phone.returnPressed.connect(self._register)

        self.activate_button = QPushButton("Concluir cadastro e iniciar teste")
        self.activate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.activate_button.setStyleSheet(
            "QPushButton { background: #2563EB; color: white; border: none; }"
            "QPushButton:hover { background: #1D4ED8; }"
            "QPushButton:disabled { background: #94A3B8; }"
        )
        self.activate_button.clicked.connect(self._register)
        layout.addWidget(self.activate_button)
        exit_button = QPushButton("Sair")
        exit_button.setStyleSheet("background: transparent; color: #64748B; border: none;")
        exit_button.clicked.connect(self.reject)
        layout.addWidget(exit_button)

    def _register(self):
        company = self.company.text().strip()
        manager = self.manager_name.text().strip()
        phone = "".join(filter(str.isdigit, self.phone.text()))
        if not company or not manager or len(phone) < 10:
            QMessageBox.warning(self, "Dados incompletos", "Preencha todos os campos corretamente.")
            return
        self.activate_button.setEnabled(False)
        self.activate_button.setText("Ativando com segurança...")
        try:
            self.manager.registrar_nova_instalacao_supabase(company, manager, phone)
            QMessageBox.information(
                self, "Cadastro concluído",
                "Seu período de avaliação por 2 dias foi liberado com sucesso.",
            )
            self.accept()
        except Exception as error:
            QMessageBox.warning(self, "Não foi possível cadastrar", friendly_desktop_error(error))
            self.activate_button.setEnabled(True)
            self.activate_button.setText("Concluir cadastro e iniciar teste")
