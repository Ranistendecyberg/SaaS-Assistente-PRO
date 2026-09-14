import sys
import os
import traceback
# Garante que o diretório raiz seja reconhecido no PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PyQt6 import QtWebEngineWidgets
from PyQt6.QtWidgets import QApplication, QMessageBox
from src.ui.main_window import MainWindow
from src.core.backup_manager import BackupManager
from src.core.paths import get_base_dir
from src.core.telemetry import record_event

def _run_build_smoke_test():
    """Importa os módulos essenciais sem abrir janelas nem alterar dados."""
    import PyQt6.sip
    from PyQt6 import QtCore, QtGui, QtWidgets, QtWebEngineCore, QtWebEngineWidgets
    import bs4
    import pandas
    import PIL
    import qrcode
    import requests
    from src.ui.screens import (
        about_screen, billing_dialog, company_account_screen, config_screen,
        dashboard_comparativo_screen, dashboard_screen, dashboard_ssi_screen,
        extraction_screen, license_screen, new_installation_screen,
        password_recovery_dialog, suggestions_screen, terms_dialog,
        tutorial_screen, user_login_dialog, whatsapp_screen,
    )
    return 0

def global_exception_handler(exc_type, exc_value, exc_traceback):
    log_path = os.path.join(get_base_dir(), 'app_data', 'crash_log.txt')
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(error_msg)
    except:
        pass
    print(error_msg)
    record_event(
        "application", "UNHANDLED_EXCEPTION", "ERROR",
        exception_type=getattr(exc_type, "__name__", str(exc_type)),
        exception=str(exc_value), traceback=error_msg,
    )
    sys.exit(1)

def main():
    if "--build-smoke-test" in sys.argv:
        return _run_build_smoke_test()

    sys.excepthook = global_exception_handler
    record_event("application", "APP_START")
    
    # 1. Cria um Backup Seguro Silencioso na inicialização
    BackupManager.criar_backup()
    
    app = QApplication(sys.argv)
    
    # Fecha a tela de carregamento do PyInstaller (Splash Screen) se existir
    try:
        import pyi_splash
        pyi_splash.update_text('Carregando Interface...')
        pyi_splash.close()
    except Exception:
        pass
    
    # 1.1 Configurar Ícone na Barra de Tarefas do Windows
    import ctypes
    from PyQt6.QtGui import QIcon
    try:
        myappid = 'saas.assistente.pro.v1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass
        
    icon_path = os.path.join(sys._MEIPASS, 'logo.ico') if getattr(sys, 'frozen', False) else os.path.join(os.path.dirname(__file__), '..', 'logo.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # 1.2 Checagem de Aceite dos Termos de Uso e Isenção de Responsabilidade
    from src.ui.screens.terms_dialog import TermsDialog
    from PyQt6.QtWidgets import QDialog
    if not TermsDialog.verificar_aceite_previo():
        terms_dialog = TermsDialog(apenas_leitura=False)
        if terms_dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
    
    # 1.5 Checagem de Cadastro Inicial (Virgem) ou Incompleto
    from src.core.license_manager import LicenseManager
    lm = LicenseManager()
    # Na versão 2.0, computadores sem vínculo iniciam o cadastro empresarial
    # ou usam um código descartável para entrar como computador adicional.
    # Fluxos de migração Firebase não fazem parte deste projeto isolado.
    if lm.precisa_configurar_primeiro_acesso():
        from src.ui.screens.new_installation_screen import NewInstallationScreen
        initial_dialog = NewInstallationScreen()
        if initial_dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
    while True:
        licenca_info = lm.validar_licenca()
        if licenca_info.get("status") != "erro_conexao":
            break

        resposta = QMessageBox.warning(
            None,
            "Falha de conexão",
            "Não foi possível consultar o cadastro da empresa no servidor seguro.\n\n"
            "Verifique sua conexão com a internet e tente novamente. "
            "Seu cadastro existente não será alterado.",
            QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Close,
            QMessageBox.StandardButton.Retry
        )
        if resposta != QMessageBox.StandardButton.Retry:
            sys.exit(0)
    status_lic = licenca_info.get("status")
    if status_lic in {"primeiro_acesso_necessario", "vinculo_invalido"}:
        QMessageBox.critical(
            None, "Vínculo não autorizado",
            "Este computador ainda não possui um vínculo válido com a concessionária.\n\n"
            "Entre em contato com o suporte para receber orientação."
        )
        sys.exit(0)

    system_config = dict(licenca_info.get("system") or {})
    if system_config.get("maintenance_mode"):
        QMessageBox.information(
            None,
            "Sistema em manutenção",
            str(system_config.get("maintenance_message") or
                "O sistema está temporariamente em manutenção. Tente novamente mais tarde."),
        )
        sys.exit(0)
    
    # 2. Tela de Trava de Licença (Trial/Assinatura)
    from src.ui.screens.license_screen import LicenseScreen
    from PyQt6.QtWidgets import QDialog
    
    lic_screen = LicenseScreen()
    if lic_screen.exec() == QDialog.DialogCode.Accepted:
        # 3. Inicializa e exibe a Tela Principal
        window = MainWindow()
        window.show()
        
        # Correção robusta para o bug de clipping no WebEngine ao maximizar
        from PyQt6.QtCore import Qt, QTimer
        QTimer.singleShot(200, lambda: window.setWindowState(Qt.WindowState.WindowMaximized))
        
        # 4. Checagem Invisível de Atualização (OTA)
        from src.core.updater import Updater
        from src.version import __version__
        CURRENT_VERSION = __version__
        updater = Updater(CURRENT_VERSION)
        updater.checar_atualizacao(window)
        
        sys.exit(app.exec())
    else:
        sys.exit(0)

if __name__ == "__main__":
    raise SystemExit(main())
