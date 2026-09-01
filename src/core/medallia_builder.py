import requests
from src.core.salesforce_utils import salesforce_15_to_18

class MedalliaBuilder:
    @staticmethod
    def build_tsi_link(sf_id: str) -> str:
        """Monta o link bruto para a pesquisa TSI."""
        id_18 = salesforce_15_to_18(sf_id)
        raw_link = f"https://survey3.medallia.com/?tsi2&q1={id_18}&w=2W"
        return raw_link

    @staticmethod
    def build_ssi_link(sf_id: str, modelo: str, cilindrada: str) -> str:
        """Monta o link bruto para a pesquisa SSI."""
        id_18 = salesforce_15_to_18(sf_id)
        # Limpar espaços do modelo
        modelo_limpo = modelo.replace(" ", "").upper()
        raw_link = f"https://survey3.medallia.com/?SSI-2Wv2&Q1={id_18}&Q2={modelo_limpo}&Q3={cilindrada}"
        return raw_link

    @staticmethod
    def encrypt_link(raw_link: str) -> str:
        """
        Pega o link bruto e faz um request HTTP para capturar o redirecionamento
        do servidor da Medallia (que contém a URL Feedless criptografada).
        """
        print(f"\n[DEBUG] Link Bruto Gerado: {raw_link}")
        try:
            # Enviamos o request sem permitir redirecionamento para pegar a URL gerada
            response = requests.get(raw_link, allow_redirects=False, timeout=10)
            
            # 1. Nova Estratégia da Medallia (Retorna 200 OK com o Feedless no Cookie)
            cookies = response.headers.get('Set-Cookie', '')
            import re
            match = re.search(r'(feedless-[a-zA-Z0-9\-]+)', cookies)
            if match:
                feedless_id = match.group(1)
                encrypted_link = f"https://survey3.medallia.com/?{feedless_id}"
                print(f"[DEBUG] Link Criptografado via Cookie: {encrypted_link}")
                return encrypted_link
            
            # 2. Antiga Estratégia da Medallia (Retornava 302 Redirect via header Location)
            if response.status_code in (301, 302, 303, 307, 308):
                encrypted_link = response.headers.get('Location', '')
                if "feedless" in encrypted_link:
                    print(f"[DEBUG] Link Criptografado via Redirect: {encrypted_link}")
                    return encrypted_link
            
            # Se não encontrou de nenhum dos jeitos, devolvemos o bruto para não travar
            print("[WARNING] Não foi possível capturar o link Feedless. Retornando bruto.")
            return raw_link
            
        except Exception as e:
            print(f"[ERROR] Falha na criptografia: {e}")
            return raw_link
