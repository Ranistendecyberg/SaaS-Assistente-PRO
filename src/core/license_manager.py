import subprocess
import uuid
import urllib.request
import json
import datetime
import os
import time
from typing import Dict, Any, Optional
from src.core.supabase_desktop import DesktopBackendError, SupabaseDesktopClient

# =========================================================================
# ⚠️ CONFIGURAÇÕES DE NUVEM
# =========================================================================
FIREBASE_URL = "https://gerador-licencas-pesquisas-default-rtdb.firebaseio.com"
VALOR_MENSALIDADE_PADRAO = 250.00
VALOR_PROMO_TRIAL = 99.90

class LicenseManager:
    """Gerencia a identificação da máquina, validação no Firebase e pagamentos."""
    
    def __init__(self):
        self.chassi = self._obter_chassi_maquina()
        self._last_db_error = None
        self.usa_supabase = True
        self.secure_backend = SupabaseDesktopClient(self.chassi)
        self._last_license_data = {}
        self._last_system_config = {}

    def _obter_chassi_maquina(self) -> str:
        try:
            chassi = subprocess.check_output('wmic csproduct get uuid', shell=True, stderr=subprocess.DEVNULL).decode().split('\n')[1].strip()
            if len(chassi) >= 10 and chassi != "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF": 
                return chassi
        except Exception: 
            pass
        return str(uuid.getnode())

    def _obter_versao_atual(self) -> str:
        try:
            from src.version import __version__
            return __version__
        except Exception:
            return "1.6.0"

    def get_hardware_id(self) -> str:
        return self.chassi

    def precisa_migrar_para_supabase(self) -> bool:
        return not self.secure_backend.has_session()

    def modo_vinculo_inicial(self) -> str:
        if self.secure_backend.has_session():
            return "ready"
        return self.secure_backend.bootstrap_mode()

    def migrar_para_supabase(self, codigo: str) -> Dict[str, Any]:
        return self.secure_backend.claim_legacy_installation(codigo)

    def registrar_nova_instalacao_supabase(self, concessionaria: str,
                                           gestor: str, telefone: str) -> Dict[str, Any]:
        return self.secure_backend.register_new_installation(
            concessionaria, gestor, telefone
        )

    @staticmethod
    def _parse_iso_datetime(value):
        if not value:
            return None
        try:
            parsed = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone().replace(tzinfo=None)
            return parsed
        except (TypeError, ValueError):
            return None

    def _validar_licenca_supabase(self) -> Dict[str, Any]:
        if self.precisa_migrar_para_supabase():
            return {"status": "migracao_necessaria"}
        try:
            response = self.secure_backend.license_status(self._obter_versao_atual())
        except DesktopBackendError as error:
            if error.code in {"UNAUTHORIZED", "MIGRATION_REQUIRED"}:
                return {"status": "vinculo_invalido", "codigo_erro": error.code}
            self._registrar_erro_conexao(error)
            return {"status": "erro_conexao", "mensagem": "Não foi possível consultar a licença no servidor seguro."}

        license_data = dict(response.get("license") or {})
        company = dict(response.get("company") or {})
        usage = dict(response.get("usage") or {})
        self._last_system_config = dict(response.get("system") or {})
        expires_at = self._parse_iso_datetime(license_data.get("expires_at"))
        now = datetime.datetime.now()
        seconds_left = (expires_at - now).total_seconds() if expires_at else -1
        raw_type = str(license_data.get("license_type") or license_data.get("status") or "active").lower()
        if seconds_left <= 0 or str(license_data.get("status") or "").lower() in {"expired", "revoked", "suspended"}:
            status = "vencida"
            days_left = 0
        else:
            import math
            status = "trial" if raw_type == "trial" else "ativa"
            days_left = max(1, math.ceil(seconds_left / 86400))

        data = {
            "status": status,
            "tipo": status,
            "dias_restantes": days_left,
            "data_expiracao": expires_at.strftime("%Y-%m-%d %H:%M:%S") if expires_at else "",
            "mensagens_extras": int(license_data.get("extra_messages") or 0),
            "valor_mensalidade": float(license_data.get("monthly_price") or VALOR_MENSALIDADE_PADRAO),
            "links_relatorios": license_data.get("report_links") or {},
            "aviso_reajuste": license_data.get("adjustment_notice") or self._last_system_config.get("global_notice") or "",
            "diagnostico_detalhado_ate": license_data.get("detailed_diagnostics_until"),
            "concessionaria": company.get("name") or "",
            "gestor": company.get("manager_name") or "",
            "telefone": company.get("phone") or "",
            "enviadas_hoje": int(usage.get("messages_used") or 0),
            "limite_diario": int(usage.get("daily_limit") or (6 if status == "trial" else 30)),
            "system": self._last_system_config,
        }
        self._last_license_data = data
        try:
            from src.core.paths import get_base_dir
            path = os.path.join(get_base_dir(), "app_data", "license_links.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as file:
                json.dump(data["links_relatorios"], file, ensure_ascii=False)
        except Exception:
            pass
        return data

    def _db_get(self, caminho: str) -> Optional[Any]:
        self._last_db_error = None
        try:
            req = urllib.request.Request(f"{FIREBASE_URL}/{caminho}.json", method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            self._last_db_error = e
            return None

    def _registrar_erro_conexao(self, erro: Exception):
        """Registra falhas de consulta sem transformá-las em novo cadastro."""
        try:
            from src.core.paths import get_base_dir
            log_dir = os.path.join(get_base_dir(), "app_data")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "license_connection.log")
            momento = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            erro_desc = f"{type(erro).__name__}: {erro}" if erro else "Erro desconhecido"
            with open(log_path, "a", encoding="utf-8") as arquivo:
                arquivo.write(f"[{momento}] Falha ao consultar licença: {erro_desc}\n")
        except Exception:
            pass

    def _consultar_licenca_com_retry(self, tentativas: int = 3):
        """
        Retorna (dados, erro). JSON nulo em uma resposta bem-sucedida significa
        cadastro inexistente; indisponibilidade e timeout são erros distintos.
        """
        ultimo_erro = None
        for tentativa in range(max(1, tentativas)):
            dados = self._db_get(f"licencas/{self.chassi}")
            erro_atual = self._last_db_error
            if erro_atual is None:
                return dados, None

            ultimo_erro = erro_atual
            if tentativa < tentativas - 1:
                time.sleep(0.5 * (tentativa + 1))

        self._registrar_erro_conexao(ultimo_erro)
        return None, ultimo_erro

    def _db_put(self, caminho: str, dados: Any):
        try:
            req = urllib.request.Request(f"{FIREBASE_URL}/{caminho}.json", method="PUT", data=json.dumps(dados).encode())
            urllib.request.urlopen(req, timeout=5)
            return True
        except: 
            return False

    def _db_patch(self, caminho: str, dados: Any):
        """Atualiza um nó ou múltiplos caminhos do Firebase em uma única operação."""
        try:
            sufixo = f"/{caminho}.json" if caminho else "/.json"
            req = urllib.request.Request(
                f"{FIREBASE_URL}{sufixo}",
                method="PATCH",
                data=json.dumps(dados).encode(),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception:
            return False

    @staticmethod
    def _parse_data_hora(valor):
        if not valor:
            return None
        texto = str(valor).strip()
        for formato in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y"
        ):
            try:
                return datetime.datetime.strptime(texto, formato)
            except ValueError:
                continue
        return None

    @classmethod
    def _fim_do_dia_licenca(cls, valor):
        data = cls._parse_data_hora(valor)
        if not data:
            return None
        return data.replace(hour=22, minute=0, second=0, microsecond=0)

    def _calcular_vencimento_por_dias(self, dados_atuais: dict, dias: int):
        agora = datetime.datetime.now()
        base_dt = agora
        vencimento_atual = self._fim_do_dia_licenca(dados_atuais.get("data_expiracao"))
        if vencimento_atual and vencimento_atual > agora:
            base_dt = vencimento_atual
        return (base_dt + datetime.timedelta(days=dias)).replace(
            hour=22, minute=0, second=0, microsecond=0
        )

    def validar_licenca(self) -> Dict[str, Any]:
        """
        Consulta o Firebase para checar o status e a data de expiração da máquina.
        Também atualiza a versão reportada para o painel administrativo.
        """
        if getattr(self, "usa_supabase", False):
            return self._validar_licenca_supabase()

        agora = datetime.datetime.now()
        dados, erro_conexao = self._consultar_licenca_com_retry()

        if erro_conexao is not None:
            return {
                "status": "erro_conexao",
                "mensagem": "Não foi possível consultar o cadastro no Firebase."
            }
        
        # Primeira vez abrindo o sistema na máquina
        if not dados:
            return {"status": "nao_registrado"}
            
        # Máquina já cadastrada, verificar validade
        try:
            import math
            data_exp_raw = dados["data_expiracao"]
            try:
                data_expiracao = datetime.datetime.strptime(data_exp_raw, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                data_expiracao = datetime.datetime.strptime(data_exp_raw, "%Y-%m-%d")

            # REGRA DE EXPEDIENTE: A licença é válida durante todo o dia útil até as 22:00:00 da data de expiração
            corte_expiracao = max(
                data_expiracao,
                datetime.datetime(data_expiracao.year, data_expiracao.month, data_expiracao.day, 22, 0, 0)
            )
            
            segundos_restantes = (corte_expiracao - agora).total_seconds()
            
            if segundos_restantes <= 0:
                dados["status"] = "vencida"
                dados["dias_restantes"] = 0
            else:
                dias_restantes = math.ceil(segundos_restantes / 86400)
                dados["dias_restantes"] = max(1, dias_restantes)
                
                # Preserva se a licença é trial ou assinante ativa
                tipo_licenca = dados.get("tipo")
                if not tipo_licenca:
                    tipo_licenca = "trial" if dados.get("status") == "trial" else "ativa"
                dados["tipo"] = tipo_licenca
                dados["status"] = tipo_licenca
                dados["data_expiracao"] = corte_expiracao.strftime("%Y-%m-%d %H:%M:%S")
                    
            # Promoção desativada: cobrança padrão direta
            dados["promo_ativa"] = False
            dados["segundos_promo"] = 0
                
            # Injetar contagem de envios diários no retorno
            enviadas, limite = self.obter_contagem_diaria(dados.get("status", "trial"))
            dados["enviadas_hoje"] = enviadas
            dados["limite_diario"] = limite
            
            # Injetar valor da mensalidade e aviso de reajuste
            dados["valor_mensalidade"] = self.obter_valor_mensalidade(dados)
            dados["aviso_reajuste"] = dados.get("aviso_reajuste", "")
            
            # Sincronizar versão atual do sistema no Firebase
            dados["versao"] = self._obter_versao_atual()
            
            # Persistir links dos relatórios localmente para leitura síncrona
            links = dados.get("links_relatorios")
            try:
                from src.core.paths import get_base_dir
                caminho_links = os.path.join(get_base_dir(), "app_data", "license_links.json")
                os.makedirs(os.path.dirname(caminho_links), exist_ok=True)
                with open(caminho_links, "w", encoding="utf-8") as f:
                    json.dump(links if links else {}, f, ensure_ascii=False)
            except Exception as e:
                print("Erro ao salvar links locais:", e)
            
            # Atualiza no banco para manter os dias e a versão corretos visualmente
            self._db_put(f"licencas/{self.chassi}", dados)
            return dados
            
        except Exception as e:
            print("Erro ao parsear data", e)
            return {"status": "vencida", "dias_restantes": 0, "valor_mensalidade": VALOR_MENSALIDADE_PADRAO}

    def obter_valor_mensalidade(self, dados_licenca: Optional[Dict[str, Any]] = None) -> float:
        """
        Retorna o valor da mensalidade para esta máquina:
        1. Se a máquina possuir 'valor_mensalidade' personalizado no Firebase, usa ele.
        2. Se não possuir, busca 'sistema/preco_padrao' no Firebase.
        3. Fallback: VALOR_MENSALIDADE_PADRAO (250.00).
        """
        if getattr(self, "usa_supabase", False):
            dados_licenca = dados_licenca or self._last_license_data or self.validar_licenca()
            return float(dados_licenca.get("valor_mensalidade") or VALOR_MENSALIDADE_PADRAO)
        try:
            if dados_licenca is None:
                dados_licenca = self._db_get(f"licencas/{self.chassi}") or {}
                
            valor_custom = dados_licenca.get("valor_mensalidade")
            if valor_custom is not None:
                v = float(valor_custom)
                if v > 0:
                    return v
                    
            dados_sistema = self._db_get("sistema") or {}
            preco_padrao = dados_sistema.get("preco_padrao")
            if preco_padrao is not None:
                p = float(preco_padrao)
                if p > 0:
                    return p
        except Exception:
            pass
        return VALOR_MENSALIDADE_PADRAO

    def obter_aviso_reajuste(self, dados_licenca: Optional[Dict[str, Any]] = None) -> str:
        if getattr(self, "usa_supabase", False):
            dados_licenca = dados_licenca or self._last_license_data or self.validar_licenca()
            return str(dados_licenca.get("aviso_reajuste") or "").strip()
        """Retorna uma mensagem personalizada de reajuste/aviso da máquina ou comunicado global do sistema."""
        try:
            if dados_licenca is None:
                dados_licenca = self._db_get(f"licencas/{self.chassi}") or {}
            
            # 1. Aviso específico para a máquina
            aviso_ind = dados_licenca.get("aviso_reajuste", "")
            if aviso_ind and str(aviso_ind).strip():
                return str(aviso_ind).strip()
                
            # 2. Fallback: Comunicado global do sistema
            dados_sistema = self._db_get("sistema") or {}
            aviso_global = dados_sistema.get("aviso_global") or dados_sistema.get("comunicado") or ""
            return str(aviso_global).strip()
        except Exception:
            return ""
            
    def registrar_nova_licenca(self, concessionaria: str, gestor: str, telefone: str):
        """
        Registra uma nova licença trial para a máquina e associa os dados do cliente.
        A licença expira às 22:00:00 (fim do expediente) do último dia de testes.
        """
        agora = datetime.datetime.now()
        vencimento = (agora + datetime.timedelta(days=2)).replace(hour=22, minute=0, second=0, microsecond=0)
        dados = {
            "status": "trial",
            "tipo": "trial",
            "concessionaria": concessionaria,
            "gestor": gestor,
            "telefone": telefone,
            "data_expiracao": vencimento.strftime("%Y-%m-%d %H:%M:%S"),
            "dias_restantes": 2,
            "promo_ativa": False,
            "segundos_promo": 0,
            "versao": self._obter_versao_atual()
        }
        self._db_put(f"licencas/{self.chassi}", dados)
        return dados

    def atualizar_dados_cliente(self, concessionaria: str, gestor: str, telefone: str):
        dados = self._db_get(f"licencas/{self.chassi}") or {}
        dados["concessionaria"] = concessionaria
        dados["gestor"] = gestor
        dados["telefone"] = telefone
        dados["versao"] = self._obter_versao_atual()
        self._db_put(f"licencas/{self.chassi}", dados)
        return dados

    def enviar_heartbeat(self, is_online: bool):
        if getattr(self, "usa_supabase", False):
            if is_online:
                import threading
                threading.Thread(target=self._validar_licenca_supabase, daemon=True).start()
            return
        def worker():
            try:
                agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ver = self._obter_versao_atual()
                req1 = urllib.request.Request(f"{FIREBASE_URL}/licencas/{self.chassi}/online.json", method="PUT", data=json.dumps(is_online).encode())
                urllib.request.urlopen(req1, timeout=5)
                req2 = urllib.request.Request(f"{FIREBASE_URL}/licencas/{self.chassi}/ultimo_acesso.json", method="PUT", data=json.dumps(agora).encode())
                urllib.request.urlopen(req2, timeout=5)
                req3 = urllib.request.Request(f"{FIREBASE_URL}/licencas/{self.chassi}/versao.json", method="PUT", data=json.dumps(ver).encode())
                urllib.request.urlopen(req3, timeout=5)
            except Exception:
                pass
                
        if not is_online:
            worker() # Run synchronously to guarantee delivery before exit
        else:
            import threading
            threading.Thread(target=worker, daemon=True).start()

    def obter_contagem_diaria(self, status: str = None) -> tuple[int, int]:
        if getattr(self, "usa_supabase", False):
            data = self._last_license_data or self.validar_licenca()
            inferred_status = status or data.get("status", "trial")
            limit = int(data.get("limite_diario") or (6 if inferred_status == "trial" else 30))
            return int(data.get("enviadas_hoje") or 0), limit
        if status is None:
            dados = self.validar_licenca()
            status = dados.get("status", "trial")
            
        # Limites
        limite = 6 if status == "trial" else 30
        
        from src.core.paths import get_base_dir
        import os, json, base64
        base_dir = get_base_dir()
        app_data_dir = os.path.join(base_dir, "app_data")
        path = os.path.join(app_data_dir, "trial_limits.b64")
        
        hoje = datetime.datetime.now().strftime("%Y-%m-%d")
        
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    conteudo = f.read()
                    limits = json.loads(base64.b64decode(conteudo).decode("utf-8"))
            except:
                limits = {"data": hoje, "enviadas": 0}
        else:
            limits = {"data": hoje, "enviadas": 0}
            
        if limits.get("data") != hoje:
            limits = {"data": hoje, "enviadas": 0}
            
        return limits.get("enviadas", 0), limite
        
    def checar_limite_envio(self) -> tuple[bool, str]:
        """Apenas checa se há limite, sem descontar."""
        dados = self.validar_licenca()
        mensagens_extras = dados.get("mensagens_extras", 0)
        
        if mensagens_extras > 0:
            return True, ""
            
        enviadas, limite = self.obter_contagem_diaria(dados.get("status", "trial"))
        if enviadas >= limite:
            if limite == 6:
                return False, "O Modo de Testes permite enviar apenas 6 mensagens por dia.\n\nRenove sua assinatura ou insira uma Chave de Bônus para continuar."
            else:
                return False, "Você atingiu o limite de 30 mensagens por dia do seu plano.\n\nInsira uma Chave de Mensagens Extras para continuar."
        return True, ""

    def registrar_envio(self) -> tuple[bool, str]:
        if getattr(self, "usa_supabase", False):
            try:
                result = self.secure_backend.consume_message()
            except DesktopBackendError as error:
                if error.code == "NETWORK_ERROR":
                    return False, "Não foi possível confirmar o limite de envios. Verifique a internet e tente novamente."
                return False, "O envio não foi autorizado pelo servidor de licenças."
            allowed = result.get("ok", result.get("allowed", result.get("success", False)))
            if allowed:
                self._last_license_data = {}
                return True, ""
            reason = str(result.get("reason") or result.get("error") or "").lower()
            if "trial" in reason:
                return False, "O Modo de Testes permite enviar apenas 6 mensagens por dia."
            return False, "Você atingiu o limite diário de mensagens do seu plano."
        dados = self.validar_licenca()
        mensagens_extras = dados.get("mensagens_extras", 0)
        
        # 1. Tenta consumir pacote extra primeiro (ignora limites diários)
        if mensagens_extras > 0:
            novo_saldo = mensagens_extras - 1
            self._db_put(f"licencas/{self.chassi}/mensagens_extras", novo_saldo)
            return True, ""
            
        # 2. Se não tem pacote extra, cai na regra do limite diário
        enviadas, limite = self.obter_contagem_diaria(dados.get("status", "trial"))
        
        if enviadas >= limite:
            if limite == 6:
                return False, "O Modo de Testes permite enviar apenas 6 mensagens por dia.\n\nRenove sua assinatura ou insira uma Chave de Bônus para continuar."
            else:
                return False, "Você atingiu o limite de 30 mensagens por dia do seu plano.\n\nInsira uma Chave de Mensagens Extras para continuar."
                
        # Incrementar
        from src.core.paths import get_base_dir
        import os, json, base64
        base_dir = get_base_dir()
        app_data_dir = os.path.join(base_dir, "app_data")
        os.makedirs(app_data_dir, exist_ok=True)
        path = os.path.join(app_data_dir, "trial_limits.b64")
        
        hoje = datetime.datetime.now().strftime("%Y-%m-%d")
        
        limits = {"data": hoje, "enviadas": enviadas + 1}
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                json_str = json.dumps(limits)
                b64_str = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
                f.write(b64_str)
        except Exception as e:
            print("Erro gravando limits", e)
            
        return True, ""

    def registrar_log_auditoria(self, telefone: str, tipo: str, cliente: str):
        if getattr(self, "usa_supabase", False):
            try:
                import threading
                event = {
                    "level": "INFO", "component": "messaging", "event": "MESSAGE_SENT",
                    "details": {"tipo": str(tipo)[:40]},
                }
                threading.Thread(
                    target=lambda: self.secure_backend.send_telemetry([event]), daemon=True
                ).start()
            except Exception:
                pass
            return
        """Registra um log silencioso no Firebase para auditoria do admin."""
        try:
            agora = datetime.datetime.now()
            hoje_str = agora.strftime("%Y-%m-%d")
            hora_str = agora.strftime("%H:%M:%S")
            timestamp = str(int(agora.timestamp()))
            
            # Mascarar o telefone para LGPD (ex: 55119****8888)
            tel_mask = telefone
            if len(telefone) > 8:
                tel_mask = telefone[:6] + "****" + telefone[-4:]
                
            log_data = {
                "hora": hora_str,
                "tipo": tipo,
                "cliente": cliente,
                "telefone_mask": tel_mask
            }
            
            # Dispara a requisição em background para não travar a UI
            import threading
            def _enviar():
                self._db_put(f"licencas/{self.chassi}/logs/{hoje_str}/{timestamp}", log_data)
                
            threading.Thread(target=_enviar, daemon=True).start()
        except:
            pass

    def estender_licenca(self, dias: int = 30):
        """Estende a licença da máquina garantindo validade até às 22:00:00 (fim do expediente)."""
        dados_atuais = self._db_get(f"licencas/{self.chassi}") or {}
        vencimento = self._calcular_vencimento_por_dias(dados_atuais, dias)
        exp_str = vencimento.strftime("%Y-%m-%d %H:%M:%S")
        self._db_patch(
            f"licencas/{self.chassi}",
            {"status": "ativa", "tipo": "ativa", "data_expiracao": exp_str}
        )
        return {"status": "ativa", "tipo": "ativa", "data_expiracao": exp_str}

    def ativar_chave(self, chave: str) -> Dict[str, Any]:
        chave = chave.strip().upper()
        if getattr(self, "usa_supabase", False):
            if not chave:
                return {"sucesso": False, "mensagem": "Chave inválida."}
            try:
                result = self.secure_backend.redeem_key(chave)
                success = bool(result.get("ok", result.get("success", False)))
                if success:
                    self._last_license_data = {}
                    return {"sucesso": True, "mensagem": result.get("message") or "Chave ativada com sucesso!"}
                return {"sucesso": False, "mensagem": result.get("message") or "Esta chave não pôde ser utilizada."}
            except DesktopBackendError as error:
                messages = {
                    "INVALID_KEY": "Chave inválida.",
                    "NETWORK_ERROR": "Não foi possível consultar a chave. Verifique a internet.",
                    "UNAUTHORIZED": "O vínculo deste computador não é mais válido.",
                }
                return {"sucesso": False, "mensagem": messages.get(error.code, "Chave não encontrada, utilizada ou expirada.")}
        """Valida uma chave inserida pelo usuário e estende a licença."""
        chave = chave.strip().upper()
        if not chave:
            return {"sucesso": False, "mensagem": "Chave inválida."}
            
        dados_chave = self._db_get(f"chaves/{chave}")
        if self._last_db_error is not None:
            return {
                "sucesso": False,
                "mensagem": "Não foi possível consultar a chave no Firebase. Verifique a conexão e tente novamente."
            }
        if not dados_chave:
            return {"sucesso": False, "mensagem": "Chave não encontrada no servidor."}

        status_chave = str(dados_chave.get("status", "nova")).strip().lower()
        if status_chave == "expirada":
            return {"sucesso": False, "mensagem": "Esta chave expirou antes de ser utilizada."}
        if status_chave != "nova":
            return {"sucesso": False, "mensagem": "Esta chave já foi utilizada."}

        agora = datetime.datetime.now()
        expira_em = self._parse_data_hora(
            dados_chave.get("data_expiracao_chave") or dados_chave.get("expira_em")
        )
        if expira_em and agora > expira_em:
            self._db_patch(
                f"chaves/{chave}",
                {
                    "status": "expirada",
                    "data_expiracao_registrada": agora.strftime("%Y-%m-%d %H:%M:%S")
                }
            )
            return {
                "sucesso": False,
                "mensagem": "Esta chave expirou. O prazo de utilização era de 24 horas após a emissão."
            }

        tipo_chave = dados_chave.get("tipo", "dias")
        dados_atuais = self._db_get(f"licencas/{self.chassi}")
        if self._last_db_error is not None:
            return {
                "sucesso": False,
                "mensagem": "Não foi possível consultar a licença atual. Verifique a conexão e tente novamente."
            }
        dados_atuais = dados_atuais or {}

        atualizacoes_licenca = {
            "concessionaria": dados_chave.get("concessionaria", "Desconhecida")
        }

        if tipo_chave == "mensagens":
            quantidade = int(dados_chave.get("quantidade", 6))
            saldo_atual = int(dados_atuais.get("mensagens_extras", 0) or 0)
            atualizacoes_licenca["mensagens_extras"] = saldo_atual + quantidade
            mensagem_sucesso = f"Bônus ativado com sucesso!\nForam adicionadas {quantidade} mensagens extras ao seu pacote."
        elif tipo_chave == "data_vencimento":
            vencimento_solicitado = self._fim_do_dia_licenca(dados_chave.get("data_vencimento"))
            if not vencimento_solicitado:
                return {"sucesso": False, "mensagem": "A chave possui uma data de vencimento inválida."}

            vencimento_atual = self._fim_do_dia_licenca(dados_atuais.get("data_expiracao"))
            vencimento_final = max(
                data for data in (vencimento_solicitado, vencimento_atual)
                if data is not None
            )
            exp_str = vencimento_final.strftime("%Y-%m-%d %H:%M:%S")
            atualizacoes_licenca.update({
                "status": "ativa",
                "tipo": "ativa",
                "data_expiracao": exp_str
            })
            mensagem_sucesso = (
                "Licença ativada com sucesso!\n"
                f"Válida até {vencimento_final.strftime('%d/%m/%Y')} às 22:00."
            )
        else:
            dias_ganhos = int(dados_chave.get("dias", 30))
            vencimento_final = self._calcular_vencimento_por_dias(dados_atuais, dias_ganhos)
            atualizacoes_licenca.update({
                "status": "ativa",
                "tipo": "ativa",
                "data_expiracao": vencimento_final.strftime("%Y-%m-%d %H:%M:%S")
            })
            mensagem_sucesso = f"Licença ativada com sucesso!\nForam adicionados {dias_ganhos} dias."

        agora_str = agora.strftime("%Y-%m-%d %H:%M:%S")
        atualizacoes_atomicas = {
            f"licencas/{self.chassi}/{campo}": valor
            for campo, valor in atualizacoes_licenca.items()
        }
        atualizacoes_atomicas.update({
            f"chaves/{chave}/status": "usada",
            f"chaves/{chave}/chassi_vinculado": self.chassi,
            f"chaves/{chave}/data_uso": agora_str
        })
        if not self._db_patch("", atualizacoes_atomicas):
            return {
                "sucesso": False,
                "mensagem": "Não foi possível concluir a ativação no Firebase. A chave não foi consumida."
            }

        return {"sucesso": True, "mensagem": mensagem_sucesso}

    def gerar_pix(self, amount: Optional[float] = None) -> Dict[str, Any]:
        try:
            return self.secure_backend.create_pix()
        except DesktopBackendError as error:
            message = (
                "Não foi possível conectar ao servidor de pagamentos. Tente novamente."
                if error.code == "NETWORK_ERROR"
                else "Não foi possível gerar o PIX com segurança."
            )
            return {"sucesso": False, "mensagem": message}

    def verificar_pagamento(self, payment_id) -> bool:
        try:
            result = self.secure_backend.check_pix(str(payment_id))
            if result.get("aprovado"):
                self._last_license_data = {}
                return True
            return False
        except DesktopBackendError:
            return False
