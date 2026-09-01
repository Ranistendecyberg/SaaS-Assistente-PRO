import os
import sys
import pandas as pd
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from src.core.dashboard_engine import DashboardEngine

def test_math():
    engine = DashboardEngine()
    
    # 10 clientes
    # 7 clientes: validos, todas 10
    # 1 cliente: invalido, todas 10 (nao contabiliza)
    # 1 cliente: Top2Box 80 (4x 10, 1x 4), TSI 88 (4x10+4 = 44)
    # 1 cliente: Top2Box 60 (3x 10, 2x 6), TSI 86 (3x10+6+7 = 43)
    
    records = []
    
    cols = [
        'Avaliação satisfação instalações e infra',
        'Avaliação satisfação consultor',
        'Avaliação satisfação qualidade',
        'Avaliação satisfação entrega',
        'Avaliação satisfação custo benefício'
    ]
    
    # 7 validos com 10
    for _ in range(7):
        rec = {'Responsável pela realização serviço': 'Sim, fui eu que levei e retirei a motocicleta'}
        for c in cols: rec[c] = 10
        records.append(rec)
        
    # 1 invalido com 10
    rec = {'Responsável pela realização serviço': 'Não, outra pessoa levou'}
    for c in cols: rec[c] = 10
    records.append(rec)
    
    # 1 com Top2Box 80% (4 de 10) e TSI 88% (44 pontos) -> 10, 10, 10, 10, 4
    rec = {'Responsável pela realização serviço': 'Sim, fui eu que levei e retirei a motocicleta'}
    rec[cols[0]] = 10
    rec[cols[1]] = 10
    rec[cols[2]] = 10
    rec[cols[3]] = 10
    rec[cols[4]] = 4
    records.append(rec)
    
    # 1 com Top2Box 60% (3 de 10) e TSI 86% (43 pontos) -> 10, 10, 10, 6, 7
    rec = {'Responsável pela realização serviço': 'Sim, fui eu que levei e retirei a motocicleta'}
    rec[cols[0]] = 10
    rec[cols[1]] = 10
    rec[cols[2]] = 10
    rec[cols[3]] = 6
    rec[cols[4]] = 7
    records.append(rec)

    df = pd.DataFrame(records)
    
    # Filtro igual no engine
    col_resp = 'Responsável pela realização serviço'
    df = df[df[col_resp].astype(str).str.strip() == "Sim, fui eu que levei e retirei a motocicleta"]
    
    metrics = engine.calculate_metrics(df)
    
    print(f"Total Valid Respondents: {len(df)}")
    print(f"Top2Box Global: {metrics['top2box_global']}% (Expected: ~93.33%)")
    print(f"TSI Global: {metrics['tsi_global']}% (Expected: ~97.11%)")

if __name__ == "__main__":
    test_math()
