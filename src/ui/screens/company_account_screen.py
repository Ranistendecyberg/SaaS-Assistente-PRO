from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from src.core.supabase_auth import SupabaseUserClient
from src.core.supabase_desktop import DesktopBackendError, friendly_desktop_error
from src.core.v2_business_rules import can_manage_company, can_transfer_principal


class _AccountTask(QThread):
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


class CompanyAccountScreen(QWidget):
    """Painel da empresa, unidades e computadores vinculados na versao 2.0."""

    COLORS = {
        "ink": "#0F172A", "muted": "#64748B", "line": "#D9E2EF",
        "blue": "#2563EB", "navy": "#162B63", "green": "#059669",
        "amber": "#D97706", "red": "#DC2626", "surface": "#FFFFFF",
        "background": "#F4F7FB",
    }

    def __init__(self, parent=None, auth_client=None):
        super().__init__(parent)
        self.auth = auth_client or SupabaseUserClient()
        self._task = None
        self._company_id = ""
        self._role = ""
        self._company = {}
        self._estimated_amount = Decimal("0")
        self._additional_seat_price = Decimal("0")
        self._subscription_allows_links = False
        self._subscription_expiry = ""
        self._units = []
        self._installations = []
        self._login_prompt_open = False
        self.setStyleSheet(f"background:{self.COLORS['background']}; color:{self.COLORS['ink']};")
        self._build_ui()

    @staticmethod
    def _date(value):
        if not value:
            return "—"
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return str(value)

    @staticmethod
    def _money(value):
        try:
            amount = Decimal(str(value or 0)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            amount = Decimal("0.00")
        return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _build_ui(self):
        viewport_layout = QVBoxLayout(self)
        viewport_layout.setContentsMargins(0, 0, 0, 0)
        viewport_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setStyleSheet(
            "QScrollArea{background:#F4F7FB;border:none;}"
            "QScrollBar:vertical{background:#E8EEF7;width:11px;margin:4px 2px;}"
            "QScrollBar::handle:vertical{background:#94A3B8;border-radius:5px;min-height:36px;}"
            "QScrollBar::handle:vertical:hover{background:#64748B;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )
        page = QWidget()
        page.setStyleSheet(f"background:{self.COLORS['background']};")
        root = QVBoxLayout(page)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(16)
        self.scroll_area.setWidget(page)
        viewport_layout.addWidget(self.scroll_area)

        heading = QHBoxLayout()
        titles = QVBoxLayout()
        self.title = QLabel("Conta Empresarial")
        self.title.setStyleSheet("font-size:28px;font-weight:800;color:#0F172A;")
        self.subtitle = QLabel("Empresa, unidades, computadores e cobrança consolidada")
        self.subtitle.setWordWrap(True)
        self.subtitle.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.subtitle.setStyleSheet("font-size:13px;color:#64748B;")
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        heading.addLayout(titles)
        heading.addStretch()
        self.refresh_button = QPushButton("Atualizar dados")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setStyleSheet(self._button_style(self.COLORS["blue"]))
        self.refresh_button.clicked.connect(self.refresh_data)
        heading.addWidget(self.refresh_button)
        root.addLayout(heading)

        self.banner = QFrame()
        self.banner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.banner.setFixedHeight(112)
        self.banner.setStyleSheet("QFrame{background:#162B63;border-radius:16px;}")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(22, 18, 22, 18)
        banner_text = QVBoxLayout()
        banner_text.setSpacing(4)
        banner_text.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.company_name = QLabel("Carregando conta empresarial...")
        self.company_name.setWordWrap(True)
        self.company_name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.company_name.setStyleSheet("font-size:22px;font-weight:800;color:white;")
        self.company_meta = QLabel("Conectando ao servidor seguro")
        self.company_meta.setWordWrap(True)
        self.company_meta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.company_meta.setStyleSheet("font-size:12px;color:#BFDBFE;")
        banner_text.addWidget(self.company_name)
        banner_text.addWidget(self.company_meta)
        banner_layout.addLayout(banner_text, 1)
        self.role_badge = QLabel("—")
        self.role_badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.role_badge.setStyleSheet(
            "background:#DBEAFE;color:#1D4ED8;border-radius:12px;padding:7px 12px;font-weight:700;"
        )
        banner_layout.addWidget(self.role_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self.banner, 0)

        cards = QHBoxLayout()
        self.status_value, status_card = self._metric_card("ASSINATURA", "—", "Situação contratual")
        self.devices_value, devices_card = self._metric_card("COMPUTADORES", "—", "Principal e adicionais")
        self.price_value, price_card = self._metric_card("VALOR CONSOLIDADO", "—", "Estimativa mensal atual")
        self.expiry_value, expiry_card = self._metric_card("VIGÊNCIA", "—", "Trial ou período contratado")
        for card in (status_card, devices_card, price_card, expiry_card):
            cards.addWidget(card, 1)
        root.addLayout(cards)

        content = QHBoxLayout()
        content.setSpacing(16)

        units_card = self._section("Unidades e documentos", "Matriz e filiais autorizadas na conta")
        units_layout = units_card.layout()
        self.units_table = self._table(["Unidade", "Tipo", "CPF / CNPJ", "Status"])
        self.units_table.setMinimumHeight(150)
        units_layout.addWidget(self.units_table)
        content.addWidget(units_card, 5)

        link_card = self._section(
            "Adicionar computador",
            "Escolha a unidade e gere um código de ativação válido por 15 minutos.",
        )
        link_layout = link_card.layout()
        self.unit_combo = QComboBox()
        self.unit_combo.setMinimumHeight(42)
        self.unit_combo.setStyleSheet(self._field_style())
        unit_prompt = QLabel("Unidade que utilizará o computador")
        unit_prompt.setWordWrap(True)
        unit_prompt.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        link_layout.addWidget(unit_prompt)
        link_layout.addWidget(self.unit_combo)
        self.link_price_hint = QLabel("O valor adicional será exibido após carregar a conta.")
        self.link_price_hint.setWordWrap(True)
        self.link_price_hint.setStyleSheet("color:#475569;font-size:11px;font-weight:600;")
        link_layout.addWidget(self.link_price_hint)
        self.link_button = QPushButton("Gerar código de ativação")
        self.link_button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.link_button.setMinimumHeight(44)
        self.link_button.setStyleSheet(self._button_style(self.COLORS["green"]))
        self.link_button.clicked.connect(self.issue_link_code)
        link_layout.addWidget(self.link_button)
        self.link_result = QLabel("O código será exibido somente uma vez.")
        self.link_result.setWordWrap(True)
        self.link_result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.link_result.setStyleSheet(
            "background:#F8FAFC;border:1px dashed #CBD5E1;border-radius:10px;"
            "padding:12px;color:#475569;font-size:12px;"
        )
        link_layout.addWidget(self.link_result)
        self.copy_link_button = QPushButton("Copiar código")
        self.copy_link_button.setStyleSheet(self._outline_button_style())
        self.copy_link_button.setEnabled(False)
        self.copy_link_button.clicked.connect(self._copy_link_code)
        link_layout.addWidget(self.copy_link_button)
        link_layout.addStretch()
        content.addWidget(link_card, 3)
        root.addLayout(content, 3)

        devices_card = self._section("Computadores vinculados", "Selecione um adicional para programar ou cancelar a remoção")
        devices_layout = devices_card.layout()
        self.devices_table = self._table([
            "Computador", "Unidade", "Classe", "Situação", "Versão", "Último acesso",
        ])
        self.devices_table.setMinimumHeight(150)
        self.devices_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.devices_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        devices_layout.addWidget(self.devices_table)
        actions = QHBoxLayout()
        actions.addStretch()
        self.transfer_principal_button = QPushButton("Tornar Principal")
        self.transfer_principal_button.setStyleSheet(self._outline_button_style())
        self.transfer_principal_button.clicked.connect(self.transfer_selected_principal)
        self.cancel_removal_button = QPushButton("Cancelar remoção")
        self.cancel_removal_button.setStyleSheet(self._outline_button_style())
        self.cancel_removal_button.clicked.connect(self.cancel_selected_removal)
        self.remove_button = QPushButton("Programar remoção")
        self.remove_button.setStyleSheet(self._button_style(self.COLORS["red"]))
        self.remove_button.clicked.connect(self.schedule_selected_removal)
        actions.addWidget(self.transfer_principal_button)
        actions.addWidget(self.cancel_removal_button)
        actions.addWidget(self.remove_button)
        devices_layout.addLayout(actions)
        root.addWidget(devices_card, 4)

        billing_card = self._section(
            "Cobrança consolidada",
            "Atualize os dados fiscais e escolha PIX ou boleto para a fatura empresarial.",
        )
        billing_layout = billing_card.layout()
        self.billing_button = QPushButton("Abrir cobrança e pagamentos")
        self.billing_button.setMinimumHeight(46)
        self.billing_button.setStyleSheet(self._button_style(self.COLORS["blue"]))
        self.billing_button.clicked.connect(self.open_billing)
        billing_layout.addWidget(self.billing_button)
        root.addWidget(billing_card)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._company_id and not self._task:
            QTimer.singleShot(0, self._ensure_authenticated)

    def _ensure_authenticated(self):
        if self._login_prompt_open or self._task or self._company_id:
            return
        if self.auth.load_session():
            self.refresh_data()
            return

        from src.ui.screens.user_login_dialog import UserLoginDialog

        self._login_prompt_open = True
        dialog = UserLoginDialog(self.auth, self)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        self._login_prompt_open = False
        if accepted:
            self.refresh_data()

    def _section(self, title, subtitle):
        card = QFrame()
        card.setStyleSheet("QFrame{background:white;border:1px solid #D9E2EF;border-radius:14px;}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        label = QLabel(title)
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        label.setStyleSheet("font-size:16px;font-weight:800;color:#0F172A;border:none;")
        description = QLabel(subtitle)
        description.setWordWrap(True)
        description.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        description.setStyleSheet("font-size:11px;color:#64748B;border:none;")
        layout.addWidget(label)
        layout.addWidget(description)
        return card

    def _metric_card(self, label, value, hint):
        card = QFrame()
        card.setStyleSheet("QFrame{background:white;border:1px solid #D9E2EF;border-radius:14px;}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        caption = QLabel(label)
        caption.setWordWrap(True)
        caption.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        caption.setStyleSheet("font-size:10px;font-weight:800;color:#64748B;border:none;")
        amount = QLabel(value)
        amount.setWordWrap(True)
        amount.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        amount.setStyleSheet("font-size:22px;font-weight:800;color:#0F172A;border:none;")
        detail = QLabel(hint)
        detail.setWordWrap(True)
        detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        detail.setStyleSheet("font-size:10px;color:#94A3B8;border:none;")
        layout.addWidget(caption)
        layout.addWidget(amount)
        layout.addWidget(detail)
        return amount, card

    @staticmethod
    def _table(headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setStyleSheet(
            "QTableWidget{background:white;border:1px solid #E2E8F0;border-radius:8px;"
            "gridline-color:#E2E8F0;alternate-background-color:#F8FAFC;}"
            "QHeaderView::section{background:#EEF2F7;color:#475569;font-weight:700;"
            "border:none;padding:8px;} QTableWidget::item{padding:7px;}"
            "QTableWidget::item:selected{background:#DBEAFE;color:#1E3A8A;}"
        )
        return table

    @staticmethod
    def _field_style():
        return (
            "QComboBox{background:white;border:1px solid #CBD5E1;border-radius:8px;"
            "padding:8px;color:#0F172A;} QComboBox:focus{border:2px solid #2563EB;}"
        )

    @staticmethod
    def _button_style(color):
        return (
            f"QPushButton{{background:{color};color:white;border:none;border-radius:8px;"
            "padding:10px 16px;font-weight:700;} QPushButton:hover{border:2px solid #BFDBFE;}"
            "QPushButton:disabled{background:#CBD5E1;color:#64748B;}"
        )

    @staticmethod
    def _outline_button_style():
        return (
            "QPushButton{background:white;color:#334155;border:1px solid #CBD5E1;"
            "border-radius:8px;padding:10px 16px;font-weight:700;}"
            "QPushButton:hover{background:#F8FAFC;} QPushButton:disabled{color:#94A3B8;}"
        )

    def _run(self, operation, success, failure=None):
        if self._task:
            return
        self._set_busy(True)
        self._task = _AccountTask(operation, self)
        task = self._task

        def succeeded(result):
            self._task = None
            success(result)
            task.deleteLater()

        def failed(error):
            self._task = None
            if failure:
                failure(error)
            else:
                self._show_error(error)
            task.deleteLater()

        task.succeeded.connect(succeeded)
        task.failed.connect(failed)
        self._task.start()

    def _set_busy(self, busy):
        self.refresh_button.setDisabled(busy)
        self.link_button.setDisabled(
            busy or not can_manage_company(self._role) or
            not self._subscription_allows_links or self.unit_combo.count() == 0
        )
        self.copy_link_button.setDisabled(busy or not bool(self.copy_link_button.property("code")))
        self.remove_button.setDisabled(busy or not can_manage_company(self._role))
        self.cancel_removal_button.setDisabled(busy or not can_manage_company(self._role))
        self.transfer_principal_button.setDisabled(busy or not can_transfer_principal(self._role))
        self.billing_button.setDisabled(busy or not self._company_id)

    def open_billing(self):
        if not self._company_id:
            return
        from src.ui.screens.billing_dialog import BillingDialog

        headquarters = next(
            (unit for unit in self._units if unit.get("unit_type") == "headquarters"),
            self._units[0] if self._units else {},
        )
        BillingDialog(
            self.auth,
            self._company_id,
            self._role,
            self,
            defaults={
                "legal_name": str(self._company.get("name") or ""),
                "billing_cnpj": self._format_cnpj(headquarters.get("cnpj")),
            },
            estimated_amount=self._estimated_amount,
        ).exec()

    def refresh_data(self):
        def operation():
            listed = self.auth.list_companies()
            memberships = list(listed.get("memberships") or [])
            if not memberships:
                raise DesktopBackendError("COMPANY_REQUIRED")
            membership = memberships[0]
            company_id = str(membership.get("company_id") or "")
            summary = self.auth.account_summary(company_id)
            summary["membership_role"] = membership.get("role")
            return summary

        self._run(operation, self._render_summary, self._handle_refresh_failure)

    def _handle_refresh_failure(self, error):
        if isinstance(error, DesktopBackendError) and error.code in {
            "USER_SESSION_REQUIRED", "UNAUTHORIZED", "INVALID_JWT", "JWT_EXPIRED",
        }:
            self.auth.clear_session()
            QTimer.singleShot(0, self._ensure_authenticated)
            return
        if isinstance(error, DesktopBackendError) and error.code == "COMPANY_REQUIRED":
            answer = QMessageBox.question(
                self,
                "Conta empresarial não encontrada",
                "O e-mail informado não está cadastrado em nenhuma conta empresarial.\n\n"
                "Deseja entrar com outro e-mail?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.auth.clear_session()
                QTimer.singleShot(0, self._ensure_authenticated)
            else:
                self._set_busy(False)
            return
        self._show_error(error)

    def _render_summary(self, summary):
        self._company_id = str((summary.get("company") or {}).get("id") or "")
        self._role = str(summary.get("role") or summary.get("membership_role") or "")
        company = dict(summary.get("company") or {})
        self._company = company
        subscription = dict(summary.get("subscription") or {})
        self._units = list(summary.get("units") or [])
        self._installations = list(summary.get("installations") or [])

        role_names = {"owner": "Proprietário", "admin": "Administrador", "operator": "Operador"}
        self.company_name.setText(str(company.get("name") or "Conta empresarial"))
        self.company_meta.setText(
            f"Responsável: {company.get('manager_name') or '—'}  •  Contato: {company.get('phone') or '—'}"
        )
        self.role_badge.setText(role_names.get(self._role, self._role or "Usuário"))
        status_names = {
            "trial": "Teste gratuito", "active": "Ativa", "past_due": "Pendente",
            "suspended": "Suspensa", "cancelled": "Cancelada",
        }
        self.status_value.setText(status_names.get(subscription.get("status"), "—"))

        billable = [row for row in self._installations if row.get("billing_status") != "removed"]
        additional = max(0, len(billable) - 1)
        try:
            base = Decimal(str(subscription.get("base_price") or 0))
            unit_price = Decimal(str(subscription.get("additional_seat_price") or 0))
        except (InvalidOperation, ValueError):
            base = Decimal("0")
            unit_price = Decimal("0")
        self._additional_seat_price = unit_price
        self._estimated_amount = base + unit_price * additional if billable else Decimal("0")
        self.devices_value.setText(str(len(billable)))
        self.price_value.setText(self._money(self._estimated_amount))
        expiry = subscription.get("current_period_end") or subscription.get("trial_expires_at")
        self._subscription_expiry = str(expiry or "")
        self._subscription_allows_links = self._subscription_is_active(subscription)
        if self._subscription_allows_links:
            next_amount = self._estimated_amount + self._additional_seat_price
            self.link_price_hint.setText(
                f"Valor atual: {self._money(self._estimated_amount)}/mês. "
                f"Com o próximo computador: {self._money(next_amount)}/mês "
                f"(+ {self._money(self._additional_seat_price)})."
            )
            self.link_button.setText("Gerar código de ativação")
        else:
            expiry_text = self._date(expiry).split(" ")[0]
            self.link_price_hint.setText(
                f"Assinatura vencida em {expiry_text}. Renove a assinatura para adicionar um computador."
            )
            self.link_button.setText("Assinatura vencida")
            if subscription.get("status") == "trial":
                self.status_value.setText("Teste vencido")
        self.expiry_value.setText(self._date(expiry).split(" ")[0])
        self._fill_units()
        self._fill_installations()
        self._set_busy(False)

    def _fill_units(self):
        self.units_table.setRowCount(len(self._units))
        self.unit_combo.clear()
        for row, unit in enumerate(self._units):
            values = [
                unit.get("display_name") or "—",
                "Matriz" if unit.get("unit_type") == "headquarters" else "Filial",
                self._format_cnpj(unit.get("cnpj")),
                "Ativa" if unit.get("active") else "Inativa",
            ]
            for column, value in enumerate(values):
                self.units_table.setItem(row, column, QTableWidgetItem(str(value)))
            if unit.get("active"):
                self.unit_combo.addItem(str(unit.get("display_name") or "Unidade"), str(unit.get("id") or ""))

    def _fill_installations(self):
        units = {str(unit.get("id")): unit.get("display_name") for unit in self._units}
        self.devices_table.setRowCount(len(self._installations))
        for row, installation in enumerate(self._installations):
            hardware = str(installation.get("hardware_id") or "")
            values = [
                self._masked_hardware(hardware),
                units.get(str(installation.get("business_unit_id")), "—"),
                "Principal" if installation.get("device_class") == "principal" else "Adicional",
                self._billing_label(installation.get("billing_status")),
                installation.get("app_version") or "—",
                self._date(installation.get("last_seen_at")),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, str(installation.get("id") or ""))
                self.devices_table.setItem(row, column, item)

    @staticmethod
    def _format_cnpj(value):
        digits = "".join(filter(str.isdigit, str(value or "")))
        if len(digits) == 11:
            return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
        if len(digits) != 14:
            return digits or "—"
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"

    @staticmethod
    def _masked_hardware(value):
        value = str(value or "")
        if len(value) <= 12:
            return value or "—"
        return f"{value[:6]}…{value[-6:]}"

    @staticmethod
    def _billing_label(value):
        return {
            "active": "Ativo", "pending_removal": "Remoção programada",
            "blocked": "Bloqueado", "removed": "Removido",
        }.get(value, str(value or "—"))

    @staticmethod
    def _subscription_is_active(subscription):
        if subscription.get("status") not in {"trial", "active"}:
            return False
        expiry = subscription.get("current_period_end") or subscription.get("trial_expires_at")
        if not expiry:
            return False
        try:
            parsed = datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
            now = datetime.now(parsed.tzinfo) if parsed.tzinfo else datetime.now()
            return parsed > now
        except (TypeError, ValueError):
            return False

    def issue_link_code(self):
        if not self._subscription_allows_links:
            expiry = self._date(self._subscription_expiry).split(" ")[0]
            QMessageBox.warning(
                self, "Assinatura vencida",
                f"A assinatura venceu em {expiry}. Renove-a antes de adicionar outro computador.",
            )
            return
        unit_id = str(self.unit_combo.currentData() or "")
        self._run(
            lambda: self.auth.issue_device_link_code(self._company_id, unit_id),
            self._link_code_created,
        )

    def _link_code_created(self, result):
        code = str(result.get("link_code") or "")
        expires = self._date((result.get("code") or {}).get("expires_at"))
        self.link_result.setText(
            f"CÓDIGO: {code}\nVálido até: {expires}\n"
            "No outro computador, escolha Computador adicional e digite este código.\n"
            "O vínculo altera a próxima cobrança. Não pague um PIX emitido antes da alteração. "
            "Máquinas novas não herdam automaticamente um período já pago."
        )
        self.link_result.setStyleSheet(
            "background:#ECFDF5;border:2px solid #10B981;border-radius:10px;"
            "padding:12px;color:#064E3B;font-size:14px;font-weight:700;"
        )
        self.copy_link_button.setProperty("code", code)
        self._copy_link_code()
        self._set_busy(False)
        QMessageBox.information(self, "Código criado", "O código foi copiado para a área de transferência.")

    def _copy_link_code(self):
        code = str(self.copy_link_button.property("code") or "")
        if not code:
            return
        try:
            QGuiApplication.clipboard().setText(code)
        except Exception:
            return

    def _selected_installation(self):
        row = self.devices_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selecione um computador", "Escolha um computador adicional na tabela.")
            return None
        return self._installations[row]

    def transfer_selected_principal(self):
        installation = self._selected_installation()
        if not installation:
            return
        if installation.get("device_class") == "principal":
            QMessageBox.warning(
                self, "Já é principal",
                "O computador selecionado já é o principal da empresa.",
            )
            return
        answer = QMessageBox.question(
            self, "Transferir Principal",
            "Deseja tornar este computador o PRINCIPAL da empresa?\n\nO computador principal atual será rebaixado para adicional.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._run_secured(
            lambda: self.auth.transfer_principal(installation.get("id")),
            lambda _result: self.refresh_data(),
        )

    def schedule_selected_removal(self):
        installation = self._selected_installation()
        if not installation:
            return
        if installation.get("device_class") == "principal":
            QMessageBox.warning(
                self, "Computador principal",
                "O computador principal não pode ser removido por esta opção.",
            )
            return
        answer = QMessageBox.question(
            self, "Programar remoção",
            "Este computador continuará faturável até o fim do período vigente. Deseja programar a remoção?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._run_secured(
            lambda: self.auth.schedule_device_removal(self._company_id, installation.get("id")),
            lambda _result: self.refresh_data(),
        )

    def cancel_selected_removal(self):
        installation = self._selected_installation()
        if not installation:
            return
        self._run_secured(
            lambda: self.auth.cancel_device_removal(self._company_id, installation.get("id")),
            lambda _result: self.refresh_data(),
        )

    def _run_secured(self, operation, success):
        self._run(
            operation,
            success,
            lambda error: self._handle_secured_error(error, operation, success),
        )

    def _handle_secured_error(self, error, operation, success):
        self._set_busy(False)
        if not isinstance(error, DesktopBackendError) or error.code != "EMAIL_OTP_REQUIRED":
            self._show_error(error)
            return
        from src.ui.screens.email_confirmation_dialog import EmailConfirmationDialog

        dialog = EmailConfirmationDialog(self.auth, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # O código por e-mail devolve uma nova sessão OTP. Somente então a
            # mesma operação autorizada pelo usuário é repetida.
            self._run_secured(operation, success)

    def _show_error(self, error):
        self._set_busy(False)
        messages = {
            "COMPANY_REQUIRED": "Nenhuma conta empresarial foi encontrada para este usuário.",
            "EMAIL_OTP_REQUIRED": "Confirme esta alteração com o código enviado ao seu e-mail.",
            "FORBIDDEN": "Seu perfil não possui permissão para realizar esta alteração.",
            "PRINCIPAL_TRANSFER_REQUIRED": "O computador principal exige um processo de transferência.",
            "REMOVAL_NOT_PENDING": "Este computador não possui remoção programada.",
            "SUBSCRIPTION_NOT_ACTIVE": (
                "A assinatura está vencida ou inativa. Renove-a antes de adicionar outro computador."
            ),
            "SUBSCRIPTION_EXPIRED": (
                "A assinatura venceu. Renove-a antes de adicionar outro computador."
            ),
            "LINK_CODE_RATE_LIMITED": (
                "Foram gerados muitos códigos. Aguarde 10 minutos e tente novamente."
            ),
        }
        if isinstance(error, DesktopBackendError):
            message = messages.get(error.code, friendly_desktop_error(error))
        else:
            message = "Não foi possível carregar a conta empresarial. Tente novamente."
        QMessageBox.warning(self, "Conta empresarial", message)
