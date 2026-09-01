import pandas as pd

from src.core.dashboard_engine import DashboardEngine


def build_engine():
    engine = DashboardEngine.__new__(DashboardEngine)
    engine.config = {
        "consultores": [
            {"cpf": "00000000012345678901", "nome": "ANA VENDEDORA"}
        ]
    }
    return engine


def test_prioriza_cpf_do_vendedor_e_mapeia_nome():
    engine = build_engine()
    df = pd.DataFrame({
        "CPF do funcionário (Vendedor)": ["123.456.789-01"],
        "Atenção no atendimento do vendedor moto": [10],
    })

    resultado = engine.enriquecer_consultores(df)

    assert engine._encontrar_coluna_consultor(df) == "CPF do funcionário (Vendedor)"
    assert resultado["Consultor_Nome"].tolist() == ["ANA VENDEDORA"]


def test_aceita_nome_direto_e_ignora_coluna_de_comentario():
    engine = build_engine()
    df = pd.DataFrame({
        "Nome do Vendedor": ["CARLOS SILVA"],
        "Comentário Atendimento Vendedor": ["Ótimo atendimento"],
    })

    resultado = engine.enriquecer_consultores(df)

    assert engine._encontrar_coluna_consultor(df) == "Nome do Vendedor"
    assert resultado["Consultor_Nome"].tolist() == ["CARLOS SILVA"]


def test_valor_vazio_fica_nao_identificado():
    engine = build_engine()
    df = pd.DataFrame({"CPF do Vendedor": [pd.NA]})

    resultado = engine.enriquecer_consultores(df)

    assert resultado["Consultor_Nome"].tolist() == ["Não Identificado"]
