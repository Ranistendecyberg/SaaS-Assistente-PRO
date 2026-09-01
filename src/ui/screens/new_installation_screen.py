from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from src.core.license_manager import LicenseManager
from src.core.supabase_auth import SupabaseUserClient
from src.core.supabase_desktop import DesktopBackendError, friendly_desktop_error
from src.core.v2_business_rules import is_valid_cnpj
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
        subtitle = QLabel("Conta empresarial segura · Versão 2.0")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 13px; color: #64748B;")
        card_layout.addWidget(subtitle)

        mode_row = QHBoxLayout()
        self.new_mode_button = QPushButton("Nova empresa")
        self.link_mode_button = QPushButton("Computador adicional")
        self.new_mode_button.clicked.connect(lambda: self._show_mode("new"))
        self.link_mode_button.clicked.connect(lambda: self._show_mode("link"))
        mode_row.addWidget(self.new_mode_button)
        mode_row.addWidget(self.link_mode_button)
        card_layout.addLayout(mode_row)

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
            "Cadastre a matriz e confirme seu e-mail. O teste gratuito de 2 dias "
            "será liberado automaticamente neste computador."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #64748B;")
        layout.addWidget(explanation)
        self.company = self._field("Ex.: Grupo Auto Motors")
        self.cnpj = self._field("00.000.000/0000-00")
        self.owner = self._field("Nome completo")
        self.phone = self._field("WhatsApp com DDD")
        self.email = self._field("E-mail que será usado no acesso")
        self.password = self._field("Mínimo de 8 caracteres", password=True)
        self.password_confirmation = self._field("Repita a senha", password=True)
        for label, field in (
            ("Nome da empresa/concessionária", self.company),
            ("CNPJ da matriz", self.cnpj),
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
            "Entre com um usuário autorizado e informe o código de vínculo "
            "gerado no computador principal."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #64748B;")
        layout.addWidget(explanation)
        self.link_email = self._field("E-mail de acesso")
        self.link_password = self._field("Senha", password=True)
        self.link_code = self._field("PC-...")
        self._add_field(layout, "E-mail", self.link_email)
        self._add_field(layout, "Senha", self.link_password)
        self._add_field(layout, "Código do computador", self.link_code)
        self.link_button = QPushButton("Entrar e vincular computador")
        self.link_button.setStyleSheet(
            "QPushButton { background: #0F766E; color: white; border: none; }"
            "QPushButton:hover { background: #115E59; }"
            "QPushButton:disabled { background: #94A3B8; }"
        )
        self.link_button.clicked.connect(self._link_existing_company)
        layout.addWidget(self.link_button)
        recovery = QPushButton("Esqueci minha senha")
        recovery.setStyleSheet("background: transparent; color: #2563EB; border: none;")
        recovery.clicked.connect(self._request_recovery)
        layout.addWidget(recovery)
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
        self.verification_text = QLabel("Digite o código de 6 números enviado por e-mail.")
        self.verification_text.setWordWrap(True)
        self.verification_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.verification_text)
        self.email_code = self._field("Código de 6 números")
        self.email_code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.email_code.setMaxLength(6)
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
        for button in (self.create_button, self.link_button, self.verify_button,
                       self.new_mode_button, self.link_mode_button):
            button.setEnabled(not busy)
        self.status.setText(text)

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
        if not is_valid_cnpj(self.cnpj.text()):
            raise ValueError("Informe um CNPJ válido para a matriz.")
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
        self._run(lambda: self.auth.sign_up(email, password), self._signup_started,
                  "Criando sua conta segura...")

    def _signup_started(self, response):
        self._set_busy(False)
        if response.get("access_token"):
            self._complete_trial()
            return
        self.new_form.setVisible(False)
        self.link_form.setVisible(False)
        self.verification_form.setVisible(True)
        self.new_mode_button.setEnabled(False)
        self.link_mode_button.setEnabled(False)
        self.verification_text.setText(
            f"Enviamos um código de 6 números para {self._pending_email}.\n"
            "Ele confirma que o endereço pertence a você."
        )
        self.email_code.setFocus()

    def _verify_email(self):
        code = "".join(filter(str.isdigit, self.email_code.text()))
        if len(code) != 6:
            QMessageBox.warning(self, "Código inválido", "Digite os seis números recebidos por e-mail.")
            return
        self._run(lambda: self.auth.verify_signup(self._pending_email, code),
                  lambda _session: self._complete_trial(), "Confirmando seu e-mail...")

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
        self._set_busy(False)
        QMessageBox.information(
            self, "Cadastro concluído",
            "Empresa, usuário e computador principal cadastrados com sucesso.\n\n"
            "Seu teste gratuito de 2 dias já está ativo.",
        )
        self.accept()

    def _link_existing_company(self):
        email = self.link_email.text().strip().lower()
        password = self.link_password.text()
        code = self.link_code.text().strip().upper()
        if "@" not in email or not password or len(code) < 20:
            QMessageBox.warning(self, "Dados incompletos",
                                "Informe o e-mail, a senha e o código completo do computador.")
            return

        def operation():
            session = self.auth.sign_in(email, password)
            return self.manager.secure_backend.redeem_device_link_code(
                code, session.access_token, __version__
            )

        self._run(operation, self._computer_linked,
                  "Validando acesso e vinculando computador...")

    def _computer_linked(self, _result):
        self._set_busy(False)
        QMessageBox.information(self, "Computador vinculado",
                                "Este computador foi vinculado à conta empresarial com sucesso.")
        self.accept()

    def _request_recovery(self):
        email = self.link_email.text().strip().lower()
        if "@" not in email:
            QMessageBox.warning(self, "E-mail necessário", "Informe primeiro seu e-mail de acesso.")
            return
        self._run(lambda: self.auth.request_password_recovery(email),
                  lambda _result: self._recovery_sent(),
                  "Solicitando recuperação segura...")

    def _recovery_sent(self):
        self._set_busy(False)
        QMessageBox.information(
            self, "Verifique seu e-mail",
            "Se o endereço estiver cadastrado, você receberá as instruções para criar uma nova senha.",
        )

    def _show_error(self, error):
        self._set_busy(False)
        if isinstance(error, ValueError):
            message = str(error)
        elif isinstance(error, DesktopBackendError):
            messages = {
                "SIGNUPS_NOT_ALLOWED": "O cadastro de novas contas ainda não foi liberado no servidor de testes.",
                "USER_ALREADY_REGISTERED": "Este e-mail já possui conta. Use Computador adicional.",
                "EMAIL_CONFIRMATION_REQUIRED": "Confirme o e-mail antes de concluir o cadastro.",
                "CNPJ_ALREADY_REGISTERED": "Este CNPJ já está vinculado a uma conta empresarial.",
                "USER_ALREADY_HAS_COMPANY": "Este usuário já pertence a uma empresa.",
                "INVALID_ONBOARDING": "Confira os dados da empresa, CNPJ e responsável.",
                "ONBOARDING_RATE_LIMITED": "Foram feitas muitas tentativas. Aguarde uma hora e tente novamente.",
                "INVALID_LOGIN_CREDENTIALS": "E-mail ou senha incorretos.",
                "INVALID_CREDENTIALS": "E-mail ou senha incorretos.",
                "OTP_EXPIRED": "O código expirou ou está incorreto. Solicite um novo cadastro.",
                "LINK_CODE_EXPIRED": "O código expirou. Gere outro no computador principal.",
                "LINK_CODE_NOT_AVAILABLE": "O código já foi utilizado, revogado ou não existe.",
            }
            message = messages.get(error.code, friendly_desktop_error(error))
        else:
            message = "Não foi possível concluir esta etapa. Tente novamente."
        QMessageBox.warning(self, "Não foi possível continuar", message)
