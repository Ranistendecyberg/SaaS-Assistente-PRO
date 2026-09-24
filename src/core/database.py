import os
import json
import re
import logging
from datetime import datetime, timezone
from src.core.paths import get_base_dir

class DatabaseManager:
    def __init__(self):
        self.base_dir = get_base_dir()
        self.app_data_dir = os.path.join(self.base_dir, "app_data")
        os.makedirs(self.app_data_dir, exist_ok=True)
        
        self.db_path = os.path.join(self.app_data_dir, "historico_tsi.json")
        self.ssi_db_path = os.path.join(self.app_data_dir, "historico_ssi.json")
        self.sent_path = os.path.join(self.app_data_dir, "sent_surveys.json")

        # -------------------------------------------------------
        # Cache em memória — invalidado automaticamente em escritas
        # -------------------------------------------------------
        self._records_cache: list | None = None          # cache de load_all_records()
        self._ssi_cache: list | None = None              # cache de load_ssi_records()
        self._records_signature: tuple | None = None     # (mtime_ns, tamanho)
        self._ssi_signature: tuple | None = None         # (mtime_ns, tamanho)
        self._leads_index_cache: dict | None = None      # índice pré-computado de find_lead()
        self._leads_map_mtime: float = 0.0               # mtime do leads_map.json na última leitura
        
        if not os.path.exists(self.db_path):
            self._atomic_write_json(self.db_path, [])
                
        if not os.path.exists(self.ssi_db_path):
            self._atomic_write_json(self.ssi_db_path, [])

    def _ensure_cache_attrs(self) -> None:
        """Garante que os atributos de cache existam.

        Necessário quando a instância é criada via ``__new__`` nos testes
        sem invocar ``__init__`` (que é onde os atributos são declarados).
        """
        if not hasattr(self, '_records_cache'):
            self._records_cache = None
        if not hasattr(self, '_ssi_cache'):
            self._ssi_cache = None
        if not hasattr(self, '_records_signature'):
            self._records_signature = None
        if not hasattr(self, '_ssi_signature'):
            self._ssi_signature = None
        if not hasattr(self, '_leads_index_cache'):
            self._leads_index_cache = None
        if not hasattr(self, '_leads_map_mtime'):
            self._leads_map_mtime = 0.0
        if not hasattr(self, '_typed_index_cache'):
            self._typed_index_cache = {}

    @staticmethod
    def _atomic_write_json(path, data, *, ensure_ascii=True, indent=4):
        """Grava JSON sem deixar o arquivo principal pela metade em uma interrupção."""
        temp_path = f"{path}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, path)
        except Exception:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def _read_json(path, expected_type, default, *, strict=False, label="arquivo JSON"):
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, expected_type):
                raise ValueError(
                    f"estrutura inválida: esperado {expected_type.__name__}, "
                    f"recebido {type(data).__name__}"
                )
            return data
        except Exception as e:
            logging.error(f"Erro ao carregar {label}: {e}")
            if strict:
                raise
            return default

    @staticmethod
    def _file_signature(path):
        """Assinatura barata para invalidar caches entre instâncias."""
        try:
            stat = os.stat(path)
            return stat.st_mtime_ns, stat.st_size
        except OSError:
            return None

    def load_all_records(self):
        """Retorna todos os registros do histórico em formato de lista de dicionários.
        
        Usa cache em memória para evitar parse de JSON a cada chamada. O cache
        é invalidado automaticamente após qualquer escrita via save_records().
        """
        self._ensure_cache_attrs()
        signature = self._file_signature(self.db_path)
        if self._records_cache is not None and signature == self._records_signature:
            return self._records_cache
        self._records_cache = self._read_json(
            self.db_path, list, [], label="banco de dados TSI"
        )
        self._records_signature = self._file_signature(self.db_path)
        return self._records_cache

    def save_records(self, new_records):
        """
        Recebe uma lista de registros (dict) raspados recentemente.
        Verifica duplicidades pela O.S. (chave 'Ordens de Serviço: OS')
        e adiciona apenas os registros inéditos ao banco.
        """
        if not new_records:
            return

        try:
            existing_records = self._read_json(
                self.db_path, list, [], strict=True, label="banco de dados TSI"
            )
        except Exception:
            logging.error("Histórico TSI preservado: a atualização foi cancelada porque o arquivo atual é inválido.")
            return 0
        
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
                self._atomic_write_json(
                    self.db_path, existing_records, ensure_ascii=False
                )
                logging.info(
                    f"Banco de Dados TSI atualizado com {added_count} novos registros "
                    "e dados complementares mesclados."
                )
                # Invalida o cache para que a próxima leitura reflita os novos dados
                self._records_cache = None
                self._records_signature = None
                self._leads_index_cache = None
            except Exception as e:
                logging.error(f"Erro ao salvar banco de dados TSI: {e}")
                
                
        return added_count

    def load_sent_surveys(self):
        """Retorna um set com os IDs (sf_id) das pesquisas que já foram enviadas pelo robô."""
        data = self._read_json(
            self.sent_path, list, [], label="histórico de pesquisas enviadas"
        )
        return set(data)

    @staticmethod
    def whatsapp_phone_key(phone):
        """Chave de comparação; não altera o telefone original extraído."""
        digits = re.sub(r'\D', '', str(phone or '')).lstrip('0')
        if len(digits) in (10, 11):
            digits = '55' + digits
        return digits if len(digits) in (12, 13) and digits.startswith('55') else ''

    def load_unavailable_whatsapp(self):
        path = os.path.join(self.app_data_dir, 'unavailable_whatsapp.json')
        signature = self._file_signature(path)
        if getattr(self, '_unavailable_signature', None) != signature or not hasattr(self, '_unavailable_cache'):
            self._unavailable_cache = self._read_json(path, dict, {}, label='números sem WhatsApp')
            self._unavailable_signature = signature
        return self._unavailable_cache

    def mark_whatsapp_unavailable(self, phone, item):
        key = self.whatsapp_phone_key(phone)
        if not key:
            return False
        path = os.path.join(self.app_data_dir, 'unavailable_whatsapp.json')
        try:
            records = self._read_json(path, dict, {}, strict=True, label='números sem WhatsApp')
            entry = records.setdefault(key, {'reason': 'WHATSAPP_PHONE_UNAVAILABLE', 'surveys': []})
            survey = {'id': str(item.get('id') or ''), 'tipo': str(item.get('tipo') or '')}
            if survey['id'] and survey not in entry['surveys']:
                entry['surveys'].append(survey)
            entry['confirmed_at'] = datetime.now(timezone.utc).isoformat()
            self._atomic_write_json(path, records)
            self._unavailable_cache = records
            self._unavailable_signature = self._file_signature(path)
            return True
        except Exception:
            logging.exception('Não foi possível salvar a confirmação de número sem WhatsApp.')
            return False

    def is_whatsapp_unavailable(self, item):
        records = self.load_unavailable_whatsapp()
        key = self.whatsapp_phone_key(item.get('telefone'))
        if key:
            # Um telefone diferente, vindo de nova extração, é avaliado normalmente.
            return key in records
        survey = {'id': str(item.get('id') or ''), 'tipo': str(item.get('tipo') or '')}
        # SSI pode trazer o telefone apenas na ficha, ausente na lista extraída.
        return bool(survey['id']) and any(survey in entry.get('surveys', []) for entry in records.values())

    def mark_survey_as_sent(self, survey_id: str):
        """Marca uma pesquisa como enviada pelo Whatsapp."""
        try:
            sent = self._read_json(
                self.sent_path, list, [], strict=True,
                label="histórico de pesquisas enviadas",
            )
        except Exception:
            logging.error("Histórico de envios preservado: não foi possível marcar a pesquisa como enviada.")
            return False
        if survey_id not in sent:
            sent.append(survey_id)
            try:
                self._atomic_write_json(self.sent_path, sent)
            except Exception as e:
                logging.error(f"Erro ao salvar histórico de pesquisas enviadas: {e}")
                return False
        return True

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
        """Retorna todos os registros do histórico SSI.
        
        Usa cache em memória invalidado em escritas via save_ssi_records().
        """
        self._ensure_cache_attrs()
        signature = self._file_signature(self.ssi_db_path)
        if self._ssi_cache is not None and signature == self._ssi_signature:
            return self._ssi_cache
        self._ssi_cache = self._read_json(
            self.ssi_db_path, list, [], label="banco de dados SSI"
        )
        self._ssi_signature = self._file_signature(self.ssi_db_path)
        return self._ssi_cache

    def save_ssi_records(self, new_records: list):
        """Atualiza o banco SSI evitando duplicidades de URL/ID."""
        try:
            current_records = self._read_json(
                self.ssi_db_path, list, [], strict=True, label="banco de dados SSI"
            )
        except Exception:
            logging.error("Histórico SSI preservado: a atualização foi cancelada porque o arquivo atual é inválido.")
            return False
        
        # Cria um mapa com base no ID da pesquisa extraído do link de Ação
        # (import re movido ao topo do módulo — sem custo repetido por iteração)
        existing_map = {}
        for r in current_records:
            acao = str(r.get('Ação', '')).strip()
            match = re.search(r'/([a-zA-Z0-9]{15,18})(?:\?|/|$)', acao)
            if match:
                existing_map[match.group(1)] = r
            else:
                # Se não tem ID, usa uma concatenação como fallback
                fallback_id = str(r.get('Relação de Posse: Name', '')) + str(r.get('Data de resposta SSI 2W', ''))
                if fallback_id: existing_map[fallback_id] = r
                
        for nr in new_records:
            acao = str(nr.get('Ação', '')).strip()
            match = re.search(r'/([a-zA-Z0-9]{15,18})(?:\?|/|$)', acao)
            if match:
                existing_map[match.group(1)] = nr
            else:
                fallback_id = str(nr.get('Relação de Posse: Name', '')) + str(nr.get('Data de resposta SSI 2W', ''))
                if fallback_id: existing_map[fallback_id] = nr
                
        updated_list = list(existing_map.values())
        try:
            self._atomic_write_json(
                self.ssi_db_path, updated_list, ensure_ascii=False
            )
            # Invalida o cache SSI
            self._ssi_cache = None
            self._ssi_signature = None
            return True
        except Exception as e:
            logging.error(f"Erro ao salvar banco SSI: {e}")
            return False

    def save_leads_mapping(self, leads_list: list):
        """
        Salva o mapeamento das O.S. / Posses extraídas na lista de envio/reenvio
        associando o número da O.S., Chassi ou Posse ao Nome do Cliente e Telefone.
        Isso permite cruzar com as respostas de auditoria e exibir o nome real do cliente.
        """
        self._ensure_cache_attrs()
        if not leads_list:
            return
            
        map_path = os.path.join(self.app_data_dir, "leads_map.json")
        try:
            current_map = self._read_json(
                map_path, dict, {}, strict=True, label="mapeamento de clientes"
            )
        except Exception:
            logging.error("Mapeamento de clientes preservado: a atualização foi cancelada.")
            return False

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
                self._atomic_write_json(
                    map_path, current_map, ensure_ascii=False
                )
                # Invalida o mapa e todos os índices derivados. Limpar apenas
                # ``_leads_index_cache`` não basta: get_leads_mapping() repõe
                # esse cache antes de find_lead() decidir se deve reconstruir
                # os índices tipados, deixando resultados antigos em memória.
                self._leads_index_cache = None
                self._typed_index_cache.clear()
                self._leads_map_mtime = 0.0
            except Exception as e:
                logging.error(f"Erro ao salvar leads_map.json: {e}")
                return False
        return True

    def get_leads_mapping(self) -> dict:
        """Retorna o dicionário de mapeamento OS/Posse -> Dados do Cliente higienizado.
        
        Usa mtime do arquivo para evitar releituras desnecessárias: o arquivo
        só é relido quando modificado desde a última leitura.
        """
        self._ensure_cache_attrs()
        map_path = os.path.join(self.app_data_dir, "leads_map.json")
        if not os.path.exists(map_path):
            return {}

        # Verifica mtime para decidir se o cache ainda é válido
        try:
            current_mtime = os.path.getmtime(map_path)
        except OSError:
            current_mtime = 0.0

        if self._leads_index_cache is not None and current_mtime == self._leads_map_mtime:
            # Arquivo não foi modificado desde a última leitura — retorna cache direto
            return self._leads_index_cache

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
                    self._atomic_write_json(
                        map_path, clean_map, ensure_ascii=False
                    )
                except Exception:
                    pass

            # Um arquivo alterado por outra instância também invalida os
            # índices derivados deste objeto.
            self._typed_index_cache.clear()
            self._leads_index_cache = clean_map
            self._leads_map_mtime = current_mtime
            return clean_map
        except Exception as e:
            logging.error(f"Erro ao ler leads_map: {e}")
            return {}

    @staticmethod
    def normalize_lead_key(value) -> str:
        """Normaliza OS, posse, chassi ou ID para cruzamento entre relatórios."""
        raw = str(value or "").strip().upper()
        if raw.lower() in ("", "nan", "none", "-", "sem os", "sem posse"):
            return ""
        normalized = re.sub(r"[^A-Z0-9]", "", raw)
        if normalized.isdigit():
            normalized = normalized.lstrip("0") or "0"
        return normalized

    def _build_leads_index(self, mapping: dict, tipo: str | None) -> dict:
        """Constrói o índice de busca normalizado a partir do mapeamento de leads.
        
        Centraliza a lógica de normalização de chaves para que find_lead()
        possa fazer um único lookup O(1) em vez de varrer o mapa a cada busca.
        """
        normalized_index: dict = {}
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
                index_seen: set = set()

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
        return normalized_index

    def find_lead(self, *keys, tipo: str = None) -> dict:
        """
        Busca um cliente mesmo quando a O.S. muda de formatação entre a fila
        e o auditor (zeros à esquerda, espaços, pontos, hífens ou OS completa).
        
        O índice de normalização é pré-computado e cacheado em memória;
        apenas a busca de candidatos é feita a cada chamada — O(k) onde k
        é o número de chaves passadas, não o tamanho do mapeamento.
        """
        self._ensure_cache_attrs()
        mapping = self.get_leads_mapping()
        if not mapping:
            return {}

        # Obtém ou constrói o índice cacheado
        # Chave de cache inclui o tipo para não misturar SSI e TSI
        cache_key = f"leads_index_{tipo or 'all'}"
        
        # O _leads_index_cache é invalidado (None) em qualquer escrita de mapa.
        # Aqui usamos um dict por tipo para suportar filtros simultâneos.
        if cache_key not in self._typed_index_cache:
            self._typed_index_cache[cache_key] = self._build_leads_index(mapping, tipo)

        normalized_index = self._typed_index_cache[cache_key]

        # Mantém a prioridade dos argumentos informados pelo chamador.
        candidates = []
        seen_candidates: set = set()

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
        try:
            lidos = self._read_json(
                path, list, [], strict=True, label="comunicados lidos"
            )
        except Exception:
            logging.error("Histórico de comunicados preservado: não foi possível registrar a leitura.")
            return False
        if msg_hash not in lidos:
            lidos.append(msg_hash)
            try:
                self._atomic_write_json(path, lidos)
            except Exception as e:
                logging.error(f"Erro ao salvar comunicado lido: {e}")
                return False
        return True
