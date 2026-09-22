from __future__ import annotations

from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from io import BytesIO

import qrcode
from PIL import Image
from PyQt6.QtCore import QThread, QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QGuiApplication, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from src.core.supabase_desktop import DesktopBackendError, friendly_desktop_error


class _BillingTask(QThread):
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


class BillingDialog(QDialog):
    """Dados fiscais e pagamento da fatura empresarial consolidada."""

    FIELD_LABELS = (
        ("legal_name", "Nome completo ou razão social"),
        ("billing_cnpj", "CPF ou CNPJ para cobrança"),
        ("billing_email", "E-mail de cobrança"),
        ("postal_code", "CEP"),
        ("street", "Rua / avenida"),
        ("street_number", "Número"),
        ("address_extra", "Complemento (opcional)"),
        ("neighborhood", "Bairro"),
        ("city", "Cidade"),
        ("state", "UF"),
    )

    def __init__(
        self, auth, company_id: str, role: str, parent=None,
        defaults=None, estimated_amount=None,
    ):
        super().__init__(parent)
        self.auth = auth
        self.company_id = company_id
        self.role = role
        self._task = None
        self._last_attempt = {}
        self._status_attempt_id = ""
        self._defaults = dict(defaults or {})
        self._estimated_amount = estimated_amount
        self._reconciliation_required = False
        self._payment_environment = ""
        self.setWindowTitle("Cobrança empresarial — SaaS Assistente PRO")
        self.resize(760, 760)
        self.setMinimumSize(620, 560)
        self.setStyleSheet("QDialog{background:#F4F7FB;color:#0F172A;}")
        self._build_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(15000)
        self._refresh_timer.timeout.connect(self._refresh_payment)
        self._load()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        title = QLabel("Cobrança consolidada")
        title.setStyleSheet("font-size:26px;font-weight:800;color:#0F172A;")
        layout.addWidget(title)
        description = QLabel(
            "Uma única fatura reúne o computador principal e os adicionais. "
            "O acesso somente será renovado após a confirmação segura do Mercado Pago."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color:#64748B;font-size:13px;")
        layout.addWidget(description)

        self.environment_banner = QLabel("Confirmando o ambiente de pagamento...")
        self.environment_banner.setWordWrap(True)
        self.environment_banner.setStyleSheet(
            "background:#F1F5F9;border:1px solid #CBD5E1;border-radius:10px;"
            "padding:12px;color:#475569;font-size:13px;font-weight:800;"
        )
        layout.addWidget(self.environment_banner)

        amount_card = QFrame()
        amount_card.setObjectName("billingAmountCard")
        amount_card.setStyleSheet(
            "QFrame#billingAmountCard{background:#EAF2FF;border:1px solid #BFDBFE;"
            "border-radius:12px;} QFrame#billingAmountCard QLabel{border:none;background:transparent;}"
        )
        amount_layout = QHBoxLayout(amount_card)
        amount_layout.setContentsMargins(18, 14, 18, 14)
        amount_text = QVBoxLayout()
        amount_title = QLabel("Valor previsto da próxima fatura")
        amount_title.setStyleSheet("color:#475569;font-size:12px;font-weight:700;")
        self.amount_value = QLabel(self._money(self._estimated_amount))
        self.amount_value.setStyleSheet("color:#0F172A;font-size:24px;font-weight:800;")
        amount_hint = QLabel("O valor definitivo será confirmado pelo servidor ao gerar o pagamento.")
        amount_hint.setWordWrap(True)
        amount_hint.setStyleSheet("color:#64748B;font-size:11px;")
        amount_text.addWidget(amount_title)
        amount_text.addWidget(self.amount_value)
        amount_text.addWidget(amount_hint)
        amount_layout.addLayout(amount_text)
        layout.addWidget(amount_card)

        profile_card = QFrame()
        profile_card.setObjectName("billingProfileCard")
        profile_card.setStyleSheet(
            "QFrame#billingProfileCard{background:white;border:1px solid #D9E2EF;"
            "border-radius:12px;} QFrame#billingProfileCard QLabel{border:none;background:transparent;}"
        )
        profile_layout = QVBoxLayout(profile_card)
        profile_layout.setContentsMargins(18, 16, 18, 16)
        profile_title = QLabel("Dados para emissão do PIX ou boleto")
        profile_title.setStyleSheet("font-size:16px;font-weight:800;border:none;")
        profile_layout.addWidget(profile_title)
        form = QFormLayout()
        form.setVerticalSpacing(10)
        self.fields = {}
        for key, label in self.FIELD_LABELS:
            field = QLineEdit()
            field.setMinimumHeight(40)
            field.setStyleSheet(
                "QLineEdit{background:white;border:1px solid #CBD5E1;border-radius:8px;"
                "padding:8px;color:#0F172A;} QLineEdit:focus{border:2px solid #2563EB;}"
            )
            if key == "state":
                field.setMaxLength(2)
                field.setPlaceholderText("UF")
            self.fields[key] = field
            form.addRow(label, field)
        profile_layout.addLayout(form)
        self.save_button = QPushButton("Salvar dados de cobrança")
        self.save_button.setMinimumHeight(44)
        self.save_button.setStyleSheet(self._button("#2563EB"))
        self.save_button.clicked.connect(self._save_profile)
        profile_layout.addWidget(self.save_button)
        layout.addWidget(profile_card)

        payment_card = QFrame()
        payment_card.setObjectName("billingPaymentCard")
        payment_card.setStyleSheet(
            "QFrame#billingPaymentCard{background:white;border:1px solid #D9E2EF;"
            "border-radius:12px;} QFrame#billingPaymentCard QLabel{border:none;background:transparent;}"
        )
        payment_layout = QVBoxLayout(payment_card)
        payment_layout.setContentsMargins(18, 16, 18, 16)
        payment_title = QLabel("Escolha a forma de pagamento")
        payment_title.setStyleSheet("font-size:16px;font-weight:800;border:none;")
        payment_layout.addWidget(payment_title)
        note = QLabel("A validade é informada pelo provedor. Cada cobrança cobre as máquinas da emissão. "
                      "Se alterar os computadores, gere uma cobrança atualizada e não pague o código anterior.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#64748B;border:none;")
        payment_layout.addWidget(note)
        buttons = QHBoxLayout()
        self.pix_button = QPushButton("Gerar PIX")
        self.boleto_button = QPushButton("Gerar boleto")
        for button, color in ((self.pix_button, "#059669"), (self.boleto_button, "#D97706")):
            button.setMinimumHeight(46)
            button.setStyleSheet(self._button(color))
            buttons.addWidget(button)
        self.pix_button.clicked.connect(lambda: self._create_payment("pix"))
        self.boleto_button.clicked.connect(lambda: self._create_payment("boleto"))
        payment_layout.addLayout(buttons)
        self.result = QLabel("Nenhuma cobrança foi gerada nesta tela.")
        self.result.setWordWrap(True)
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.result.setStyleSheet(
            "background:#F8FAFC;border:1px dashed #CBD5E1;border-radius:8px;"
            "padding:12px;color:#475569;"
        )
        payment_layout.addWidget(self.result)
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setFixedSize(276, 276)
        self.qr_label.setStyleSheet(
            "background:white;border:1px solid #CBD5E1;border-radius:10px;padding:12px;"
        )
        self.qr_label.setVisible(False)
        qr_row = QHBoxLayout()
        qr_row.addStretch()
        qr_row.addWidget(self.qr_label)
        qr_row.addStretch()
        payment_layout.addLayout(qr_row)
        result_actions = QHBoxLayout()
        self.copy_button = QPushButton("Copiar código")
        self.open_button = QPushButton("Abrir pagamento")
        for button in (self.copy_button, self.open_button):
            button.setMinimumHeight(38)
            button.setStyleSheet(self._outline_button())
        self.copy_button.clicked.connect(self._copy_code)
        self.open_button.clicked.connect(self._open_payment)
        result_actions.addWidget(self.copy_button)
        result_actions.addWidget(self.open_button)
        result_actions.addStretch()
        payment_layout.addLayout(result_actions)
        self.check_status_button = QPushButton("Consultar status no Mercado Pago")
        self.check_status_button.setStyleSheet(self._outline_button())
        self.check_status_button.clicked.connect(self._check_provider_status)
        payment_layout.addWidget(self.check_status_button)
        layout.addWidget(payment_card)
        layout.addStretch()
        scroll.setWidget(page)
        root.addWidget(scroll)

        footer = QFrame()
        footer.setStyleSheet("QFrame{background:#E8EEF7;border-top:1px solid #CBD5E1;}")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 12, 18, 12)
        footer_layout.addStretch()
        close_button = QPushButton("Fechar")
        close_button.setMinimumWidth(130)
        close_button.setStyleSheet(self._button("#475569"))
        close_button.clicked.connect(self.reject)
        footer_layout.addWidget(close_button)
        root.addWidget(footer)
        self._set_busy(False)

    @staticmethod
    def _button(color):
        return (
            f"QPushButton{{background:{color};color:white;border:none;border-radius:8px;"
            "padding:10px 16px;font-weight:700;} QPushButton:disabled{background:#CBD5E1;color:#64748B;}"
        )

    @staticmethod
    def _outline_button():
        return (
            "QPushButton{background:white;color:#334155;border:1px solid #CBD5E1;"
            "border-radius:8px;padding:8px 14px;font-weight:700;}"
            "QPushButton:disabled{background:#F1F5F9;color:#94A3B8;}"
        )

    @staticmethod
    def _money(value):
        try:
            amount = Decimal(str(value or 0)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            amount = Decimal("0.00")
        return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _set_busy(self, busy):
        owner = self.role == "owner"
        self.save_button.setDisabled(busy or not owner)
        self.pix_button.setDisabled(busy or not owner or self._reconciliation_required)
        self.boleto_button.setDisabled(busy or not owner or self._reconciliation_required)
        self.copy_button.setDisabled(busy or not self._payment_code())
        self.open_button.setDisabled(busy or not self._payment_url())
        self.check_status_button.setDisabled(busy or not owner or not self._status_attempt_id)

    def _run(self, operation, success):
        if self._task:
            return
        self._set_busy(True)
        self._task = _BillingTask(operation, self)
        task = self._task

        def done(result):
            self._task = None
            try:
                success(result)
            except Exception as error:
                self._clear_payment()
                self._show_error(error)
            finally:
                self._set_busy(False)
                task.deleteLater()

        def failed(error):
            self._task = None
            self._clear_payment()
            self._set_busy(False)
            if isinstance(error, DesktopBackendError) and error.code == "EMAIL_OTP_REQUIRED":
                from src.ui.screens.email_confirmation_dialog import EmailConfirmationDialog
                if EmailConfirmationDialog(self.auth, self).exec() == QDialog.DialogCode.Accepted:
                    task.deleteLater()
                    self._run(operation, success)
                    return
            self._show_error(error)
            task.deleteLater()

        task.succeeded.connect(done)
        task.failed.connect(failed)
        self._task.start()

    def _load(self):
        self._run(lambda: self.auth.billing_summary(self.company_id), self._loaded)

    def _loaded(self, response):
        self._clear_payment()
        environment = str(response.get("payment_environment") or "").strip().lower()
        if environment not in {"test", "production"}:
            raise ValueError("INVALID_PAYMENT_ENVIRONMENT")
        self._payment_environment = environment
        if environment == "test":
            self.environment_banner.setText(
                "AMBIENTE DE TESTE — PIX e boleto são simulados e não movimentam dinheiro real."
            )
            self.environment_banner.setStyleSheet(
                "background:#FFF7ED;border:2px solid #F97316;border-radius:10px;"
                "padding:12px;color:#9A3412;font-size:13px;font-weight:900;"
            )
        else:
            self.environment_banner.setText(
                "AMBIENTE DE PRODUÇÃO — PIX e boleto gerados nesta tela são cobranças reais."
            )
            self.environment_banner.setStyleSheet(
                "background:#ECFDF5;border:2px solid #10B981;border-radius:10px;"
                "padding:12px;color:#065F46;font-size:13px;font-weight:900;"
            )
        invoices = list(response.get("invoices") or [])
        attempts = list(invoices[0].get("billing_payment_attempts") or []) if invoices else []
        self._status_attempt_id = str(next((row.get("id") for row in attempts
            if row.get("id") and row.get("status") == "pending"), "") or "")
        self._reconciliation_required = bool(response.get("reconciliation_required"))
        if response.get("reconciliation_required"):
            self.result.setText("Existe um pagamento em conferência. Não pague novamente. Contate o suporte.")
            return
        profile = dict(response.get("profile") or {})
        for key, field in self.fields.items():
            field.setText(str(profile.get(key) or self._defaults.get(key) or ""))
        invoices = list(response.get("invoices") or [])
        if invoices and invoices[0].get("status", "open") == "open":
            attempts = list(invoices[0].get("billing_payment_attempts") or [])
            pending = next((row for row in attempts if row.get("status") == "pending"), None)
            if pending:
                try:
                    invoice_amount = Decimal(str(invoices[0].get("total_amount") or 0))
                    current_amount = Decimal(str(self._estimated_amount))
                except (InvalidOperation, ValueError, TypeError):
                    invoice_amount = current_amount = Decimal("0")
                if self._estimated_amount is not None and invoice_amount != current_amount:
                    self._last_attempt = {}
                    self._show_pix_qr("")
                    self.pix_button.setText("Gerar PIX com valor atualizado")
                    self.result.setText(
                        f"A quantidade de computadores mudou. A cobrança anterior de "
                        f"{self._money(invoice_amount)} não será reutilizada.\n"
                        f"Gere uma nova cobrança no valor atualizado de {self._money(current_amount)}."
                    )
                else:
                    self._show_attempt(invoices[0], pending, reused=True)

    def _profile(self):
        return {key: field.text().strip() for key, field in self.fields.items()}

    def _save_profile(self):
        self._run(
            lambda: self.auth.save_billing_profile(self.company_id, self._profile()),
            lambda _response: QMessageBox.information(self, "Dados salvos", "Os dados de cobrança foram atualizados."),
        )

    def _create_payment(self, method):
        if self._task:
            return
        self._clear_payment()
        self.result.setText("Conferindo a fatura e os computadores no servidor...")
        self._run(
            lambda: self.auth.create_company_payment(self.company_id, method),
            lambda response: self._show_attempt(response.get("invoice") or {}, response.get("attempt") or {}, response.get("reused", False)),
        )

    def _show_attempt(self, invoice, attempt, reused=False):
        self._clear_payment()
        attempt_environment = str(attempt.get("provider_environment") or "").strip().lower()
        if attempt_environment in {"test", "production"}:
            if self._payment_environment and attempt_environment != self._payment_environment:
                raise ValueError("PAYMENT_ENVIRONMENT_MISMATCH")
        elif self._payment_environment:
            raise ValueError("INVALID_PAYMENT_ENVIRONMENT")
        if attempt.get("id"):
            self._status_attempt_id = str(attempt["id"])
        try:
            value = Decimal(str(invoice.get("total_amount")))
            if not value.is_finite() or value <= 0 or value != value.quantize(Decimal("0.01")):
                raise ValueError("INVALID_INVOICE_AMOUNT")
        except (InvalidOperation, TypeError):
            raise ValueError("INVALID_INVOICE_AMOUNT")
        if invoice.get("status", "open") != "open" or not self._attempt_payable(attempt):
            self.result.setText(self._unavailable_payment_message(invoice, attempt))
            return
        self._last_attempt = dict(attempt)
        self._last_attempt["invoice_id"] = invoice.get("id")
        self.amount_value.setText(self._money(value))
        self.pix_button.setText("Gerar PIX")
        method = "PIX" if attempt.get("payment_method") == "pix" else "boleto"
        amount = self._money(invoice.get("total_amount"))
        reused_text = " A tentativa existente foi reaproveitada com segurança." if reused else ""
        environment_text = (
            "AMBIENTE DE TESTE — esta cobrança não movimenta dinheiro real.\n"
            if attempt_environment == "test" else ""
        )
        boleto_test_note = (
            "\nA linha digitável foi recebida. A página externa do sandbox pode não ser exibida; "
            "isso não invalida a criação do boleto de teste."
            if method == "boleto" and attempt_environment == "test" else ""
        )
        self.result.setText(
            f"{environment_text}{method} da fatura no valor de {amount} gerado."
            f"{reused_text}\nO acesso será renovado somente após a confirmação do Mercado Pago."
            f"{boleto_test_note}"
        )
        if method == "boleto":
            self.copy_button.setText("Copiar linha digitável")
            self.open_button.setText("Abrir boleto no Mercado Pago")
        self._show_pix_qr(self._payment_code() if method == "PIX" else "")
        self._refresh_timer.start()

    @staticmethod
    def _unavailable_payment_message(invoice, attempt):
        if invoice.get("status") == "paid":
            return "Esta fatura consta como paga. Confira a vigência na Conta Empresarial."
        status = attempt.get("status")
        if status in {"refunded", "charged_back"}:
            return "Pagamento devolvido ou contestado. Consulte o suporte antes de pagar novamente."
        if invoice.get("status") == "cancelled" or status == "cancelled":
            return "Esta cobrança consta como cancelada no sistema. Não pague um código antigo salvo."
        if status == "expired":
            return "Esta tentativa consta como expirada. Não utilize o código antigo."
        if status in {"rejected", "failed"}:
            return "Esta tentativa de pagamento falhou ou foi recusada. Consulte o status antes de tentar novamente."
        if attempt.get("payable") is False:
            return "Esta cobrança não está liberada para pagamento pelo servidor. Pode exigir atualização ou conferência. O cancelamento no provedor não está confirmado nesta tela; não pague um código antigo."
        if attempt.get("expires_at"):
            return "O prazo informado para esta tentativa terminou ou não pôde ser validado. Não utilize o código antigo."
        return "Esta cobrança não está disponível para pagamento. Consulte o suporte antes de gerar outra."

    @staticmethod
    def _attempt_payable(attempt):
        if attempt.get("payable") is False or attempt.get("status", "pending") != "pending":
            return False
        if attempt.get("expires_at"):
            try:
                expiry = datetime.fromisoformat(str(attempt["expires_at"]).replace("Z", "+00:00"))
                if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
                    return False
            except (ValueError, TypeError):
                return False
        return True

    def _clear_payment(self):
        self._last_attempt = {}
        self._show_pix_qr("")
        self.copy_button.setText("Copiar código")
        self.open_button.setText("Abrir pagamento")
        self.copy_button.setEnabled(False)
        self.open_button.setEnabled(False)

    def _check_provider_status(self):
        if self._task or self.role != "owner" or not self._status_attempt_id:
            return
        attempt_id = self._status_attempt_id

        def operation():
            result = self.auth.refresh_company_payment(self.company_id, attempt_id)
            summary = self.auth.billing_summary(self.company_id)
            return result, summary

        def received(response):
            result, summary = response
            self._loaded(summary)
            outcome = result.get("result") or {}
            payment_method = str(self._last_attempt.get("payment_method") or "pix").lower()
            payment_name = "boleto" if payment_method == "boleto" else "PIX"
            if outcome.get("reconciliation_required") or summary.get("reconciliation_required"):
                message = "Pagamento em conferência. Não pague novamente; contate o suporte."
            elif outcome.get("invoice_status") == "paid":
                message = (
                    "Pagamento confirmado pelo provedor. "
                    "Atualize a Conta Empresarial para conferir a vigência."
                )
            elif outcome.get("attempt_status") == "pending":
                message = (
                    "Mercado Pago consultado: o pagamento ainda aguarda confirmação. "
                    f"Não gere outro {payment_name}; consulte novamente mais tarde."
                )
            elif outcome.get("attempt_status") in {"rejected", "cancelled", "expired", "refunded"}:
                message = (
                    "Mercado Pago consultado: esta tentativa não está mais disponível para pagamento. "
                    "Atualize a cobrança antes de tentar novamente."
                )
            else:
                message = (
                    "Consulta concluída, mas o provedor ainda não informou um estado final. "
                    "Não gere outro pagamento; tente consultar novamente mais tarde."
                )
            self.result.setText(message)
            QMessageBox.information(self, "Status do pagamento", message)

        self.result.setText("Consultando o Mercado Pago. Não gere outro pagamento enquanto aguarda.")
        self._run(operation, received)

    def _refresh_payment(self):
        if self._task or not self._last_attempt.get("id"):
            return
        attempt_id = self._last_attempt["id"]
        def received(response):
            self._reconciliation_required = bool(response.get("reconciliation_required"))
            if response.get("reconciliation_required"):
                self._clear_payment()
                self.result.setText("Pagamento em conferência. Não pague novamente; contate o suporte.")
                return
            for invoice in response.get("invoices") or []:
                for attempt in invoice.get("billing_payment_attempts") or []:
                    if attempt.get("id") == attempt_id:
                        self._show_attempt(invoice, attempt, reused=True)
                        return
            self._clear_payment()
            self.result.setText("Cobrança atualizada no servidor. Gere ou consulte o pagamento novamente.")
        self._run(lambda: self.auth.billing_summary(self.company_id), received)

    def reject(self):
        if self._task:
            return
        self._refresh_timer.stop()
        super().reject()

    def closeEvent(self, event):
        if self._task:
            event.ignore()
            return
        self._refresh_timer.stop()
        super().closeEvent(event)

    def _show_pix_qr(self, code):
        if not code:
            self.qr_label.clear()
            self.qr_label.setVisible(False)
            return
        qr = qrcode.QRCode(box_size=8, border=2)
        qr.add_data(code)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        image = image.resize((250, 250), Image.Resampling.NEAREST)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        pixmap = QPixmap()
        if not pixmap.loadFromData(buffer.getvalue(), "PNG"):
            raise ValueError("QR_RENDER_FAILED")
        self.qr_label.setPixmap(pixmap)
        self.qr_label.setVisible(True)

    def _payment_code(self):
        if not self._attempt_payable(self._last_attempt):
            return ""
        return str(self._last_attempt.get("pix_copy_paste") or self._last_attempt.get("boleto_barcode") or "")

    def _payment_url(self):
        url = str(self._last_attempt.get("payment_url") or "")
        return url if self._attempt_payable(self._last_attempt) and QUrl(url).scheme() == "https" else ""

    def _copy_code(self):
        code = self._payment_code()
        if code:
            QGuiApplication.clipboard().setText(code)
            QMessageBox.information(self, "Código copiado", "O código de pagamento foi copiado.")

    def _open_payment(self):
        url = self._payment_url()
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _show_error(self, error):
        messages = {
            "PAYMENT_RECONCILIATION_REQUIRED": "Um pagamento precisa de conferência. Não pague novamente; contate o suporte.",
            "PAYMENT_REPRICE_CANCELLATION_FAILED": "O cancelamento da cobrança anterior ainda não foi confirmado. Aguarde e tente novamente.",
            "PAYMENT_METHOD_ALREADY_PENDING": "Já existe uma cobrança em outro meio de pagamento. Conclua ou cancele a anterior antes de trocar.",
            "INVOICE_CHANGED": "Os computadores ou valores mudaram. Atualize a cobrança antes de pagar.",
            "BILLING_PROFILE_REQUIRED": "Salve os dados de cobrança antes de gerar o pagamento.",
            "INVALID_BILLING_PROFILE": "Confira CPF ou CNPJ, e-mail, CEP e endereço de cobrança.",
            "OWNER_REQUIRED": "Somente o proprietário pode alterar dados ou gerar a cobrança.",
            "EMAIL_OTP_REQUIRED": "Confirme esta alteração com o código enviado ao seu e-mail.",
            "PAYMENT_PROVIDER_ERROR": "O Mercado Pago não conseguiu concluir a operação. Não pague novamente; consulte o status mais tarde.",
            "PAYMENT_RATE_LIMITED": "Aguarde pelo menos 30 segundos antes de consultar ou tentar novamente.",
            "PAYMENT_NOT_RECORDED": "A cobrança ainda não possui identificador confirmado no provedor. Contate o suporte; não pague novamente.",
            "PAYMENT_NOT_FOUND": "Cobrança não encontrada nesta conta. Atualize os dados e tente novamente.",
        }
        if isinstance(error, DesktopBackendError):
            if error.code == "PAYMENT_RECONCILIATION_REQUIRED":
                self._reconciliation_required = True
                self._set_busy(False)
            message = messages.get(error.code, friendly_desktop_error(error))
            provider_code = str(error.details.get("provider_code") or "").strip()
            support_code = str(error.details.get("support_code") or "").strip()
            if error.code == "PAYMENT_PROVIDER_ERROR" and provider_code:
                message += f"\n\nMotivo técnico: {provider_code}"
            if support_code:
                message += f"\nCódigo para o suporte: {support_code}"
        else:
            message = "Não foi possível concluir a operação de cobrança."
        QMessageBox.warning(self, "Cobrança empresarial", message)
