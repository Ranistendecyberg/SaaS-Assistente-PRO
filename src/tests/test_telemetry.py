import json
import threading
from unittest.mock import patch

from src.core.telemetry import TelemetryClient, anonymous_id, sanitize


def make_client(tmp_path):
    client = TelemetryClient.__new__(TelemetryClient)
    client.queue_path = str(tmp_path / "telemetry_queue.json")
    client.machine_id = "MAQUINA-TESTE"
    client.session_id = "sessao-teste"
    client._lock = threading.Lock()
    client._worker_running = False
    client._diagnostic_enabled = False
    client._diagnostic_checked_at = None
    client._diagnostic_check_running = False
    return client


def test_sanitizacao_remove_dados_pessoais_e_urls():
    result = sanitize({
        "cliente": "Maria da Silva",
        "telefone": "5598999998888",
        "cpf": "123.456.789-01",
        "target": "Falha em https://myhonda.example/ficha/segredo para 98999998888",
        "records": 7,
    })
    serialized = json.dumps(result, ensure_ascii=False)
    assert "Maria da Silva" not in serialized
    assert "5598999998888" not in serialized
    assert "123.456.789-01" not in serialized
    assert "/ficha/segredo" not in serialized
    assert result["records"] == 7


def test_fila_permanece_quando_firebase_falha(tmp_path):
    client = make_client(tmp_path)
    client.flush_async = lambda: None
    client.is_detailed_enabled = lambda: False
    client.record("ssi_dispatch", "CONTACT_PAGE_TIMEOUT", "ERROR", {"attempts": 11})

    with patch("src.core.telemetry.urllib.request.urlopen", side_effect=OSError("offline")):
        client._flush_worker()

    queued = json.loads((tmp_path / "telemetry_queue.json").read_text(encoding="utf-8"))
    assert len(queued) == 1
    assert queued[0]["payload"]["event"] == "CONTACT_PAGE_TIMEOUT"


def test_fila_e_esvaziada_depois_do_envio(tmp_path):
    client = make_client(tmp_path)
    client.flush_async = lambda: None
    client.is_detailed_enabled = lambda: False
    client.record("application", "APP_START")

    class Response:
        def close(self):
            pass

    with patch("src.core.telemetry.urllib.request.urlopen", return_value=Response()):
        client._flush_worker()

    queued = json.loads((tmp_path / "telemetry_queue.json").read_text(encoding="utf-8"))
    assert queued == []


def test_referencia_anonima_e_estavel():
    assert anonymous_id("pesquisa-123") == anonymous_id("pesquisa-123")
    assert "pesquisa-123" not in anonymous_id("pesquisa-123")
