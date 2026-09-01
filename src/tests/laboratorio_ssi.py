import sys
import os
import pandas as pd
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QPushButton)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from bs4 import BeautifulSoup

class LaboratorioSSI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Laboratório SSI - Teste Offline de Painéis")
        self.resize(1200, 800)
        
        self.html_path = r"C:\Users\Berg\Desktop\Relatorios\TSI CLASSICO\SSI\SSI 2.0 - Todas Respostas\SSI 2.0 - Todas Respostas ~ myHonda.html"
        self.df = pd.DataFrame()
        
        # UI Principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Barra de Filtros (Simulação)
        filtros_layout = QHBoxLayout()
        
        self.lbl_status = QLabel("Carregando arquivo local...")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #333;")
        filtros_layout.addWidget(self.lbl_status)
        
        filtros_layout.addStretch()
        
        filtros_layout.addWidget(QLabel("Loja:"))
        self.combo_loja = QComboBox()
        self.combo_loja.addItem("Todas")
        self.combo_loja.currentTextChanged.connect(self.atualizar_dashboard)
        filtros_layout.addWidget(self.combo_loja)
        
        filtros_layout.addWidget(QLabel("Mês de Resposta:"))
        self.combo_mes = QComboBox()
        self.combo_mes.addItem("Todos")
        self.combo_mes.currentTextChanged.connect(self.atualizar_dashboard)
        filtros_layout.addWidget(self.combo_mes)
        
        filtros_layout.addWidget(QLabel("Modalidade:"))
        self.combo_modalidade = QComboBox()
        self.combo_modalidade.addItem("Todas")
        self.combo_modalidade.currentTextChanged.connect(self.atualizar_dashboard)
        filtros_layout.addWidget(self.combo_modalidade)
        
        btn_recarregar = QPushButton("Recarregar HTML")
        btn_recarregar.clicked.connect(self.carregar_dados)
        filtros_layout.addWidget(btn_recarregar)
        
        main_layout.addLayout(filtros_layout)
        
        # Dashboard WebView
        self.web_view = QWebEngineView()
        main_layout.addWidget(self.web_view, stretch=1)
        
        # Carrega os dados ao iniciar
        self.carregar_dados()

    def carregar_dados(self):
        self.lbl_status.setText("Extraindo HTML...")
        QApplication.processEvents()
        
        try:
            with open(self.html_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            
            linhas = soup.find_all("tr")
            header_row = soup.find("tr", class_="headerRow")
            
            if not header_row or not linhas:
                self.lbl_status.setText("Erro: Tabela não encontrada no HTML.")
                return
                
            headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
            
            dados = []
            current_loja = "Desconhecida"
            
            for linha in linhas:
                # Checa se é uma linha de agrupamento de Loja
                texto_linha = linha.get_text(separator=" ", strip=True)
                if "Concessionária de vendas: Número da conta:" in texto_linha:
                    import re
                    match = re.search(r'Número da conta:\s*(\d+)', texto_linha)
                    if match:
                        current_loja = match.group(1)
                
                # Se for linha de dados (even ou odd)
                classes = linha.get("class", [])
                if "even" in classes or "odd" in classes:
                    celulas = [td.get_text(strip=True) for td in linha.find_all(["td", "th"])]
                    if len(celulas) == len(headers):
                        registro = dict(zip(headers, celulas))
                        registro["Loja"] = current_loja
                        dados.append(registro)
                    
            self.df = pd.DataFrame(dados)
            self.lbl_status.setText(f"HTML Carregado! {len(self.df)} respostas lidas.")
            
            # Preencher os filtros com os dados reais
            self.preencher_filtros()
            
            # Renderizar o dashboard
            self.atualizar_dashboard()
            
        except Exception as e:
            self.lbl_status.setText(f"Erro ao ler HTML: {e}")

    def preencher_filtros(self):
        self.combo_modalidade.blockSignals(True)
        self.combo_modalidade.clear()
        self.combo_modalidade.addItem("Todas")
        if 'Modalidade de Compra' in self.df.columns:
            modalidades = self.df['Modalidade de Compra'].dropna().unique()
            for mod in modalidades:
                if str(mod).strip(): self.combo_modalidade.addItem(str(mod))
        self.combo_modalidade.blockSignals(False)

        self.combo_mes.blockSignals(True)
        self.combo_mes.clear()
        self.combo_mes.addItem("Todos")
        if 'Data de resposta SSI 2W' in self.df.columns:
            # Puxa o mês extraindo a string (ex: '16/02/2024')
            datas = self.df['Data de resposta SSI 2W'].dropna()
            meses = set()
            for d in datas:
                partes = str(d).split('/')
                if len(partes) >= 3:
                    meses.add(f"{partes[1]}/{partes[2][:4]}")
            for m in sorted(list(meses)):
                self.combo_mes.addItem(m)
        self.combo_mes.blockSignals(False)

        self.combo_loja.blockSignals(True)
        self.combo_loja.clear()
        self.combo_loja.addItem("Todas")
        if 'Loja' in self.df.columns:
            lojas = self.df['Loja'].dropna().unique()
            for loja in sorted(lojas):
                if str(loja).strip() and str(loja).strip() != "Desconhecida": 
                    self.combo_loja.addItem(str(loja))
        self.combo_loja.blockSignals(False)

    def atualizar_dashboard(self):
        if self.df.empty:
            return
            
        df_filtrado = self.df.copy()
        
        if self.combo_modalidade.currentText() != "Todas" and 'Modalidade de Compra' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['Modalidade de Compra'] == self.combo_modalidade.currentText()]
            
        if self.combo_loja.currentText() != "Todas" and 'Loja' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['Loja'] == self.combo_loja.currentText()]
            
        if self.combo_mes.currentText() != "Todos" and 'Data de resposta SSI 2W' in df_filtrado.columns:
            mes_alvo = self.combo_mes.currentText()
            df_filtrado = df_filtrado[df_filtrado['Data de resposta SSI 2W'].astype(str).str.contains(f"/{mes_alvo}")]
            
        total_respostas = len(df_filtrado)
        
        if total_respostas == 0:
            html_vazio = "<html><body><h2>Nenhum dado encontrado para esses filtros.</h2></body></html>"
            self.web_view.setHtml(html_vazio)
            return

        def safe_numeric(val):
            try: return float(str(val).replace(',','.'))
            except: return -1

        col_sat = "Avaliação experiência compra dealer moto"
        if col_sat in df_filtrado.columns:
            df_filtrado['_sat_num'] = df_filtrado[col_sat].apply(safe_numeric)
            validos_sat = df_filtrado[df_filtrado['_sat_num'] >= 0]
            if len(validos_sat) > 0:
                top2_sat = len(validos_sat[validos_sat['_sat_num'] >= 9])
                indice_ssi = (top2_sat / len(validos_sat)) * 100
            else:
                indice_ssi = 0
        else:
            indice_ssi = 0

        # Calcular Top2Box para os Pilares (Atendimento, Negociação, Entrega, Instalações)
        def calc_top2(col_name):
            if col_name in df_filtrado.columns:
                temp_col = df_filtrado[col_name].apply(safe_numeric)
                validos = df_filtrado[temp_col >= 0]
                if len(validos) > 0:
                    top2 = len(validos[validos[col_name].apply(safe_numeric) >= 9])
                    return round((top2 / len(validos)) * 100, 2)
            return 0.0

        pct_atendimento = calc_top2("Atenção no atendimento do vendedor moto")
        pct_negociacao = calc_top2("Negociação Geral")
        pct_entrega = calc_top2("Avaliação Entrega Motocicleta")
        pct_instalacoes = calc_top2("Conforto das instalações moto")

        col_test = "Realizou Test-Ride"
        if col_test in df_filtrado.columns:
            testes_feitos = len(df_filtrado[df_filtrado[col_test].astype(str).str.upper() == 'SIM'])
            taxa_test_ride = (testes_feitos / total_respostas) * 100 if total_respostas > 0 else 0
        else:
            taxa_test_ride = 0

        col_recompra = "Compraria outra mesmo dealer moto"
        if col_recompra in df_filtrado.columns:
            # Normalmente "1" ou "Sim"
            recompras = len(df_filtrado[df_filtrado[col_recompra].astype(str).str.contains('1|Sim', case=False)])
            taxa_recompra = (recompras / total_respostas) * 100 if total_respostas > 0 else 0
        else:
            taxa_recompra = 0

        import math
        # Agrupar por Loja para o gráfico
        lojas_labels = []
        lojas_ssi = []
        lojas_qtde = []
        lojas_faltam = []
        meta_ssi = 95.0

        if 'Loja' in df_filtrado.columns and col_sat in df_filtrado.columns:
            for loja, group in df_filtrado.groupby('Loja'):
                if str(loja).strip() == "Desconhecida":
                    continue
                validos = group[group['_sat_num'] >= 0]
                if len(validos) > 0:
                    top2 = len(validos[validos['_sat_num'] >= 9])
                    ssi_loja = (top2 / len(validos)) * 100
                    lojas_labels.append(str(loja))
                    lojas_ssi.append(round(ssi_loja, 2))
                    lojas_qtde.append(len(validos))

                    # Calculo de quantidade necessária para atingir a meta
                    if ssi_loja < meta_ssi:
                        m = meta_ssi / 100.0
                        # X = (M*N - T) / (1 - M)
                        if m < 1.0: # Prevent division by zero
                            x = (m * len(validos) - top2) / (1.0 - m)
                            faltam = math.ceil(x)
                            if faltam < 1: faltam = 1
                            lojas_faltam.append(faltam)
                        else:
                            lojas_faltam.append(999) # Impossível se meta=100% e tem detratores
                    else:
                        lojas_faltam.append(0)

        import json
        labels_json = json.dumps(lojas_labels)
        data_json = json.dumps(lojas_ssi)
        qtde_json = json.dumps(lojas_qtde)
        faltam_json = json.dumps(lojas_faltam)
        quantidade_lojas = len(lojas_ssi)

        cores_lojas = []
        for ssi in lojas_ssi:
            if ssi >= meta_ssi:
                cores_lojas.append('#059669') # Verde Escuro
            else:
                cores_lojas.append('#EA580C') # Laranja Escuro/Alerta

        cores_json = json.dumps(cores_lojas)

        # Extrair Mural de Comentários (Detratores: Nota Geral <= 8)
        colunas_comentarios = [
            'Comentário Atendimento Vendedor', 'Comentário Entrega Motocicleta',
            'Comentário Negociação Geral', 'Comentário processo vendas dealer moto',
            'Comentários Instalações', 'Comentários Recomendação', 'Comentário Test-Ride'
        ]
        
        comentarios_html = ""
        count_comentarios = 0
        if col_sat in df_filtrado.columns:
            df_detratores = df_filtrado[df_filtrado['_sat_num'] <= 8].copy()
            df_detratores = df_detratores.sort_values(by='_sat_num', ascending=True)
            
            for idx, row in df_detratores.iterrows():
                if count_comentarios >= 20: break # Limite de 20 comentários para n travar a tela
                loja_nome = row['Loja'] if 'Loja' in row else 'Desconhecida'
                nota = row['_sat_num']
                
                textos = []
                for c in colunas_comentarios:
                    if c in row and pd.notna(row[c]) and str(row[c]).strip() not in ["", "nan", "None"]:
                        # Tira a palavra comentário para ficar mais limpo
                        titulo_pilar = c.replace('Comentário ', '').replace('Comentários ', '')
                        textos.append(f"<b>{titulo_pilar}</b>: <i>\"{str(row[c]).strip()}\"</i>")
                        
                if textos:
                    texto_final = "<br><br>".join(textos)
                    cor_borda = "#EF4444" if nota <= 6 else "#F59E0B" # Vermelho p/ <=6, Laranja p/ 7 e 8
                    cor_fundo_nota = "#FEE2E2" if nota <= 6 else "#FEF3C7"
                    cor_texto_nota = "#B91C1C" if nota <= 6 else "#D97706"

                    comentarios_html += f"""
                    <div style="background: white; border-left: 5px solid {cor_borda}; padding: 15px; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
                            <span style="font-weight: bold; color: #1E293B; font-size: 14px;">Loja: {loja_nome}</span>
                            <span style="background: {cor_fundo_nota}; color: {cor_texto_nota}; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;">Nota Geral: {nota:.0f}</span>
                        </div>
                        <div style="color: #475569; font-size: 13px; line-height: 1.5;">{texto_final}</div>
                    </div>
                    """
                    count_comentarios += 1

        if count_comentarios == 0:
            comentarios_html = "<div style='color: #64748B; font-style: italic; padding: 10px;'>Nenhum comentário de insatisfação encontrado nos filtros atuais. Excelente! 🎉</div>"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2"></script>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #F8FAFC; margin: 0; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}
                .top-panel {{ flex: 0 0 auto; padding: 15px 20px; background-color: #F8FAFC; z-index: 10; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
                .scroll-panel {{ flex: 1 1 auto; overflow-y: auto; padding: 20px; background-color: #F1F5F9; }}
                .kpi-container {{ display: flex; gap: 15px; margin-bottom: 15px; }}
                .kpi-card {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); flex: 1; text-align: center; border-bottom: 4px solid #1D4ED8; }}
                .kpi-card.green {{ border-color: #10B981; }}
                .kpi-card.orange {{ border-color: #F59E0B; }}
                .kpi-card.purple {{ border-color: #8B5CF6; }}
                .kpi-title {{ font-size: 12px; color: #64748B; font-weight: 600; text-transform: uppercase; }}
                .kpi-value {{ font-size: 26px; font-weight: bold; color: #1E293B; margin-top: 5px; }}
                .charts-container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
                .chart-box {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); height: 240px; }}
            </style>
        </head>
        <body>
            <div class="top-panel">
                <div class="kpi-container">
                    <div class="kpi-card green">
                        <div class="kpi-title">Índice SSI Global (Top2Box)</div>
                        <div class="kpi-value">{indice_ssi:.2f}%</div>
                        <div style="font-size: 12px; color: #64748B; margin-top: 5px;">Meta: {meta_ssi:.2f}%</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">Taxa de Test-Ride</div>
                        <div class="kpi-value">{taxa_test_ride:.2f}%</div>
                    </div>
                    <div class="kpi-card orange">
                        <div class="kpi-title">Taxa de Recompra</div>
                        <div class="kpi-value">{taxa_recompra:.2f}%</div>
                    </div>
                    <div class="kpi-card purple">
                        <div class="kpi-title">Total de Pesquisas</div>
                        <div class="kpi-value">{total_respostas}</div>
                    </div>
                </div>
                
                <div class="charts-container">
                    <div class="chart-box">
                        <canvas id="chartAvaliacao"></canvas>
                    </div>
                    <div class="chart-box">
                        <canvas id="chartModalidade"></canvas>
                    </div>
                </div>
            </div>

            <div class="scroll-panel">
                <h3 style="color: #1E293B; margin-top: 0; margin-bottom: 15px; border-bottom: 2px solid #E2E8F0; padding-bottom: 10px; font-size: 18px;">
                    Mural de Alertas: A Voz do Cliente (Notas ≤ 8)
                </h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 20px;">
                    {comentarios_html}
                </div>
            </div>

            <script>
                Chart.register(ChartDataLabels);
                
                // Gráfico da Esquerda: Pilares da Avaliação (Top2Box)
                const ctx1 = document.getElementById('chartAvaliacao').getContext('2d');
                new Chart(ctx1, {{
                    type: 'bar',
                    data: {{
                        labels: ['Atendimento', 'Negociação', 'Entrega', 'Instalações'],
                        datasets: [{{
                            label: 'Top2Box (%)',
                            data: [{pct_atendimento}, {pct_negociacao}, {pct_entrega}, {pct_instalacoes}], 
                            backgroundColor: '#3B82F6',
                            borderRadius: 4
                        }}]
                    }},
                    options: {{ 
                        maintainAspectRatio: false,
                        plugins: {{
                            datalabels: {{
                                anchor: 'end',
                                align: 'top',
                                formatter: function(value) {{
                                    return value.toFixed(2) + '%';
                                }},
                                font: {{ weight: 'bold' }},
                                color: '#1E293B'
                            }},
                            legend: {{ display: false }},
                            title: {{ display: true, text: 'Top2Box por Pilar', font: {{size: 16}} }}
                        }},
                        scales: {{
                            y: {{ beginAtZero: true, max: 115 }}
                        }}
                    }}
                }});

                // Gráfico da Direita: Top2Box por Concessionária
                const ctx2 = document.getElementById('chartModalidade').getContext('2d');
                new Chart(ctx2, {{
                    data: {{
                        labels: {labels_json},
                        datasets: [{{
                            type: 'line',
                            label: 'Meta ({meta_ssi}%)',
                            data: Array({quantidade_lojas}).fill({meta_ssi}),
                            borderColor: '#EF4444',
                            borderWidth: 2,
                            borderDash: [5, 5],
                            pointRadius: 0,
                            fill: false,
                            datalabels: {{ display: false }}
                        }}, {{
                            type: 'bar',
                            label: 'Índice SSI Global (%)',
                            data: {data_json}, 
                            backgroundColor: {cores_json}, // Cores Condicionais
                            borderRadius: 4
                        }}]
                    }},
                    options: {{
                        maintainAspectRatio: false,
                        plugins: {{
                            datalabels: {{
                                labels: {{
                                    value: {{
                                        anchor: 'end',
                                        align: 'top',
                                        formatter: function(value, context) {{
                                            if (context.dataset.type === 'line') return null;
                                            return value.toFixed(2) + '%';
                                        }},
                                        font: {{ weight: 'bold' }},
                                        color: '#1E293B'
                                    }},
                                    countNum: {{
                                        anchor: 'center',
                                        align: 'center',
                                        formatter: function(value, context) {{
                                            if (context.dataset.type === 'line') return null;
                                            const qtde = {qtde_json};
                                            return qtde[context.dataIndex];
                                        }},
                                        font: {{ weight: 'bold', size: 18 }},
                                        color: '#FFFFFF'
                                    }},
                                    countText: {{
                                        anchor: 'center',
                                        align: 'bottom',
                                        offset: 14,
                                        formatter: function(value, context) {{
                                            if (context.dataset.type === 'line') return null;
                                            const faltam = {faltam_json};
                                            const qtd_falta = faltam[context.dataIndex];
                                            if (qtd_falta > 0) {{
                                                return ['Qtd Pesquisas', '⚠️ Faltam ' + qtd_falta + ' pesquisas (notas 9/10)'];
                                            }}
                                            return 'Qtd Pesquisas';
                                        }},
                                        font: {{ weight: '600', size: 10 }},
                                        color: '#D1FAE5',
                                        textAlign: 'center'
                                    }}
                                }}
                            }},
                            legend: {{ display: true, position: 'bottom' }},
                            title: {{ display: true, text: 'Top2Box por Concessionária vs Meta', font: {{size: 16}} }}
                        }},
                        scales: {{
                            y: {{ beginAtZero: true, max: 115 }}
                        }}
                    }}
                }});
            </script>
        </body>
        </html>
        """
        self.web_view.setHtml(html)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LaboratorioSSI()
    window.show()
    sys.exit(app.exec())
