from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)

from src.core.supabase_auth import (
    EMAIL_OTP_MAX_LENGTH,
    EMAIL_OTP_MIN_LENGTH,
    SupabaseUserClient,
)
from src.core.supabase_desktop import DesktopBackendError, friendly_desktop_error
from src.core.telemetry import record_event


class _RecoveryTask(QThread):
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


class PasswordRecoveryDialog(QDialog):
    """Recuperação por código, sem gravar senha, código ou sessão temporária."""

    def __init__(self, email="", auth=None, parent=None):
        super().__init__(parent)
        self.auth = auth or SupabaseUserClient()
        self._task = None
        self._recovery_session = None
        self._mfa_factor_id = ""
        self.setWindowTitle("Recuperar senha — SaaS Assistente PRO")
        self.setMinimumWidth(480)
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
        title = QLabel("Crie uma nova senha")
        title.setStyleSheet("font-size: 21px; font-weight: 800; color: #0F172A;")
        layout.addWidget(title)
        help_text = QLabel(
            "Informe seu e-mail e solicite o código. Depois, digite os números "
            "recebidos e escolha a nova senha."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        layout.addWidget(QLabel("E-mail de acesso"))
        self.email = QLineEdit(str(email or "").strip().lower())
        self.email.setPlaceholderText("nome@empresa.com.br")
        layout.addWidget(self.email)
        self.send_button = QPushButton("Enviar código de recuperação")
        self.send_button.setStyleSheet("background: #2563EB; color: white; border: none;")
        self.send_button.clicked.connect(self._request_code)
        layout.addWidget(self.send_button)

        layout.addWidget(QLabel("Código recebido por e-mail"))
        self.code = QLineEdit()
        self.code.setPlaceholderText("Digite o código numérico")
        self.code.setMaxLength(EMAIL_OTP_MAX_LENGTH)
        layout.addWidget(self.code)
        layout.addWidget(QLabel("Nova senha"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Mínimo de 8 caracteres")
        layout.addWidget(self.password)
        layout.addWidget(QLabel("Confirmar nova senha"))
        self.confirmation = QLineEdit()
        self.confirmation.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirmation.setPlaceholderText("Repita a nova senha")
        layout.addWidget(self.confirmation)

        self.mfa_label = QLabel("Código do aplicativo autenticador")
        self.mfa_label.setVisible(False)
        layout.addWidget(self.mfa_label)
        self.mfa_code = QLineEdit()
        self.mfa_code.setPlaceholderText("Código atual de 6 números")
        self.mfa_code.setMaxLength(6)
        self.mfa_code.setVisible(False)
        layout.addWidget(self.mfa_code)

        self.save_button = QPushButton("Validar código e alterar senha")
        self.save_button.setStyleSheet("background: #16A34A; color: white; border: none;")
        self.save_button.clicked.connect(self._update_password)
        layout.addWidget(self.save_button)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def _set_busy(self, busy, message=""):
        self.send_button.setEnabled(not busy)
        self.save_button.setEnabled(not busy)
        self.status.setText(message)

    def _run(self, operation, success, message):
        self._set_busy(True, message)
        self._task = _RecoveryTask(operation, self)
        self._task.succeeded.connect(success)
        self._task.failed.connect(self._show_error)
        self._task.start()

    def _request_code(self):
        email = self.email.text().strip().lower()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            QMessageBox.warning(self, "E-mail inválido", "Informe um e-mail válido.")
            return
        self._run(
            lambda: self.auth.request_password_recovery(email),
            self._code_sent,
            "Enviando o código com segurança...",
        )

    def _code_sent(self, _result):
        self._set_busy(False)
        self.status.setText(
            "Se o endereço estiver cadastrado, o código foi enviado. Verifique também o spam."
        )
        self.code.setFocus()

    def _update_password(self):
        email = self.email.text().strip().lower()
        code = "".join(filter(str.isdigit, self.code.text()))
        password = self.password.text()
        if "@" not in email:
            QMessageBox.warning(
                self, "Dados incompletos",
                "Informe o e-mail de acesso.",
            )
            return
        if len(password) < 8:
            QMessageBox.warning(self, "Senha inválida", "A nova senha deve possuir pelo menos 8 caracteres.")
            return
        if password != self.confirmation.text():
            QMessageBox.warning(self, "Senhas diferentes", "As duas senhas informadas não são iguais.")
            return

        if self._recovery_session is not None:
            mfa_code = "".join(filter(str.isdigit, self.mfa_code.text()))
            if len(mfa_code) != 6:
                QMessageBox.warning(
                    self, "Código incompleto",
                    "Informe os 6 números exibidos no aplicativo autenticador.",
                )
                return

            def operation_with_mfa():
                aal2_token = self.auth.verify_recovery_totp(
                    self._recovery_session, self._mfa_factor_id, mfa_code,
                )
                self.auth.update_recovered_password(aal2_token, password)
                return {"changed": True}

            self._run(
                operation_with_mfa, self._recovery_verified,
                "Confirmando o autenticador e alterando a senha...",
            )
            return

        if not EMAIL_OTP_MIN_LENGTH <= len(code) <= EMAIL_OTP_MAX_LENGTH:
            QMessageBox.warning(
                self, "Dados incompletos",
                "Informe o código numérico recebido por e-mail.",
            )
            return

        def operation():
            recovery = self.auth.verify_password_recovery(email, code)
            if recovery.totp_factors:
                return {"mfa_required": True, "recovery": recovery}
            self.auth.update_recovered_password(recovery.access_token, password)
            return {"changed": True}

        self._run(operation, self._recovery_verified, "Validando o código e alterando a senha...")

    def _recovery_verified(self, result):
        if result.get("mfa_required"):
            recovery = result["recovery"]
            self._recovery_session = recovery
            self._mfa_factor_id = str(recovery.totp_factors[0].get("id") or "")
            self.email.setEnabled(False)
            self.code.clear()
            self.code.setEnabled(False)
            self.send_button.setEnabled(False)
            self.mfa_label.setVisible(True)
            self.mfa_code.setVisible(True)
            self.save_button.setText("Confirmar autenticador e alterar senha")
            self._set_busy(False)
            self.send_button.setEnabled(False)
            self.status.setText(
                "Esta conta possui MFA. Digite o código atual do seu aplicativo autenticador."
            )
            self.mfa_code.setFocus()
            return
        self._password_changed(result)

    def _password_changed(self, _result):
        self.password.clear()
        self.confirmation.clear()
        self.code.clear()
        self.mfa_code.clear()
        self._recovery_session = None
        self._mfa_factor_id = ""
        self._set_busy(False)
        QMessageBox.information(
            self, "Senha alterada",
            "Sua senha foi atualizada. Entre novamente usando a nova senha.",
        )
        self.accept()

    def _show_error(self, error):
        self.password.clear()
        self.confirmation.clear()
        self._set_busy(False)
        if isinstance(error, DesktopBackendError):
            record_event(
                "authentication", "PASSWORD_RECOVERY_FAILED", "WARNING",
                error_code=error.code, http_status=error.status,
            )
            messages = {
                "OTP_EXPIRED": "O código expirou ou está incorreto. Solicite um novo código.",
                "INVALID_RECOVERY_CODE": "Informe o código numérico recebido por e-mail.",
                "WEAK_PASSWORD": "A nova senha deve possuir pelo menos 8 caracteres.",
                "SAME_PASSWORD": "A nova senha deve ser diferente da senha atual.",
                "PASSWORD_TOO_SHORT": "A nova senha deve possuir pelo menos 8 caracteres.",
                "INSUFFICIENT_AAL": (
                    "Esta conta exige a confirmação do aplicativo autenticador. "
                    "Solicite um novo código de recuperação e tente novamente."
                ),
                "INVALID_MFA_CODE": "Informe os 6 números do aplicativo autenticador.",
                "MFA_VERIFICATION_FAILED": (
                    "O código do autenticador não foi aceito. Aguarde o próximo e tente novamente."
                ),
                "MFA_CHALLENGE_EXPIRED": (
                    "O código do autenticador expirou. Use o código atual do aplicativo."
                ),
                "OVER_EMAIL_SEND_RATE_LIMIT": (
                    "Aguarde um minuto antes de solicitar outro código."
                ),
                "EMAIL_RATE_LIMIT_EXCEEDED": (
                    "Aguarde um minuto antes de solicitar outro código."
                ),
            }
            message = messages.get(error.code)
            if not message:
                message = (
                    f"{friendly_desktop_error(error)}\n\n"
                    f"Referência técnica: {error.code}"
                )
        else:
            record_event(
                "authentication", "PASSWORD_RECOVERY_FAILED", "WARNING",
                error_code=type(error).__name__,
            )
            message = "Não foi possível alterar a senha agora. Tente novamente."
        QMessageBox.warning(self, "Recuperação não concluída", message)

    def done(self, result):
        self.password.clear()
        self.confirmation.clear()
        self.code.clear()
        self.mfa_code.clear()
        self._recovery_session = None
        self._mfa_factor_id = ""
        super().done(result)
