from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from src.core.license_manager import LicenseManager
from src.core.supabase_auth import (
    EMAIL_OTP_MAX_LENGTH,
    EMAIL_OTP_MIN_LENGTH,
    SupabaseUserClient,
)
from src.core.supabase_desktop import DesktopBackendError, friendly_desktop_error
from src.core.v2_business_rules import is_valid_document
from src.version import __version__


class _NetworkTask(QThread):
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


class NewInstallationScreen(QDialog):
    """Primeiro acesso seguro da versão 2.0."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = LicenseManager()
        self.auth = SupabaseUserClient()
        self._task = None
        self._pending_email = ""
        self.setWindowTitle("Primeiro acesso — SaaS Assistente PRO 2.0")
        available = QGuiApplication.primaryScreen().availableGeometry()
        self.setMinimumSize(620, 600)
        self.resize(
            min(680, max(620, available.width() - 40)),
            min(800, max(600, available.height() - 60)),
        )
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        self._build_ui()
        self._show_mode("new")

    @staticmethod
    def _field(placeholder, password=False):
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        if password:
            field.setEchoMode(QLineEdit.EchoMode.Password)
        return field

    def reject(self):
        if self._task is not None and self._task.isRunning():
            return
        super().reject()

    def closeEvent(self, event):
        if self._task is not None and self._task.isRunning():
            event.ignore()
            return
        super().closeEvent(event)

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog { background: #F1F5F9; }
            QFrame#card { background: white; border: 1px solid #DCE5F0; border-radius: 16px; }
            QLabel { border: none; color: #334155; }
            QLineEdit { min-height: 42px; padding: 0 13px; border: 1px solid #CBD5E1;
                        border-radius: 8px; background: white; color: #0F172A; font-size: 13px; }
            QLineEdit:focus { border: 2px solid #2563EB; }
            QPushButton { min-height: 44px; border-radius: 8px; font-size: 13px; font-weight: 700; }
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        card = QFrame(objectName="card")
        outer.addWidget(card)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 22, 28, 22)
        card_layout.setSpacing(10)

        title = QLabel("SaaS Assistente PRO")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 25px; font-weight: 800; color: #0F172A;")
        card_layout.addWidget(title)
        subtitle = QLabel("Conta segura · Pessoa física ou jurídica")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 13px; color: #64748B;")
        card_layout.addWidget(subtitle)

        mode_row = QHBoxLayout()
        self.new_mode_button = QPushButton("Nova conta")
        self.link_mode_button = QPushButton("Computador adicional")
        self.new_mode_button.clicked.connect(lambda: self._show_mode("new"))
        self.link_mode_button.clicked.connect(lambda: self._show_mode("link"))
        mode_row.addWidget(self.new_mode_button)
        mode_row.addWidget(self.link_mode_button)
        card_layout.addLayout(mode_row)
        self.login_button = QPushButton("Já tenho conta — Entrar")
        self.login_button.setStyleSheet("background: white; color: #2563EB; border: 1px solid #CBD5E1;")
        self.login_button.clicked.connect(self._login_existing_account)
        card_layout.addWidget(self.login_button)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(2, 4, 8, 4)
        self.content_layout.setSpacing(9)
        scroll.setWidget(self.content)
        card_layout.addWidget(scroll, 1)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("color: #64748B; font-size: 12px;")
        card_layout.addWidget(self.status)
        exit_button = QPushButton("Sair")
        exit_button.setStyleSheet("background: transparent; color: #64748B; border: none;")
        exit_button.clicked.connect(self.reject)
        card_layout.addWidget(exit_button)

        self._build_new_company_form()
        self._build_link_form()
        self._build_verification_form()

    def _label(self, text):
        label = QLabel(text)
        label.setStyleSheet("font-weight: 700; color: #334155;")
        return label

    def _add_field(self, layout, label, field):
        layout.addWidget(self._label(label))
        layout.addWidget(field)

    def _build_new_company_form(self):
        self.new_form = QFrame()
        layout = QVBoxLayout(self.new_form)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(7)
        explanation = QLabel(
            "Cadastre sua conta com CPF ou CNPJ e confirme seu e-mail. O teste gratuito de 2 dias "
            "será liberado automaticamente neste computador."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #64748B;")
        layout.addWidget(explanation)
        self.company = self._field("Seu nome completo ou nome da empresa")
        self.cnpj = self._field("CPF (11 dígitos) ou CNPJ (14 dígitos)")
        self.owner = self._field("Nome completo")
        self.phone = self._field("WhatsApp com DDD")
        self.email = self._field("E-mail que será usado no acesso")
        self.password = self._field("Mínimo de 8 caracteres", password=True)
        self.password_confirmation = self._field("Repita a senha", password=True)
        for label, field in (
            ("Seu nome ou nome da empresa", self.company),
            ("CPF ou CNPJ do titular", self.cnpj),
            ("Proprietário da conta", self.owner),
            ("WhatsApp", self.phone),
            ("E-mail de acesso", self.email),
            ("Senha", self.password),
            ("Confirmar senha", self.password_confirmation),
        ):
            self._add_field(layout, label, field)
        self.create_button = QPushButton("Criar conta e enviar código")
        self.create_button.setStyleSheet(
            "QPushButton { background: #2563EB; color: white; border: none; }"
            "QPushButton:hover { background: #1D4ED8; }"
            "QPushButton:disabled { background: #94A3B8; }"
        )
        self.create_button.clicked.connect(self._start_signup)
        layout.addWidget(self.create_button)
        self.content_layout.addWidget(self.new_form)

    def _build_link_form(self):
        self.link_form = QFrame()
        layout = QVBoxLayout(self.link_form)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(9)
        explanation = QLabel(
            "No computador principal, abra Conta Empresarial e gere um código "
            "de ativação. Digite esse código abaixo; não é necessário informar "
            "e-mail ou senha neste computador."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #64748B;")
        layout.addWidget(explanation)
        self.link_code = self._field("PC-ABCD-1234")
        self.link_code.setMaxLength(16)
        self._add_field(layout, "Código de ativação", self.link_code)
        hint = QLabel("O código vale por 15 minutos e pode ser usado somente uma vez.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748B; font-size: 12px;")
        layout.addWidget(hint)
        self.link_button = QPushButton("Ativar este computador")
        self.link_button.setStyleSheet(
            "QPushButton { background: #0F766E; color: white; border: none; }"
            "QPushButton:hover { background: #115E59; }"
            "QPushButton:disabled { background: #94A3B8; }"
        )
        self.link_button.clicked.connect(self._link_existing_company)
        layout.addWidget(self.link_button)
        self.content_layout.addWidget(self.link_form)

    def _build_verification_form(self):
        self.verification_form = QFrame()
        layout = QVBoxLayout(self.verification_form)
        layout.setContentsMargins(0, 30, 0, 4)
        layout.setSpacing(12)
        title = QLabel("Confirme seu e-mail")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #0F172A;")
        layout.addWidget(title)
        self.verification_text = QLabel(
            "Digite o código numérico recebido ou confirme pelo link enviado por e-mail."
        )
        self.verification_text.setWordWrap(True)
        self.verification_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.verification_text)
        self.email_code = self._field("Código recebido por e-mail")
        self.email_code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.email_code.setMaxLength(EMAIL_OTP_MAX_LENGTH)
        layout.addWidget(self.email_code)
        self.verify_button = QPushButton("Confirmar e iniciar teste")
        self.verify_button.setStyleSheet(
            "QPushButton { background: #16A34A; color: white; border: none; }"
            "QPushButton:hover { background: #15803D; }"
            "QPushButton:disabled { background: #94A3B8; }"
        )
        self.verify_button.clicked.connect(self._verify_email)
        self.email_code.returnPressed.connect(self._verify_email)
        layout.addWidget(self.verify_button)
        self.link_confirmed_button = QPushButton("Já confirmei pelo link do e-mail")
        self.link_confirmed_button.setStyleSheet(
            "QPushButton { background: #E2E8F0; color: #334155; border: none; }"
            "QPushButton:hover { background: #CBD5E1; }"
            "QPushButton:disabled { color: #94A3B8; }"
        )
        self.link_confirmed_button.clicked.connect(self._confirm_from_email_link)
        layout.addWidget(self.link_confirmed_button)
        self.content_layout.addWidget(self.verification_form)

    def _show_mode(self, mode):
        self.new_form.setVisible(mode == "new")
        self.link_form.setVisible(mode == "link")
        self.verification_form.setVisible(False)
        selected = "background: #2563EB; color: white; border: none;"
        normal = "background: #E2E8F0; color: #475569; border: none;"
        self.new_mode_button.setStyleSheet(selected if mode == "new" else normal)
        self.link_mode_button.setStyleSheet(selected if mode == "link" else normal)
        self.status.setText("")

    def _set_busy(self, busy, text=""):
        self.login_button.setEnabled(not busy)
        for button in (self.create_button, self.link_button, self.verify_button,
                       self.link_confirmed_button,
                       self.new_mode_button, self.link_mode_button):
            button.setEnabled(not busy)
        self.status.setText(text)

    def _login_existing_account(self):
        from src.ui.screens.user_login_dialog import UserLoginDialog
        from src.ui.screens.email_confirmation_dialog import EmailConfirmationDialog
        if self._task:
            return
        if UserLoginDialog(self.auth, self).exec() != QDialog.DialogCode.Accepted:
            return
        if EmailConfirmationDialog(self.auth, self).exec() != QDialog.DialogCode.Accepted:
            return
        self._run(
            lambda: self.auth.recover_principal_access(self.manager.get_hardware_id()),
            self._principal_recovered,
            "Recuperando o acesso deste computador, sem alterar sua licença...",
        )

    def _principal_recovered(self, result):
        token = result.get("installation_token")
        if not result.get("ok") or not isinstance(token, str) or len(token) != 64:
            self._show_error(ValueError("Não foi possível confirmar a recuperação. Tente novamente."))
            return
        try:
            self.manager.secure_backend.save_installation_token(token)
        except Exception:
            self._show_error(ValueError("Não foi possível salvar o acesso neste computador. Aguarde um minuto e tente novamente."))
            return
        self.password.clear()
        self.password_confirmation.clear()
        self._set_busy(False)
        QMessageBox.information(self, "Acesso recuperado",
            "O acesso deste computador principal foi recuperado.\n"
            "A licença, a validade e eventuais bloqueios foram preservados.")
        self.accept()

    def _run(self, operation, on_success, busy_text):
        self._set_busy(True, busy_text)
        self._task = _NetworkTask(operation, self)
        self._task.succeeded.connect(on_success)
        self._task.failed.connect(self._show_error)
        self._task.finished.connect(lambda: setattr(self, "_task", None))
        self._task.start()

    def _validate_new_company(self):
        company = self.company.text().strip()
        owner = self.owner.text().strip()
        phone = "".join(filter(str.isdigit, self.phone.text()))
        email = self.email.text().strip().lower()
        password = self.password.text()
        if len(company) < 2 or len(owner) < 2 or len(phone) < 10:
            raise ValueError("Preencha corretamente a empresa, o responsável e o WhatsApp.")
        if not is_valid_document(self.cnpj.text()):
            raise ValueError("Informe um CPF ou CNPJ válido para o titular.")
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise ValueError("Informe um e-mail válido.")
        if len(password) < 8:
            raise ValueError("A senha deve possuir pelo menos 8 caracteres.")
        if password != self.password_confirmation.text():
            raise ValueError("As senhas informadas não são iguais.")
        return email, password

    def _start_signup(self):
        try:
            email, password = self._validate_new_company()
        except ValueError as error:
            QMessageBox.warning(self, "Confira o cadastro", str(error))
            return
        self._pending_email = email
        def operation():
            response = self.auth.sign_up(email, password)
            if response.get("access_token"):
                return {"authenticated": True}
            try:
                self.auth.sign_in(email, password)
                return {"authenticated": True}
            except DesktopBackendError as error:
                if error.code in {"EMAIL_NOT_CONFIRMED", "EMAIL_NOT_VERIFIED"}:
                    return {"confirmation_required": True}
                raise

        self._run(operation, self._signup_started, "Criando sua conta segura...")

    def _signup_started(self, response):
        self._set_busy(False)
        if response.get("authenticated"):
            self._complete_trial()
            return
        self.new_form.setVisible(False)
        self.link_form.setVisible(False)
        self.verification_form.setVisible(True)
        self.new_mode_button.setEnabled(False)
        self.link_mode_button.setEnabled(False)
        self.verification_text.setText(
            f"Enviamos a confirmação para {self._pending_email}.\n"
            "Use o código, se ele aparecer, ou abra o link e volte a esta tela."
        )
        self.email_code.setFocus()

    def _verify_email(self):
        code = "".join(filter(str.isdigit, self.email_code.text()))
        if not EMAIL_OTP_MIN_LENGTH <= len(code) <= EMAIL_OTP_MAX_LENGTH:
            QMessageBox.warning(
                self, "Código inválido", "Digite o código numérico recebido por e-mail."
            )
            return
        self._run(lambda: self.auth.verify_signup(self._pending_email, code),
                  lambda _session: self._complete_trial(), "Confirmando seu e-mail...")

    def _confirm_from_email_link(self):
        self._run(
            lambda: self.auth.sign_in(self._pending_email, self.password.text()),
            lambda _session: self._complete_trial(),
            "Verificando a confirmação do seu e-mail...",
        )

    def _complete_trial(self):
        self._run(
            lambda: self.auth.create_company_trial(
                self.company.text(), self.owner.text(), self.phone.text(),
                self.cnpj.text(), self.manager.get_hardware_id(), __version__,
            ), self._trial_created,
            "Liberando o teste gratuito neste computador...",
        )

    def _trial_created(self, result):
        self.manager.secure_backend.save_installation_token(result.get("installation_token"))
        self.password.clear()
        self.password_confirmation.clear()
        self._set_busy(False)
        QMessageBox.information(
            self, "Cadastro concluído",
            "Empresa, usuário e computador principal cadastrados com sucesso.\n\n"
            "Seu teste gratuito de 2 dias já está ativo.",
        )
        self.accept()

    def _link_existing_company(self):
        compact = "".join(character for character in self.link_code.text().upper()
                          if character.isalnum())
        if len(compact) == 8:
            compact = "PC" + compact
        code = (f"PC-{compact[2:6]}-{compact[6:10]}"
                if len(compact) == 10 and compact.startswith("PC") else "")
        allowed = set("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
        if not code or any(character not in allowed for character in compact[2:]):
            QMessageBox.warning(
                self, "Código inválido",
                "Digite o código de ativação exibido no computador principal.",
            )
            return

        self._run(
            lambda: self.manager.secure_backend.redeem_device_link_code(code, __version__),
            self._computer_linked,
            "Validando o código e ativando este computador...",
        )

    def _computer_linked(self, _result):
        self._set_busy(False)
        if _result.get("payment_required"):
            QMessageBox.information(self, "Computador vinculado — pagamento pendente",
                "O vínculo foi concluído. Este computador não está incluído no período já pago. "
                "Peça ao proprietário para conferir a cobrança atualizada no computador principal. "
                "Não reutilize um PIX antigo.")
            self.accept()
            return
        QMessageBox.information(self, "Computador vinculado",
                                "Este computador foi vinculado à conta empresarial com sucesso.")
        self.accept()

    def _show_error(self, error):
        self._set_busy(False)
        if isinstance(error, ValueError):
            message = str(error)
        elif isinstance(error, DesktopBackendError):
            messages = {
                "SIGNUPS_NOT_ALLOWED": "O cadastro de novas contas ainda não foi liberado no servidor de testes.",
                "USER_ALREADY_REGISTERED": "Este e-mail já possui conta. Use Já tenho conta — Entrar.",
                "EMAIL_CONFIRMATION_REQUIRED": "Confirme o e-mail antes de concluir o cadastro.",
                "EMAIL_NOT_CONFIRMED": "Abra o link recebido no e-mail e tente novamente.",
                "EMAIL_NOT_VERIFIED": "Abra o link recebido no e-mail e tente novamente.",
                "CNPJ_ALREADY_REGISTERED": "Este CPF ou CNPJ já está vinculado a uma conta.",
                "USER_ALREADY_HAS_COMPANY": "Este usuário já possui conta. Use Já tenho conta — Entrar no computador principal.",
                "RECOVERY_NOT_ALLOWED": "Este equipamento não foi reconhecido como principal desta conta, ou o vínculo está bloqueado. Use um código para computador adicional ou solicite suporte. Nenhuma licença foi alterada.",
                "RECOVERY_RATE_LIMITED": "O acesso foi recuperado recentemente. Aguarde um minuto antes de tentar novamente.",
                "EMAIL_OTP_REQUIRED": "Confirme o código enviado ao seu e-mail e tente novamente.",
                "INVALID_ONBOARDING": "Confira os dados da conta, CPF ou CNPJ e responsável.",
                "ONBOARDING_RATE_LIMITED": "Foram feitas muitas tentativas. Aguarde uma hora e tente novamente.",
                "INVALID_LOGIN_CREDENTIALS": (
                    "Use Já tenho conta — Entrar com sua senha existente ou "
                    "selecione Esqueci minha senha nessa tela."
                ),
                "INVALID_CREDENTIALS": (
                    "Use Já tenho conta — Entrar com sua senha existente ou "
                    "selecione Esqueci minha senha nessa tela."
                ),
                "OTP_EXPIRED": "O código expirou ou está incorreto. Solicite um novo cadastro.",
                "LINK_CODE_EXPIRED": "O código expirou. Gere outro no computador principal.",
                "LINK_CODE_NOT_AVAILABLE": "O código já foi utilizado, revogado ou não existe.",
                "LINK_CODE_RATE_LIMITED": "Muitas tentativas foram feitas. Aguarde 15 minutos e tente novamente.",
                "INVALID_LINK_CODE": "O código de ativação não é válido.",
            }
            message = messages.get(error.code, friendly_desktop_error(error))
        else:
            message = "Não foi possível concluir esta etapa. Tente novamente."
        QMessageBox.warning(self, "Não foi possível continuar", message)
