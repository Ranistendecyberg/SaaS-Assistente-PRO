from __future__ import annotations

from io import BytesIO

import qrcode
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QVBoxLayout,
)

from src.core.supabase_desktop import DesktopBackendError


class _MfaTask(QThread):
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


class MfaDialog(QDialog):
    """Eleva a sessão do usuário para AAL2 com TOTP.

    Se ainda não existir um autenticador verificado, o diálogo inicia o
    cadastro e mostra QR code e chave manual. Nenhum segredo é persistido.
    """

    def __init__(self, auth_client, parent=None):
        super().__init__(parent)
        self.auth = auth_client
        self._task = None
        self._factor_id = ""
        self._enrolling = False
        self.setWindowTitle("Confirmação de segurança")
        self.setModal(True)
        self.setMinimumWidth(470)
        self.setStyleSheet("background:#F8FAFC;color:#0F172A;")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        title = QLabel("🔐 Confirmação de segurança")
        title.setStyleSheet("font-size:22px;font-weight:800;color:#0F172A;")
        root.addWidget(title)
        self.instructions = QLabel("Verificando o seu autenticador...")
        self.instructions.setWordWrap(True)
        self.instructions.setStyleSheet("font-size:13px;color:#475569;")
        root.addWidget(self.instructions)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setVisible(False)
        root.addWidget(self.qr_label)

        self.secret_label = QLabel()
        self.secret_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.secret_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.secret_label.setWordWrap(True)
        self.secret_label.setVisible(False)
        self.secret_label.setStyleSheet(
            "background:white;border:1px dashed #CBD5E1;border-radius:8px;"
            "padding:10px;color:#334155;font-family:Consolas;"
        )
        root.addWidget(self.secret_label)

        self.code = QLineEdit()
        self.code.setPlaceholderText("Código de 6 números")
        self.code.setMaxLength(6)
        self.code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code.setEnabled(False)
        self.code.setStyleSheet(
            "QLineEdit{background:white;border:2px solid #CBD5E1;border-radius:9px;"
            "padding:11px;font-size:18px;font-weight:700;letter-spacing:5px;}"
            "QLineEdit:focus{border-color:#2563EB;}"
        )
        self.code.returnPressed.connect(self._verify)
        root.addWidget(self.code)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        cancel.setStyleSheet(
            "QPushButton{background:white;color:#334155;border:1px solid #CBD5E1;"
            "border-radius:8px;padding:10px 18px;font-weight:700;}"
        )
        self.confirm = QPushButton("Confirmar código")
        self.confirm.setEnabled(False)
        self.confirm.clicked.connect(self._verify)
        self.confirm.setStyleSheet(
            "QPushButton{background:#2563EB;color:white;border:none;border-radius:8px;"
            "padding:10px 18px;font-weight:700;}"
            "QPushButton:disabled{background:#CBD5E1;color:#64748B;}"
        )
        actions.addWidget(cancel)
        actions.addWidget(self.confirm)
        root.addLayout(actions)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._factor_id and not self._task:
            self._load_factor()

    def _run(self, operation, success):
        if self._task:
            return
        self.confirm.setDisabled(True)
        self._task = _MfaTask(operation, self)
        task = self._task

        def succeeded(result):
            self._task = None
            try:
                success(result)
            except Exception as error:
                self._show_error(error)
            task.deleteLater()

        def failed(error):
            self._task = None
            self.confirm.setEnabled(bool(self._factor_id))
            self._show_error(error)
            task.deleteLater()

        task.succeeded.connect(succeeded)
        task.failed.connect(failed)
        self._task.start()

    def _load_factor(self):
        def ready(result):
            factors = list(result.get("totp") or [])
            if factors:
                self._factor_id = str(factors[0].get("id") or "")
                self.instructions.setText(
                    "Abra o aplicativo autenticador e informe o código atual. "
                    "Esta confirmação protege alterações na conta empresarial."
                )
                self._enable_code()
                return
            self._enrolling = True
            self.instructions.setText("Preparando o cadastro do autenticador...")
            self._run(self.auth.enroll_totp, self._enrollment_ready)

        self._run(self.auth.list_mfa_factors, ready)

    def _enrollment_ready(self, result):
        self._factor_id = str(result.get("id") or "")
        totp = dict(result.get("totp") or {})
        uri = str(totp.get("uri") or "")
        secret = str(totp.get("secret") or "")
        if not self._factor_id or not uri:
            self._show_error(DesktopBackendError("INVALID_SERVER_RESPONSE"))
            return
        qr = qrcode.QRCode(box_size=7, border=2)
        qr.add_data(uri)
        qr.make(fit=True)
        image = qr.make_image(fill_color="#0F172A", back_color="white")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        pixmap = QPixmap()
        if not pixmap.loadFromData(buffer.getvalue(), "PNG"):
            self._show_error(DesktopBackendError("QR_RENDER_FAILED"))
            return
        self.qr_label.setPixmap(pixmap.scaled(
            220, 220, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        self.qr_label.setVisible(True)
        if secret:
            self.secret_label.setText(f"Chave manual: {secret}")
            self.secret_label.setVisible(True)
        self.instructions.setText(
            "Escaneie o QR code no Microsoft Authenticator, Google Authenticator "
            "ou aplicativo compatível. Depois, informe o código de 6 números."
        )
        self._enable_code()

    def _enable_code(self):
        self.code.setEnabled(True)
        self.confirm.setEnabled(True)
        self.code.setFocus()

    def _verify(self):
        code = "".join(filter(str.isdigit, self.code.text()))
        if len(code) != 6:
            QMessageBox.warning(self, "Código incompleto", "Informe os 6 números do autenticador.")
            return
        self._run(lambda: self.auth.verify_totp(self._factor_id, code), self._verified)

    def _verified(self, _session):
        QMessageBox.information(
            self, "Segurança confirmada",
            "Identidade confirmada. A operação administrativa pode continuar.",
        )
        self.accept()

    def _show_error(self, error):
        code = error.code if isinstance(error, DesktopBackendError) else ""
        messages = {
            "INVALID_MFA_CODE": "Informe um código válido de 6 números.",
            "MFA_VERIFICATION_FAILED": "O código não foi aceito. Aguarde o próximo e tente novamente.",
            "MFA_CHALLENGE_EXPIRED": "O código expirou. Digite o código atual do aplicativo.",
            "QR_RENDER_FAILED": "Não foi possível exibir o QR code do autenticador.",
            "NETWORK_ERROR": "Não foi possível falar com o servidor. Verifique a internet e tente novamente.",
        }
        QMessageBox.warning(
            self, "Confirmação de segurança",
            messages.get(code, "Não foi possível confirmar o autenticador. Tente novamente."),
        )
