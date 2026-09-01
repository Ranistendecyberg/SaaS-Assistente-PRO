import os
import zipfile
import datetime

class BackupManager:
    @staticmethod
    def criar_backup():
        """
        Cria um backup zip da pasta 'src' e 'app_data' e mantém os últimos 15 backups.
        Isso garante que o usuário sempre tenha um ponto de restauração seguro caso algo dê errado.
        """
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            backups_dir = os.path.join(base_dir, "backups")
            os.makedirs(backups_dir, exist_ok=True)
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = os.path.join(backups_dir, f"backup_saas_{timestamp}.zip")
            
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 1. Backup da pasta src (código)
                src_dir = os.path.join(base_dir, "src")
                if os.path.exists(src_dir):
                    for root, dirs, files in os.walk(src_dir):
                        if "__pycache__" in root:
                            continue
                        for file in files:
                            if file.endswith('.pyc'): continue
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, base_dir)
                            zipf.write(file_path, arcname)
                            
                # 2. Backup da pasta app_data (banco de dados)
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
                    os.remove(os.path.join(backups_dir, b))
                    
        except Exception as e:
            print(f"Aviso: Não foi possível criar o backup automático - {e}")
