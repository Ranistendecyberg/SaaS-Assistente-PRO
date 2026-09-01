import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QComboBox, QFrame, QFileDialog, QMessageBox)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from src.core.dashboard_engine import DashboardEngine
from src.core.pdf_report_generator import PDFReportGenerator
import urllib.parse
import os

class DashboardScreen(QWidget):
    def __init__(self):
        super().__init__()
        self._is_loading_filters = False
        self.engine = DashboardEngine()
        
        self.df_base = self.engine.load_data()
        
        self.setup_ui()
        self.carregar_filtros()
        self.atualizar_dashboard()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Título
        lbl_titulo = QLabel("📊 Painel de Resultados TSI")
        lbl_titulo.setStyleSheet("color: #1E293B; font-size: 22px; font-weight: 800; border: none;")
        layout.addWidget(lbl_titulo)
        
        # Filtros (Painel Superior)
        filtros_frame = QFrame()
        filtros_frame.setStyleSheet("background-color: white; border: 1px solid #CBD5E1; border-radius: 8px;")
        filtros_layout = QHBoxLayout(filtros_frame)
        filtros_layout.setContentsMargins(15, 10, 15, 10)
        
        self.cb_loja = QComboBox()
        self.cb_consultor = QComboBox()
        self.cb_mes = QComboBox()
        self.cb_categoria = QComboBox()
        
        btn_atualizar = QPushButton("🔄 Atualizar Painel")
        btn_atualizar.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 8px 15px; border-radius: 5px;")
        btn_atualizar.clicked.connect(self.forcar_recarga)

        btn_pdf = QPushButton("📄 PDF Diretoria")
        btn_pdf.setStyleSheet("background-color: #DC2626; color: white; font-weight: bold; padding: 8px 15px; border-radius: 5px;")
        btn_pdf.clicked.connect(self.exportar_pdf_executivo)
        
        self.cb_loja.currentTextChanged.connect(self.atualizar_dashboard)
        self.cb_consultor.currentTextChanged.connect(self.atualizar_dashboard)
        self.cb_mes.currentTextChanged.connect(self.atualizar_dashboard)
        self.cb_categoria.currentTextChanged.connect(self.atualizar_dashboard)
        
        def _add_filter(nome, cb):
            vbox = QVBoxLayout()
            lbl = QLabel(nome)
            lbl.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px; border: none;")
            cb.setStyleSheet("""
                QComboBox {
                    background-color: #F8FAFC; 
                    border: 1px solid #E2E8F0; 
                    border-radius: 5px; 
                    padding-left: 10px; 
                    padding-top: 5px;
                    padding-bottom: 5px;
                    color: #1E293B; 
                    font-weight: bold;
                }
                QComboBox::drop-down {
                    border: none;
                    background: transparent;
                }
                QComboBox QAbstractItemView {
                    background-color: white;
                    color: black;
                    selection-background-color: #E2E8F0;
                }
            """)
            cb.setFixedWidth(150)
            vbox.addWidget(lbl)
            vbox.addWidget(cb)
            filtros_layout.addLayout(vbox)
            
        _add_filter("Concessionária:", self.cb_loja)
        _add_filter("Consultor Técnico:", self.cb_consultor)
        _add_filter("Mês:", self.cb_mes)
        _add_filter("Categoria Produto:", self.cb_categoria)
        
        filtros_layout.addStretch()
        filtros_layout.addWidget(btn_atualizar)
        filtros_layout.addWidget(btn_pdf)
        
        layout.addWidget(filtros_frame)
        
        # Gráficos em QWebEngineView
        self.web_view = QWebEngineView()
        self.web_view.setStyleSheet("background-color: white; border: 1px solid #CBD5E1; border-radius: 8px;")
        layout.addWidget(self.web_view, stretch=1)

    def forcar_recarga(self):
        self.carregar_filtros()
        self.atualizar_dashboard()

    def showEvent(self, event):
        super().showEvent(event)
        self.carregar_filtros()
        self.atualizar_dashboard()

    def carregar_dados(self):
        self.carregar_filtros()
        self.atualizar_dashboard()

    def carregar_filtros(self):
        self._is_loading_filters = True
        # Recarregar df base do banco mais recente
        self.df_base = self.engine.load_data()
        
        self.cb_loja.clear()
        self.cb_consultor.clear()
        self.cb_mes.clear()
        self.cb_categoria.clear()
        
        self.cb_loja.addItem("Todas")
        self.cb_consultor.addItem("Todos")
        self.cb_mes.addItem("Todos")
        self.cb_categoria.addItem("Todas")
        
        if not self.df_base.empty:
            if 'Loja_Nome' in self.df_base.columns:
                for v in sorted(self.df_base['Loja_Nome'].dropna().unique()):
                    v_str = str(v).strip()
                    if v_str and v_str.lower() not in ['nan', 'none', 'desconhecida', 'desconhecido', '']:
                        self.cb_loja.addItem(v_str)
                    
            if 'Consultor_Nome' in self.df_base.columns:
                for v in sorted(self.df_base['Consultor_Nome'].dropna().unique()):
                    v_str = str(v).strip()
                    if v_str and v_str.lower() not in ['nan', 'none', 'desconhecido', '']:
                        self.cb_consultor.addItem(v_str)
                    
            if 'Mes' in self.df_base.columns:
                def sort_mes_tsi(m):
                    if str(m) == "Desconhecido": return (9999, 99)
                    try:
                        partes = str(m).split('/')
                        return (int(partes[1]), int(partes[0]))
                    except:
                        return (9999, 99)
                
                meses_unicos = [str(v).strip() for v in sorted(self.df_base['Mes'].dropna().unique(), key=sort_mes_tsi) if str(v).strip() and str(v).strip().lower() not in ['nan', 'none', 'desconhecido', '']]
                for v_str in meses_unicos:
                    self.cb_mes.addItem(v_str)
                
                # Selecionar automaticamente o mês atual por padrão (ou o mais recente disponível)
                from datetime import datetime
                cur_mes_ano = datetime.now().strftime("%m/%Y")
                if cur_mes_ano in meses_unicos:
                    self.cb_mes.setCurrentText(cur_mes_ano)
                elif meses_unicos:
                    self.cb_mes.setCurrentText(meses_unicos[-1])
                    
            if 'Categoria Produto' in self.df_base.columns:
                for v in sorted(self.df_base['Categoria Produto'].dropna().unique()):
                    v_str = str(v).strip()
                    if v_str and v_str.lower() not in ['nan', 'none', 'desconhecido', '']:
                        self.cb_categoria.addItem(v_str)
                    
        self._is_loading_filters = False

    def atualizar_dashboard(self):
        if self._is_loading_filters:
            return
            
        # Não recarregamos o df_base aqui para não destruir o sentido do cache na troca de filtros
        # self.df_base = self.engine.load_data()
        
        if self.df_base.empty:
            html = "<h2>Ainda não há dados coletados pelo Auditor.</h2><p>Aguarde o auditor extrair o histórico TSI na aba principal.</p>"
            self.web_view.setHtml(html)
            return
            

        # --- CALCULO HISTORICO ANUAL ---
        self.meses_historico = []
        self.respostas_historico = []
        self.tsi_historico = []
        self.t2b_historico = []
        pilares_tsi_colunas = {
            'Instalações & Infra': 'Avaliação satisfação instalações e infra',
            'Consultor Técnico': 'Avaliação satisfação consultor',
            'Qualidade do Serviço': 'Avaliação satisfação qualidade',
            'Entrega do Veículo': 'Avaliação satisfação entrega',
            'Custo/Benefício': 'Avaliação satisfação custo benefício',
            'Agendamento': 'Avaliação satisfação agendamento',
            'Recepção': 'Avaliação satisfação recepção',
        }
        self.pilares_historico = {nome: {'indices': [], 'top2box': [], 'quantidades': []} for nome in pilares_tsi_colunas}
        
        df_historico = self.df_base.copy()
        if self.cb_loja.currentText() != "Todas" and 'Loja_Nome' in df_historico.columns:
            df_historico = df_historico[df_historico['Loja_Nome'] == self.cb_loja.currentText()]
        if self.cb_consultor.currentText() != "Todos" and 'Consultor_Nome' in df_historico.columns:
            df_historico = df_historico[df_historico['Consultor_Nome'] == self.cb_consultor.currentText()]
        if self.cb_categoria.currentText() != "Todas" and 'Categoria Produto' in df_historico.columns:
            df_historico = df_historico[df_historico['Categoria Produto'] == self.cb_categoria.currentText()]

        def sort_mes_tsi(m):
            if str(m) == "Desconhecido": return (9999, 99)
            try:
                partes = str(m).split('/')
                return (int(partes[1]), int(partes[0]))
            except: return (9999, 99)
            
        if 'Mes' in df_historico.columns:
            meses_unicos = sorted(df_historico['Mes'].dropna().unique(), key=sort_mes_tsi)
            import datetime
            mes_selecionado = self.cb_mes.currentText()
            ano_atual = str(mes_selecionado).split('/')[-1] if '/' in str(mes_selecionado) else str(datetime.datetime.now().year)
            anos_presentes = [str(m).split('/')[-1] for m in meses_unicos if '/' in str(m)]
            if anos_presentes and ano_atual not in anos_presentes:
                ano_atual = max(anos_presentes)
            self.ano_historico = ano_atual

            # Exibe sempre os 12 meses. Sem respostas, o volume é zero e o índice é N/A.
            for numero_mes in range(1, 13):
                m = f"{numero_mes:02d}/{ano_atual}"
                df_m = df_historico[df_historico['Mes'].astype(str) == m]
                self.meses_historico.append(m)
                self.respostas_historico.append(len(df_m))
                if len(df_m) > 0:
                    metricas_m = self.engine.calculate_metrics(df_m)
                    tsi_val = metricas_m['tsi_global'] if metricas_m else 0
                    t2b_val = metricas_m['top2box_global'] if metricas_m else 0
                    self.tsi_historico.append(round(tsi_val, 2))
                    self.t2b_historico.append(round(t2b_val, 2))
                else:
                    self.tsi_historico.append(None)
                    self.t2b_historico.append(None)
                for nome_pilar, coluna_pilar in pilares_tsi_colunas.items():
                    serie_valida = df_m[coluna_pilar].dropna() if coluna_pilar in df_m.columns else []
                    quantidade_valida = len(serie_valida)
                    self.pilares_historico[nome_pilar]['quantidades'].append(quantidade_valida)
                    if quantidade_valida:
                        indice_pilar = float(serie_valida.sum()) / (quantidade_valida * 10) * 100
                        top2_pilar = float((serie_valida >= 9).sum()) / quantidade_valida * 100
                        self.pilares_historico[nome_pilar]['indices'].append(round(indice_pilar, 2))
                        self.pilares_historico[nome_pilar]['top2box'].append(round(top2_pilar, 2))
                    else:
                        self.pilares_historico[nome_pilar]['indices'].append(None)
                        self.pilares_historico[nome_pilar]['top2box'].append(None)
                    
        # --- CALCULO HISTORICO DIARIO (MES ATUAL) ---
        self.dias_historico = []
        self.respostas_dias = []
        self.tsi_dias = []

        mes_diario_alvo = self.cb_mes.currentText()
        if mes_diario_alvo == "Todos":
            for mes_hist, qtd_hist in reversed(list(zip(self.meses_historico, self.respostas_historico))):
                if qtd_hist > 0:
                    mes_diario_alvo = mes_hist
                    break

        if mes_diario_alvo and mes_diario_alvo != "Todos" and 'Mes' in df_historico.columns:
            df_mes = df_historico[df_historico['Mes'] == mes_diario_alvo].copy()
            
            col_data_tsi = 'Data do Faturamento'
            if col_data_tsi not in df_mes.columns:
                for c in df_mes.columns:
                    if 'data' in str(c).lower():
                        col_data_tsi = c
                        break
                        
            def extract_dia_tsi(date_str):
                try:
                    match = re.search(r'(\d{2}/\d{2})', str(date_str))
                    if match: return match.group(1)
                except: pass
                return "Desconhecido"
                
            if col_data_tsi in df_mes.columns:
                df_mes['Dia'] = df_mes[col_data_tsi].apply(extract_dia_tsi)
                
                def sort_dia_tsi(d):
                    try:
                        partes = d.split('/')
                        return (int(partes[1]), int(partes[0]))
                    except: return (99, 99)
                    
                dias_unicos = sorted(df_mes['Dia'].dropna().unique(), key=sort_dia_tsi)
                for d in dias_unicos:
                    if d == "Desconhecido": continue
                    df_d = df_mes[df_mes['Dia'] == d]
                    if len(df_d) > 0:
                        self.dias_historico.append(str(d))
                        self.respostas_dias.append(len(df_d))
                        metricas_d = self.engine.calculate_metrics(df_d)
                        tsi_val_d = metricas_d['top2box_global'] if metricas_d else 0
                        self.tsi_dias.append(round(tsi_val_d, 2))
        # -------------------------------

        df_filtrado_lojas = self.df_base.copy()
        
        if self.cb_consultor.currentText() != "Todos":
            df_filtrado_lojas = df_filtrado_lojas[df_filtrado_lojas['Consultor_Nome'] == self.cb_consultor.currentText()]
            
        if self.cb_mes.currentText() != "Todos":
            df_filtrado_lojas = df_filtrado_lojas[df_filtrado_lojas['Mes'] == self.cb_mes.currentText()]
            
        if self.cb_categoria.currentText() != "Todas":
            if 'Categoria Produto' in df_filtrado_lojas.columns:
                df_filtrado_lojas = df_filtrado_lojas[df_filtrado_lojas['Categoria Produto'] == self.cb_categoria.currentText()]

        df_filtrado = df_filtrado_lojas.copy()
        
        if self.cb_loja.currentText() != "Todas":
            df_filtrado = df_filtrado[df_filtrado['Loja_Nome'] == self.cb_loja.currentText()]

        metricas = self.engine.calculate_metrics(df_filtrado)
        if metricas is None:
            self.web_view.setHtml("<h2>Nenhuma resposta encontrada para esses filtros.</h2>")
            return
            
        html = self.gerar_html_graficos(metricas, df_filtrado, df_filtrado_lojas)
        self.web_view.setHtml(html)

    def gerar_html_graficos(self, metricas, df_filtrado=None, df_filtrado_lojas=None):
        if df_filtrado_lojas is None:
            df_filtrado_lojas = df_filtrado
        total_pesquisas = len(df_filtrado) if df_filtrado is not None else 0
        # Extrair dados do Dicionário
        tsi = metricas['tsi_global']
        t2b = metricas['top2box_global']
        meta = metricas['meta_global']
        recup = metricas.get('pesquisas_recuperacao', 0)
        individual_mestre = metricas['individual_mestre']
        individual_extra = metricas['individual_extra']

        mes_em_foco = self.cb_mes.currentText()
        if mes_em_foco == "Todos":
            mes_em_foco = next((m for m, q in reversed(list(zip(self.meses_historico, self.respostas_historico))) if q > 0), "Período selecionado")
        variacao_tsi = None
        if mes_em_foco in self.meses_historico:
            idx_foco = self.meses_historico.index(mes_em_foco)
            anteriores = [v for v in self.tsi_historico[:idx_foco] if v is not None]
            if anteriores:
                variacao_tsi = tsi - anteriores[-1]
        if variacao_tsi is None:
            variacao_html = '<span class="delta neutral">Sem comparação anterior</span>'
        else:
            classe_delta = "positive" if variacao_tsi >= 0 else "negative"
            sinal_delta = "+" if variacao_tsi >= 0 else ""
            variacao_html = f'<span class="delta {classe_delta}">{sinal_delta}{variacao_tsi:.2f} p.p. vs. mês anterior</span>'
        historico_series = {
            'Geral': {'indices': self.tsi_historico, 'top2box': self.t2b_historico, 'quantidades': self.respostas_historico},
            **self.pilares_historico,
        }
        historico_series_json = json.dumps(historico_series, ensure_ascii=False)
        botoes_pilares_html = ''.join(
            f'<button class="pillar-btn{" active" if nome == "Geral" else ""}" data-pillar="{nome}">{nome}</button>'
            for nome in historico_series
        )
        
        labels_mestre = list(individual_mestre.keys())
        tsi_data = [round(individual_mestre[k]['TSI'], 2) for k in labels_mestre]
        meta_data = [meta for _ in labels_mestre]
        
        # Limpar labels para exibição (nomes amigáveis)
        mapeamento = {
            'Avaliação satisfação instalações e infra': 'Infraestrutura',
            'Avaliação satisfação consultor': 'Consultor',
            'Avaliação satisfação qualidade': 'Qualidade',
            'Avaliação satisfação entrega': 'Entregas',
            'Avaliação satisfação custo benefício': 'Custo Benefício'
        }
        labels_clean = [mapeamento.get(l, l) for l in labels_mestre]
        

        # Mural Voz do Cliente
        comentarios_html = ""
        count_comentarios = 0
        if df_filtrado is not None:
            import pandas as pd
            df_com = df_filtrado.copy()
            col_sat = 'Avaliação satisfação geral'
            if col_sat not in df_com.columns:
                col_sat = 'Nota Pesquisa TSI'
                
            if col_sat in df_com.columns:
                df_com['_sat_num'] = pd.to_numeric(df_com[col_sat], errors='coerce').fillna(10)
                
                colunas_comentarios = [
                    'Motivo satisfação geral', 
                    'Detalhes instalações e infra', 
                    'Motivo insatisfação consultor', 
                    'Motivo insatisfação qualidade', 
                    'Motivo insatisfação entrega', 
                    'Motivo insatisfação custo beneficio', 
                    'Comentário conclusão final'
                ]
                
                df_com['has_comment'] = False
                for c in colunas_comentarios:
                    if c in df_com.columns:
                        has_val = df_com[c].notna() & (df_com[c].astype(str).str.strip() != "") & (df_com[c].astype(str).str.strip() != "nan") & (df_com[c].astype(str).str.strip() != "None") & (df_com[c].astype(str).str.strip() != "-")
                        df_com['has_comment'] = df_com['has_comment'] | has_val
                        
                df_detratores = df_com[df_com['has_comment']].copy()
                df_detratores = df_detratores.sort_values(by='_sat_num', ascending=True)
                
                for idx, row in df_detratores.iterrows():
                    if count_comentarios >= 20: break 
                    loja_nome = row['Loja_Nome'] if 'Loja_Nome' in row else 'Desconhecida'
                    nota = row['_sat_num']
                    
                    textos = []
                    for c in colunas_comentarios:
                        if c in row and pd.notna(row[c]) and str(row[c]).strip() not in ["", "nan", "None", "-"]:
                            titulo_pilar = c.replace('Motivo insatisfação ', '').replace('Detalhes ', '').replace('Motivo satisfação ', '')
                            titulo_pilar = titulo_pilar.capitalize()
                            textos.append(f"<b>{titulo_pilar}</b>: <i>\"{str(row[c]).strip()}\"</i>")
                            
                    if textos:
                        texto_final = "<br><br>".join(textos)
                        cor_borda = "#EF4444" if nota <= 6 else "#F59E0B"
                        cor_fundo_nota = "#FEE2E2" if nota <= 6 else "#FEF3C7"
                        cor_texto_nota = "#B91C1C" if nota <= 6 else "#D97706"
        
                        comentarios_html += f'''
                        <div style="background: white; border-left: 5px solid {cor_borda}; padding: 15px; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
                                <span style="font-weight: bold; color: #1E293B; font-size: 14px;">Loja: {loja_nome}</span>
                                <span style="background: {cor_fundo_nota}; color: {cor_texto_nota}; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;">Nota Geral: {nota:.0f}</span>
                            </div>
                            <div style="color: #475569; font-size: 13px; line-height: 1.5;">{texto_final}</div>
                        </div>
                        '''
                        count_comentarios += 1
                        
        if count_comentarios == 0:
            comentarios_html = "<div style='color: #64748B; font-style: italic; padding: 10px;'>Nenhum comentário de insatisfação encontrado nos filtros atuais. Excelente! 🎉</div>"

        # Formatador de texto para Recuperação
        if recup == -1:
            recup_html = "<span>Impossível</span>"
        elif recup == 0:
            recup_html = "<span style='font-size:16px;'>Meta Atingida!</span>"
        else:
            recup_html = f"<span>{recup}</span>"
            
        # O dashboard_screen.py está em src/ui/screens (3 níveis abaixo da raiz)
        # Usamos o CDN oficial do ECharts para garantir que sempre carregue independente de PyInstaller
        echarts_url = "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"

        # Construir cards para métricas extras
        cards_extras_html = ""
        for k, v in individual_extra.items():
            nome = k.replace("Avaliação satisfação", "").strip()
            if nome.lower().startswith("geral"):
                nome = "Geral"
            elif "amigo" in nome.lower():
                nome = "Recomendação"
            elif "retorno" in nome.lower():
                nome = "Retorno"
            elif "agendamento" in nome.lower():
                nome = "Agendamento"
            elif "recepção" in nome.lower():
                nome = "Recepção"
            
            cards_extras_html += f"""
                <div class="extra-card">
                    <h4>{nome.upper()}</h4>
                    <div class="extra-stats">
                        <span class="t2b-pill">T2B: {v['Top2Box']:.2f}%</span>
                        <span class="tsi-pill">TSI: {v['TSI']:.2f}%</span>
                    </div>
                </div>
            """


        # Data for Lojas Chart
        lojas_labels = []
        lojas_tsi = []
        lojas_qtde = []
        lojas_faltam = []
        cores_lojas = []
        
        if df_filtrado_lojas is not None and 'Loja_Nome' in df_filtrado_lojas.columns:
            for loja, group in df_filtrado_lojas.groupby('Loja_Nome'):
                if str(loja).strip() in ["Desconhecida", "nan", ""]: continue
                metrics_loja = self.engine.calculate_metrics(group)
                if metrics_loja:
                    tsi_val = metrics_loja['tsi_global']
                    lojas_labels.append(str(loja))
                    lojas_tsi.append(round(tsi_val, 2))
                    lojas_qtde.append(len(group))
                    
                    recup = metrics_loja.get('pesquisas_recuperacao', 0)
                    if recup == -1: recup = 999
                    lojas_faltam.append(recup)
                    
                    paleta = ['#3b82f6', '#f59e0b', '#10b981', '#8b5cf6', '#ec4899', '#14b8a6', '#f43f5e', '#6366f1']
                    cores_lojas.append(paleta[len(lojas_labels) % len(paleta)])

        labels_lojas_json = __import__('json').dumps(lojas_labels)
        tsi_lojas_json = __import__('json').dumps(lojas_tsi)
        qtde_lojas_json = __import__('json').dumps(lojas_qtde)
        faltam_lojas_json = __import__('json').dumps(lojas_faltam)
        cores_lojas_json = __import__('json').dumps(cores_lojas)
        meta_lojas_json = __import__('json').dumps([meta for _ in lojas_labels])
        

        # Data for Categorias Chart
        cat_labels = []
        cat_tsi = []
        cat_qtde = []
        cores_cat = []
        
        if df_filtrado is not None and 'Categoria Produto' in df_filtrado.columns:
            for cat, group in df_filtrado.groupby('Categoria Produto'):
                if str(cat).strip() in ["nan", "", "None"]: continue
                metrics_cat = self.engine.calculate_metrics(group)
                if metrics_cat:
                    tsi_val = metrics_cat['tsi_global']
                    cat_labels.append(str(cat))
                    cat_tsi.append(round(tsi_val, 2))
                    cat_qtde.append(len(group))
                    
                    paleta = ['#3b82f6', '#f59e0b', '#10b981', '#8b5cf6', '#ec4899', '#14b8a6', '#f43f5e', '#6366f1']
                    cores_cat.append(paleta[len(cat_labels) % len(paleta)])

        ordem_cat = {"Alta": 1, "Média": 2, "Baixa": 3, "Scooter": 4}
        cat_data = list(zip(cat_labels, cat_tsi, cat_qtde, cores_cat))
        cat_data.sort(key=lambda x: ordem_cat.get(x[0], 99))
        if cat_data:
            cat_labels, cat_tsi, cat_qtde, cores_cat = zip(*cat_data)
            cat_labels = list(cat_labels)
            cat_tsi = list(cat_tsi)
            cat_qtde = list(cat_qtde)
            cores_cat = list(cores_cat)

        # Data for Consultor Chart
        cons_labels = []
        cons_tsi = []
        cons_qtde = []
        cores_cons = []
        
        if df_filtrado is not None and 'Consultor_Nome' in df_filtrado.columns:
            for cons, group in df_filtrado.groupby('Consultor_Nome'):
                if str(cons).strip() in ["nan", "", "None", "Desconhecida"]: continue
                metrics_cons = self.engine.calculate_metrics(group)
                if metrics_cons:
                    tsi_val = metrics_cons['tsi_global']
                    nome_cons = str(cons).strip()
                    if nome_cons.isdigit():
                        nome_cons = "ID " + nome_cons[-4:]
                    elif " " in nome_cons:
                        nome_cons = nome_cons.split()[0]

                    cons_labels.append(nome_cons)
                    cons_tsi.append(round(tsi_val, 2))
                    cons_qtde.append(len(group))
                    
        cons_data = list(zip(cons_labels, cons_tsi, cons_qtde))
        cons_data.sort(key=lambda x: x[1], reverse=True)
        if cons_data:
            cons_labels, cons_tsi, cons_qtde = zip(*cons_data)
            cons_labels = list(cons_labels)
            cons_tsi = list(cons_tsi)
            cons_qtde = list(cons_qtde)
            for i in range(len(cons_labels)):
                paleta = ['#3b82f6', '#f59e0b', '#10b981', '#8b5cf6', '#ec4899', '#14b8a6', '#f43f5e', '#6366f1']
                cores_cons.append(paleta[i % len(paleta)])

        labels_cat_json = __import__('json').dumps(cat_labels)
        tsi_cat_json = __import__('json').dumps(cat_tsi)
        qtde_cat_json = __import__('json').dumps(cat_qtde)
        cores_cat_json = __import__('json').dumps(cores_cat)
        
        labels_cons_json = __import__('json').dumps(cons_labels)
        tsi_cons_json = __import__('json').dumps(cons_tsi)
        qtde_cons_json = __import__('json').dumps(cons_qtde)
        cores_cons_json = __import__('json').dumps(cores_cons)
        
        meta_cat_json = __import__('json').dumps([meta for _ in cat_labels])
        meta_cons_json = __import__('json').dumps([meta for _ in cons_labels])

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script src="{echarts_url}"></script>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
                
                body {{ 
                    font-family: 'Outfit', sans-serif; 
                    margin: 0; 
                    padding: 20px; 
                    background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
                    color: #1e293b;
                    min-height: 100vh;
                }}
                
                .dashboard-grid {{
                    display: grid;
                    grid-template-columns: 1fr 2fr;
                    gap: 20px;
                    margin-bottom: 20px;
                }}
                
                .glass-panel {{
                    background: rgba(255, 255, 255, 0.7);
                    backdrop-filter: blur(10px);
                    -webkit-backdrop-filter: blur(10px);
                    border: 1px solid rgba(255, 255, 255, 0.5);
                    border-radius: 16px;
                    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);
                    padding: 20px;
                    transition: transform 0.3s ease, box-shadow 0.3s ease;
                }}
                .glass-panel:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 15px 30px rgba(0, 0, 0, 0.08);
                }}
                
                #gauge-container {{ width: 100%; height: 230px; }}
                #bar-container {{ width: 100%; height: 260px; }}
                
                .section-title {{
                    font-size: 16px;
                    font-weight: 800;
                    color: #334155;
                    margin-top: 0;
                    margin-bottom: 15px;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                }}
                
                .extras-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
                    gap: 15px;
                }}
                
                .extra-card {{
                    background: white;
                    border-radius: 12px;
                    padding: 15px;
                    border-left: 4px solid #6366f1;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.02);
                }}
                
                .extra-card h4 {{
                    margin: 0 0 10px 0;
                    font-size: 13px;
                    color: #475569;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }}
                
                .extra-stats {{
                    display: flex;
                    gap: 10px;
                }}
                
                .t2b-pill, .tsi-pill {{
                    font-size: 11px;
                    font-weight: 800;
                    padding: 4px 8px;
                    border-radius: 20px;
                }}
                
                .t2b-pill {{ background: #eff6ff; color: #2563eb; }}
                .tsi-pill {{ background: #fef3c7; color: #d97706; }}

                .kpi-row {{
                    display: flex;
                    gap: 15px;
                    margin-top: 15px;
                }}
                .kpi-mini {{
                    flex: 1;
                    text-align: center;
                    background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%);
                    color: white;
                    border-radius: 10px;
                    padding: 15px 10px;
                    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3);
                }}
                .kpi-mini.green {{
                    background: linear-gradient(135deg, #059669 0%, #10b981 100%);
                    box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
                }}
                .kpi-mini.red {{
                    background: linear-gradient(135deg, #ef4444 0%, #f87171 100%);
                    box-shadow: 0 4px 15px rgba(239, 68, 68, 0.3);
                }}
                .kpi-mini h5 {{ margin: 0 0 5px 0; font-size: 11px; opacity: 0.9; font-weight: 400; text-transform: uppercase; }}
                .kpi-mini span {{ font-size: 22px; font-weight: 800; }}
                .focus-header {{
                    display: flex; justify-content: space-between; align-items: center; gap: 20px;
                    padding: 18px 22px; margin-bottom: 14px; border-radius: 16px;
                    background: linear-gradient(120deg, #0f172a 0%, #1e3a8a 100%); color: white;
                    box-shadow: 0 12px 28px rgba(15, 23, 42, .16);
                }}
                .focus-eyebrow {{ font-size: 11px; letter-spacing: 1.2px; text-transform: uppercase; color: #93c5fd; font-weight: 800; }}
                .focus-title {{ margin: 4px 0 0; font-size: 24px; font-weight: 800; }}
                .focus-period {{ text-align: right; }}
                .focus-period strong {{ display: block; font-size: 20px; }}
                .delta {{ display: inline-block; margin-top: 5px; padding: 4px 9px; border-radius: 999px; font-size: 11px; font-weight: 800; }}
                .delta.positive {{ background: #dcfce7; color: #166534; }}
                .delta.negative {{ background: #fee2e2; color: #991b1b; }}
                .delta.neutral {{ background: #e2e8f0; color: #475569; }}
                .pillar-nav {{ display: flex; flex-wrap: wrap; gap: 7px; margin: -3px 0 12px; }}
                .pillar-btn {{ border: 1px solid #cbd5e1; background: #f8fafc; color: #475569; border-radius: 999px; padding: 6px 11px; font: inherit; font-size: 11px; font-weight: 700; cursor: pointer; }}
                .pillar-btn:hover {{ border-color: #60a5fa; color: #1d4ed8; }}
                .pillar-btn.active {{ background: #2563eb; border-color: #2563eb; color: white; }}
            </style>
        </head>
        <body>
            <div class="focus-header">
                <div>
                    <div class="focus-eyebrow">Resultado do mês em foco</div>
                    <div class="focus-title">TSI {tsi:.2f}% · {total_pesquisas} respostas</div>
                </div>
                <div class="focus-period"><strong>{mes_em_foco}</strong>{variacao_html}</div>
            </div>

            <div class="glass-panel" style="margin-bottom: 20px;">
                <h2 class="section-title">Histórico anual {getattr(self, 'ano_historico', '')} · quantidade e índices</h2>
                <div class="pillar-nav">{botoes_pilares_html}</div>
                <div id="history-container" style="width: 100%; height: 320px;"></div>
                <div style="margin-top: 6px; font-size: 11px; color: #64748b;">Meses sem respostas apresentam volume 0 e índice —.</div>
            </div>

            <div class="dashboard-grid">
                <!-- Painel Esquerdo: TSI Geral -->
                <div class="glass-panel">
                    <h2 class="section-title">Índice Global ({total_pesquisas} Pesquisas)</h2>
                    <div id="gauge-container"></div>
                    <div class="kpi-row">
                        <div class="kpi-mini">
                            <h5>TOP2BOX</h5>
                            <span>{t2b:.2f}%</span>
                        </div>
                        <div class="kpi-mini green">
                            <h5>Meta TSI</h5>
                            <span>{meta:.2f}%</span>
                        </div>
                        <div class="kpi-mini red">
                            <h5>Faltam p/ Meta</h5>
                            {recup_html}
                        </div>
                    </div>
                </div>
                
                <!-- Painel Direito: Análise por Bloco -->
                <div class="glass-panel">
                    <h2 class="section-title">Desempenho por Bloco (Meta vs Realizado TSI)</h2>
                    <div id="bar-container"></div>
                </div>
            </div>

            <!-- Painel Inferior: Métricas Secundárias -->
            <div class="glass-panel" style="margin-top: 10px;">
                <h2 class="section-title">Métricas de Satisfação Secundárias</h2>
                <div class="extras-grid">
                    {cards_extras_html}
                </div>
            </div>
            

            <!-- Painel Lojas -->
            <div class="glass-panel" style="margin-top: 10px;">
                <h2 class="section-title">TSI por Concessionária vs Meta</h2>
                <div id="lojas-container" style="width: 100%; height: 320px;"></div>
            </div>
            

            <!-- Categoria e Consultor Grid -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 10px;">
                <div class="glass-panel">
                    <h2 class="section-title">TSI por Categoria</h2>
                    <div id="categoria-container" style="width: 100%; height: 320px;"></div>
                </div>
                <div class="glass-panel">
                    <h2 class="section-title">TSI por Consultor</h2>
                    <div id="consultor-container" style="width: 100%; height: 320px;"></div>
                </div>
            </div>

            <!-- MURAL DE ALERTAS: A VOZ DO CLIENTE -->
            <div class="glass-panel" style="margin-top: 10px;">
                <h2 class="section-title">Mural de Alertas: A Voz do Cliente (Feedbacks e Justificativas)</h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 15px;">
                    {comentarios_html}
                </div>
            </div>
            
            <script>
                var gaugeDom = document.getElementById('gauge-container');
                var gaugeChart = echarts.init(gaugeDom);
                
                var barDom = document.getElementById('bar-container');
                var barChart = echarts.init(barDom);

                // --- GAUGE CHART (TSI) ---
                var gaugeOption = {{
                    series: [
                        {{
                            type: 'gauge',
                            startAngle: 180,
                            endAngle: 0,
                            min: 0,
                            max: 100,
                            splitNumber: 10,
                            radius: '130%',
                            center: ['50%', '75%'],
                            itemStyle: {{
                                color: '#3b82f6',
                                shadowColor: 'rgba(59, 130, 246, 0.4)',
                                shadowBlur: 10,
                                shadowOffsetX: 2,
                                shadowOffsetY: 2
                            }},
                            progress: {{ show: true, width: 18 }},
                            pointer: {{ icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z', length: '12%', width: 20, offsetCenter: [0, '-60%'], itemStyle: {{ color: 'auto' }} }},
                            axisLine: {{ lineStyle: {{ width: 18 }} }},
                            axisTick: {{ show: false }},
                            splitLine: {{ length: 15, lineStyle: {{ width: 2, color: '#999' }} }},
                            axisLabel: {{ distance: 25, color: '#999', fontSize: 12 }},
                            title: {{ show: true, offsetCenter: [0, '25%'], fontSize: 16, color: '#64748b', fontWeight: 'bold' }},
                            detail: {{
                                valueAnimation: true,
                                fontSize: 34,
                                fontWeight: 'bolder',
                                color: '#1e293b',
                                offsetCenter: [0, '-5%'],
                                formatter: function(value) {{ return value.toFixed(2) + '%'; }}
                            }},
                            data: [{{ value: {tsi}, name: 'Resultado TSI Atual' }}]
                        }},
                        // Ponteiro da Meta
                        {{
                            type: 'gauge',
                            startAngle: 180,
                            endAngle: 0,
                            min: 0,
                            max: 100,
                            radius: '130%',
                            center: ['50%', '75%'],
                            itemStyle: {{ color: '#ef4444' }},
                            progress: {{ show: false }},
                            pointer: {{ show: true, icon: 'triangle', length: '20%', width: 10, offsetCenter: [0, '-50%'] }},
                            axisLine: {{ show: false }},
                            axisTick: {{ show: false }},
                            splitLine: {{ show: false }},
                            axisLabel: {{ show: false }},
                            title: {{ show: false }},
                            detail: {{ show: false }},
                            data: [{{ value: {meta}, name: 'Meta TSI' }}]
                        }}
                    ]
                }};

                // --- BAR/LINE CHART (BLOCOS) ---
                var barOption = {{
                    tooltip: {{
                        trigger: 'axis',
                        axisPointer: {{ type: 'cross', crossStyle: {{ color: '#999' }} }}
                    }},
                    legend: {{ data: ['Realizado TSI', 'Meta TSI'] }},
                    grid: {{ left: '3%', right: '15%', bottom: '5%', containLabel: true }},
                    xAxis: [
                        {{
                            type: 'category',
                            data: {json.dumps(labels_clean)},
                            axisPointer: {{ type: 'shadow' }},
                            axisLabel: {{ fontWeight: '600', color: '#475569', interval: 0 }}
                        }}
                    ],
                    yAxis: [
                        {{
                            type: 'value',
                            name: 'Score %',
                            min: 0,
                            max: 100,
                            axisLabel: {{ formatter: function(value) {{ return value.toFixed(2) + '%'; }} }}
                        }}
                    ],
                    series: [
                        {{
                            name: 'Realizado TSI',
                            type: 'bar',
                            z: 10,
                            barWidth: 35,
                            itemStyle: {{
                                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                                    {{offset: 0, color: '#f59e0b'}},
                                    {{offset: 1, color: '#d97706'}}
                                ]),
                                borderRadius: [6, 6, 0, 0]
                            }},
                            data: {json.dumps(tsi_data)},
                            label: {{ show: true, position: 'top', formatter: function(params) {{ return params.value.toFixed(2) + '%'; }}, fontWeight: 'bold', backgroundColor: '#fff', padding: [2, 4] }},
                            markLine: {{
                                z: 0,
                                data: [
                                    {{ yAxis: {meta}, name: 'Meta TSI' }}
                                ],
                                label: {{ show: true, position: 'end', formatter: function(params) {{ return 'Meta: ' + params.value.toFixed(2) + '%'; }}, fontWeight: 'bold', color: '#ef4444' }},
                                lineStyle: {{ width: 3, type: 'dashed', color: '#ef4444' }},
                                symbol: ['none', 'none']
                            }}
                        }},
                        {{
                            name: 'Meta TSI',
                            type: 'line',
                            itemStyle: {{ color: '#ef4444' }},
                            lineStyle: {{ width: 3, type: 'dashed' }},
                            data: []
                        }}
                    ]
                }};

                gaugeOption && gaugeChart.setOption(gaugeOption);
                barOption && barChart.setOption(barOption);

                // --- LOJAS CHART ---
                var lojasDom = document.getElementById('lojas-container');
                var lojasChart = echarts.init(lojasDom);
                var faltam_arr = {faltam_lojas_json};
                var qtde_arr = {qtde_lojas_json};
                var cores_arr = {cores_lojas_json};
                var tsi_arr = {tsi_lojas_json};
                
                var lojasOption = {{
                    tooltip: {{ 
                        trigger: 'axis', 
                        axisPointer: {{ type: 'shadow' }},
                        formatter: function(params) {{
                            var p = params[0];
                            if (p.seriesName === 'Meta') return p.name + '<br/>Meta: ' + p.value + '%';
                            var q = qtde_arr[p.dataIndex];
                            return '<b>' + p.name + '</b><br/>TSI: <b>' + p.value.toFixed(2) + '%</b><br/>Pesquisas: <b>' + q + '</b>';
                        }}
                    }},
                    legend: {{ data: ['Índice TSI (%)', 'Meta'], bottom: 0 }},
                    grid: {{ left: '3%', right: '4%', bottom: '15%', containLabel: true }},
                    xAxis: {{ type: 'category', data: {labels_lojas_json}, axisLabel: {{ interval: 0, fontWeight: 'bold' }} }},
                    yAxis: {{ type: 'value', max: 115, axisLabel: {{ formatter: '{{value}}%' }} }},
                    series: [
                        {{
                            name: 'Índice TSI (%)',
                            type: 'bar',
                            data: tsi_arr.map(function(val, idx) {{ return {{ value: val, itemStyle: {{ color: cores_arr[idx], borderRadius: [4,4,0,0] }} }}; }}),
                            barMaxWidth: 150,
                            label: {{
                                show: true,
                                position: 'top',
                                formatter: function(params) {{ return Number(params.value).toFixed(2) + '%'; }},
                                color: '#1e293b',
                                fontWeight: 'bold',
                                fontSize: 13
                            }}
                        }},
                        {{
                            name: 'Volume',
                            type: 'bar',
                            barGap: '-100%',
                            data: tsi_arr.map(function(val, idx) {{ return {{ value: val, itemStyle: {{ color: 'transparent' }} }}; }}),
                            barMaxWidth: 150,
                            tooltip: {{ show: false }},
                            label: {{
                                show: true,
                                position: 'inside',
                                align: 'center',
                                verticalAlign: 'middle',
                                formatter: function(params) {{
                                    var f = faltam_arr[params.dataIndex];
                                    var q = qtde_arr[params.dataIndex];
                                    var t = '{{a|' + q + '}}\\n{{b|Qtd Pesquisas}}';
                                    if (f > 0 && f !== 999) {{
                                        t += '\\n{{c|⚠️ Faltam ' + f + ' pesquisas}}';
                                    }}
                                    return t;
                                }},
                                rich: {{
                                    a: {{ color: '#fff', fontSize: 24, fontWeight: 'bold', lineHeight: 28 }},
                                    b: {{ color: 'rgba(255,255,255,0.95)', fontSize: 13, fontWeight: '600', lineHeight: 22 }},
                                    c: {{ color: '#fef3c7', fontSize: 12, fontWeight: 'bold', lineHeight: 20 }}
                                }}
                            }}
                        }},
                        {{
                            name: 'Meta',
                            type: 'line',
                            data: {meta_lojas_json},
                            symbol: 'none',
                            itemStyle: {{ color: '#ef4444' }},
                            lineStyle: {{ type: 'dashed', width: 2 }},
                            label: {{ show: true, position: 'top', formatter: function(params) {{ return Number(params.value).toFixed(2) + '%'; }}, color: '#1e293b', fontWeight: 'bold' }}
                        }}
                    ]
                }};
                lojasChart.setOption(lojasOption);

                // --- CATEGORIA CHART ---
                var catDom = document.getElementById('categoria-container');
                var catChart = null;
                if (catDom) {{
                    catChart = echarts.init(catDom);
                    var qtde_cat_arr = {qtde_cat_json};
                    var cores_cat_arr = {cores_cat_json};
                    var tsi_cat_arr = {tsi_cat_json};
                    var catOption = {{
                        tooltip: {{ 
                            trigger: 'axis', 
                            axisPointer: {{ type: 'shadow' }},
                            formatter: function(params) {{
                                var p = params[0];
                                if (p.seriesName === 'Meta') return p.name + '<br/>Meta: ' + p.value + '%';
                                var q = qtde_cat_arr[p.dataIndex];
                                return '<b>' + p.name + '</b><br/>TSI: <b>' + p.value.toFixed(2) + '%</b><br/>Pesquisas: <b>' + q + '</b>';
                            }}
                        }},
                        legend: {{ data: ['Índice TSI (%)', 'Meta'], bottom: 0 }},
                        grid: {{ left: '3%', right: '4%', bottom: '15%', containLabel: true }},
                        xAxis: {{ type: 'category', data: {labels_cat_json}, axisLabel: {{ interval: 0, fontWeight: 'bold' }} }},
                        yAxis: {{ type: 'value', max: 115, axisLabel: {{ formatter: '{{value}}%' }} }},
                        series: [
                            {{
                                name: 'Índice TSI (%)',
                                type: 'bar',
                                data: tsi_cat_arr.map(function(val, idx) {{ return {{ value: val, itemStyle: {{ color: cores_cat_arr[idx], borderRadius: [4,4,0,0] }} }}; }}),
                                barMaxWidth: 80,
                                label: {{
                                    show: true,
                                    position: 'inside',
                                    align: 'center',
                                    verticalAlign: 'middle',
                                    formatter: function(params) {{
                                        var val = params.value;
                                        var q = qtde_cat_arr[params.dataIndex];
                                        return '{{a|' + val.toFixed(2) + '%}}\\n{{b|Qtd. ' + q + '}}';
                                    }},
                                    rich: {{
                                        a: {{ color: '#fff', fontSize: 16, fontWeight: 'bold', lineHeight: 20 }},
                                        b: {{ color: 'rgba(255,255,255,0.9)', fontSize: 10, fontWeight: '500' }}
                                    }}
                                }}
                            }},
                            {{
                                name: 'Meta',
                                type: 'line',
                                data: {meta_cat_json},
                                symbol: 'none',
                                itemStyle: {{ color: '#ef4444' }},
                                lineStyle: {{ type: 'dashed', width: 2 }},
                                label: {{ show: true, position: 'top', formatter: function(params) {{ return Number(params.value).toFixed(2) + '%'; }}, color: '#1e293b', fontWeight: 'bold' }}
                            }}
                        ]
                    }};
                    catChart.setOption(catOption);
                }}

                // --- CONSULTOR CHART ---
                var consDom = document.getElementById('consultor-container');
                var consChart = null;
                if (consDom) {{
                    consChart = echarts.init(consDom);
                    var qtde_cons_arr = {qtde_cons_json};
                    var cores_cons_arr = {cores_cons_json};
                    var tsi_cons_arr = {tsi_cons_json};
                    var consOption = {{
                        tooltip: {{ 
                            trigger: 'axis', 
                            axisPointer: {{ type: 'shadow' }},
                            formatter: function(params) {{
                                var p = params[0];
                                if (p.seriesName === 'Meta') return p.name + '<br/>Meta: ' + p.value + '%';
                                var q = qtde_cons_arr[p.dataIndex];
                                return '<b>' + p.name + '</b><br/>TSI: <b>' + p.value.toFixed(2) + '%</b><br/>Pesquisas: <b>' + q + '</b>';
                            }}
                        }},
                        legend: {{ data: ['Índice TSI (%)', 'Meta'], bottom: 0 }},
                        grid: {{ left: '3%', right: '4%', bottom: '20%', containLabel: true }},
                        xAxis: {{ type: 'category', data: {labels_cons_json}, axisLabel: {{ interval: 0, fontWeight: 'bold', rotate: 30, width: 80, overflow: 'truncate', fontSize: 11 }} }},
                        yAxis: {{ type: 'value', max: 115, axisLabel: {{ formatter: '{{value}}%' }} }},
                        series: [
                            {{
                                name: 'Índice TSI (%)',
                                type: 'bar',
                                data: tsi_cons_arr.map(function(val, idx) {{ return {{ value: val, itemStyle: {{ color: cores_cons_arr[idx], borderRadius: [4,4,0,0] }} }}; }}),
                                barMaxWidth: 80,
                                label: {{
                                    show: true,
                                    position: 'inside',
                                    align: 'center',
                                    verticalAlign: 'middle',
                                    formatter: function(params) {{
                                        var val = params.value;
                                        var q = qtde_cons_arr[params.dataIndex];
                                        return '{{a|' + val.toFixed(2) + '%}}\\n{{b|Qtd. ' + q + '}}';
                                    }},
                                    rich: {{
                                        a: {{ color: '#fff', fontSize: 14, fontWeight: 'bold', lineHeight: 18 }},
                                        b: {{ color: 'rgba(255,255,255,0.9)', fontSize: 9, fontWeight: '500' }}
                                    }}
                                }}
                            }},
                            {{
                                name: 'Meta',
                                type: 'line',
                                data: {meta_cons_json},
                                symbol: 'none',
                                itemStyle: {{ color: '#ef4444' }},
                                lineStyle: {{ type: 'dashed', width: 2 }},
                                label: {{ show: true, position: 'top', formatter: function(params) {{ return Number(params.value).toFixed(2) + '%'; }}, color: '#1e293b', fontWeight: 'bold' }}
                            }}
                        ]
                    }};
                    consChart.setOption(consOption);
                }}


                
                // --- HISTORY CHART ---
                var histDom = document.getElementById('history-container');
                var histChart = null;
                if (histDom) {{
                    histChart = echarts.init(histDom);
                    var historicoSeries = {historico_series_json};
                    var histOption = {{
                        tooltip: {{
                            trigger: 'axis',
                            axisPointer: {{ type: 'cross', crossStyle: {{ color: '#999' }} }}
                        }},
                        legend: {{ data: ['Volume de Pesquisas', 'TSI (%)', 'Top2Box (%)'] }},
                        grid: {{ left: '3%', right: '4%', bottom: '5%', containLabel: true }},
                        xAxis: [
                            {{
                                type: 'category',
                                data: {json.dumps(self.meses_historico)},
                                axisPointer: {{ type: 'shadow' }}
                            }}
                        ],
                        yAxis: [
                            {{
                                type: 'value',
                                name: 'Volume',
                                min: 0,
                                axisLabel: {{ formatter: '{{value}}' }}
                            }},
                            {{
                                type: 'value',
                                name: 'Scores (%)',
                                min: 0,
                                max: 100,
                                axisLabel: {{ formatter: '{{value}}%' }}
                            }}
                        ],
                        series: [
                            {{
                                name: 'Volume de Pesquisas',
                                type: 'bar',
                                itemStyle: {{ color: '#10B981', borderRadius: [4, 4, 0, 0] }},
                                data: {json.dumps(self.respostas_historico)},
                                label: {{ show: true, position: 'inside', formatter: '{{c}}', fontWeight: 'bold', color: '#ffffff' }}
                            }},
                            {{
                                name: 'Top2Box (%)',
                                type: 'line',
                                yAxisIndex: 1,
                                itemStyle: {{ color: '#3B82F6' }},
                                lineStyle: {{ width: 3, type: 'dashed' }},
                                data: {json.dumps(self.t2b_historico)},
                                label: {{ show: true, position: 'bottom', formatter: function(p) {{ return p.value == null ? '' : Number(p.value).toFixed(2) + '%'; }}, fontWeight: 'bold' }}
                            }},
                            {{
                                name: 'TSI (%)',
                                type: 'line',
                                yAxisIndex: 1,
                                itemStyle: {{ color: '#F59E0B' }},
                                lineStyle: {{ width: 3 }},
                                data: {json.dumps(self.tsi_historico)},
                                label: {{ show: true, position: 'top', formatter: function(p) {{ return p.value == null ? '' : Number(p.value).toFixed(2) + '%'; }}, fontWeight: 'bold' }}
                            }}
                        ]
                    }};
                    histOption && histChart.setOption(histOption);
                    document.querySelectorAll('.pillar-btn').forEach(function(btn) {{
                        btn.addEventListener('click', function() {{
                            document.querySelectorAll('.pillar-btn').forEach(function(item) {{ item.classList.remove('active'); }});
                            btn.classList.add('active');
                            var nome = btn.getAttribute('data-pillar');
                            var serie = historicoSeries[nome];
                            histChart.setOption({{
                                legend: {{ data: ['Volume de Pesquisas', nome + ' (%)', 'Top2Box (%)'] }},
                                series: [
                                    {{ name: 'Volume de Pesquisas', data: serie.quantidades }},
                                    {{ name: 'Top2Box (%)', data: serie.top2box }},
                                    {{ name: nome + ' (%)', data: serie.indices }}
                                ]
                            }});
                        }});
                    }});
                }}

                window.addEventListener('resize', function() {{ 
                    if(gaugeChart) gaugeChart.resize();
                    lojasChart.resize();
                    if(catChart) catChart.resize();
                    if(consChart) consChart.resize(); 
                    if(barChart) barChart.resize();
                    if(histChart) histChart.resize();
                }});
            </script>
        </body>
        </html>
        """
        return html

    def exportar_pdf_executivo(self):
        if self.df_base.empty:
            QMessageBox.warning(self, "Aviso", "Não há dados no banco TSI para gerar o relatório.")
            return

        loja_nome = self.cb_loja.currentText()
        mes_ref = self.cb_mes.currentText()
        default_filename = f"Relatorio_Executivo_TSI_{mes_ref.replace('/', '-')}.pdf"
        filepath, _ = QFileDialog.getSaveFileName(self, "Salvar Relatório Executivo - Pós-Vendas (TSI)", default_filename, "PDF Files (*.pdf)")
        
        if not filepath:
            return

        # Filtrar DataFrame
        df = self.df_base.copy()
        if loja_nome != "Todas" and 'Loja_Nome' in df.columns:
            df = df[df['Loja_Nome'] == loja_nome]
        if self.cb_consultor.currentText() != "Todos" and 'Consultor_Nome' in df.columns:
            df = df[df['Consultor_Nome'] == self.cb_consultor.currentText()]
        if mes_ref != "Todos" and 'Mes' in df.columns:
            df = df[df['Mes'] == mes_ref]
        if self.cb_categoria.currentText() != "Todas" and 'Categoria Produto' in df.columns:
            df = df[df['Categoria Produto'] == self.cb_categoria.currentText()]

        total_respostas = len(df)
        if total_respostas == 0:
            QMessageBox.warning(self, "Aviso", "Nenhum dado encontrado para os filtros selecionados.")
            return

        # NPS
        col_nps = 'Recomendaria dealer amigo e família'
        promotores = neutros = detratores = 0
        if col_nps in df.columns:
            s_nps = df[col_nps].dropna()
            promotores = int((s_nps >= 9).sum())
            neutros = int(((s_nps >= 7) & (s_nps <= 8)).sum())
            detratores = int((s_nps <= 6).sum())
            nps_val = ((promotores - detratores) / len(s_nps) * 100) if len(s_nps) > 0 else 0.0
        else:
            nps_val = 0.0

        col_geral = 'Avaliação satisfação geral'
        top2box_val = (df[col_geral] >= 9).sum() / len(df[col_geral].dropna()) * 100 if col_geral in df.columns and len(df[col_geral].dropna()) > 0 else 0.0

        dimensoes = {}
        dim_map = {
            'Agendamento': 'Avaliação satisfação agendamento',
            'Recepção': 'Avaliação satisfação recepção',
            'Instalações & Infra': 'Avaliação satisfação instalações e infra',
            'Consultor Técnico': 'Avaliação satisfação consultor',
            'Qualidade do Serviço': 'Avaliação satisfação qualidade',
            'Entrega do Veículo': 'Avaliação satisfação entrega',
            'Custo/Benefício': 'Avaliação satisfação custo benefício'
        }
        for label, col in dim_map.items():
            if col in df.columns:
                s = df[col].dropna()
                dimensoes[label] = (s >= 9).sum() / len(s) * 100 if len(s) > 0 else 0.0

        ranking = []
        if 'Consultor_Nome' in df.columns:
            for cons_nome, group in df.groupby('Consultor_Nome'):
                if cons_nome in ['Desconhecido', '', 'nan']: continue
                c_total = len(group)
                if col_nps in group.columns:
                    c_s = group[col_nps].dropna()
                    c_p = (c_s >= 9).sum()
                    c_d = (c_s <= 6).sum()
                    c_nps = ((c_p - c_d) / len(c_s) * 100) if len(c_s) > 0 else 0.0
                else:
                    c_nps = 0.0
                if col_geral in group.columns:
                    c_g = group[col_geral].dropna()
                    c_top = (c_g >= 9).sum() / len(c_g) * 100 if len(c_g) > 0 else 0.0
                else:
                    c_top = 0.0
                ranking.append({'nome': cons_nome, 'respostas': c_total, 'nps': c_nps, 'media': c_top})
            ranking.sort(key=lambda x: x['respostas'], reverse=True)

        detratores_list = []
        if col_nps in df.columns:
            df_det = df[df[col_nps] <= 6]
            col_cli_candidates = [c for c in df.columns if str(c).strip().lower() in ['cliente', 'nome do cliente', 'nome cliente']]
            if col_cli_candidates:
                col_cli = col_cli_candidates[0]
            else:
                col_cli = next((c for c in df.columns if any(k in c.lower() for k in ['cliente', 'nome']) and 'consultor' not in c.lower() and 'loja' not in c.lower() and not any(x in c.lower() for x in ['contat', 'após', 'apos', 'dealer', 'serviço', 'servico', 'pesquisa', 'origem', 'resposta', 'tipo', 'sexo', 'categoria', 'segmento', '?', 'coment', 'atendido'])), None)
            col_fone = next((c for c in df.columns if any(k in c.lower() for k in ['telefone', 'fone', 'celular', 'contato'])), None)
            col_os_name = next((c for c in df.columns if 'ordens de servi' in c.lower() or c.lower() == 'os'), 'Ordens de Serviço: OS')
            leads_map = self.engine.db_manager.get_leads_mapping() if hasattr(self.engine, 'db_manager') else {}

            for _, r in df_det.iterrows():
                os_raw = str(r.get(col_os_name, ''))
                os_num = os_raw.split('-')[-1].strip() if '-' in os_raw else os_raw.strip()
                if not os_num or os_num == 'nan': os_num = "-"
                
                nome_cli = ""
                if col_cli and pd.notna(r.get(col_cli)):
                    nome_cli = str(r.get(col_cli)).strip()
                
                lead_info = None
                if leads_map:
                    chaves_busca = [
                        os_raw,
                        os_num,
                        os_num.lstrip('0') if os_num != '-' else '',
                        str(r.get('id', '')).strip()
                    ]
                    for k in chaves_busca:
                        if k and k not in ['-', 'Sem OS', 'Sem Posse', '', 'nan', 'None'] and k in leads_map:
                            lead_info = leads_map[k]
                            break

                if lead_info:
                    nome_cruzado = str(lead_info.get('cliente', '')).strip()
                    if nome_cruzado and nome_cruzado.upper() not in ['N/D', 'NONE', 'S/N', 'N/A', '-', '']:
                        if not nome_cli or nome_cli.lower() in ['nan', 'none', '-', '', 'sim', 'não', 'nao', 'n/d', 's/n'] or nome_cli.startswith("Cliente (OS") or nome_cli == "Cliente Auditado":
                            nome_cli = nome_cruzado

                if not nome_cli or nome_cli.lower() in ['nan', 'none', '']:
                    nome_cli = f"Cliente (OS #{os_num})" if os_num != "-" else "Cliente Auditado"

                fone_cli = ""
                if col_fone and pd.notna(r.get(col_fone)):
                    fone_cli = str(r.get(col_fone)).strip()
                if fone_cli.lower() in ['nan', 'none', 's/n']:
                    fone_cli = ""
                    
                if not fone_cli and lead_info:
                    fone_cruzado = str(lead_info.get('telefone', '')).strip()
                    if fone_cruzado and fone_cruzado.lower() not in ['nan', 'none', 's/n', 'n/d', '-', '']:
                        fone_cli = fone_cruzado

                data_r = str(r.get('Data de Resposta', '-'))
                nota_r = int(r.get(col_nps, 0)) if pd.notna(r.get(col_nps)) else 0
                motivo_r = str(r.get('Motivo satisfação geral', '')) or str(r.get('Motivo insatisfação consultor', '')) or str(r.get('Motivo insatisfação qualidade', '')) or str(r.get('Comentário conclusão final', 'Insatisfação registrada'))
                
                detratores_list.append({
                    'data': data_r,
                    'cliente': nome_cli,
                    'telefone': fone_cli,
                    'os': os_num,
                    'nota': nota_r,
                    'motivo': motivo_r[:110]
                })

        metrics = {
            'nps': nps_val,
            'top2box': top2box_val,
            'total_respostas': total_respostas,
            'promotores_count': promotores,
            'neutros_count': neutros,
            'detratores_count': detratores,
            'promotores_pct': (promotores / total_respostas * 100) if total_respostas > 0 else 0.0,
            'neutros_pct': (neutros / total_respostas * 100) if total_respostas > 0 else 0.0,
            'detratores_pct': (detratores / total_respostas * 100) if total_respostas > 0 else 0.0,
            'saas_taxa_resp': 68.5,
            'dimensoes': dimensoes
        }

        sucesso = PDFReportGenerator.generate_tsi_report(filepath, loja_nome, mes_ref, metrics, ranking, detratores_list)
        if sucesso:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Relatório Gerado com Sucesso")
            msg_box.setText("O Relatório Executivo de Pós-Vendas (TSI) foi gerado com sucesso!")
            msg_box.setInformativeText(f"Arquivo salvo em:\n{filepath}\n\nDeseja abrir o arquivo agora?")
            btn_abrir = msg_box.addButton("Abrir PDF", QMessageBox.ButtonRole.AcceptRole)
            btn_ok = msg_box.addButton("Fechar", QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()

            if msg_box.clickedButton() == btn_abrir:
                QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))
        else:
            QMessageBox.critical(self, "Erro", "Não foi possível gerar o arquivo PDF.")

