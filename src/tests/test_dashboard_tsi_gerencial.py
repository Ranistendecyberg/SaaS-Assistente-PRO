from types import SimpleNamespace

import pandas as pd

from src.ui.screens.dashboard_comparativo_screen import DashboardComparativoScreen


class _Combo:
    def __init__(self, texto):
        self._texto = texto

    def currentText(self):
        return self._texto


class _DbFake:
    def get_leads_mapping(self):
        return {}

    def find_lead(self, *args, **kwargs):
        return None


class _TelaFake:
    _calcular_participacao_whatsapp = lambda self, df, tipo: (0, 0.0)


def _registro(os_num, cliente, consultor, tsi, agendamento):
    return {
        'Ordens de Serviço: OS': f'1717379-{os_num}',
        'Cliente': cliente,
        'Data de Resposta': '01/08/2026 10:00',
        'Mes': '08/2026',
        'Loja_Nome': 'Loja Bacabal',
        'Consultor_Nome': consultor,
        'Nota Pesquisa TSI': tsi,
        'Nota Top2Box': '100,00',
        'Recomendaria dealer amigo e família': 10,
        'Avaliação satisfação geral': 10,
        'Avaliação satisfação agendamento': agendamento,
        'Avaliação satisfação recepção': 10,
        'Avaliação satisfação instalações e infra': 10,
        'Avaliação satisfação consultor': 10,
        'Avaliação satisfação qualidade': 10,
        'Avaliação satisfação entrega': 10,
        'Avaliação satisfação custo benefício': 9 if tsi == '98,00' else 10,
        'Categoria Produto': 'Baixa',
        'Segmento': 'HDA',
    }


def test_tsi_usa_nota_oficial_e_mantem_ausencia_no_denominador():
    tela = _TelaFake()
    tela.df_tsi = pd.DataFrame([
        _registro('75878', 'Raimundo', 'Rita', '98,00', None),
        _registro('75585', 'Vanderlan', 'Rita', '100,00', 10),
        _registro('75544', 'Carlito', 'Outro', '100,00', 10),
        _registro('75509', 'João', 'Outro', '100,00', 10),
    ])
    tela.combo_loja = _Combo('Todas as Unidades')
    tela.combo_mes = _Combo('08/2026')
    tela.combo_consultor = _Combo('Todos')
    tela.sent_surveys = set()
    tela.db = _DbFake()
    tela.engine_tsi = SimpleNamespace(_normalizar_rotulo=lambda valor: str(valor).lower())

    metricas, ranking, _, _ = DashboardComparativoScreen._calcular_metricas_tsi(tela)

    assert metricas['tsi'] == 99.5
    assert metricas['dimensoes']['Agendamento'] == 75.0
    assert metricas['dimensoes_detalhes']['Agendamento'] == {'top2': 3, 'validas': 4}
    assert metricas['distribuicao_segmentos'] == [
        {'nome': 'Baixa', 'respostas': 4, 'tsi': 99.5}
    ]

    rita = next(item for item in ranking if item['nome'] == 'Rita')
    assert rita['tsi'] == 99.0
    assert rita['pilares']['Agendamento'] == 50.0
    assert rita['pilares_contagens']['Agendamento'] == {'top2': 1, 'validas': 2}
