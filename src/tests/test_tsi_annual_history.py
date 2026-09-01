import inspect
from types import SimpleNamespace

from src.ui.screens.extraction_screen import ExtractionScreen


def test_filtro_anual_tsi_usa_intervalo_exato_do_salesforce():
    fonte = inspect.getsource(ExtractionScreen.extrair_dados_auditor)

    assert 'select#colDt_q, select[name="colDt_q"]' in fonte
    assert "=== 'cury'" in fonte
    assert 'input[name="run"]' in fonte


def test_monitor_tsi_conclui_quando_intervalo_anual_estabiliza():
    tela = SimpleNamespace(
        is_full_history=True,
        tsi_relatorio_baseline="5:relatorio-mensal",
        tsi_relatorio_em_transicao=False,
        tsi_relatorio_token="execucao-123",
        tsi_relatorio_ultima_assinatura=None,
        tsi_relatorio_estavel=0,
    )
    estado = {
        "loading": False,
        "empty": False,
        "rows": 12,
        "signature": "12:relatorio-anual",
        "interval": "cury",
        "runMarkers": [],
    }

    assert ExtractionScreen._avaliar_estado_relatorio(tela, "TSI", estado) is False
    assert ExtractionScreen._avaliar_estado_relatorio(tela, "TSI", estado) is True


def test_monitor_tsi_nao_importa_tabela_antiga_enquanto_relatorio_executa():
    tela = SimpleNamespace(
        is_full_history=True,
        tsi_relatorio_baseline="5:relatorio-mensal",
        tsi_relatorio_token="execucao-123",
        tsi_relatorio_em_transicao=False,
        tsi_relatorio_ultima_assinatura=None,
        tsi_relatorio_estavel=0,
    )
    tabela_antiga = {
        "loading": False,
        "empty": False,
        "rows": 5,
        "signature": "5:relatorio-mensal",
        "interval": "cury",
        "runMarkers": ["execucao-123"],
    }

    for _ in range(5):
        assert ExtractionScreen._avaliar_estado_relatorio(
            tela, "TSI", tabela_antiga
        ) is False

    tabela_nova = dict(tabela_antiga, rows=30, signature="30:relatorio-anual", runMarkers=[])
    assert ExtractionScreen._avaliar_estado_relatorio(tela, "TSI", tabela_nova) is False
    assert ExtractionScreen._avaliar_estado_relatorio(tela, "TSI", tabela_nova) is True


def test_monitor_ssi_aceita_intervalo_personalizado_quando_relatorio_concluiu():
    tela = SimpleNamespace(
        is_full_history=True,
        ssi_relatorio_baseline="14:relatorio-mensal",
        ssi_relatorio_token="execucao-ssi-123",
        ssi_relatorio_em_transicao=False,
        ssi_relatorio_ultima_assinatura=None,
        ssi_relatorio_estavel=0,
    )
    estado = {
        "loading": False,
        "empty": False,
        "statusPresent": True,
        "completed": True,
        "rows": 258,
        "signature": "258:relatorio-anual-ssi",
        "interval": "custom",
        "runMarkers": [],
    }

    assert ExtractionScreen._avaliar_estado_relatorio(tela, "SSI", estado) is False
    assert ExtractionScreen._avaliar_estado_relatorio(tela, "SSI", estado) is True


def test_monitor_ssi_aguarda_status_oficial_concluido():
    tela = SimpleNamespace(
        is_full_history=True,
        ssi_relatorio_baseline="14:relatorio-mensal",
        ssi_relatorio_token="execucao-ssi-123",
        ssi_relatorio_em_transicao=False,
        ssi_relatorio_ultima_assinatura=None,
        ssi_relatorio_estavel=0,
    )
    processando = {
        "loading": False,
        "empty": False,
        "statusPresent": True,
        "completed": False,
        "rows": 258,
        "signature": "258:relatorio-anual-ssi",
        "interval": "custom",
        "runMarkers": [],
    }

    for _ in range(3):
        assert ExtractionScreen._avaliar_estado_relatorio(tela, "SSI", processando) is False

    concluido = dict(processando, completed=True)
    assert ExtractionScreen._avaliar_estado_relatorio(tela, "SSI", concluido) is False
    assert ExtractionScreen._avaliar_estado_relatorio(tela, "SSI", concluido) is True
