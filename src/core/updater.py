import sys
import os
import urllib.request
import subprocess
import time
import hashlib
import re
from urllib.parse import urlparse
from PyQt6.QtWidgets import (
    QMessageBox, QApplication, QDialog, QVBoxLayout, 
    QHBoxLayout, QLabel, QProgressBar, QPushButton
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# Pega as configurações de nuvem compartilhadas
from src.core.license_manager import LicenseManager


def validate_installer_file(path, expected_sha256):
    if os.path.getsize(path) < 1024 * 100:
        raise RuntimeError("O arquivo recebido é pequeno demais para ser um instalador válido.")
    digest = hashlib.sha256()
    with open(path, "rb") as downloaded_file:
        if downloaded_file.read(2) != b"MZ":
            raise RuntimeError("O arquivo recebido não é um instalador Windows válido.")
        downloaded_file.seek(0)
        for block in iter(lambda: downloaded_file.read(1024 * 1024), b""):
            digest.update(block)
    downloaded_hash = digest.hexdigest().lower()
    if downloaded_hash != str(expected_sha256 or "").strip().lower():
        raise RuntimeError(
            "A assinatura de segurança do instalador não confere. "
            "O arquivo foi descartado e não será executado."
        )
    return downloaded_hash


class DownloadWorker(QThread):
    progress = pyqtSignal(int, str)  # percent, text
    finished = pyqtSignal(str)       # path
    error = pyqtSignal(str)

    def __init__(self, url, nova_versao, expected_sha256=""):
        super().__init__()
        self.url = url
        self.nova_versao = nova_versao
        self.expected_sha256 = str(expected_sha256 or "").strip().lower()

    def run(self):
        partial_path = ""
        try:
            temp_dir = os.path.join(os.environ.get('TEMP', ''), 'SaaS_Intelligence_Update')
            os.makedirs(temp_dir, exist_ok=True)
            installer_path = os.path.join(temp_dir, f"Instalador_SaaS_Assistente_PRO_v{self.nova_versao}.exe")
            partial_path = installer_path + ".part"
            for stale_file in (partial_path, installer_path):
                try:
                    os.remove(stale_file)
                except FileNotFoundError:
                    pass
            req = urllib.request.Request(self.url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.info().get('Content-Length', -1))
                downloaded = 0
                block_size = 65536
                start_time = time.time()
                last_emit = 0

                with open(partial_path, 'wb') as f:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        f.write(buffer)
                        downloaded += len(buffer)

                        now = time.time()
                        if now - last_emit > 0.08 or downloaded == total_size:
                            last_emit = now
                            elapsed = max(now - start_time, 0.001)
                            speed_mb = (downloaded / (1024 * 1024)) / elapsed
                            if total_size > 0:
                                percent = int((downloaded / total_size) * 100)
                                down_mb = downloaded / (1024 * 1024)
                                tot_mb = total_size / (1024 * 1024)
                                self.progress.emit(percent, f"Baixando: {down_mb:.1f} MB / {tot_mb:.1f} MB ({speed_mb:.1f} MB/s)")
                            else:
                                down_mb = downloaded / (1024 * 1024)
                                self.progress.emit(50, f"Baixando: {down_mb:.1f} MB ({speed_mb:.1f} MB/s)")

            validate_installer_file(partial_path, self.expected_sha256)
            os.replace(partial_path, installer_path)
            self.finished.emit(installer_path)
        except Exception as e:
            if partial_path:
                try:
                    os.remove(partial_path)
                except OSError:
                    pass
            self.error.emit(str(e))


def build_silent_installer_command(installer_path):
    """Argumentos padronizados para atualização automática via Inno Setup."""
    log_path = os.path.join(os.environ.get("TEMP", ""), "SaaS_Intelligence_Update", "install.log")
    return [
        installer_path,
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/SP-",
        "/CLOSEAPPLICATIONS",
        "/FORCECLOSEAPPLICATIONS",
        f"/LOG={log_path}",
    ]


def resolve_update_assistant_path():
    """Localiza o assistente independente empacotado junto com o SaaS."""
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.join(base_dir, "SaaS Update Assistant.exe")


def resolve_installed_app_path():
    """Retorna o executável que o instalador oficial cria para o usuário atual."""
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        return os.path.join(
            local_app_data,
            "Programs",
            "SaaS Assistente PRO",
            "SaaS Assistente PRO.exe",
        )
    return os.path.join(os.path.dirname(sys.executable), "SaaS Assistente PRO.exe")


def build_update_assistant_command(
    installer_path,
    version,
    parent_pid=None,
    helper_path=None,
    launch_path=None,
):
    """Comando que fecha, instala e reabre o Desktop sem intervenção adicional."""
    assistant = str(helper_path or resolve_update_assistant_path())
    if not os.path.isfile(assistant):
        raise FileNotFoundError("O Assistente de Atualização não foi encontrado nesta instalação.")
    return [
        assistant,
        "--installer", os.path.abspath(installer_path),
        "--version", str(version),
        "--parent-pid", str(parent_pid or os.getpid()),
        "--launch-path", os.path.abspath(launch_path or resolve_installed_app_path()),
    ]


class UpdateInstallConfirmationDialog(QDialog):
    """Confirma a instalação sem herdar dimensões/cores do tema global."""

    def __init__(self, nova_versao, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Atualização pronta para instalar")
        self.setFixedSize(560, 300)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("""
            QDialog {
                background-color: #0F172A;
                color: #F8FAFC;
                font-family: 'Segoe UI', Arial;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(13)

        title = QLabel(f"✓ Versão {nova_versao} pronta para instalar")
        title.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #F8FAFC;
                font-size: 18px;
                font-weight: 700;
            }
        """)
        layout.addWidget(title)

        verified = QLabel("O download foi concluído e validado com segurança.")
        verified.setStyleSheet("""
            QLabel {
                background-color: #0D2A24;
                color: #6EE7B7;
                border: 1px solid #145C4B;
                border-radius: 7px;
                padding: 9px 11px;
                font-size: 12px;
                font-weight: 600;
            }
        """)
        layout.addWidget(verified)

        explanation = QLabel(
            "Ao continuar, o SaaS Assistente PRO será fechado para aplicar a atualização.\n\n"
            "O Assistente de Atualização fará a instalação e abrirá a nova versão "
            "automaticamente. Você não precisará reabrir o sistema."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #CBD5E1;
                font-size: 12px;
                line-height: 1.35;
            }
        """)
        layout.addWidget(explanation, 1)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addStretch(1)

        cancel_button = QPushButton("Cancelar")
        cancel_button.setFixedSize(120, 38)
        cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1px solid #334155;
                border-radius: 7px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #29364A; }
            QPushButton:pressed { background-color: #162033; }
        """)
        cancel_button.clicked.connect(self.reject)
        actions.addWidget(cancel_button)

        install_button = QPushButton("Fechar e instalar agora")
        install_button.setFixedSize(190, 38)
        install_button.setCursor(Qt.CursorShape.PointingHandCursor)
        install_button.setDefault(True)
        install_button.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 7px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:pressed { background-color: #1E40AF; }
        """)
        install_button.clicked.connect(self.accept)
        actions.addWidget(install_button)
        layout.addLayout(actions)


class UpdateDownloadDialog(QDialog):
    def __init__(self, url, nova_versao, expected_sha256="", parent=None):
        super().__init__(parent)
        self.url = url
        self.nova_versao = nova_versao
        self.setWindowTitle("Atualização do Sistema")
        self.setFixedSize(500, 205)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #0F172A;
                color: #FFFFFF;
                font-family: 'Segoe UI', Arial;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        lbl_tit = QLabel(f"🚀 Atualização automática · versão {self.nova_versao}")
        lbl_tit.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #F8FAFC;
                font-size: 15px;
                font-weight: 700;
            }
        """)
        layout.addWidget(lbl_tit)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1E293B;
                border-radius: 6px;
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #38BDF8);
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Conectando aos servidores...")
        self.lbl_status.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #CBD5E1;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.lbl_status)

        lbl_hint = QLabel(
            "Ao concluir, o sistema será fechado, atualizado e aberto novamente automaticamente."
        )
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet("""
            QLabel {
                background-color: #111C2D;
                color: #AFC0D4;
                border: 1px solid #263449;
                border-radius: 7px;
                padding: 8px 10px;
                font-size: 11px;
            }
        """)
        layout.addWidget(lbl_hint)

        self.worker = DownloadWorker(self.url, self.nova_versao, expected_sha256)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, percent, text):
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(text)

    def _on_finished(self, installer_path):
        self.progress_bar.setValue(100)
        self.lbl_status.setText("Arquivo verificado. Preparando a instalação...")
        QApplication.processEvents()
        time.sleep(0.6)

        confirmation = UpdateInstallConfirmationDialog(self.nova_versao, self)
        if confirmation.exec() != QDialog.DialogCode.Accepted:
            self.lbl_status.setText("Instalação cancelada. Você pode tentar novamente mais tarde.")
            self.reject()
            return

        try:
            subprocess.Popen(
                build_update_assistant_command(
                    installer_path, self.nova_versao, parent_pid=os.getpid()
                ),
                close_fds=True,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        except Exception as error:
            self._on_error(f"Não foi possível iniciar o instalador: {error}")
            return

        # O assistente aguarda este processo terminar, instala e abre a versão nova.
        QApplication.closeAllWindows()
        QApplication.quit()
        os._exit(0)

    def _on_error(self, err_msg):
        self.lbl_status.setText(f"Erro no download: {err_msg}")
        self.lbl_status.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #FCA5A5;
                font-size: 12px;
                font-weight: 700;
            }
        """)
        QMessageBox.critical(self, "Falha no Download", f"Não foi possível baixar a atualização:\n{err_msg}")
        self.reject()


class Updater:
    """Gerencia a verificação de atualizações OTA e aciona o download + instalador"""
    def __init__(self, current_version):
        self.current_version = current_version
        
    def checar_atualizacao(self, parent_widget=None):
        try:
            manager = LicenseManager()
            response = manager.secure_backend.license_status(self.current_version)
            system = dict(response.get("system") or {})
            dados = {
                "versao_atual": system.get("current_version"),
                "url_download": system.get("installer_url"),
                "obrigatorio": system.get("update_required", False),
                "versao_minima": system.get("minimum_version"),
                "sha256": system.get("installer_sha256"),
            }
                
            if not dados:
                return
                
            versao_nuvem = dados.get("versao_atual") or dados.get("versao_recente", "1.0.0")
            link = dados.get("link_download") or dados.get("url_download", "")
            obrigatorio = dados.get("obrigatorio") if "obrigatorio" in dados else dados.get("force_update", False)
            obrigatorio = bool(obrigatorio) or self._versao_maior(dados.get("versao_minima"), self.current_version)
            checksum = str(dados.get("sha256") or "").strip().lower()
            
            # Se a versão na nuvem for maior, alerta o usuário
            if self._versao_maior(versao_nuvem, self.current_version):
                if obrigatorio:
                    msg = f"ATUALIZAÇÃO OBRIGATÓRIA!\n\nA versão {versao_nuvem} precisa ser instalada para o sistema continuar funcionando."
                    resp = QMessageBox.question(parent_widget, "Atualização Obrigatória", msg,
                                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if resp == QMessageBox.StandardButton.Yes:
                        self.executar_atualizacao(link, versao_nuvem, parent_widget, checksum)
                    else:
                        sys.exit(0)
                else:
                    msg = (
                        f"🚀 Uma nova versão ({versao_nuvem}) está disponível!\n\n"
                        f"Deseja atualizar agora para obter as novidades e melhorias?"
                    )
                    resp = QMessageBox.question(
                        parent_widget,
                        "Atualização Disponível",
                        msg,
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if resp == QMessageBox.StandardButton.Yes:
                        self.executar_atualizacao(link, versao_nuvem, parent_widget, checksum)
                        
        except Exception as e:
            print("Erro ao checar atualizacao:", e)

    def _versao_maior(self, v1, v2):
        """Compara versões numéricas e pré-lançamentos como 2.0.0-beta.1."""
        parsed_1 = self._parse_version(v1)
        parsed_2 = self._parse_version(v2)
        if parsed_1 is None or parsed_2 is None:
            return False

        core_1, prerelease_1 = parsed_1
        core_2, prerelease_2 = parsed_2
        size = max(len(core_1), len(core_2))
        core_1 += (0,) * (size - len(core_1))
        core_2 += (0,) * (size - len(core_2))
        if core_1 != core_2:
            return core_1 > core_2

        # A versão final é sempre posterior ao pré-lançamento do mesmo número.
        if prerelease_1 is None or prerelease_2 is None:
            return prerelease_1 is None and prerelease_2 is not None

        for left, right in zip(prerelease_1, prerelease_2):
            if left == right:
                continue
            left_numeric = left.isdigit()
            right_numeric = right.isdigit()
            if left_numeric and right_numeric:
                return int(left) > int(right)
            if left_numeric != right_numeric:
                return not left_numeric
            return left > right
        return len(prerelease_1) > len(prerelease_2)

    @staticmethod
    def _parse_version(value):
        text = str(value or "0").strip().lower().lstrip("v")
        text = text.split("+", 1)[0]
        match = re.fullmatch(r"(\d+(?:\.\d+)*)(?:-([0-9a-z.-]+))?", text)
        if not match:
            return None
        core = tuple(int(part) for part in match.group(1).split("."))
        prerelease = tuple(match.group(2).split(".")) if match.group(2) else None
        return core, prerelease

    def executar_atualizacao(self, url, nova_versao, parent=None, expected_sha256=""):
        if not url:
            if parent:
                QMessageBox.warning(parent, "Aviso", "Nenhum link de download configurado no servidor.")
            return False

        parsed = urlparse(str(url).strip())
        if parsed.scheme != "https" or not parsed.netloc:
            if parent:
                QMessageBox.critical(
                    parent, "Link de atualização inseguro",
                    "O endereço do instalador precisa usar HTTPS. A atualização foi bloqueada."
                )
            return False

        checksum = str(expected_sha256 or "").strip().lower()
        if len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum):
            if parent:
                QMessageBox.critical(
                    parent, "Atualização sem assinatura",
                    "O administrador ainda não publicou a assinatura SHA-256 do instalador. "
                    "Por segurança, o download não será executado."
                )
            return False

        dialog = UpdateDownloadDialog(url, nova_versao, checksum, parent)
        dialog.exec()
        return dialog.result() == QDialog.DialogCode.Accepted
