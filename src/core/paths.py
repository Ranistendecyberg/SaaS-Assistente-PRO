import sys
import os

def get_base_dir():
    # Salvar sempre na pasta oculta do Windows (AppData/Roaming) para proteger contra exclusão acidental e engenharia reversa
    appdata_path = os.getenv('APPDATA')
    if appdata_path:
        base = os.path.join(appdata_path, "SaasAssistentePRO")
        os.makedirs(base, exist_ok=True)
        return base
        
    # Fallback caso APPDATA não exista (Linux/Mac/etc)
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
