import json

from src.core.database import DatabaseManager


def build_database(mapping):
    database = DatabaseManager.__new__(DatabaseManager)
    database.get_leads_mapping = lambda: mapping
    return database


def test_encontra_os_com_formatacao_diferente():
    database = build_database({
        "001014412-000075878": {
            "cliente": "MARIA TESTE",
            "telefone": "86999999999",
            "os": "000075878",
            "os_full": "001014412-000075878",
            "tipo": "TSI",
            "id": "a0OTESTE1234567",
        }
    })

    lead = database.find_lead("1014412 - 75878", "075878", tipo="TSI")

    assert lead["cliente"] == "MARIA TESTE"


def test_respeita_tipo_da_pesquisa():
    database = build_database({
        "75878": {
            "cliente": "MARIA TESTE",
            "os": "75878",
            "tipo": "TSI",
        }
    })

    assert database.find_lead("75878", tipo="SSI") == {}


def test_nao_usa_codigo_da_concessionaria_como_os():
    database = build_database({
        "1717379-4870": {
            "cliente": "FRANCIVALDO COSTA DA SILVA",
            "os": "4870",
            "os_full": "1717379-4870",
            "tipo": "TSI",
        }
    })

    assert database.find_lead("1717379-75878", "75878", tipo="TSI") == {}


def test_nova_extracao_corrige_cliente_e_telefone_do_historico(tmp_path):
    database = DatabaseManager.__new__(DatabaseManager)
    database.db_path = str(tmp_path / "historico_tsi.json")
    registro_antigo = {
        "Ordens de Serviço: OS": "1717379-75878",
        "Cliente": "FRANCIVALDO COSTA DA SILVA",
        "Telefone": "99991545832",
        "Nota Top2Box": "100,00",
    }
    with open(database.db_path, "w", encoding="utf-8") as arquivo:
        json.dump([registro_antigo], arquivo, ensure_ascii=False)

    database.save_records([{
        "Ordens de Serviço: OS": "1717379-75878",
        "Cliente": "RAIMUNDO FAGNER LOPES COSTA",
        "Telefone": "86999999999",
        "Nota Top2Box": "0,00",
    }])

    registro_salvo = database.load_all_records()[0]
    assert registro_salvo["Cliente"] == "RAIMUNDO FAGNER LOPES COSTA"
    assert registro_salvo["Telefone"] == "86999999999"
    assert registro_salvo["Nota Top2Box"] == "100,00"
