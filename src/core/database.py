import os
import json
import logging
from src.core.paths import get_base_dir

class DatabaseManager:
    def __init__(self):
        self.base_dir = get_base_dir()
        self.app_data_dir = os.path.join(self.base_dir, "app_data")
        os.makedirs(self.app_data_dir, exist_ok=True)
        
        self.db_path = os.path.join(self.app_data_dir, "historico_tsi.json")
        self.ssi_db_path = os.path.join(self.app_data_dir, "historico_ssi.json")
        self.sent_path = os.path.join(self.app_data_dir, "sent_surveys.json")
        
        if not os.path.exists(self.db_path):
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump([], f)
                
        if not os.path.exists(self.ssi_db_path):
            with open(self.ssi_db_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def load_all_records(self):
        """Retorna todos os registros do histórico em formato de lista de dicionários."""
        if not os.path.exists(self.db_path):
            return []
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Erro ao carregar banco de dados TSI: {e}")
            return []

    def save_records(self, new_records):
        """
        Recebe uma lista de registros (dict) raspados recentemente.
        Verifica duplicidades pela O.S. (chave 'Ordens de Serviço: OS')
        e adiciona apenas os registros inéditos ao banco.
        """
        if not new_records:
            return

        existing_records = self.load_all_records()
        
        # Mapa por O.S. para inserir registros inéditos e enriquecer registros
        # antigos com campos que passaram a estar disponíveis.
        existing_by_os = {
            self.normalize_lead_key(rec.get('Ordens de Serviço: OS', '')): rec
            for rec in existing_records
            if rec.get('Ordens de Serviço: OS')
        }
        
        added_count = 0
        updated = False
        for rec in new_records:
            os_number = str(rec.get('Ordens de Serviço: OS', '')).strip()
            os_key = self.normalize_lead_key(os_number)
            if os_number and os_key not in existing_by_os:
                existing_records.append(rec)
                existing_by_os[os_key] = rec
                added_count += 1
                updated = True
            elif os_key in existing_by_os:
                existing = existing_by_os[os_key]
                for key, value in rec.items():
                    new_value = str(value or '').strip()
                    old_value = str(existing.get(key, '') or '').strip()
                    if new_value and new_value.lower() not in ('nan', 'none', '-', 'n/d', 's/n'):
                        # Cliente e telefone vêm do relatório recém-extraído e
                        # devem corrigir enriquecimentos antigos incorretos.
                        refreshable_identity = key in ('Cliente', 'Telefone')
                        if (
                            not old_value
                            or old_value.lower() in ('nan', 'none', '-', 'n/d', 's/n')
                            or (refreshable_identity and old_value != new_value)
                        ):
                            existing[key] = value
                            updated = True
                
        if updated:
            try:
                with open(self.db_path, "w", encoding="utf-8") as f:
                    json.dump(existing_records, f, ensure_ascii=False, indent=4)
                logging.info(
                    f"Banco de Dados TSI atualizado com {added_count} novos registros "
                    "e dados complementares mesclados."
                )
            except Exception as e:
                logging.error(f"Erro ao salvar banco de dados TSI: {e}")
                
                
        return added_count

    def load_sent_surveys(self):
        """Retorna um set com os IDs (sf_id) das pesquisas que já foram enviadas pelo robô."""
        if not os.path.exists(self.sent_path):
            return set()
        try:
            with open(self.sent_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data)
        except Exception as e:
            logging.error(f"Erro ao carregar sent_surveys: {e}")
            return set()

    def mark_survey_as_sent(self, survey_id: str):
        """Marca uma pesquisa como enviada pelo Whatsapp."""
        sent = list(self.load_sent_surveys())
        if survey_id not in sent:
            sent.append(survey_id)
            try:
                with open(self.sent_path, "w", encoding="utf-8") as f:
                    json.dump(sent, f, indent=4)
            except:
                pass

    def clear_sent_history(self):
        """Limpa o histórico de pesquisas enviadas, permitindo reenvio."""
        try:
            if os.path.exists(self.sent_path):
                os.remove(self.sent_path)
            return True
        except Exception as e:
            logging.error(f"Erro ao limpar sent_surveys: {e}")
            return False

    def load_ssi_records(self):
        """Retorna todos os registros do histórico SSI."""
        try:
            if os.path.exists(self.ssi_db_path):
                with open(self.ssi_db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Erro ao carregar banco SSI: {e}")
        return []

    def save_ssi_records(self, new_records: list):
        """Atualiza o banco SSI evitando duplicidades de URL/ID."""
        current_records = self.load_ssi_records()
        
        # Cria um mapa com base no ID da pesquisa extraído do link de Ação
        existing_map = {}
        for r in current_records:
            acao = str(r.get('Ação', '')).strip()
            import re
            match = re.search(r'/([a-zA-Z0-9]{15,18})(?:\?|/|$)', acao)
            if match:
                existing_map[match.group(1)] = r
            else:
                # Se não tem ID, usa uma concatenação como fallback
                fallback_id = str(r.get('Relação de Posse: Name', '')) + str(r.get('Data de resposta SSI 2W', ''))
                if fallback_id: existing_map[fallback_id] = r
                
        for nr in new_records:
            acao = str(nr.get('Ação', '')).strip()
            import re
            match = re.search(r'/([a-zA-Z0-9]{15,18})(?:\?|/|$)', acao)
            if match:
                existing_map[match.group(1)] = nr
            else:
                fallback_id = str(nr.get('Relação de Posse: Name', '')) + str(nr.get('Data de resposta SSI 2W', ''))
                if fallback_id: existing_map[fallback_id] = nr
                
        updated_list = list(existing_map.values())
        try:
            with open(self.ssi_db_path, "w", encoding="utf-8") as f:
                json.dump(updated_list, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar banco SSI: {e}")

    def save_leads_mapping(self, leads_list: list):
        """
        Salva o mapeamento das O.S. / Posses extraídas na lista de envio/reenvio
        associando o número da O.S., Chassi ou Posse ao Nome do Cliente e Telefone.
        Isso permite cruzar com as respostas de auditoria e exibir o nome real do cliente.
        """
        if not leads_list:
            return
            
        map_path = os.path.join(self.app_data_dir, "leads_map.json")
        current_map = {}
        if os.path.exists(map_path):
            try:
                with open(map_path, "r", encoding="utf-8") as f:
                    current_map = json.load(f)
            except Exception:
                current_map = {}

        updated = False
        # Higienização de chaves legadas corrompidas (códigos de concessionária como '1717379', '101')
        sanitized_map = {}
        for k, v in current_map.items():
            os_f = str(v.get('os_full', '')).strip()
            if '-' in os_f:
                prefix = os_f.split('-')[0].strip()
                suffix = os_f.split('-')[-1].strip()
                if k == prefix and k != suffix and k != os_f:
                    updated = True
                    continue
            sanitized_map[k] = v
        current_map = sanitized_map

        for item in leads_list:
            nome = str(item.get('cliente', '')).strip()
            fone = str(item.get('telefone', '')).strip()
            os_raw = str(item.get('os', '')).strip()
            os_full = str(item.get('os_full', '')).strip()
            tipo = str(item.get('tipo', '')).strip()
            lead_id = str(item.get('id', '')).strip()
            
            if nome and nome.upper() not in ['N/D', '', 'NONE', 'S/N', 'N/A']:
                os_clean = os_raw.split('-')[-1].strip() if '-' in os_raw else os_raw
                lead_data = {
                    'cliente': nome,
                    'telefone': fone if fone not in ['S/N', 'N/D', 'None'] else '',
                    'os': os_clean,
                    'os_full': os_full or os_raw,
                    'tipo': tipo,
                    'id': lead_id
                }
                
                # Chaves de busca seguras (NUNCA indexar prefixo de concessionária isolado):
                keys_to_index = []
                for k_val in [os_clean, os_raw, os_full, lead_id]:
                    if k_val and k_val not in ['-', 'Sem OS', 'Sem Posse', '', 'nan', 'None']:
                        keys_to_index.append(k_val)
                        if '-' in k_val:
                            partes = k_val.split('-')
                            # Apenas o sufixo (número real da OS ou chassi) é chave válida:
                            if partes[-1].strip() and len(partes[-1].strip()) >= 3:
                                keys_to_index.append(partes[-1].strip())
                            # Para SSI, a Posse (prefixo) é única por venda:
                            if tipo == 'SSI' and partes[0].strip() and len(partes[0].strip()) >= 6:
                                keys_to_index.append(partes[0].strip())
                        lstripped = k_val.lstrip('0')
                        if lstripped and lstripped != k_val and len(lstripped) >= 3:
                            keys_to_index.append(lstripped)
                
                for k in set(keys_to_index):
                    current_map[k] = lead_data
                    updated = True

        if updated:
            try:
                with open(map_path, "w", encoding="utf-8") as f:
                    json.dump(current_map, f, indent=4, ensure_ascii=False)
            except Exception as e:
                logging.error(f"Erro ao salvar leads_map.json: {e}")

    def get_leads_mapping(self) -> dict:
        """Retorna o dicionário de mapeamento OS/Posse -> Dados do Cliente (Nome, Telefone) higienizado."""
        map_path = os.path.join(self.app_data_dir, "leads_map.json")
        if not os.path.exists(map_path):
            return {}
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                raw_map = json.load(f)
            
            clean_map = {}
            corrompido = False
            for k, v in raw_map.items():
                os_f = str(v.get('os_full', '')).strip()
                if '-' in os_f:
                    prefix = os_f.split('-')[0].strip()
                    suffix = os_f.split('-')[-1].strip()
                    if k == prefix and k != suffix and k != os_f:
                        corrompido = True
                        continue
                clean_map[k] = v
                
            if corrompido:
                try:
                    with open(map_path, "w", encoding="utf-8") as f:
                        json.dump(clean_map, f, indent=4, ensure_ascii=False)
                except Exception:
                    pass
            return clean_map
        except Exception as e:
            logging.error(f"Erro ao ler leads_map: {e}")
            return {}

    @staticmethod
    def normalize_lead_key(value) -> str:
        """Normaliza OS, posse, chassi ou ID para cruzamento entre relatórios."""
        import re
        raw = str(value or "").strip().upper()
        if raw.lower() in ("", "nan", "none", "-", "sem os", "sem posse"):
            return ""
        normalized = re.sub(r"[^A-Z0-9]", "", raw)
        if normalized.isdigit():
            normalized = normalized.lstrip("0") or "0"
        return normalized

    def find_lead(self, *keys, tipo: str = None) -> dict:
        """
        Busca um cliente mesmo quando a O.S. muda de formatação entre a fila
        e o auditor (zeros à esquerda, espaços, pontos, hífens ou OS completa).
        """
        mapping = self.get_leads_mapping()
        if not mapping:
            return {}

        # Mantém a prioridade dos argumentos informados pelo chamador. Partes
        # de uma chave composta não são indexadas isoladamente: o primeiro
        # trecho de uma O.S. é o código da concessionária e não identifica um
        # cliente. Usá-lo sozinho fazia qualquer O.S. da mesma loja apontar
        # para o primeiro lead encontrado.
        candidates = []
        seen_candidates = set()

        def add_variants(target, raw_value):
            normalized = self.normalize_lead_key(raw_value)
            variants = [normalized]
            if "-" in raw_value:
                compound = "-".join(
                    self.normalize_lead_key(part)
                    for part in raw_value.split("-")
                    if self.normalize_lead_key(part)
                )
                variants.append(compound)
            for variant in variants:
                if variant and variant not in seen_candidates:
                    target.append(variant)
                    seen_candidates.add(variant)

        for key in keys:
            raw = str(key or "").strip()
            if not raw:
                continue
            add_variants(candidates, raw)

        normalized_index = {}
        for stored_key, lead in mapping.items():
            if tipo and str(lead.get("tipo", "")).upper() != tipo.upper():
                continue
            values = [
                stored_key,
                lead.get("os"),
                lead.get("os_full"),
                lead.get("id"),
            ]
            for value in values:
                raw = str(value or "").strip()
                index_variants = []
                index_seen = set()

                normalized = self.normalize_lead_key(raw)
                if normalized:
                    index_variants.append(normalized)
                    index_seen.add(normalized)
                if "-" in raw:
                    compound = "-".join(
                        self.normalize_lead_key(part)
                        for part in raw.split("-")
                        if self.normalize_lead_key(part)
                    )
                    if compound and compound not in index_seen:
                        index_variants.append(compound)

                for variant in index_variants:
                    normalized_index.setdefault(variant, lead)

        for candidate in candidates:
            if candidate in normalized_index:
                return normalized_index[candidate]
        return {}

    def is_comunicado_lido(self, mensagem: str) -> bool:
        """Verifica se o comunicado/aviso já foi marcado como 'Entendido e Ciente' nesta máquina."""
        if not mensagem:
            return True
        import hashlib
        msg_hash = hashlib.sha256(mensagem.strip().encode('utf-8')).hexdigest()
        path = os.path.join(self.app_data_dir, "comunicados_lidos.json")
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                lidos = json.load(f)
                return msg_hash in lidos
        except Exception:
            return False

    def marcar_comunicado_lido(self, mensagem: str):
        """Salva o hash do comunicado como 'Entendido e Ciente' para não emitir o alerta novamente."""
        if not mensagem:
            return
        import hashlib
        msg_hash = hashlib.sha256(mensagem.strip().encode('utf-8')).hexdigest()
        path = os.path.join(self.app_data_dir, "comunicados_lidos.json")
        lidos = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lidos = json.load(f)
            except Exception:
                lidos = []
        if msg_hash not in lidos:
            lidos.append(msg_hash)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(lidos, f, indent=4)
            except Exception as e:
                print(f"Erro ao salvar comunicado lido: {e}")
