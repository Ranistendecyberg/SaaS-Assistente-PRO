from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QFrame, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from src.core.license_manager import LicenseManager
from src.core.supabase_desktop import friendly_desktop_error


class MigrationScreen(QDialog):
    """Ativação única que vincula uma instalação legada ao Supabase."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = LicenseManager()
        self.setWindowTitle("Atualização de Segurança")
        self.setFixedSize(520, 430)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint
        )
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog { background: #F8FAFC; }
            QFrame { background: white; border: 1px solid #DCE5F0; border-radius: 14px; }
            QLineEdit { min-height: 46px; padding: 0 14px; border: 2px solid #CBD5E1;
                        border-radius: 8px; background: white; color: #0F172A; font-size: 15px; }
            QLineEdit:focus { border-color: #2563EB; }
            QPushButton { min-height: 46px; border-radius: 8px; font-size: 14px; font-weight: 700; }
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        card = QFrame()
        outer.addWidget(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(14)

        title = QLabel("🔐 Atualização de Segurança")
        title.setStyleSheet("border: none; font-size: 23px; font-weight: 800; color: #0F172A;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        description = QLabel(
            "Esta nova versão utiliza um servidor mais seguro.\n"
            "Informe o Código de Migração enviado pelo suporte.\n\n"
            "Esta confirmação será solicitada somente uma vez neste computador."
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setStyleSheet("border: none; color: #475569; font-size: 13px; line-height: 1.4;")
        layout.addWidget(description)

        hardware = QLabel(f"Identificação: {self.manager.get_hardware_id()}")
        hardware.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        hardware.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hardware.setStyleSheet("border: none; color: #64748B; font-size: 11px;")
        layout.addWidget(hardware)

        self.code = QLineEdit()
        self.code.setPlaceholderText("Cole aqui o Código de Migração")
        self.code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code.returnPressed.connect(self._activate)
        layout.addWidget(self.code)

        self.activate_button = QPushButton("Vincular este computador")
        self.activate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.activate_button.setStyleSheet(
            "QPushButton { background: #2563EB; color: white; border: none; }"
            "QPushButton:hover { background: #1D4ED8; }"
            "QPushButton:disabled { background: #94A3B8; }"
        )
        self.activate_button.clicked.connect(self._activate)
        layout.addWidget(self.activate_button)

        exit_button = QPushButton("Sair")
        exit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_button.setStyleSheet("QPushButton { background: transparent; color: #64748B; border: none; }")
        exit_button.clicked.connect(self.reject)
        layout.addWidget(exit_button)

    def _activate(self):
        code = self.code.text().strip()
        if not code:
            QMessageBox.warning(self, "Código necessário", "Informe o Código de Migração enviado pelo suporte.")
            return
        self.activate_button.setEnabled(False)
        self.activate_button.setText("Validando com segurança...")
        try:
            self.manager.migrar_para_supabase(code)
            QMessageBox.information(
                self, "Computador vinculado",
                "Migração concluída com sucesso. O código não será solicitado novamente neste computador.",
            )
            self.accept()
        except Exception as error:
            QMessageBox.warning(self, "Não foi possível migrar", friendly_desktop_error(error))
            self.activate_button.setEnabled(True)
            self.activate_button.setText("Vincular este computador")
