"""Licenciamento seguro da versão 2.0, exclusivamente via Supabase."""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import re
import subprocess
import threading
import uuid
from typing import Any, Dict, Optional

from src.core.paths import get_base_dir
from src.core.supabase_desktop import DesktopBackendError, SupabaseDesktopClient


VALOR_MENSALIDADE_PADRAO = 300.00


class LicenseManager:
    """Gerencia a licença do dispositivo junto ao backend Supabase.

    Mudanças de escalabilidade (2.0.7):
    - Singleton via ``get_instance()``: apenas uma instância por processo,
      evitando múltiplos subprocessos ``powershell`` e múltiplas instâncias
      de ``SupabaseDesktopClient`` em paralelo.
    - ``chassi`` cacheado como variável de classe: o subprocess só é lançado
      uma vez por processo, independentemente de quantas telas usam o manager.
    - Construtor idempotente: chamar ``LicenseManager()`` diretamente ainda
      funciona, mas retorna o mesmo estado singleton internamente.
    """

    # ------------------------------------------------------------------
    # Controle de singleton
    # ------------------------------------------------------------------
    _instance: Optional["LicenseManager"] = None
    _instance_lock: threading.Lock = threading.Lock()
    _cached_chassi: str = ""          # hardware ID cacheado entre instâncias

    @classmethod
    def get_instance(cls) -> "LicenseManager":
        """Retorna a instância singleton, criando-a na primeira chamada.

        Toda a aplicação deve usar este método para obter o LicenseManager.
        O construtor direto ``LicenseManager()`` ainda funciona para testes
        e código legado, mas cria uma instância independente.
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = object.__new__(cls)
                    instance._init_once()
                    cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        """Inicializa a instância (para compatibilidade com código legado).

        Nota: Use ``LicenseManager.get_instance()`` na aplicação para
        garantir que apenas um objeto compartilhe o estado de licença.
        """
        if not hasattr(self, "_initialized"):
            self._init_once()

    def _init_once(self) -> None:
        """Inicialização real — executada apenas uma vez por processo."""
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.chassi = self._obter_chassi_maquina()
        self.secure_backend = SupabaseDesktopClient(self.chassi)
        self._last_license_data: Dict[str, Any] = {}
        self._last_system_config: Dict[str, Any] = {}

    def _obter_chassi_maquina(self) -> str:
        """Obtém o UUID de hardware do sistema.

        Usa cache de classe para que o subprocess ``powershell`` seja
        lançado somente uma vez por processo, mesmo que múltiplas telas
        instanciem ``LicenseManager()`` no mesmo ciclo de vida.
        """
        if LicenseManager._cached_chassi:
            return LicenseManager._cached_chassi

        try:
            output = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID",
                ],
                shell=False,
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).decode(errors="ignore").splitlines()
            # O PowerShell normalmente devolve apenas uma linha. A leitura
            # antiga exigia duas linhas e, por isso, quase sempre caía no MAC.
            for line in output:
                value = line.strip().upper()
                if (
                    re.fullmatch(
                        r"[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}",
                        value,
                    )
                    and value not in {
                        "00000000-0000-0000-0000-000000000000",
                        "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
                    }
                ):
                    LicenseManager._cached_chassi = value
                    return value
        except (OSError, subprocess.SubprocessError):
            pass

        # Em algumas instalações corporativas o acesso ao WMI/CIM é negado.
        # MachineGuid é estável entre mudanças de Wi-Fi, VPN e adaptadores,
        # ao contrário de uuid.getnode(). Guardamos somente um hash derivado.
        try:
            import winreg

            access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                access,
            ) as key:
                machine_guid = str(winreg.QueryValueEx(key, "MachineGuid")[0]).strip()
            if len(machine_guid) >= 16:
                digest = hashlib.sha256(
                    f"SaaSAssistentePRO:{machine_guid}".encode("utf-8")
                ).hexdigest().upper()
                value = f"WIN-{digest[:32]}"
                LicenseManager._cached_chassi = value
                return value
        except (ImportError, OSError, ValueError):
            pass

        fallback = str(uuid.getnode())
        LicenseManager._cached_chassi = fallback
        return fallback

    @staticmethod
    def _obter_versao_atual() -> str:
        try:
            from src.version import __version__
            return __version__
        except Exception:
            return "2.0.0"

    def get_hardware_id(self) -> str:
        return self.chassi

    def precisa_configurar_primeiro_acesso(self) -> bool:
        return not self.secure_backend.has_session()

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

    def _registrar_erro_conexao(self, error: Exception) -> None:
        try:
            log_dir = os.path.join(get_base_dir(), "app_data")
            os.makedirs(log_dir, exist_ok=True)
            moment = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(os.path.join(log_dir, "license_connection.log"), "a", encoding="utf-8") as file:
                file.write(f"[{moment}] Falha ao consultar licença: {type(error).__name__}\n")
        except Exception:
            pass

    def _validar_licenca_supabase(self) -> Dict[str, Any]:
        if self.precisa_configurar_primeiro_acesso():
            return {"status": "primeiro_acesso_necessario"}
        try:
            response = self.secure_backend.license_status(self._obter_versao_atual())
        except DesktopBackendError as error:
            if error.code in {"UNAUTHORIZED", "INSTALLATION_SESSION_REQUIRED"}:
                return {"status": "vinculo_invalido", "codigo_erro": error.code}
            self._registrar_erro_conexao(error)
            return {
                "status": "erro_conexao",
                "mensagem": "Não foi possível consultar a licença no servidor seguro.",
            }

        license_data = dict(response.get("license") or {})
        company = dict(response.get("company") or {})
        usage = dict(response.get("usage") or {})
        self._last_system_config = dict(response.get("system") or {})
        expires_at = self._parse_iso_datetime(license_data.get("expires_at"))
        seconds_left = (
            (expires_at - datetime.datetime.now()).total_seconds() if expires_at else -1
        )
        raw_status = str(license_data.get("status") or "").lower()
        raw_type = str(
            license_data.get("license_type") or license_data.get("status") or "active"
        ).lower()
        if seconds_left <= 0 or raw_status in {
            "expired", "revoked", "suspended", "blocked", "cancelled"
        }:
            status = "vencida"
            days_left = 0
        else:
            status = "trial" if raw_type == "trial" else "ativa"
            days_left = max(1, math.ceil(seconds_left / 86400))

        data = {
            "status": status,
            "tipo": status,
            "dias_restantes": days_left,
            "data_expiracao": expires_at.strftime("%Y-%m-%d %H:%M:%S") if expires_at else "",
            "mensagens_extras": int(license_data.get("extra_messages") or 0),
            "valor_mensalidade": float(
                license_data.get("monthly_price") or VALOR_MENSALIDADE_PADRAO
            ),
            "links_relatorios": license_data.get("report_links") or {},
            "aviso_reajuste": license_data.get("adjustment_notice")
            or self._last_system_config.get("global_notice") or "",
            "diagnostico_detalhado_ate": license_data.get("detailed_diagnostics_until"),
            "concessionaria": company.get("name") or "",
            "gestor": company.get("manager_name") or "",
            "telefone": company.get("phone") or "",
            "enviadas_hoje": int(usage.get("messages_used") or 0),
            "limite_lote": max(1, min(1000, int(license_data.get("batch_limit") or 1))),
            "limite_diario": int(
                usage.get("daily_limit") or (6 if status == "trial" else 30)
            ),
            "system": self._last_system_config,
        }
        self._last_license_data = data
        self._save_report_links(data["links_relatorios"])
        return data

    @staticmethod
    def _save_report_links(links: Dict[str, Any]) -> None:
        try:
            path = os.path.join(get_base_dir(), "app_data", "license_links.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            temporary = path + ".tmp"
            with open(temporary, "w", encoding="utf-8") as file:
                json.dump(links, file, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        except Exception:
            pass

    def validar_licenca(self) -> Dict[str, Any]:
        return self._validar_licenca_supabase()

    def obter_valor_mensalidade(
        self, dados_licenca: Optional[Dict[str, Any]] = None
    ) -> float:
        data = dados_licenca or self._last_license_data or self.validar_licenca()
        try:
            return float(data.get("valor_mensalidade") or VALOR_MENSALIDADE_PADRAO)
        except (TypeError, ValueError):
            return VALOR_MENSALIDADE_PADRAO

    def obter_aviso_reajuste(
        self, dados_licenca: Optional[Dict[str, Any]] = None
    ) -> str:
        data = dados_licenca or self._last_license_data or self.validar_licenca()
        return str(data.get("aviso_reajuste") or "").strip()

    def enviar_heartbeat(self, is_online: bool) -> None:
        def worker():
            try:
                self.secure_backend.heartbeat(is_online, self._obter_versao_atual())
            except DesktopBackendError:
                pass

        if is_online:
            threading.Thread(target=worker, daemon=True).start()
        else:
            worker()

    def obter_contagem_diaria(self, status: str = None) -> tuple[int, int]:
        data = self._last_license_data or self.validar_licenca()
        inferred = status or data.get("status", "trial")
        limit = int(data.get("limite_diario") or (6 if inferred == "trial" else 30))
        return int(data.get("enviadas_hoje") or 0), limit

    def checar_limite_envio(self) -> tuple[bool, str]:
        data = self.validar_licenca()
        if data.get("status") not in {"trial", "ativa"}:
            return False, "A licença deste computador não está disponível para envios."
        if int(data.get("mensagens_extras") or 0) > 0:
            return True, ""
        sent, limit = self.obter_contagem_diaria(data.get("status"))
        if sent < limit:
            return True, ""
        if limit == 6:
            return False, "O Modo de Testes permite enviar apenas 6 mensagens por dia."
        return False, f"Você atingiu o limite diário de {limit} mensagens do seu plano."

    def registrar_envio(self) -> tuple[bool, str]:
        try:
            result = self.secure_backend.consume_message()
        except DesktopBackendError as error:
            if error.code == "NETWORK_ERROR":
                return False, "Não foi possível confirmar o limite. Verifique a internet."
            return False, "O envio não foi autorizado pelo servidor de licenças."
        allowed = result.get("ok", result.get("allowed", result.get("success", False)))
        if allowed:
            self._last_license_data = {}
            return True, ""
        reason = str(result.get("reason") or result.get("error") or "").lower()
        if "trial" in reason:
            return False, "O Modo de Testes permite enviar apenas 6 mensagens por dia."
        return False, "Você atingiu o limite diário de mensagens do seu plano."

    def reservar_envio(self) -> tuple[bool, str, str]:
        reservation_id = str(uuid.uuid4())
        try:
            result = self.secure_backend.reserve_message(reservation_id)
        except DesktopBackendError as error:
            if error.code == "NETWORK_ERROR":
                return False, "Não foi possível reservar o envio. Verifique a internet.", ""
            return False, "O servidor não autorizou este envio.", ""
        allowed = bool(result.get("ok") and result.get("allowed", True))
        if allowed:
            self._last_license_data = {}
            return True, "", reservation_id
        if str(result.get("error") or "").upper() == "DAILY_LIMIT_REACHED":
            limit = result.get("daily_limit")
            return False, f"Você atingiu o limite diário de {limit} mensagens.", ""
        return False, "O servidor não autorizou este envio.", ""

    def confirmar_envio(self, reservation_id: str) -> tuple[bool, str]:
        try:
            result = self.secure_backend.confirm_message(reservation_id)
        except DesktopBackendError:
            return False, "O envio ocorreu, mas a confirmação da cota ficou pendente."
        self._last_license_data = {}
        return bool(result.get("ok")), "" if result.get("ok") else "A confirmação da cota ficou pendente."

    def liberar_reserva_envio(self, reservation_id: str) -> tuple[bool, str]:
        if not reservation_id:
            return True, ""
        try:
            result = self.secure_backend.release_message(reservation_id)
        except DesktopBackendError:
            return False, "Não foi possível devolver a reserva ao servidor neste momento."
        self._last_license_data = {}
        return bool(result.get("ok")), "" if result.get("ok") else "A reserva não pôde ser devolvida."

    def registrar_log_auditoria(self, telefone: str, tipo: str, cliente: str) -> None:
        event = {
            "level": "INFO",
            "component": "messaging",
            "event": "MESSAGE_SENT",
            "details": {"tipo": str(tipo)[:40]},
        }
        threading.Thread(
            target=lambda: self._send_audit_event(event), daemon=True
        ).start()

    def _send_audit_event(self, event: Dict[str, Any]) -> None:
        try:
            self.secure_backend.send_telemetry([event])
        except DesktopBackendError:
            pass

    def ativar_chave(self, chave: str) -> Dict[str, Any]:
        code = str(chave or "").strip().upper()
        if not code:
            return {"sucesso": False, "mensagem": "Chave inválida."}
        try:
            result = self.secure_backend.redeem_key(code)
        except DesktopBackendError as error:
            messages = {
                "INVALID_KEY": "Chave inválida.",
                "KEY_EXPIRED": "Esta chave expirou antes de ser utilizada.",
                "NETWORK_ERROR": "Não foi possível consultar a chave. Verifique a internet.",
                "UNAUTHORIZED": "O vínculo deste computador não é mais válido.",
            }
            return {
                "sucesso": False,
                "mensagem": messages.get(
                    error.code, "Chave não encontrada, utilizada ou expirada."
                ),
            }
        success = bool(result.get("ok", result.get("success", False)))
        if success:
            self._last_license_data = {}
            return {
                "sucesso": True,
                "mensagem": result.get("message") or "Chave ativada com sucesso!",
            }
        return {
            "sucesso": False,
            "mensagem": result.get("message") or "Esta chave não pôde ser utilizada.",
        }

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
