from types import MethodType, SimpleNamespace

import pandas as pd
from bs4 import BeautifulSoup

from src.ui.screens.dashboard_comparativo_screen import DashboardComparativoScreen
from src.ui.screens.dashboard_ssi_screen import DashboardSSIScreen


class _Combo:
    def __init__(self, value):
        self.items = [value]
        self.value = value

    def currentText(self):
        return self.value

    def count(self):
        return len(self.items)

    def clear(self):
        self.items = []
        self.value = ""

    def addItem(self, value):
        self.items.append(value)
        if not self.value:
            self.value = value

    def addItems(self, values):
        self.items.extend(values)

    def setCurrentText(self, value):
        self.value = value


def _fake_renderer():
    fake = SimpleNamespace()
    fake._filtrar_respostas_por_estado = MethodType(
        DashboardComparativoScreen._filtrar_respostas_por_estado, fake
    )
    fake._formatar_verbalizacao_pdf = DashboardComparativoScreen._formatar_verbalizacao_pdf
    return fake


def test_pdf_cliente_em_tres_linhas_e_verbalizacoes_separadas():
    fake = _fake_renderer()
    metrics = {"tsi": 98.0, "total_respostas": 1, "dimensoes": {}}
    response = {
        "cliente": "CLIENTE TESTE",
        "data": "12/08/2026 10:00",
        "os": "1717379-12345",
        "categoria": "Baixa",
        "consultor": "Rita",
        "loja": "Loja Teste",
        "status": "PROMOTOR",
        "nota": 10,
        "comentario": "Recepção: Ótima &bull; Entrega: Excelente",
        "tem_comentario": True,
        "notas_pilares": {"Recepção": "10", "Entrega": "10"},
    }

    html = DashboardComparativoScreen._render_tsi_html(
        fake, metrics, [], [response], is_pdf=True, mes_ref="08/2026"
    )

    card_node = BeautifulSoup(html, "html.parser").select_one(".pdf-response-card")
    card = str(card_node)
    assert "CLIENTE TESTE" in card
    assert "12/08/2026 10:00" in card
    assert "O.S." not in card
    assert "Recepção: <b>10</b>" in card
    assert "PROMOTOR • Nota 10" in card
    verbalizacao = card_node.select_one(".pdf-verbatim-row .resp-verbatim-text")
    assert verbalizacao.get_text(" | ", strip=True) == "Recepção: Ótima | Entrega: Excelente"


def test_vendedores_ssi_respeitam_mes_loja_e_modalidade():
    fake = SimpleNamespace(
        df=pd.DataFrame({
            "Data de resposta SSI 2W": ["01/08/2026", "01/07/2026", "02/08/2026"],
            "Loja": ["Bacabal", "Bacabal", "Outra"],
            "Modalidade de Compra": ["CONSORCIO", "CONSORCIO", "CONSORCIO"],
            "Consultor_Nome": ["VENDEDOR AGOSTO", "VENDEDOR JULHO", "VENDEDOR OUTRA LOJA"],
        }),
        combo_modalidade=_Combo("CONSORCIO"),
        combo_loja=_Combo("Bacabal"),
        combo_mes=_Combo("08/2026"),
        combo_consultor=_Combo("Todos"),
    )

    DashboardSSIScreen._preencher_vendedores_contextuais(fake)

    assert fake.combo_consultor.items == ["Todos", "VENDEDOR AGOSTO"]
