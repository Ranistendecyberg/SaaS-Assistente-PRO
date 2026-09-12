import sys
import os

def get_base_dir():
    # Salvar sempre na pasta oculta do Windows (AppData/Roaming) para proteger contra exclusão acidental e engenharia reversa
    appdata_path = os.getenv('APPDATA')
    if appdata_path:
        # A versão 2.0 usa autenticação, tokens e contrato próprios. Manter a
        # pasta separada impede que um beta sobrescreva a sessão/dados da 1.9.6.
        base = os.path.join(appdata_path, "SaasAssistentePRO-v2")
        os.makedirs(base, exist_ok=True)
        return base
        
    # Fallback caso APPDATA não exista (Linux/Mac/etc)
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
