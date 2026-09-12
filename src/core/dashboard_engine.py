import os
import json
import re
import unicodedata
import pandas as pd
from src.core.database import DatabaseManager

class DashboardEngine:
    def __init__(self):
        self.db_manager = DatabaseManager()
        from src.core.paths import get_base_dir
        self.config_path = os.path.join(get_base_dir(), "app_data", "config.json")
        self.config = self.load_config()

        # Índices pré-computados para lookup O(1) em lojas e consultores.
        # Reconstruídos automaticamente quando load_config() detecta mudança.
        self._lojas_index: dict = {}       # codigo/cnpj -> (nome, meta)
        self._consultores_index: dict = {} # cpf_clean -> nome
        self._rebuild_indexes()

    # ------------------------------------------------------------------
    # Configuração e índices
    # ------------------------------------------------------------------

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"lojas": [], "consultores": []}

    def _rebuild_indexes(self) -> None:
        """Pré-computa dicionários de busca a partir da configuração atual.

        Elimina os loops O(n) executados por linha de DataFrame em
        _get_loja_nome_meta() e _get_consultor_nome().
        """
        # Índice de lojas: código e CNPJ apontam para (nome, meta)
        lojas_index: dict = {}
        for loja in self.config.get("lojas", []):
            nome = loja.get("nome", "")
            meta = float(loja.get("meta_tsi", 0))
            for field in ("cnpj", "codigo"):
                key = str(loja.get(field, "")).strip()
                if key:
                    lojas_index[key] = (nome, meta)
        self._lojas_index = lojas_index

        # Índice de consultores: CPF normalizado (sem zeros à esquerda) -> nome
        consultores_index: dict = {}
        for cons in self.config.get("consultores", []):
            nome = cons.get("nome", "")
            cpf_raw = str(cons.get("cpf", "")).strip()
            # Registra tanto o CPF bruto quanto o CPF sem zeros à esquerda
            cpf_clean = re.sub(r'\D', '', cpf_raw).lstrip('0')
            if cpf_raw:
                consultores_index[cpf_raw] = nome
            if cpf_clean and cpf_clean != cpf_raw:
                consultores_index[cpf_clean] = nome
        self._consultores_index = consultores_index

    def _get_loja_nome_meta(self, codigo):
        """Lookup O(1) de nome e meta da loja pelo código ou CNPJ."""
        codigo = str(codigo).strip()
        if codigo in self._lojas_index:
            return self._lojas_index[codigo]
        return codigo, 0.0

    def _get_consultor_nome(self, cpf):
        """Lookup O(1) de nome do consultor pelo CPF."""
        cpf_original = str(cpf).strip()
        cpf_clean = re.sub(r'\D', '', cpf_original).lstrip('0')

        if cpf_clean and cpf_clean in self._consultores_index:
            return self._consultores_index[cpf_clean]
        if cpf_original in self._consultores_index:
            return self._consultores_index[cpf_original]
        return cpf_original

    @staticmethod
    def _normalizar_rotulo(valor):
        """Normaliza cabeçalhos sem depender de acentos ou capitalização."""
        texto = unicodedata.normalize("NFKD", str(valor or ""))
        return " ".join(
            "".join(ch for ch in texto if not unicodedata.combining(ch)).lower().split()
        )

    def _encontrar_coluna_consultor(self, df):
        """
        Localiza CPF ou nome do vendedor/consultor por prioridade.

        Evita confundir avaliações e comentários sobre o vendedor com o campo
        identificador do funcionário.
        """
        if df is None or df.empty:
            return None

        rejeitar = (
            "cliente", "coment", "avali", "atendimento", "atencao", "nota",
            "satisf", "recomenda", "pergunta", "resposta", "pontuacao"
        )
        candidatos = []
        for coluna in df.columns:
            rotulo = self._normalizar_rotulo(coluna)
            if any(termo in rotulo for termo in rejeitar):
                continue

            score = 0
            tem_pessoa = any(termo in rotulo for termo in ("vendedor", "consultor", "funcionario"))
            if ("cpf" in rotulo or "cnpj" in rotulo) and tem_pessoa:
                score = 100
            elif "cpf" in rotulo and "cliente" not in rotulo:
                score = 85
            elif tem_pessoa and any(termo in rotulo for termo in ("nome", "responsavel")):
                score = 75
            elif rotulo in ("vendedor", "consultor", "funcionario"):
                score = 65

            if score:
                candidatos.append((score, str(coluna)))

        return max(candidatos, default=(0, None), key=lambda item: item[0])[1]

    def enriquecer_consultores(self, df):
        """Cria Consultor_Nome a partir de CPF cadastrado ou nome já disponível."""
        if df is None:
            return pd.DataFrame()

        resultado = df.copy()
        coluna = self._encontrar_coluna_consultor(resultado)
        if not coluna:
            resultado['Consultor_Nome'] = "Não Identificado"
            return resultado

        valores_invalidos = {"", "nan", "none", "<na>", "-", "nao identificado", "desconhecido"}

        def resolver(valor):
            if valor is None or (not isinstance(valor, (list, dict)) and pd.isna(valor)):
                original = ""
            else:
                original = str(valor).strip()
            if self._normalizar_rotulo(original) in valores_invalidos:
                return "Não Identificado"
            return str(self._get_consultor_nome(original)).strip() or "Não Identificado"

        resultado['Consultor_Nome'] = resultado[coluna].apply(resolver)
        return resultado

    def load_data(self):
        # Recarrega config com reconstrução de índices somente quando o arquivo mudou
        self.config = self.load_config()
        self._rebuild_indexes()

        records = self.db_manager.load_all_records()
        if not records:
            return pd.DataFrame()
            
        df = pd.DataFrame(records)
        
        # Filtro de Respondente
        # "Responsável pela realização serviço" == "Sim, fui eu que levei e retirei a motocicleta"
        col_resp = 'Responsável pela realização serviço'
        if col_resp in df.columns:
            # Filtro estrito: apenas respostas exatas entram na contabilização de Dashboard
            df = df[df[col_resp].astype(str).str.strip() == "Sim, fui eu que levei e retirei a motocicleta"]
            
        # Converter notas para numérico
        colunas_notas = [
            'Avaliação satisfação geral',
            'Recomendaria dealer amigo e família',
            'Avaliação satisfação retorno ao dealer',
            'Avaliação satisfação agendamento',
            'Avaliação satisfação recepção',
            'Avaliação satisfação instalações e infra',
            'Avaliação satisfação consultor',
            'Avaliação satisfação qualidade',
            'Avaliação satisfação entrega',
            'Avaliação satisfação custo benefício'
        ]
        
        for col in colunas_notas:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        # --- CORREÇÃO DO AGRUPAMENTO HTML E CÓDIGO DA LOJA ---
        # A OS (ex: 1717379-75793) sempre contém o Código da Concessionária no início.
        col_os = next((c for c in df.columns if "Ordens de Servi" in c or "OS" in c), 'Ordens de Serviço: OS')
        col_cod = next((c for c in df.columns if "concession" in c.lower() and ("dico" in c.lower() or "cod" in c.lower())), None)
        
        if col_cod and col_cod in df.columns:
            df['Código concessionária'] = df[col_cod]
            
        if col_os in df.columns:
            os_loja = df[col_os].astype(str).str.split('-').str[0].str.strip()
            if 'Código concessionária' in df.columns:
                mask_invalido = df['Código concessionária'].isna() | (df['Código concessionária'].astype(str).str.strip().isin(['', 'nan', 'None', 'Desconhecida']))
                df.loc[mask_invalido, 'Código concessionária'] = os_loja[mask_invalido]
            else:
                df['Código concessionária'] = os_loja
        elif 'Código concessionária' not in df.columns:
            df['Código concessionária'] = "Desconhecida"

        # Enriquecer com dados da loja — lookup O(1) via índice pré-computado
        df['Loja_Nome'] = df['Código concessionária'].apply(lambda x: self._get_loja_nome_meta(x)[0])
        df['Loja_Meta'] = df['Código concessionária'].apply(lambda x: self._get_loja_nome_meta(x)[1])
            
        df = self.enriquecer_consultores(df)
            
        # Mês de Resposta
        if 'Data de Resposta' in df.columns:
            def extract_mes_ano_tsi(date_str):
                try:
                    texto = str(date_str).strip()
                    match = re.search(r'\b\d{1,2}/(\d{1,2})/(\d{4})\b', texto)
                    if match:
                        return f"{int(match.group(1)):02d}/{match.group(2)}"
                    match_iso = re.search(r'\b(\d{4})-(\d{1,2})-\d{1,2}(?!\d)', texto)
                    if match_iso:
                        return f"{int(match_iso.group(2)):02d}/{match_iso.group(1)}"
                    match_mes = re.search(r'\b(\d{1,2})/(\d{4})\b', texto)
                    if match_mes:
                        return f"{int(match_mes.group(1)):02d}/{match_mes.group(2)}"
                except Exception:
                    pass
                return "Desconhecido"
            df['Mes'] = df['Data de Resposta'].apply(extract_mes_ano_tsi)
        else:
            df['Mes'] = "Desconhecido"

        return df

    def calculate_metrics(self, df):
        """Calcula TSI e Top2Box global e por pergunta"""
        if df.empty:
            return None
            
        colunas_mestre = [
            'Avaliação satisfação instalações e infra',
            'Avaliação satisfação consultor',
            'Avaliação satisfação qualidade',
            'Avaliação satisfação entrega',
            'Avaliação satisfação custo benefício'
        ]
        
        colunas_extras = [
            'Avaliação satisfação geral',
            'Recomendaria dealer amigo e família',
            'Avaliação satisfação retorno ao dealer',
            'Avaliação satisfação agendamento',
            'Avaliação satisfação recepção'
        ]
        
        # O cálculo global é restrito EXCLUSIVAMENTE aos blocos mestre
        soma_notas = 0
        total_respostas_mestre = 0
        top2box_count = 0
        
        for col in colunas_mestre:
            if col in df.columns:
                valid_series = df[col].dropna()
                soma_notas += valid_series.sum()
                total_respostas_mestre += len(valid_series)
                top2box_count += len(valid_series[valid_series >= 9])
                
        tsi_global = (soma_notas / (total_respostas_mestre * 10)) * 100 if total_respostas_mestre > 0 else 0
        top2box_global = (top2box_count / total_respostas_mestre) * 100 if total_respostas_mestre > 0 else 0
        
        import math
        
        # Meta media (da base filtrada) ignorando lojas com meta zero (não configuradas)
        if 'Loja_Meta' in df.columns:
            metas_validas = df[df['Loja_Meta'] > 0]['Loja_Meta']
            meta_global = metas_validas.mean() if not metas_validas.empty else 0
        else:
            meta_global = 0
        
        # Cálculo de recuperação de meta
        pesquisas_recuperacao = 0
        if meta_global > tsi_global:
            if meta_global >= 100:
                pesquisas_recuperacao = -1 # Impossível
            else:
                m = meta_global / 100.0
                N_max = total_respostas_mestre * 10
                numerador = (m * N_max) - soma_notas
                denominador = 50 * (1 - m)
                if denominador > 0:
                    pesquisas_recuperacao = max(0, math.ceil(numerador / denominador))

        # Cálculo individual por pergunta - Mestres
        individual_mestre = {}
        for col in colunas_mestre:
            if col in df.columns:
                valid_series = df[col].dropna()
                total_r = len(valid_series)
                if total_r > 0:
                    tsi_p = (valid_series.sum() / (total_r * 10)) * 100
                    top_p = (len(valid_series[valid_series >= 9]) / total_r) * 100
                else:
                    tsi_p = 0
                    top_p = 0
                individual_mestre[col] = {"TSI": tsi_p, "Top2Box": top_p}

        # Cálculo individual por pergunta - Extras
        individual_extra = {}
        for col in colunas_extras:
            if col in df.columns:
                valid_series = df[col].dropna()
                total_r = len(valid_series)
                if total_r > 0:
                    tsi_p = (valid_series.sum() / (total_r * 10)) * 100
                    top_p = (len(valid_series[valid_series >= 9]) / total_r) * 100
                else:
                    tsi_p = 0
                    top_p = 0
                individual_extra[col] = {"TSI": tsi_p, "Top2Box": top_p}

        return {
            "tsi_global": round(tsi_global, 2),
            "top2box_global": round(top2box_global, 2),
            "meta_global": round(meta_global, 2),
            "pesquisas_recuperacao": pesquisas_recuperacao,
            "individual_mestre": individual_mestre,
            "individual_extra": individual_extra
        }
