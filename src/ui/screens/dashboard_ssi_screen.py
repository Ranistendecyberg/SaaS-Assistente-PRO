import pandas as pd
import json
import math
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QPushButton, QFrame, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWebEngineWidgets import QWebEngineView
from src.core.database import DatabaseManager
from src.core.pdf_report_generator import PDFReportGenerator
from src.core.ssi_metrics import (
    calculate_percentage as calculate_ssi_percentage,
    numeric_series as ssi_numeric_series,
    official_series as ssi_official_series,
    raw_column as ssi_raw_column,
    recommendation_summary,
)

class DashboardSSIScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.df = pd.DataFrame()
        self.setup_ui()
        
        # Carrega os dados na inicialização com um pequeno delay para a UI respirar
        QTimer.singleShot(100, self.carregar_dados)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        lbl_titulo = QLabel("📊 Painel de Resultados SSI")
        lbl_titulo.setStyleSheet("color: #1E293B; font-size: 22px; font-weight: 800; border: none;")
        layout.addWidget(lbl_titulo)
        
        # Barra de Filtros
        filtros_frame = QFrame()
        filtros_frame.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #CBD5E1;")
        filtros_layout = QHBoxLayout(filtros_frame)
        filtros_layout.setContentsMargins(15, 8, 15, 8)
        filtros_layout.setSpacing(10)
        
        self.lbl_status = QLabel("")
        self.lbl_status.setVisible(False)
        
        lbl_loja = QLabel("Loja:")
        lbl_loja.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px; border: none;")
        filtros_layout.addWidget(lbl_loja)
        
        combo_style = """
            QComboBox {
                padding: 4px 8px; 
                border: 1px solid #CBD5E1; 
                border-radius: 5px; 
                min-width: 180px;
                max-width: 220px;
                background-color: #F8FAFC;
                color: #1E293B;
                font-weight: bold;
                font-size: 12px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: black;
                selection-background-color: #E2E8F0;
            }
        """
        
        self.combo_loja = QComboBox()
        self.combo_loja.setStyleSheet(combo_style)
        self.combo_loja.addItem("Todas")
        self.combo_loja.currentTextChanged.connect(self._ao_mudar_filtros_base)
        filtros_layout.addWidget(self.combo_loja)
        
        lbl_mes = QLabel("Mês de Resposta:")
        lbl_mes.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px; border: none; margin-left: 5px;")
        filtros_layout.addWidget(lbl_mes)
        
        combo_style_mes = combo_style.replace("min-width: 180px;", "min-width: 100px;").replace("max-width: 220px;", "max-width: 120px;")
        
        self.combo_mes = QComboBox()
        self.combo_mes.setStyleSheet(combo_style_mes)
        self.combo_mes.addItem("Todos")
        self.combo_mes.currentTextChanged.connect(self._ao_mudar_filtros_base)
        filtros_layout.addWidget(self.combo_mes)
        
        lbl_mod = QLabel("Modalidade:")
        lbl_mod.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px; border: none; margin-left: 5px;")
        filtros_layout.addWidget(lbl_mod)
        
        self.combo_modalidade = QComboBox()
        self.combo_modalidade.setStyleSheet(combo_style_mes)
        self.combo_modalidade.addItem("Todas")
        self.combo_modalidade.currentTextChanged.connect(self._ao_mudar_filtros_base)
        filtros_layout.addWidget(self.combo_modalidade)
        
        lbl_cons = QLabel("Vendedor:")
        lbl_cons.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px; border: none; margin-left: 5px;")
        filtros_layout.addWidget(lbl_cons)
        
        self.combo_consultor = QComboBox()
        self.combo_consultor.setStyleSheet(combo_style_mes)
        self.combo_consultor.addItem("Todos")
        self.combo_consultor.currentTextChanged.connect(self.atualizar_dashboard)
        filtros_layout.addWidget(self.combo_consultor)
        
        filtros_layout.addStretch()
        
        btn_recarregar = QPushButton("🔄 Atualizar Painel")
        btn_recarregar.setStyleSheet("""
            QPushButton {
                background-color: #2563EB; 
                color: white; 
                padding: 6px 14px; 
                border-radius: 5px; 
                font-weight: bold; 
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        btn_recarregar.clicked.connect(self.carregar_dados)
        filtros_layout.addWidget(btn_recarregar)

        btn_pdf = QPushButton("📄 PDF Diretoria")
        btn_pdf.setStyleSheet("""
            QPushButton {
                background-color: #DC2626; 
                color: white; 
                padding: 6px 14px; 
                border-radius: 5px; 
                font-weight: bold; 
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #B91C1C;
            }
        """)
        btn_pdf.clicked.connect(self.exportar_pdf_executivo)
        filtros_layout.addWidget(btn_pdf)
        
        layout.addWidget(filtros_frame)
        
        # Dashboard WebView
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, stretch=1)

    def showEvent(self, event):
        super().showEvent(event)
        if self.df.empty:
            self.carregar_dados()
        else:
            self.atualizar_dashboard()

    def carregar_dados(self):
        try:
            records = self.db.load_ssi_records()
            if not records:
                self.lbl_status.setText("Aviso: O Banco SSI está vazio. Realize uma extração.")
                self.df = pd.DataFrame()
                self.preencher_filtros()
                self.atualizar_dashboard()
                return
                
            self.df = pd.DataFrame(records)
            
            # Identificação robusta da Concessionária/Loja no SSI:
            col_cod = next((c for c in self.df.columns if ('concession' in c.lower() or 'dealer' in c.lower() or 'loja' in c.lower()) and any(k in c.lower() for k in ['cod', 'dico', 'num', 'mero', 'vendas']) and 'regi' not in c.lower() and 'macro' not in c.lower()), None)
            if not col_cod:
                col_cod = next((c for c in self.df.columns if 'concession' in c.lower() and 'vendas' in c.lower() and 'regi' not in c.lower() and 'macro' not in c.lower()), None)
            
            if col_cod and col_cod in self.df.columns:
                self.df['Loja'] = self.df[col_cod].astype(str).str.strip()
            else:
                col_conta_nome = next((c for c in self.df.columns if 'nome da conta' in c.lower()), None)
                col_conta_num = next((c for c in self.df.columns if 'número da conta' in c.lower() or 'numero da conta' in c.lower()), None)
                if col_conta_nome and col_conta_nome in self.df.columns:
                    self.df['Loja'] = self.df[col_conta_nome].astype(str).str.strip()
                elif col_conta_num and col_conta_num in self.df.columns:
                    self.df['Loja'] = self.df[col_conta_num].astype(str).str.strip()
                elif 'Loja' not in self.df.columns:
                    self.df['Loja'] = "Desconhecida"

            # Se houver valores vazios, NaN ou 'Desconhecida', tenta fallbacks em outras colunas de concessionária
            mask_invalida = self.df['Loja'].isna() | self.df['Loja'].astype(str).str.lower().isin(['', 'nan', 'none', '<na>', 'desconhecida', 'desconhecido', '-'])
            if mask_invalida.any():
                for fallback_col in [c for c in self.df.columns if ('concession' in c.lower() or 'dealer' in c.lower()) and 'regi' not in c.lower() and 'macro' not in c.lower()]:
                    if fallback_col == 'Loja' or fallback_col == col_cod: continue
                    vals = self.df[fallback_col].astype(str).str.strip()
                    mask_fallback_valida = ~vals.str.lower().isin(['', 'nan', 'none', '<na>', 'desconhecida', 'desconhecido', '-'])
                    mask_para_atualizar = mask_invalida & mask_fallback_valida
                    if mask_para_atualizar.any():
                        self.df.loc[mask_para_atualizar, 'Loja'] = vals[mask_para_atualizar]
                        mask_invalida = self.df['Loja'].isna() | self.df['Loja'].astype(str).str.lower().isin(['', 'nan', 'none', '<na>', 'desconhecida', 'desconhecido', '-'])
                    
            # Mapeamento do nome da Loja a partir do config.json
            import os
            from src.core.paths import get_base_dir
            config_path = os.path.join(get_base_dir(), "app_data", "config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                        
                    lojas_map = {}
                    for loja in config.get("lojas", []):
                        codigo = str(loja.get("codigo", "")).strip() or str(loja.get("cnpj", "")).strip()
                        nome = loja.get("nome", codigo)
                        if codigo and nome: 
                            lojas_map[codigo] = nome
                    
                    if 'Loja' in self.df.columns and lojas_map:
                        self.df['Loja'] = self.df['Loja'].apply(lambda x: lojas_map.get(str(x).strip(), str(x).strip()))
                except Exception as e:
                    print(f"[SSI] Erro ao carregar config de lojas: {e}")
                    
            from src.core.dashboard_engine import DashboardEngine
            engine = DashboardEngine()
            self.df = engine.enriquecer_consultores(self.df)
                    
            self.lbl_status.setText(f"Banco SSI carregado! {len(self.df)} respostas totais.")
            
            self.preencher_filtros()
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self.atualizar_dashboard)
            
        except Exception as e:
            self.lbl_status.setText(f"Erro ao ler Banco SSI: {e}")

    def preencher_filtros(self):
        if self.df.empty: return
        
        self.combo_modalidade.blockSignals(True)
        self.combo_modalidade.clear()
        self.combo_modalidade.addItem("Todas")
        if 'Modalidade de Compra' in self.df.columns:
            modalidades = self.df['Modalidade de Compra'].dropna().unique()
            for mod in modalidades:
                if str(mod).strip() and str(mod).strip() != "nan": self.combo_modalidade.addItem(str(mod))
        self.combo_modalidade.blockSignals(False)

        self.combo_mes.blockSignals(True)
        self.combo_mes.clear()
        self.combo_mes.addItem("Todos")
        
        # Encontrar coluna de data dinamicamente
        col_data = 'Data de resposta SSI 2W'
        if col_data not in self.df.columns:
            for c in self.df.columns:
                c_str = str(c).lower()
                if ('data' in c_str and 'resposta' in c_str) or ('data' in c_str and 'ssi' in c_str):
                    col_data = c
                    break
                    
        if col_data in self.df.columns:
            datas = self.df[col_data].dropna()
            meses = set()
            import re
            for d in datas:
                d_str = str(d).strip()
                if not d_str or d_str == "nan": continue
                
                # Tenta achar formato DD/MM/YYYY ou MM/DD/YYYY
                match = re.search(r'\d{2}/(\d{2})/(\d{4})', d_str)
                if match:
                    meses.add(f"{match.group(1)}/{match.group(2)}")
                else:
                    # Tenta achar formato YYYY-MM-DD
                    match2 = re.search(r'(\d{4})-(\d{2})-\d{2}', d_str)
                    if match2:
                        meses.add(f"{match2.group(2)}/{match2.group(1)}")
                        
                        
            def sort_mes(m):
                try:
                    partes = m.split('/')
                    return (int(partes[1]), int(partes[0]))
                except:
                    return (9999, 99)
                    
            lista_meses_ordenada = sorted(list(meses), key=sort_mes)
            for m in lista_meses_ordenada:
                if m: self.combo_mes.addItem(m)
            
            # Selecionar automaticamente o mês atual por padrão (ou o mais recente disponível)
            from datetime import datetime
            cur_mes_ano = datetime.now().strftime("%m/%Y")
            if cur_mes_ano in lista_meses_ordenada:
                self.combo_mes.setCurrentText(cur_mes_ano)
            elif lista_meses_ordenada:
                self.combo_mes.setCurrentText(lista_meses_ordenada[-1])
            self.combo_mes.blockSignals(False)
        else:
            self.combo_mes.blockSignals(False)

        self.combo_loja.blockSignals(True)
        self.combo_loja.clear()
        self.combo_loja.addItem("Todas")
        if 'Loja' in self.df.columns:
            lojas = self.df['Loja'].dropna().unique()
            for loja in sorted(lojas):
                loja_str = str(loja).strip()
                if loja_str and loja_str.lower() not in ["desconhecida", "desconhecido", "nan", "none", "<na>", ""]: 
                    self.combo_loja.addItem(loja_str)
        self.combo_loja.blockSignals(False)

        self.combo_consultor.blockSignals(True)
        self.combo_consultor.clear()
        self.combo_consultor.addItem("Todos")
        
        self._preencher_vendedores_contextuais()
        self.combo_consultor.blockSignals(False)

    def _ao_mudar_filtros_base(self, _valor=None):
        """Mantém vendedores limitados às respostas dos filtros selecionados."""
        if self.df.empty:
            self.atualizar_dashboard()
            return
        self.combo_consultor.blockSignals(True)
        self._preencher_vendedores_contextuais()
        self.combo_consultor.blockSignals(False)
        self.atualizar_dashboard()

    def _preencher_vendedores_contextuais(self):
        selecionado = self.combo_consultor.currentText() if self.combo_consultor.count() else "Todos"
        base = self.df.copy()

        if self.combo_modalidade.currentText() != "Todas" and 'Modalidade de Compra' in base.columns:
            base = base[base['Modalidade de Compra'] == self.combo_modalidade.currentText()]
        if self.combo_loja.currentText() != "Todas" and 'Loja' in base.columns:
            base = base[base['Loja'] == self.combo_loja.currentText()]

        mes_alvo = self.combo_mes.currentText()
        col_data = 'Data de resposta SSI 2W'
        if col_data not in base.columns:
            col_data = next((c for c in base.columns if 'data' in str(c).lower() and ('resposta' in str(c).lower() or 'ssi' in str(c).lower())), None)
        if mes_alvo != "Todos" and col_data:
            try:
                p_mes, p_ano = mes_alvo.split('/')
                pattern = f"(?:{p_mes}/{p_ano}|{p_ano}-{p_mes})"
                base = base[base[col_data].astype(str).str.contains(pattern, regex=True)]
            except Exception:
                base = base[base[col_data].astype(str).str.contains(mes_alvo, regex=False)]

        vendedores = []
        if 'Consultor_Nome' in base.columns:
            invalidos = {'', 'nan', 'none', '<na>', 'não identificado', 'nao identificado', 'desconhecido'}
            vendedores = sorted({
                str(valor).strip() for valor in base['Consultor_Nome'].dropna().unique()
                if str(valor).strip().lower() not in invalidos
            })

        self.combo_consultor.clear()
        self.combo_consultor.addItem("Todos")
        self.combo_consultor.addItems(vendedores)
        self.combo_consultor.setCurrentText(selecionado if selecionado in vendedores else "Todos")

    def atualizar_dashboard(self):
        if self.df.empty:
            html_vazio = "<html><body><div style='padding:20px; font-family:sans-serif; color:#64748B;'>Nenhum dado encontrado para esses filtros.</div></body></html>"
            self.web_view.setHtml(html_vazio)
            return
            
        df_filtrado = self.df.copy()
        
        if self.combo_modalidade.currentText() != "Todas" and 'Modalidade de Compra' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['Modalidade de Compra'] == self.combo_modalidade.currentText()]
            
        if self.combo_loja.currentText() != "Todas" and 'Loja' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['Loja'] == self.combo_loja.currentText()]
            
        if self.combo_consultor.currentText() != "Todos" and 'Consultor_Nome' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['Consultor_Nome'] == self.combo_consultor.currentText()]
            
        col_data = 'Data de resposta SSI 2W'
        if col_data not in df_filtrado.columns:
            for c in df_filtrado.columns:
                if ('data' in str(c).lower() and 'resposta' in str(c).lower()) or ('data' in str(c).lower() and 'ssi' in str(c).lower()):
                    col_data = c
                    break

        if self.combo_mes.currentText() != "Todos" and col_data in df_filtrado.columns:
            mes_alvo = self.combo_mes.currentText()
            try:
                p_mes, p_ano = mes_alvo.split('/')
                pattern = f"(?:{p_mes}/{p_ano}|{p_ano}-{p_mes})"
                df_filtrado = df_filtrado[df_filtrado[col_data].astype(str).str.contains(pattern, regex=True)]
            except Exception:
                df_filtrado = df_filtrado[df_filtrado[col_data].astype(str).str.contains(mes_alvo, regex=False)]
            
        total_respostas = len(df_filtrado)
        
        if total_respostas == 0:
            html_vazio = "<html><body><div style='padding:20px; font-family:sans-serif; color:#64748B;'>Nenhum dado encontrado para esses filtros.</div></body></html>"
            self.web_view.setHtml(html_vazio)
            return

        col_sat = ssi_raw_column(df_filtrado, 'satisfaction')
        df_filtrado['_sat_num'] = ssi_numeric_series(df_filtrado, col_sat).fillna(-1)

        # Mesmas colunas percentuais oficiais usadas no Relatório Gerencial.
        indice_ssi = calculate_ssi_percentage(df_filtrado, 'satisfaction')
        nps_recomendacao = recommendation_summary(df_filtrado)['nps']
        pct_atendimento = calculate_ssi_percentage(df_filtrado, 'service')
        pct_negociacao = calculate_ssi_percentage(df_filtrado, 'negotiation')
        pct_entrega = calculate_ssi_percentage(df_filtrado, 'delivery')
        pct_instalacoes = calculate_ssi_percentage(df_filtrado, 'installations')
        taxa_test_ride = calculate_ssi_percentage(df_filtrado, 'test_ride')
        taxa_recompra = calculate_ssi_percentage(df_filtrado, 'repurchase')

        lojas_labels = []
        lojas_ssi = []
        lojas_qtde = []
        lojas_faltam = []
        meta_ssi = 95.0

        if 'Loja' in df_filtrado.columns:
            for loja, group in df_filtrado.groupby('Loja'):
                loja_str = str(loja).strip()
                if loja_str.lower() in ["desconhecida", "desconhecido", "nan", "none", "<na>", ""]:
                    continue
                validos = group[group['_sat_num'] >= 0]
                if len(validos) > 0:
                    ssi_loja = calculate_ssi_percentage(group, 'satisfaction')
                    top2 = int(round(ssi_loja / 100.0 * len(validos)))
                    lojas_labels.append(loja_str)
                    lojas_ssi.append(round(ssi_loja, 2))
                    lojas_qtde.append(len(validos))

                    if ssi_loja < meta_ssi:
                        m = meta_ssi / 100.0
                        if m < 1.0: 
                            x = (m * len(validos) - top2) / (1.0 - m)
                            faltam = math.ceil(x)
                            if faltam < 1: faltam = 1
                            lojas_faltam.append(faltam)
                        else:
                            lojas_faltam.append(999) 
                    else:
                        lojas_faltam.append(0)

        labels_json = json.dumps(lojas_labels)
        data_json = json.dumps(lojas_ssi)
        qtde_json = json.dumps(lojas_qtde)
        faltam_json = json.dumps(lojas_faltam)
        quantidade_lojas = len(lojas_ssi)

        cores_lojas = []
        for ssi in lojas_ssi:
            if ssi >= meta_ssi:
                cores_lojas.append('#059669') 
            else:
                cores_lojas.append('#EA580C')

        cores_json = json.dumps(cores_lojas)
        
        # Ranking Vendedores / Consultores
        cons_labels = []
        cons_ssi = []
        cons_qtde = []
        
        if 'Consultor_Nome' in df_filtrado.columns:
            for cons, group in df_filtrado.groupby('Consultor_Nome'):
                cons_str = str(cons).strip()
                if cons_str.lower() in ["nan", "none", "<na>", "", "não identificado", "nao identificado", "desconhecido"]:
                    continue
                validos = group[group['_sat_num'] >= 0]
                if len(validos) > 0:
                    ssi_cons = calculate_ssi_percentage(group, 'satisfaction')
                    cons_labels.append(cons_str)
                    cons_ssi.append(round(ssi_cons, 2))
                    cons_qtde.append(len(validos))
                    
        # Ordenar os vendedores por nota e por quantidade de pesquisas (desempate)
        cons_zip = list(zip(cons_labels, cons_ssi, cons_qtde))
        cons_zip.sort(key=lambda x: (x[1], x[2]), reverse=True)
        cons_labels = [x[0] for x in cons_zip]
        cons_ssi = [x[1] for x in cons_zip]
        cons_qtde = [x[2] for x in cons_zip]
        
        cons_labels_json = json.dumps(cons_labels)
        cons_ssi_json = json.dumps(cons_ssi)
        cons_qtde_json = json.dumps(cons_qtde)

        colunas_comentarios = [
            'Comentário Atendimento Vendedor', 'Comentário Entrega Motocicleta',
            'Comentário Negociação Geral', 'Comentário processo vendas dealer moto',
            'Comentários Instalações', 'Comentários Recomendação', 'Comentário Test-Ride'
        ]
        
        # --- CALCULO HISTORICO ANUAL ---
        self.meses_historico = []
        self.respostas_historico = []
        self.ssi_historico = []
        pilares_ssi = {
            'Atendimento': 'service',
            'Negociação': 'negotiation',
            'Instalações & Conforto': 'installations',
            'Entrega da Motocicleta': 'delivery',
            'Recompra': 'repurchase',
            'Recomendação': 'recommendation',
            'Test Ride': 'test_ride',
        }
        self.pilares_historico = {nome: {'indices': [], 'quantidades': []} for nome in pilares_ssi}
        
        df_historico = self.df.copy()
        if self.combo_modalidade.currentText() != "Todas" and 'Modalidade de Compra' in df_historico.columns:
            df_historico = df_historico[df_historico['Modalidade de Compra'] == self.combo_modalidade.currentText()]
        if self.combo_loja.currentText() != "Todas" and 'Loja' in df_historico.columns:
            df_historico = df_historico[df_historico['Loja'] == self.combo_loja.currentText()]
        if self.combo_consultor.currentText() != "Todos" and 'Consultor_Nome' in df_historico.columns:
            df_historico = df_historico[df_historico['Consultor_Nome'] == self.combo_consultor.currentText()]
            
        col_data_hist = 'Data de resposta SSI 2W'
        if col_data_hist not in df_historico.columns:
            for c in df_historico.columns:
                if 'data' in str(c).lower() and 'resposta' in str(c).lower():
                    col_data_hist = c
                    break
                    
        def extract_mes_ano_ssi(date_str):
            try:
                import re
                match = re.search(r'(\d{2})/(\d{4})', str(date_str))
                if match: return f"{match.group(1)}/{match.group(2)}"
            except: pass
            return "Desconhecido"
            
        if col_data_hist in df_historico.columns:
            df_historico['Mes'] = df_historico[col_data_hist].apply(extract_mes_ano_ssi)
            
            def sort_mes_ssi(m):
                if str(m) == "Desconhecido": return (9999, 99)
                try:
                    partes = str(m).split('/')
                    return (int(partes[1]), int(partes[0]))
                except: return (9999, 99)
                
            meses_unicos = sorted(df_historico['Mes'].dropna().unique(), key=sort_mes_ssi)
            
            import datetime
            mes_selecionado = self.combo_mes.currentText()
            ano_atual = str(mes_selecionado).split('/')[-1] if '/' in str(mes_selecionado) else str(datetime.datetime.now().year)
            anos_presentes = [str(m).split('/')[-1] for m in meses_unicos if '/' in str(m)]
            if anos_presentes and ano_atual not in anos_presentes:
                ano_atual = max(anos_presentes)
            self.ano_historico = ano_atual

            # Mantém a linha do tempo completa; mês sem resposta não recebe nota zero.
            for numero_mes in range(1, 13):
                m = f"{numero_mes:02d}/{ano_atual}"
                df_m = df_historico[df_historico['Mes'] == m].copy()
                self.meses_historico.append(m)
                self.respostas_historico.append(len(df_m))
                if len(df_m) > 0:
                    self.ssi_historico.append(round(calculate_ssi_percentage(df_m, 'satisfaction'), 2))
                else:
                    self.ssi_historico.append(None)
                for nome_pilar, chave_pilar in pilares_ssi.items():
                    coluna_pilar = ssi_raw_column(df_m, chave_pilar)
                    quantidade_oficial = int(ssi_official_series(df_m, chave_pilar).notna().sum())
                    if quantidade_oficial:
                        quantidade_valida = quantidade_oficial
                    elif chave_pilar == 'test_ride' and coluna_pilar in df_m.columns:
                        respostas_validas = df_m[coluna_pilar].astype(str).str.strip().str.lower().isin(['sim', 'não', 'nao'])
                        quantidade_valida = int(respostas_validas.sum())
                    else:
                        quantidade_valida = int(ssi_numeric_series(df_m, coluna_pilar).notna().sum()) if coluna_pilar else 0
                    self.pilares_historico[nome_pilar]['quantidades'].append(quantidade_valida)
                    self.pilares_historico[nome_pilar]['indices'].append(
                        round(calculate_ssi_percentage(df_m, chave_pilar), 2) if quantidade_valida else None
                    )

        self.meses_historico = __import__('json').dumps(self.meses_historico)
        self.respostas_historico = __import__('json').dumps(self.respostas_historico)
        self.ssi_historico = __import__('json').dumps(self.ssi_historico)

        # --- CALCULO HISTORICO DIARIO (MES ATUAL) ---
        self.dias_historico = []
        self.respostas_dias = []
        self.ssi_dias = []

        mes_diario_alvo = self.combo_mes.currentText()
        if mes_diario_alvo == "Todos":
            if len(self.meses_historico) > 0:
                try:
                    meses_lista = __import__('json').loads(self.meses_historico)
                    respostas_lista = __import__('json').loads(self.respostas_historico)
                    mes_diario_alvo = next((m for m, q in reversed(list(zip(meses_lista, respostas_lista))) if q > 0), "Todos")
                except: pass

        if mes_diario_alvo and mes_diario_alvo != "Todos" and col_data_hist in df_historico.columns:
            df_mes = df_historico[df_historico[col_data_hist].astype(str).str.contains(f"/{mes_diario_alvo}")].copy()
            
            def extract_dia_ssi(date_str):
                try:
                    match = re.search(r'(\d{2}/\d{2})', str(date_str))
                    if match: return match.group(1)
                except: pass
                return "Desconhecido"
                
            df_mes['Dia'] = df_mes[col_data_hist].apply(extract_dia_ssi)
            
            def sort_dia_ssi(d):
                try:
                    partes = d.split('/')
                    return (int(partes[1]), int(partes[0]))
                except: return (99, 99)
                
            dias_unicos = sorted(df_mes['Dia'].dropna().unique(), key=sort_dia_ssi)
            for d in dias_unicos:
                if d == "Desconhecido": continue
                df_d = df_mes[df_mes['Dia'] == d].copy()
                if len(df_d) > 0:
                    self.dias_historico.append(str(d))
                    self.respostas_dias.append(len(df_d))
                    
                    self.ssi_dias.append(round(calculate_ssi_percentage(df_d, 'satisfaction'), 2))

        self.dias_historico = __import__('json').dumps(self.dias_historico)
        self.respostas_dias = __import__('json').dumps(self.respostas_dias)
        self.ssi_dias = __import__('json').dumps(self.ssi_dias)
        # -------------------------------

        comentarios_html = ""
        count_comentarios = 0
        df_detratores = df_filtrado[df_filtrado['_sat_num'] <= 8].copy()
        df_detratores = df_detratores.sort_values(by='_sat_num', ascending=True)
        
        for idx, row in df_detratores.iterrows():
            if count_comentarios >= 20: break 
            loja_nome = row['Loja'] if 'Loja' in row else 'Desconhecida'
            nota = row['_sat_num']
            
            textos = []
            for c in colunas_comentarios:
                if c in row and pd.notna(row[c]) and str(row[c]).strip() not in ["", "nan", "None", "-"]:
                    titulo_pilar = c.replace('Comentário ', '').replace('Comentários ', '')
                    textos.append(f"<b>{titulo_pilar}</b>: <i>\"{str(row[c]).strip()}\"</i>")
                    
            if textos:
                texto_final = "<br><br>".join(textos)
                cor_borda = "#EF4444" if nota <= 6 else "#F59E0B"
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

        meses_lista = json.loads(self.meses_historico)
        respostas_lista = json.loads(self.respostas_historico)
        ssi_lista = json.loads(self.ssi_historico)
        mes_em_foco = self.combo_mes.currentText()
        if mes_em_foco == "Todos":
            mes_em_foco = next((m for m, q in reversed(list(zip(meses_lista, respostas_lista))) if q > 0), "Período selecionado")
        variacao_ssi = None
        if mes_em_foco in meses_lista:
            idx_foco = meses_lista.index(mes_em_foco)
            anteriores = [v for v in ssi_lista[:idx_foco] if v is not None]
            if anteriores:
                variacao_ssi = indice_ssi - anteriores[-1]
        if variacao_ssi is None:
            variacao_html = '<span class="delta neutral">Sem comparação anterior</span>'
        else:
            classe_delta = "positive" if variacao_ssi >= 0 else "negative"
            sinal_delta = "+" if variacao_ssi >= 0 else ""
            variacao_html = f'<span class="delta {classe_delta}">{sinal_delta}{variacao_ssi:.2f} p.p. vs. mês anterior</span>'
        historico_series = {
            'Geral': {'indices': ssi_lista, 'quantidades': respostas_lista},
            **self.pilares_historico,
        }
        historico_series_json = json.dumps(historico_series, ensure_ascii=False)
        botoes_pilares_html = ''.join(
            f'<button class="pillar-btn{" active" if nome == "Geral" else ""}" data-pillar="{nome}">{nome}</button>'
            for nome in historico_series
        )

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
                .chart-box {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); height: 240px; position: relative; min-width: 0; }}
                .focus-header {{ display: flex; justify-content: space-between; align-items: center; gap: 20px; padding: 16px 20px; margin-bottom: 14px; border-radius: 14px; background: linear-gradient(120deg, #0f172a 0%, #1d4ed8 100%); color: white; box-shadow: 0 10px 24px rgba(15,23,42,.14); }}
                .focus-eyebrow {{ font-size: 11px; letter-spacing: 1.1px; text-transform: uppercase; color: #bfdbfe; font-weight: 800; }}
                .focus-title {{ margin-top: 4px; font-size: 23px; font-weight: 800; }}
                .focus-period {{ text-align: right; }}
                .focus-period strong {{ display: block; font-size: 19px; }}
                .delta {{ display: inline-block; margin-top: 5px; padding: 4px 9px; border-radius: 999px; font-size: 11px; font-weight: 800; }}
                .delta.positive {{ background: #dcfce7; color: #166534; }}
                .delta.negative {{ background: #fee2e2; color: #991b1b; }}
                .delta.neutral {{ background: #e2e8f0; color: #475569; }}
                .pillar-nav {{ display: flex; flex-wrap: wrap; gap: 7px; margin: 0 0 12px; }}
                .pillar-btn {{ border: 1px solid #cbd5e1; background: #f8fafc; color: #475569; border-radius: 999px; padding: 6px 11px; font: inherit; font-size: 11px; font-weight: 700; cursor: pointer; }}
                .pillar-btn:hover {{ border-color: #60a5fa; color: #1d4ed8; }}
                .pillar-btn.active {{ background: #2563eb; border-color: #2563eb; color: white; }}
                ::-webkit-scrollbar {{ width: 10px; }}
                ::-webkit-scrollbar-track {{ background: #f1f1f1; }}
                ::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 5px; }}
                ::-webkit-scrollbar-thumb:hover {{ background: #94a3b8; }}
            </style>
        </head>
        <body>
            <div id="js-error-log" style="background: red; color: white; padding: 10px; font-weight: bold; display: none;"></div>
            <script>
                window.onerror = function(msg, url, lineNo, columnNo, error) {{
                    var logDiv = document.getElementById('js-error-log');
                    logDiv.style.display = 'block';
                    logDiv.innerHTML += msg + ' na linha ' + lineNo + '<br>';
                    return false;
                }};
            </script>
            <div class="top-panel">
                <div class="focus-header">
                    <div><div class="focus-eyebrow">Resultado do mês em foco</div><div class="focus-title">SSI {indice_ssi:.2f}% · {total_respostas} respostas</div></div>
                    <div class="focus-period"><strong>{mes_em_foco}</strong>{variacao_html}</div>
                </div>
                <div class="kpi-container">
                    <div class="kpi-card green">
                        <div class="kpi-title">Índice SSI Global (Top2Box)</div>
                        <div class="kpi-value">{indice_ssi:.2f}%</div>
                        <div style="font-size: 10px; color: #64748B; margin-top: 1px;">Meta: {meta_ssi:.2f}%</div>
                    </div>
                    <div class="kpi-card purple">
                        <div class="kpi-title">NPS Recomendação</div>
                        <div class="kpi-value">{nps_recomendacao:.2f}</div>
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
            </div>

            <div class="scroll-panel">
                <div style="background: white; padding: 15px; border-radius: 10px; box-shadow: 0 3px 10px rgba(15,23,42,0.06); margin-bottom: 15px;">
                    <h3 style="color: #1E293B; margin: 0 0 12px; border-bottom: 2px solid #E2E8F0; padding-bottom: 8px; font-size: 15px;">Histórico anual {getattr(self, 'ano_historico', '')} · quantidade e SSI</h3>
                    <div class="pillar-nav">{botoes_pilares_html}</div>
                    <div style="height: 270px; position: relative;"><canvas id="chartHistorico"></canvas></div>
                    <div style="font-size: 11px; color: #64748B; margin-top: 5px;">Meses sem respostas apresentam volume 0 e índice —.</div>
                </div>
                <!-- GRAFICOS DE TOP2BOX -->
                <div class="charts-container">
                    <div class="chart-box">
                        <canvas id="chartAvaliacao"></canvas>
                    </div>
                    <div class="chart-box">
                        <canvas id="chartModalidade"></canvas>
                    </div>
                </div>
                
                <div style="background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-top: 15px;">
                    <h3 style="color: #1E293B; margin-top: 0; margin-bottom: 12px; border-bottom: 2px solid #E2E8F0; padding-bottom: 8px; font-size: 15px; font-weight: bold;">
                        🏆 Ranking de Desempenho por Vendedor
                    </h3>
                    <div style="height: 250px; position: relative;">
                        <canvas id="chartConsultores"></canvas>
                    </div>
                </div>
                
                <!-- MURAL DE ALERTAS: A VOZ DO CLIENTE -->
                <div style="margin-top: 20px;">
                    <h3 style="color: #1E293B; margin-top: 0; margin-bottom: 12px; border-bottom: 2px solid #CBD5E1; padding-bottom: 8px; font-size: 16px; font-weight: bold;">
                        Mural de Alertas: A Voz do Cliente (Notas ≤ 8)
                    </h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 15px;">
                        {comentarios_html}
                    </div>
                </div>
            </div>

            <script>
                Chart.register(ChartDataLabels);
                
                // Gráfico da Esquerda: Pilares da Avaliação (Top2Box)
                const ctx1 = document.getElementById('chartAvaliacao').getContext('2d');
                window.chart1 = new Chart(ctx1, {{
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
                        responsive: true,
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
                window.chart2 = new Chart(ctx2, {{
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
                            backgroundColor: {cores_json}, 
                            borderRadius: 4
                        }}]
                    }},
                    options: {{
                        maintainAspectRatio: false,
                        responsive: true,
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
                                                return ['Qtd Pesquisas', '⚠️ Faltam ' + qtd_falta + ' pesquisas'];
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
            
            // Gráfico Histórico (Volume vs SSI)
            const ctxHist = document.getElementById('chartHistorico').getContext('2d');
            const historicoSeries = {historico_series_json};
            window.chartHist = new Chart(ctxHist, {{
                type: 'bar',
                data: {{
                    labels: {self.meses_historico},
                    datasets: [
                        {{
                            type: 'line',
                            label: 'SSI (%)',
                            data: {self.ssi_historico},
                            borderColor: '#F59E0B',
                            backgroundColor: '#F59E0B',
                            borderWidth: 3,
                            yAxisID: 'y1',
                            fill: false,
                            datalabels: {{ 
                                display: true, 
                                align: 'top',
                                anchor: 'end',
                                font: {{ weight: 'bold', size: 12 }}, 
                                color: '#D97706', 
                                formatter: function(v) {{ return v == null ? '' : Number(v).toFixed(2) + '%'; }} 
                            }}
                        }},
                        {{
                            type: 'bar',
                            label: 'Volume de Pesquisas',
                            data: {self.respostas_historico},
                            backgroundColor: '#10B981',
                            borderRadius: 4,
                            yAxisID: 'y',
                            datalabels: {{ 
                                display: true, 
                                anchor: 'center', 
                                align: 'center', 
                                color: '#ffffff', 
                                font: {{ weight: 'bold', size: 12 }} 
                            }}
                        }}
                    ]
                }},
                options: {{
                    maintainAspectRatio: false,
                    responsive: true,
                    plugins: {{
                        legend: {{ display: true, position: 'bottom' }}
                    }},
                    scales: {{
                        y: {{ beginAtZero: true, position: 'left', title: {{ display: true, text: 'Volume de Pesquisas' }} }},
                        y1: {{ beginAtZero: true, max: 115, position: 'right', title: {{ display: true, text: 'SSI %' }}, grid: {{ drawOnChartArea: false }} }}
                    }}
                }}
            }});
            document.querySelectorAll('.pillar-btn').forEach(function(btn) {{
                btn.addEventListener('click', function() {{
                    document.querySelectorAll('.pillar-btn').forEach(function(item) {{ item.classList.remove('active'); }});
                    btn.classList.add('active');
                    const nome = btn.getAttribute('data-pillar');
                    const serie = historicoSeries[nome];
                    window.chartHist.data.datasets[0].label = nome + ' (%)';
                    window.chartHist.data.datasets[0].data = serie.indices;
                    window.chartHist.data.datasets[1].data = serie.quantidades;
                    window.chartHist.options.scales.y1.title.text = nome + ' %';
                    window.chartHist.update();
                }});
            }});

            // Gráfico de Ranking de Vendedores
            const ctxCons = document.getElementById('chartConsultores').getContext('2d');
            window.chartCons = new Chart(ctxCons, {{
                type: 'bar',
                data: {{
                    labels: {cons_labels_json},
                    datasets: [{{
                        label: 'SSI Top2Box (%)',
                        data: {cons_ssi_json},
                        backgroundColor: '#3B82F6',
                        borderRadius: 4,
                        barThickness: 30
                    }}]
                }},
                plugins: [ChartDataLabels],
                options: {{
                    maintainAspectRatio: false,
                    responsive: true,
                    plugins: {{
                        datalabels: {{
                            display: true,
                            anchor: 'end',
                            align: 'top',
                            formatter: function(value, context) {{
                                const qtdes = {cons_qtde_json};
                                return value.toFixed(2) + '%\\n(' + qtdes[context.dataIndex] + ' pesq)';
                            }},
                            font: {{ weight: 'bold', size: 11 }},
                            color: '#1E293B',
                            textAlign: 'center'
                        }},
                        legend: {{ display: false }}
                    }},
                    scales: {{
                        y: {{ beginAtZero: true, max: 115 }}
                    }}
                }}
            }});

                window.addEventListener('resize', function() {{
                    if (window.chart1) window.chart1.resize();
                    if (window.chart2) window.chart2.resize();
                    if (window.chartHist) window.chartHist.resize();
                    if (window.chartCons) window.chartCons.resize();
                }});
            </script>
        </body>
        </html>
        """
        with open("test_ssi.html", "w", encoding="utf-8") as f:
            f.write(html)
        self.web_view.setHtml(html)

    def exportar_pdf_executivo(self):
        if self.df.empty:
            QMessageBox.warning(self, "Aviso", "Não há dados no banco SSI para gerar o relatório.")
            return

        loja_nome = self.combo_loja.currentText()
        mes_ref = self.combo_mes.currentText()
        default_filename = f"Relatorio_Executivo_SSI_{mes_ref.replace('/', '-')}.pdf"
        filepath, _ = QFileDialog.getSaveFileName(self, "Salvar Relatório Executivo - Vendas (SSI)", default_filename, "PDF Files (*.pdf)")
        
        if not filepath:
            return

        df = self.df.copy()
        if loja_nome != "Todas" and 'Loja' in df.columns:
            df = df[df['Loja'].astype(str) == loja_nome]
        elif loja_nome != "Todas":
            col_loja = next((c for c in df.columns if 'concession' in c.lower() or 'conta' in c.lower()), None)
            if col_loja:
                df = df[df[col_loja].astype(str) == loja_nome]

        col_data = 'Data de resposta SSI 2W' if 'Data de resposta SSI 2W' in df.columns else ('Data de Resposta' if 'Data de Resposta' in df.columns else next((c for c in df.columns if 'data' in str(c).lower() and 'resposta' in str(c).lower()), None))
        if not col_data:
            col_data = next((c for c in df.columns if 'data' in str(c).lower() and 'envio' not in str(c).lower() and 'ssi' in str(c).lower()), None)
        if mes_ref != "Todos" and col_data:
            try:
                p_mes, p_ano = mes_ref.split('/')
                pattern = f"(?:{p_mes}/{p_ano}|{p_ano}-{p_mes})"
                df = df[df[col_data].astype(str).str.contains(pattern, regex=True)]
            except Exception:
                df = df[df[col_data].astype(str).str.contains(mes_ref, regex=False)]

        if self.combo_modalidade.currentText() != "Todas":
            col_mod = next((c for c in df.columns if 'modalidade' in c.lower()), None)
            if col_mod:
                df = df[df[col_mod].astype(str) == self.combo_modalidade.currentText()]

        total_respostas = len(df)
        if total_respostas == 0:
            QMessageBox.warning(self, "Aviso", "Nenhum dado encontrado para os filtros selecionados.")
            return

        col_nps = ssi_raw_column(df, 'recommendation')
        resumo_recomendacao = recommendation_summary(df)
        promotores = resumo_recomendacao['promoters']
        neutros = resumo_recomendacao['neutrals']
        detratores = resumo_recomendacao['detractors']
        nps_val = resumo_recomendacao['nps']
        total_nps = resumo_recomendacao['valid']

        sat_geral = calculate_ssi_percentage(df, 'satisfaction')
        recompra_pct = calculate_ssi_percentage(df, 'repurchase')
        entrega_pct = calculate_ssi_percentage(df, 'delivery')

        dimensoes = {}
        dim_map = {
            'Atendimento Vendedor': 'service',
            'Negociação Geral': 'negotiation',
            'Instalações & Conforto': 'installations',
            'Test Ride': 'test_ride',
            'Entrega da Motocicleta': 'delivery',
            'Intenção de Recompra': 'repurchase'
        }
        for label, metric_key in dim_map.items():
            dimensoes[label] = calculate_ssi_percentage(df, metric_key)

        modalidades = []
        col_mod = next((c for c in df.columns if 'modalidade' in c.lower()), None)
        if col_mod:
            for mod_nome, group in df.groupby(col_mod):
                m_qtd = len(group)
                m_resumo = recommendation_summary(group)
                modalidades.append({
                    'nome': str(mod_nome), 'qtd': m_qtd,
                    'ssi': calculate_ssi_percentage(group, 'satisfaction'),
                    'nps': m_resumo['nps']
                })
            modalidades.sort(key=lambda x: x['qtd'], reverse=True)

        detratores_list = []
        if col_nps:
            df_det = df[pd.to_numeric(df[col_nps], errors='coerce') <= 6]
            col_cli = next((c for c in df.columns if any(k in c.lower() for k in ['cliente', 'nome']) and 'concession' not in c.lower() and 'vendedor' not in c.lower()), 'Cliente')
            col_mod_moto = next((c for c in df.columns if 'modelo' in c.lower() and 'ano' not in c.lower()), 'Modelo')
            col_posse = next((c for c in df.columns if 'posse' in c.lower() and 'rela' in c.lower()), 'Relação de Posse: Name')
            col_fone = next((c for c in df.columns if any(k in c.lower() for k in ['telefone', 'fone', 'celular', 'contato'])), None)
            col_coment = next((c for c in df.columns if 'coment' in c.lower() or 'motivo' in c.lower()), None)
            leads_map = self.db.get_leads_mapping() if hasattr(self, 'db') else {}
            
            for _, r in df_det.iterrows():
                # Chassi
                posse_str = str(r.get(col_posse, ''))
                chassi_val = "-"
                if '-' in posse_str:
                    chassi_val = posse_str.split('-')[1].strip()
                elif len(posse_str) >= 17:
                    chassi_val = posse_str.strip()

                # Telefone
                fone_val = ""
                if col_fone and pd.notna(r.get(col_fone)):
                    fone_val = str(r.get(col_fone)).strip()
                if fone_val.lower() in ['nan', 'none', 's/n']:
                    fone_val = ""

                nome_val = str(r.get(col_cli, '')).strip() if col_cli else ''
                
                lead_info = None
                if leads_map:
                    posse_num = posse_str.split('-')[0].strip() if '-' in posse_str else posse_str.strip()
                    chaves_busca = [
                        posse_str.strip(),
                        chassi_val,
                        posse_num,
                        chassi_val.lstrip('0') if chassi_val != '-' else '',
                        str(r.get('id', '')).strip()
                    ]
                    for k in chaves_busca:
                        if k and k not in ['-', 'Sem OS', 'Sem Posse', '', 'nan', 'None'] and k in leads_map:
                            lead_info = leads_map[k]
                            break

                if lead_info:
                    nome_cruzado = str(lead_info.get('cliente', '')).strip()
                    if nome_cruzado and nome_cruzado.upper() not in ['N/D', 'NONE', 'S/N', 'N/A', '-', '']:
                        if not nome_val or nome_val.lower() in ['nan', 'none', '-', '', 'sim', 'não', 'nao', 'n/d', 's/n'] or nome_val.startswith("Comprador (") or nome_val == "Cliente Auditado":
                            nome_val = nome_cruzado

                if not nome_val or nome_val.lower() in ['nan', 'none', '']:
                    nome_val = f"Comprador ({chassi_val})" if chassi_val != '-' else "Cliente Auditado"

                if not fone_val and lead_info:
                    fone_cruzado = str(lead_info.get('telefone', '')).strip()
                    if fone_cruzado and fone_cruzado.lower() not in ['nan', 'none', 's/n', 'n/d', '-', '']:
                        fone_val = fone_cruzado

                nota_val = int(pd.to_numeric(r.get(col_nps), errors='coerce')) if pd.notna(r.get(col_nps)) else 0
                motivo_val = str(r.get(col_coment, 'Insatisfação no processo comercial')) if col_coment else 'Insatisfação no processo comercial'

                detratores_list.append({
                    'data': str(r.get(col_data, '-')),
                    'cliente': nome_val,
                    'telefone': fone_val,
                    'modelo': str(r.get(col_mod_moto, '-')),
                    'chassi': chassi_val,
                    'nota': nota_val,
                    'motivo': motivo_val[:110]
                })

        metrics = {
            'nps': nps_val,
            'ssi': sat_geral,
            'satisfacao_geral': sat_geral,
            'total_respostas': total_respostas,
            'promotores_count': promotores,
            'neutros_count': neutros,
            'detratores_count': detratores,
            'promotores_pct': (promotores / total_nps * 100) if total_nps > 0 else 0.0,
            'neutros_pct': (neutros / total_nps * 100) if total_nps > 0 else 0.0,
            'detratores_pct': (detratores / total_nps * 100) if total_nps > 0 else 0.0,
            'recompra_pct': recompra_pct,
            'entrega_pct': entrega_pct,
            'saas_taxa_resp': 71.0,
            'dimensoes': dimensoes
        }

        sucesso = PDFReportGenerator.generate_ssi_report(filepath, loja_nome, mes_ref, metrics, modalidades, detratores_list)
        if sucesso:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Relatório Gerado com Sucesso")
            msg_box.setText("O Relatório Executivo de Vendas (SSI) foi gerado com sucesso!")
            msg_box.setInformativeText(f"Arquivo salvo em:\n{filepath}\n\nDeseja abrir o arquivo agora?")
            btn_abrir = msg_box.addButton("Abrir PDF", QMessageBox.ButtonRole.AcceptRole)
            btn_ok = msg_box.addButton("Fechar", QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()

            if msg_box.clickedButton() == btn_abrir:
                QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))
        else:
            QMessageBox.critical(self, "Erro", "Não foi possível gerar o arquivo PDF.")
