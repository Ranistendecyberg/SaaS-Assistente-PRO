import os
import zipfile
import datetime
import threading
from src.core.paths import get_base_dir

class BackupManager:
    @staticmethod
    def criar_backup():
        """
        Cria um backup zip da pasta 'app_data' em background (thread daemon)
        e mantém os últimos 15 backups.

        Mudança de escalabilidade (2.0.7): o backup é lançado em uma thread
        daemon para não bloquear o thread principal durante a inicialização do
        aplicativo. Erros são registrados mas nunca propagam para a UI.
        """
        threading.Thread(
            target=BackupManager._criar_backup_worker,
            daemon=True,
            name="BackupWorker",
        ).start()

    @staticmethod
    def _criar_backup_worker():
        """Worker executado em background — não bloqueia a UI."""
        try:
            base_dir = get_base_dir()
            backups_dir = os.path.join(base_dir, "backups")
            os.makedirs(backups_dir, exist_ok=True)
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = os.path.join(backups_dir, f"backup_saas_{timestamp}.zip")
            
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Backup da pasta app_data (banco de dados)
                app_data_dir = os.path.join(base_dir, "app_data")
                if os.path.exists(app_data_dir):
                    for root, dirs, files in os.walk(app_data_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, base_dir)
                            zipf.write(file_path, arcname)
                            
            # Manter apenas os últimos 15 backups (limpeza automática)
            backups = sorted([f for f in os.listdir(backups_dir) if f.endswith('.zip')])
            if len(backups) > 15:
                for b in backups[:-15]:
                    try:
                        os.remove(os.path.join(backups_dir, b))
                    except OSError:
                        pass
                        
        except Exception as e:
            print(f"Aviso: Não foi possível criar o backup automático - {e}")
