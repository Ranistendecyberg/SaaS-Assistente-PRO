from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QVBoxLayout,
)

from src.core.supabase_auth import EMAIL_OTP_MAX_LENGTH, EMAIL_OTP_MIN_LENGTH
from src.core.supabase_desktop import DesktopBackendError


class _EmailConfirmationTask(QThread):
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


class EmailConfirmationDialog(QDialog):
    """Confirma uma operação empresarial pelo e-mail da sessão atual."""

    def __init__(self, auth_client, parent=None):
        super().__init__(parent)
        self.auth = auth_client
        self._task = None
        self._email = ""
        self._requested = False
        self.setWindowTitle("Confirmar operação por e-mail")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setStyleSheet("""
            QDialog { background: #F8FAFC; }
            QLabel { color: #334155; }
            QLineEdit { min-height: 44px; padding: 0 12px; border: 2px solid #CBD5E1;
                        border-radius: 9px; background: white; color: #0F172A;
                        font-size: 18px; font-weight: 700; letter-spacing: 4px; }
            QLineEdit:focus { border-color: #2563EB; }
            QPushButton { min-height: 42px; border-radius: 8px; font-weight: 700; }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        title = QLabel("Confirme pelo seu e-mail")
        title.setStyleSheet("font-size:21px;font-weight:800;color:#0F172A;")
        layout.addWidget(title)
        self.instructions = QLabel(
            "Estamos enviando um código numérico para o e-mail desta conta."
        )
        self.instructions.setWordWrap(True)
        layout.addWidget(self.instructions)

        self.code = QLineEdit()
        self.code.setPlaceholderText("Código recebido por e-mail")
        # Permite colar códigos formatados com espaços; a validação usa apenas
        # os dígitos e continua limitada pelo tamanho oficial do OTP.
        self.code.setMaxLength(24)
        self.code.setEnabled(False)
        self.code.returnPressed.connect(self._verify)
        layout.addWidget(self.code)

        actions = QHBoxLayout()
        self.resend = QPushButton("Reenviar código")
        self.resend.setStyleSheet(
            "background:white;color:#2563EB;border:1px solid #CBD5E1;padding:0 16px;"
        )
        self.resend.clicked.connect(self._request_code)
        cancel = QPushButton("Cancelar")
        cancel.setStyleSheet(
            "background:white;color:#334155;border:1px solid #CBD5E1;padding:0 16px;"
        )
        cancel.clicked.connect(self.reject)
        self.confirm = QPushButton("Confirmar operação")
        self.confirm.setEnabled(False)
        self.confirm.setStyleSheet(
            "QPushButton{background:#2563EB;color:white;border:none;padding:0 20px;}"
            "QPushButton:disabled{background:#CBD5E1;color:#64748B;}"
        )
        self.confirm.clicked.connect(self._verify)
        actions.addWidget(self.resend)
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(self.confirm)
        layout.addLayout(actions)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._requested and not self._task:
            self._request_code()

    @staticmethod
    def _masked_email(email):
        local, _, domain = str(email).partition("@")
        if not domain:
            return "seu e-mail cadastrado"
        visible = local[:2]
        return f"{visible}{'*' * max(3, len(local) - len(visible))}@{domain}"

    def _set_busy(self, busy):
        self.code.setDisabled(busy or not self._requested)
        self.resend.setDisabled(busy)
        self.confirm.setDisabled(busy or not self._requested)

    def _run(self, operation, success):
        if self._task:
            return
        self._set_busy(True)
        self._task = _EmailConfirmationTask(operation, self)
        task = self._task

        def succeeded(result):
            self._task = None
            try:
                success(result)
            except Exception as error:
                self._show_error(error)
            self._set_busy(False)
            task.deleteLater()

        def failed(error):
            self._task = None
            self._set_busy(False)
            self._show_error(error)
            task.deleteLater()

        task.succeeded.connect(succeeded)
        task.failed.connect(failed)
        self._task.start()

    def _request_code(self):
        self._run(self.auth.request_operation_confirmation, self._code_sent)

    def _code_sent(self, email):
        self._email = str(email)
        self._requested = True
        self.instructions.setText(
            f"Enviamos um código de 8 dígitos para {self._masked_email(email)}. "
            "Digite-o abaixo para continuar."
        )
        self.code.clear()
        self.code.setEnabled(True)
        self.confirm.setEnabled(True)
        self.code.setFocus()

    def _verify(self):
        code = "".join(filter(str.isdigit, self.code.text()))
        if not EMAIL_OTP_MIN_LENGTH <= len(code) <= EMAIL_OTP_MAX_LENGTH:
            QMessageBox.warning(
                self, "Código incompleto", "Informe o código numérico recebido por e-mail."
            )
            return
        self._run(
            lambda: self.auth.verify_operation_confirmation(self._email, code),
            self._verified,
        )

    def _verified(self, _session):
        self.code.clear()
        QMessageBox.information(
            self, "Operação confirmada",
            "E-mail confirmado. As operações protegidas estão autorizadas nesta sessão.",
        )
        self.accept()

    def _show_error(self, error):
        code = error.code if isinstance(error, DesktopBackendError) else ""
        messages = {
            "INVALID_EMAIL_OTP": "Informe o código numérico recebido por e-mail.",
            "OTP_EXPIRED": "O código expirou. Solicite um novo código.",
            "TOKEN_HAS_EXPIRED": "O código expirou. Solicite um novo código.",
            "OTP_DISABLED": "O envio de código por e-mail não está habilitado no servidor.",
            "OVER_EMAIL_SEND_RATE_LIMIT": "Aguarde um minuto antes de reenviar o código.",
            "EMAIL_OTP_IDENTITY_MISMATCH": "O código não pertence ao usuário conectado.",
            "NETWORK_ERROR": "Não foi possível conectar ao servidor. Verifique a internet.",
        }
        QMessageBox.warning(
            self, "Confirmação por e-mail",
            messages.get(code, "O código não foi aceito. Confira o e-mail e tente novamente."),
        )
