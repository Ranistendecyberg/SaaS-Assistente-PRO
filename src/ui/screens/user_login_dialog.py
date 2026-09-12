from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QVBoxLayout,
)

from src.core.supabase_desktop import DesktopBackendError, friendly_desktop_error


class _LoginTask(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation

    def run(self):
        try:
            self.succeeded.emit(self.operation())
        except Exception as error:
            self.failed.emit(error)


class UserLoginDialog(QDialog):
    """Restaura a sessão empresarial sem persistir e-mail ou senha."""

    def __init__(self, auth_client, parent=None):
        super().__init__(parent)
        self.auth = auth_client
        self._task = None
        self.setWindowTitle("Entrar na conta empresarial")
        self.setModal(True)
        self.setMinimumWidth(470)
        self.setStyleSheet("""
            QDialog { background: #F8FAFC; }
            QLabel { color: #334155; }
            QLineEdit { min-height: 42px; padding: 0 12px; border: 1px solid #CBD5E1;
                        border-radius: 8px; background: white; color: #0F172A; }
            QLineEdit:focus { border: 2px solid #2563EB; }
            QPushButton { min-height: 42px; border-radius: 8px; font-weight: 700; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        title = QLabel("Acesse sua conta empresarial")
        title.setStyleSheet("font-size: 21px; font-weight: 800; color: #0F172A;")
        layout.addWidget(title)
        explanation = QLabel(
            "Entre com sua conta existente. Para recuperar o acesso deste computador, "
            "será solicitada também a confirmação por e-mail."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        layout.addWidget(QLabel("E-mail de acesso"))
        self.email = QLineEdit()
        self.email.setPlaceholderText("nome@empresa.com.br")
        layout.addWidget(self.email)
        layout.addWidget(QLabel("Senha"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Digite sua senha")
        self.password.returnPressed.connect(self._sign_in)
        layout.addWidget(self.password)

        self.recovery = QPushButton("Esqueci minha senha")
        self.recovery.setStyleSheet(
            "background:transparent;color:#2563EB;border:none;text-align:left;"
        )
        self.recovery.clicked.connect(self._recover_password)
        layout.addWidget(self.recovery)

        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel = QPushButton("Cancelar")
        self.cancel.setStyleSheet(
            "background:white;color:#334155;border:1px solid #CBD5E1;padding:0 18px;"
        )
        self.cancel.clicked.connect(self.reject)
        self.submit = QPushButton("Entrar")
        self.submit.setStyleSheet(
            "background:#2563EB;color:white;border:none;padding:0 24px;"
        )
        self.submit.clicked.connect(self._sign_in)
        actions.addWidget(self.cancel)
        actions.addWidget(self.submit)
        layout.addLayout(actions)

    def _set_busy(self, busy):
        self.email.setDisabled(busy)
        self.password.setDisabled(busy)
        self.recovery.setDisabled(busy)
        self.cancel.setDisabled(busy)
        self.submit.setDisabled(busy)
        self.submit.setText("Entrando…" if busy else "Entrar")

    def _sign_in(self):
        email = self.email.text().strip().lower()
        password = self.password.text()
        if "@" not in email or not password:
            QMessageBox.warning(self, "Dados incompletos", "Informe seu e-mail e sua senha.")
            return
        if self._task:
            return

        self._set_busy(True)
        self._task = _LoginTask(lambda: self.auth.sign_in(email, password), self)
        task = self._task

        def succeeded(_session):
            self._task = None
            self.password.clear()
            task.deleteLater()
            self.accept()

        def failed(error):
            self._task = None
            self.password.clear()
            self._set_busy(False)
            messages = {
                "INVALID_CREDENTIALS": "E-mail ou senha incorretos.",
                "INVALID_LOGIN_CREDENTIALS": "E-mail ou senha incorretos.",
                "EMAIL_NOT_CONFIRMED": "Confirme seu e-mail antes de entrar.",
                "NETWORK_ERROR": "Não foi possível conectar ao servidor. Verifique a internet.",
            }
            code = error.code if isinstance(error, DesktopBackendError) else "INTERNAL_ERROR"
            QMessageBox.warning(
                self, "Não foi possível entrar", messages.get(code, friendly_desktop_error(error))
            )
            task.deleteLater()

        task.succeeded.connect(succeeded)
        task.failed.connect(failed)
        self._task.start()

    def _recover_password(self):
        from src.ui.screens.password_recovery_dialog import PasswordRecoveryDialog

        PasswordRecoveryDialog(self.email.text(), self.auth, self).exec()
        self.password.clear()

    def done(self, result):
        self.password.clear()
        super().done(result)
