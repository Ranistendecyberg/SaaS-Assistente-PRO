import os
import json
import re
from datetime import datetime
import pandas as pd
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QPushButton, QFrame, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, QUrl, QEventLoop
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWebEngineWidgets import QWebEngineView
from src.core.database import DatabaseManager
from src.core.dashboard_engine import DashboardEngine
from src.core.pdf_report_generator import PDFReportGenerator
from src.core.paths import get_base_dir
from src.core.ssi_metrics import (
    calculate_percentage as calculate_ssi_percentage,
    format_model_year,
    raw_column as ssi_raw_column,
    recommendation_summary,
)

class DashboardComparativoScreen(QWidget):
    """
    Tela do Relatório Gerencial Geral.
    Segregação 100% rigorosa entre Pós-Vendas (TSI) e Comercial/Vendas (SSI).
    Permite visualizar os KPIs de conversão do WhatsApp vs canais tradicionais e exportar PDF Executivo.
    """
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.engine_tsi = DashboardEngine()
        self.df_tsi = pd.DataFrame()
        self.df_ssi = pd.DataFrame()
        self.sent_surveys = set()
        self.setup_ui()

    @staticmethod
    def _classificar_recomendacao(valor):
        """Classifica somente notas válidas de 0 a 10; ausência não é detrator."""
        try:
            if valor is None or pd.isna(valor):
                return "SEM_NOTA", None
            nota = float(str(valor).strip().replace(',', '.'))
            if nota < 0 or nota > 10:
                return "SEM_NOTA", None
        except (TypeError, ValueError):
            return "SEM_NOTA", None

        nota_exibida = int(round(nota))
        if nota >= 9:
            return "PROMOTOR", nota_exibida
        if nota >= 7:
            return "NEUTRO", nota_exibida
        return "DETRATOR", nota_exibida

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(10)

        # Cabeçalho da Tela
        header_frame = QFrame()
        header_frame.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        vbox_title = QVBoxLayout()
        vbox_title.setSpacing(2)
        lbl_titulo = QLabel("📊 Relatório Gerencial Geral")
        lbl_titulo.setStyleSheet("font-size: 18px; font-weight: 800; color: #0F172A; border: none;")
        lbl_sub = QLabel("Mensure o retorno dos envios via WhatsApp em relação aos canais tradicionais da montadora.")
        lbl_sub.setStyleSheet("font-size: 11px; color: #64748B; border: none;")
        vbox_title.addWidget(lbl_titulo)
        vbox_title.addWidget(lbl_sub)
        header_layout.addLayout(vbox_title)

        header_layout.addStretch()

        # Botão de Exportação em PDF
        self.btn_export_pdf = QPushButton("📄 Gerar Relatório Executivo (PDF)")
        self.btn_export_pdf.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 11px;
                padding: 8px 14px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #B91C1C;
            }
        """)
        self.btn_export_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export_pdf.clicked.connect(self.exportar_pdf_executivo)
        header_layout.addWidget(self.btn_export_pdf)

        layout.addWidget(header_frame)

        # Painel de Filtros
        filtros_frame = QFrame()
        filtros_frame.setObjectName("filtros_frame")
        filtros_frame.setStyleSheet("""
            #filtros_frame {
                background-color: #FFFFFF; 
                border: 1px solid #CBD5E1; 
                border-radius: 8px;
            }
            #filtros_frame QLabel {
                border: none;
                background: transparent;
                font-weight: bold; 
                color: #475569; 
                font-size: 11px;
            }
        """)
        filtros_layout = QHBoxLayout(filtros_frame)
        filtros_layout.setContentsMargins(12, 8, 12, 8)
        filtros_layout.setSpacing(12)

        combo_style = """
            QComboBox {
                background-color: #F8FAFC; 
                border: 1px solid #CBD5E1; 
                border-radius: 5px; 
                padding-left: 8px; 
                padding-right: 8px;
                padding-top: 4px;
                padding-bottom: 4px;
                color: #1E293B; 
                font-weight: bold;
                font-size: 12px;
                min-width: 130px;
                max-width: 150px;
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
        """

        # 1. Departamento (TSI vs SSI)
        v_dep = QVBoxLayout()
        v_dep.setSpacing(2)
        lbl_dep = QLabel("Departamento:")
        self.combo_dept = QComboBox()
        self.combo_dept.setStyleSheet(combo_style)
        self.combo_dept.addItem("🔧 Pós-Vendas (TSI)")
        self.combo_dept.addItem("🛵 Vendas (SSI)")
        self.combo_dept.currentIndexChanged.connect(self.ao_mudar_departamento)
        v_dep.addWidget(lbl_dep)
        v_dep.addWidget(self.combo_dept)
        filtros_layout.addLayout(v_dep)

        # 2. Concessionária / Loja
        v_loja = QVBoxLayout()
        v_loja.setSpacing(2)
        lbl_loja = QLabel("Concessionária:")
        self.combo_loja = QComboBox()
        self.combo_loja.setStyleSheet(combo_style.replace("min-width: 130px;", "min-width: 170px;").replace("max-width: 150px;", "max-width: 220px;"))
        self.combo_loja.addItem("Todas as Unidades")
        self.combo_loja.currentTextChanged.connect(self.ao_mudar_loja_ou_mes)
        v_loja.addWidget(lbl_loja)
        v_loja.addWidget(self.combo_loja)
        filtros_layout.addLayout(v_loja)

        # 3. Mês de Referência
        v_mes = QVBoxLayout()
        v_mes.setSpacing(2)
        lbl_mes = QLabel("Mês:")
        self.combo_mes = QComboBox()
        self.combo_mes.setStyleSheet(combo_style.replace("min-width: 130px;", "min-width: 100px;").replace("max-width: 150px;", "max-width: 120px;"))
        self.combo_mes.addItem("Todos")
        self.combo_mes.currentTextChanged.connect(self.ao_mudar_loja_ou_mes)
        v_mes.addWidget(lbl_mes)
        v_mes.addWidget(self.combo_mes)
        filtros_layout.addLayout(v_mes)

        # 4. Consultor / Vendedor
        v_cons = QVBoxLayout()
        v_cons.setSpacing(2)
        lbl_cons = QLabel("Consultor/Vendedor:")
        self.combo_consultor = QComboBox()
        self.combo_consultor.setStyleSheet(combo_style.replace("min-width: 130px;", "min-width: 150px;").replace("max-width: 150px;", "max-width: 200px;"))
        self.combo_consultor.addItem("Todos")
        self.combo_consultor.currentTextChanged.connect(self.atualizar_dashboard)
        v_cons.addWidget(lbl_cons)
        v_cons.addWidget(self.combo_consultor)
        filtros_layout.addLayout(v_cons)

        filtros_layout.addStretch()

        btn_atualizar = QPushButton("🔄 Atualizar")
        btn_atualizar.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-weight: bold;
                font-size: 11px;
                padding: 7px 12px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        btn_atualizar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_atualizar.clicked.connect(self.carregar_dados)
        filtros_layout.addWidget(btn_atualizar)

        layout.addWidget(filtros_frame)

        # Visualização Web / Gráficos Interativos
        self.web_view = QWebEngineView()
        self.web_view.setStyleSheet("background-color: transparent; border: 1px solid #CBD5E1; border-radius: 8px;")
        layout.addWidget(self.web_view, stretch=1)

    def showEvent(self, event):
        super().showEvent(event)
        self.carregar_dados()

    def ao_mudar_departamento(self):
        self.popular_filtros()
        self.atualizar_dashboard()

    def ao_mudar_loja_ou_mes(self, _valor=None):
        """No SSI, mantém a lista de vendedores sincronizada com loja e mês."""
        if self.combo_dept.currentIndex() == 1:
            self._atualizar_opcoes_consultor(self._recortar_consultores_ssi())
        self.atualizar_dashboard()

    def carregar_dados(self):
        self.df_tsi = self.engine_tsi.load_data()
        self.records_ssi = self.db.load_ssi_records()
        self.df_ssi = pd.DataFrame(self.records_ssi) if self.records_ssi else pd.DataFrame()
        self.sent_surveys = self.db.load_sent_surveys()

        # Identificação e Mapeamento robusto da Concessionária/Loja no SSI:
        if not self.df_ssi.empty:
            col_cod = next((c for c in self.df_ssi.columns if ('concession' in c.lower() or 'dealer' in c.lower() or 'loja' in c.lower()) and any(k in c.lower() for k in ['cod', 'dico', 'num', 'mero', 'vendas']) and 'regi' not in c.lower() and 'macro' not in c.lower()), None)
            if not col_cod:
                col_cod = next((c for c in self.df_ssi.columns if 'concession' in c.lower() and 'vendas' in c.lower() and 'regi' not in c.lower() and 'macro' not in c.lower()), None)
            
            if col_cod and col_cod in self.df_ssi.columns:
                self.df_ssi['Loja'] = self.df_ssi[col_cod].astype(str).str.strip()
            else:
                col_conta_nome = next((c for c in self.df_ssi.columns if 'nome da conta' in c.lower()), None)
                col_conta_num = next((c for c in self.df_ssi.columns if 'número da conta' in c.lower() or 'numero da conta' in c.lower()), None)
                if col_conta_nome and col_conta_nome in self.df_ssi.columns:
                    self.df_ssi['Loja'] = self.df_ssi[col_conta_nome].astype(str).str.strip()
                elif col_conta_num and col_conta_num in self.df_ssi.columns:
                    self.df_ssi['Loja'] = self.df_ssi[col_conta_num].astype(str).str.strip()
                elif 'Loja' not in self.df_ssi.columns:
                    self.df_ssi['Loja'] = "Desconhecida"

            # Fallbacks para lojas nulas ou 'Desconhecida'
            mask_invalida = self.df_ssi['Loja'].isna() | self.df_ssi['Loja'].astype(str).str.lower().isin(['', 'nan', 'none', '<na>', 'desconhecida', 'desconhecido', '-'])
            if mask_invalida.any():
                for fallback_col in [c for c in self.df_ssi.columns if ('concession' in c.lower() or 'dealer' in c.lower()) and 'regi' not in c.lower() and 'macro' not in c.lower()]:
                    if fallback_col == 'Loja' or fallback_col == col_cod: continue
                    vals = self.df_ssi[fallback_col].astype(str).str.strip()
                    mask_fallback_valida = ~vals.str.lower().isin(['', 'nan', 'none', '<na>', 'desconhecida', 'desconhecido', '-'])
                    mask_para_atualizar = mask_invalida & mask_fallback_valida
                    if mask_para_atualizar.any():
                        self.df_ssi.loc[mask_para_atualizar, 'Loja'] = vals[mask_para_atualizar]
                        mask_invalida = self.df_ssi['Loja'].isna() | self.df_ssi['Loja'].astype(str).str.lower().isin(['', 'nan', 'none', '<na>', 'desconhecida', 'desconhecido', '-'])

            config_path = os.path.join(get_base_dir(), "app_data", "config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                    lojas_map = {}
                    for loja in config.get("lojas", []):
                        codigo = str(loja.get("codigo", "")).strip() or str(loja.get("cnpj", "")).strip()
                        nome = loja.get("nome", codigo)
                        if codigo and nome: lojas_map[codigo] = nome
                    if 'Loja' in self.df_ssi.columns and lojas_map:
                        self.df_ssi['Loja'] = self.df_ssi['Loja'].apply(lambda x: lojas_map.get(str(x).strip(), str(x).strip()))
                        
                except Exception as e:
                    print(f"[Comparativo] Erro ao mapear lojas SSI: {e}")
                    
            self.df_ssi = self.engine_tsi.enriquecer_consultores(self.df_ssi)

        self.popular_filtros()
        self.atualizar_dashboard()

    def _atualizar_opcoes_consultor(self, df):
        if 'Consultor_Nome' not in df.columns: return
        
        cons_ativos = sorted([str(x).strip() for x in df['Consultor_Nome'].dropna().unique() 
                              if str(x).strip() and str(x).strip().lower() not in
                              ['nan', 'none', 'não identificado', 'nao identificado', 'desconhecido']])
        
        curr_sel = getattr(self, "combo_consultor", None)
        if not curr_sel: return
        
        sel_text = curr_sel.currentText()
        
        curr_sel.blockSignals(True)
        curr_sel.clear()
        curr_sel.addItem("Todos")
        if cons_ativos:
            curr_sel.addItems(cons_ativos)
            
        if sel_text in cons_ativos:
            curr_sel.setCurrentText(sel_text)
        else:
            curr_sel.setCurrentIndex(0)
            
        curr_sel.blockSignals(False)

    def _recortar_consultores_ssi(self):
        """Aplica à lista de vendedores os mesmos filtros de loja e mês do SSI."""
        if self.df_ssi.empty:
            return self.df_ssi

        df = self.df_ssi.copy()
        loja_sel = self.combo_loja.currentText()
        mes_sel = self.combo_mes.currentText()

        col_loja = 'Loja' if 'Loja' in df.columns else next(
            (c for c in df.columns if 'concession' in c.lower() or 'conta' in c.lower()),
            None
        )
        if loja_sel != "Todas as Unidades" and col_loja:
            df = df[df[col_loja].astype(str) == loja_sel]

        col_data = (
            'Data de resposta SSI 2W'
            if 'Data de resposta SSI 2W' in df.columns
            else (
                'Data de Resposta'
                if 'Data de Resposta' in df.columns
                else next(
                    (c for c in df.columns if 'data' in str(c).lower() and 'resposta' in str(c).lower()),
                    None
                )
            )
        )
        if not col_data:
            col_data = next(
                (
                    c for c in df.columns
                    if 'data' in str(c).lower()
                    and 'envio' not in str(c).lower()
                    and 'ssi' in str(c).lower()
                ),
                None
            )

        if mes_sel != "Todos" and col_data:
            try:
                p_mes, p_ano = mes_sel.split('/')
                pattern = f"(?:{p_mes}/{p_ano}|{p_ano}-{p_mes})"
                df = df[df[col_data].astype(str).str.contains(pattern, regex=True)]
            except Exception:
                df = df[df[col_data].astype(str).str.contains(mes_sel, regex=False)]

        return df

    def popular_filtros(self):
        dept_idx = self.combo_dept.currentIndex()
        loja_atual = self.combo_loja.currentText()
        mes_atual = self.combo_mes.currentText()
        consultor_atual = self.combo_consultor.currentText()

        self.combo_loja.blockSignals(True)
        self.combo_mes.blockSignals(True)
        self.combo_consultor.blockSignals(True)
        self.combo_loja.clear()
        self.combo_mes.clear()
        self.combo_consultor.clear()

        self.combo_loja.addItem("Todas as Unidades")
        self.combo_mes.addItem("Todos")
        self.combo_consultor.addItem("Todos")
        
        def sort_mes(m):
            if str(m) == "Desconhecido" or not str(m).strip(): return (9999, 99)
            try:
                partes = str(m).split('/')
                return (int(partes[1]), int(partes[0]))
            except:
                return (9999, 99)

        meses = []

        if dept_idx == 0: # TSI
            if not self.df_tsi.empty:
                if 'Loja_Nome' in self.df_tsi.columns:
                    lojas = sorted([str(x).strip() for x in self.df_tsi['Loja_Nome'].dropna().unique() 
                                    if str(x).strip() and str(x).strip().lower() not in ['nan', 'none', 'desconhecida', 'desconhecido']])
                    self.combo_loja.addItems(lojas)

                col_mes_tsi = 'Mes' if 'Mes' in self.df_tsi.columns else ('Mes_Ano' if 'Mes_Ano' in self.df_tsi.columns else None)
                if col_mes_tsi:
                    meses_unicos = [str(x).strip() for x in self.df_tsi[col_mes_tsi].dropna().unique() 
                                    if str(x).strip() and str(x).strip().lower() not in ['nan', 'none', 'desconhecido']]
                    meses = sorted(meses_unicos, key=sort_mes, reverse=True)
                    self.combo_mes.addItems(meses)
                    
                self._atualizar_opcoes_consultor(self.df_tsi)
                    
        else: # SSI
            if not self.df_ssi.empty:
                col_loja = 'Loja' if 'Loja' in self.df_ssi.columns else next((c for c in self.df_ssi.columns if 'concession' in c.lower() or 'conta' in c.lower()), None)
                if col_loja:
                    lojas = sorted([str(x).strip() for x in self.df_ssi[col_loja].dropna().unique() 
                                    if str(x).strip() and str(x).strip().lower() not in ['nan', 'none', 'desconhecida', 'desconhecido', '<na>']])
                    self.combo_loja.addItems(lojas)
                
                col_data = 'Data de resposta SSI 2W' if 'Data de resposta SSI 2W' in self.df_ssi.columns else ('Data de Resposta' if 'Data de Resposta' in self.df_ssi.columns else next((c for c in self.df_ssi.columns if 'data' in str(c).lower() and 'resposta' in str(c).lower()), None))
                if not col_data:
                    col_data = next((c for c in self.df_ssi.columns if 'data' in str(c).lower() and 'envio' not in str(c).lower() and 'ssi' in str(c).lower()), None)
                if col_data:
                    import re
                    meses_set = set()
                    for val in self.df_ssi[col_data].dropna():
                        v_str = str(val).strip()
                        if not v_str or v_str.lower() in ['nan', 'none']: continue
                        m = re.search(r'\d{2}/(\d{2})/(\d{4})', v_str)
                        if m:
                            meses_set.add(f"{m.group(1)}/{m.group(2)}")
                        else:
                            m2 = re.search(r'(\d{4})-(\d{2})-\d{2}', v_str)
                            if m2:
                                meses_set.add(f"{m2.group(2)}/{m2.group(1)}")
                            else:
                                m3 = re.search(r'(\d{2}/\d{4})', v_str)
                                if m3:
                                    meses_set.add(m3.group(1))
                    meses = sorted(list(meses_set), key=sort_mes, reverse=True)
                    self.combo_mes.addItems(meses)
                    
        if consultor_atual and self.combo_consultor.findText(consultor_atual) != -1:
            self.combo_consultor.setCurrentText(consultor_atual)

        # Selecionar Loja anterior se existir
        if loja_atual and self.combo_loja.findText(loja_atual) != -1:
            self.combo_loja.setCurrentText(loja_atual)
        else:
            self.combo_loja.setCurrentIndex(0)

        # Seleção automática: Mês Atual ou mais recente
        cur_mes_ano = datetime.now().strftime("%m/%Y")
        idx_cur = self.combo_mes.findText(cur_mes_ano)
        if idx_cur != -1:
            self.combo_mes.setCurrentIndex(idx_cur)
        elif mes_atual and self.combo_mes.findText(mes_atual) != -1:
            self.combo_mes.setCurrentText(mes_atual)
        elif self.combo_mes.count() > 1:
            # Seleciona o mês mais recente disponível
            self.combo_mes.setCurrentIndex(1)
        else:
            self.combo_mes.setCurrentIndex(0)

        # No SSI, a lista deve refletir a combinação final de loja e mês.
        if dept_idx == 1:
            self._atualizar_opcoes_consultor(self._recortar_consultores_ssi())

        self.combo_loja.blockSignals(False)
        self.combo_mes.blockSignals(False)
        self.combo_consultor.blockSignals(False)

    def _calcular_participacao_whatsapp(self, df, tipo):
        """
        Calcula, dentro do recorte já filtrado, quantas respostas podem ser
        vinculadas a pesquisas disparadas pelo aplicativo.

        O cruzamento aceita ID Salesforce direto e as chaves OS/Posse/Chassi do
        leads_map. Assim o filtro de consultor/vendedor nunca usa o total global
        de envios de outra pessoa ou departamento.
        """
        if df is None or df.empty or not self.sent_surveys:
            return 0, 0.0

        leads_map = self.db.get_leads_mapping()
        colunas_chave = [
            c for c in df.columns
            if any(termo in str(c).lower() for termo in (
                'ordens de servi', 'relação de posse', 'relacao de posse',
                'chassi', 'ação', 'acao', 'url'
            ))
        ]
        enviados_identificados = 0

        for _, row in df.iterrows():
            candidatos = set()
            for coluna in colunas_chave:
                valor = str(row.get(coluna, '') or '').strip()
                if not valor or valor.lower() in ('nan', 'none', '-'):
                    continue
                candidatos.add(valor)
                match_id = re.search(r'([a-zA-Z0-9]{15,18})', valor)
                if match_id:
                    candidatos.add(match_id.group(1))
                if '-' in valor:
                    candidatos.update(parte.strip() for parte in valor.split('-') if parte.strip())

            vinculado = any(chave in self.sent_surveys for chave in candidatos)
            if not vinculado:
                for chave in candidatos:
                    lead = leads_map.get(chave, {})
                    if str(lead.get('tipo', '')).upper() != tipo.upper():
                        continue
                    if str(lead.get('id', '')).strip() in self.sent_surveys:
                        vinculado = True
                        break
            if vinculado:
                enviados_identificados += 1

        percentual = enviados_identificados / len(df) * 100 if len(df) else 0.0
        return enviados_identificados, percentual

    def _calcular_metricas_tsi(self):
        if self.df_tsi.empty:
            return {}, [], [], []

        df = self.df_tsi.copy()
        loja_sel = self.combo_loja.currentText()
        mes_sel = self.combo_mes.currentText()

        if loja_sel != "Todas as Unidades" and 'Loja_Nome' in df.columns:
            df = df[df['Loja_Nome'] == loja_sel]

        col_mes = 'Mes' if 'Mes' in df.columns else ('Mes_Ano' if 'Mes_Ano' in df.columns else None)
        if mes_sel != "Todos" and col_mes:
            df = df[df[col_mes] == mes_sel]
            
        cons_sel = getattr(self, "combo_consultor", None)
        if cons_sel and cons_sel.currentText() != "Todos" and 'Consultor_Nome' in df.columns:
            df = df[df['Consultor_Nome'] == cons_sel.currentText()]

        total_respostas = len(df)
        if total_respostas == 0:
            return {}, [], [], []

        def serie_numerica(grupo, coluna):
            if not coluna or coluna not in grupo.columns:
                return pd.Series(dtype="float64")
            return pd.to_numeric(
                grupo[coluna].astype(str).str.replace(',', '.', regex=False),
                errors='coerce'
            )

        # O MyHonda fornece o resultado oficial de cada pesquisa na coluna
        # "Nota Pesquisa TSI" (escala de 0 a 100). Não confundir esse índice
        # com a pergunta de recomendação, usada somente na classificação
        # Promotor/Neutro/Detrator.
        col_tsi = 'Nota Pesquisa TSI' if 'Nota Pesquisa TSI' in df.columns else next((
            c for c in df.columns
            if 'nota pesquisa tsi' in self.engine_tsi._normalizar_rotulo(c)
            and 'old' not in self.engine_tsi._normalizar_rotulo(c)
        ), None)

        def calcular_tsi_grupo(grupo):
            notas_tsi = serie_numerica(grupo, col_tsi).dropna()
            if len(notas_tsi) > 0:
                return float(notas_tsi.mean())

            # Compatibilidade com bases legadas que ainda não possuam a nota
            # oficial: usa os cinco blocos que compõem o TSI no MyHonda.
            colunas_mestre = [
                'Avaliação satisfação instalações e infra',
                'Avaliação satisfação consultor',
                'Avaliação satisfação qualidade',
                'Avaliação satisfação entrega',
                'Avaliação satisfação custo benefício'
            ]
            notas = [serie_numerica(grupo, col).dropna() for col in colunas_mestre if col in grupo.columns]
            notas = [serie for serie in notas if len(serie) > 0]
            if not notas:
                return 0.0
            todas_notas = pd.concat(notas, ignore_index=True)
            return float(todas_notas.mean() * 10)

        tsi_score = calcular_tsi_grupo(df)

        # Classificação de recomendação (NPS), exibida nos cards de perfil.
        col_nps = 'Recomendaria dealer amigo e família'
        if col_nps not in df.columns:
            col_nps = next((c for c in df.columns if 'recomenda' in c.lower()), None)

        promotores = neutros = detratores = total_nps = 0
        if col_nps and col_nps in df.columns:
            s_nps = serie_numerica(df, col_nps).dropna()
            s_nps = s_nps[s_nps.between(0, 10)]
            total_nps = len(s_nps)
            promotores = int((s_nps >= 9).sum())
            neutros = int(((s_nps >= 7) & (s_nps <= 8)).sum())
            detratores = int((s_nps <= 6).sum())
        nps_score = ((promotores - detratores) / total_nps * 100) if total_nps else 0.0
        sem_nota_count = total_respostas - total_nps

        # Top2Box Geral
        col_geral = 'Avaliação satisfação geral'
        if col_geral in df.columns:
            s_geral = serie_numerica(df, col_geral).dropna()
            s_geral = s_geral[s_geral.between(0, 10)]
            top2box = (s_geral >= 9).sum() / len(s_geral) * 100 if len(s_geral) > 0 else 0.0
        else:
            top2box = 0.0

        # Participação WhatsApp calculada exclusivamente no recorte ativo.
        total_saas_enviados, taxa_resp = self._calcular_participacao_whatsapp(df, "TSI")

        # Dimensões
        dimensoes = {}
        dimensoes_detalhes = {}
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
                # O MyHonda mantém a resposta na base mesmo quando o cliente
                # informa que o item não ocorreu (ex.: não fez agendamento).
                # Portanto, sem nota equivale a zero no Top2Box e permanece no
                # denominador total de pesquisas.
                s = serie_numerica(df, col).fillna(0)
                top2_qtd = int((s >= 9).sum())
                dimensoes[label] = top2_qtd / total_respostas * 100 if total_respostas > 0 else 0.0
                dimensoes_detalhes[label] = {
                    'top2': top2_qtd,
                    'validas': int(total_respostas)
                }

        def calcular_distribuicao(coluna):
            if not coluna or coluna not in df.columns:
                return []
            invalidos = {'', 'nan', 'none', '<na>', '-', 'desconhecida', 'desconhecido'}
            valores = df[coluna].apply(
                lambda valor: str(valor).strip()
                if str(valor).strip().lower() not in invalidos
                else 'Não informado'
            )
            itens = []
            for nome, indices in valores.groupby(valores).groups.items():
                grupo = df.loc[indices]
                itens.append({
                    'nome': str(nome),
                    'respostas': int(len(grupo)),
                    'tsi': calcular_tsi_grupo(grupo)
                })
            return itens

        col_distrib_loja = 'Loja_Nome' if 'Loja_Nome' in df.columns else next(
            (c for c in df.columns if 'loja' in c.lower() or 'concession' in c.lower()),
            None
        )
        # "Segmento" no relatório MyHonda representa HDA/HAB. Para o quadro
        # gerencial, a segmentação correta da motocicleta vem de Categoria
        # Produto: Baixa, Média, Alta ou Scooter.
        col_distrib_segmento = 'Categoria Produto' if 'Categoria Produto' in df.columns else next((
            c for c in df.columns
            if 'categoria produto' in self.engine_tsi._normalizar_rotulo(c)
        ), None)
        distribuicao_lojas = calcular_distribuicao(col_distrib_loja)
        distribuicao_segmentos = calcular_distribuicao(col_distrib_segmento)

        # Ranking Consultores
        ranking = []
        if 'Consultor_Nome' in df.columns:
            for cons_nome, group in df.groupby('Consultor_Nome'):
                if str(cons_nome).strip().lower() in ['', 'nan', 'não identificado', 'nao identificado', 'desconhecido']: continue
                c_total = len(group)
                c_tsi = calcular_tsi_grupo(group)
                if col_geral and col_geral in group.columns:
                    c_g = serie_numerica(group, col_geral).dropna()
                    c_g = c_g[c_g.between(0, 10)]
                    c_top = (c_g >= 9).sum() / len(c_g) * 100 if len(c_g) > 0 else 0.0
                else:
                    c_top = 0.0
                c_pilares = {}
                c_pilares_contagens = {}
                for pilar_nome, pilar_col in dim_map.items():
                    if pilar_col and pilar_col in group.columns:
                        pilar_notas = serie_numerica(group, pilar_col).fillna(0)
                        pilar_top2 = int((pilar_notas >= 9).sum())
                        c_pilares[pilar_nome] = (
                            pilar_top2 / c_total * 100
                            if c_total > 0 else None
                        )
                        c_pilares_contagens[pilar_nome] = {
                            'top2': pilar_top2,
                            'validas': int(c_total)
                        }
                ranking.append({
                    'nome': cons_nome,
                    'respostas': c_total,
                    'tsi': c_tsi,
                    'nps': c_tsi,
                    'media': c_top,
                    'pilares': c_pilares,
                    'pilares_contagens': c_pilares_contagens
                })
            ranking.sort(key=lambda x: x['respostas'], reverse=True)

        # Detratores e Lista Completa de Respostas com Verbalizações
        detratores_list = []
        responses_list = []
        
        # Obtém o mapeamento de leads (cruzamento OS -> Nome / Telefone da lista de reenvio/envio)
        leads_map = self.db.get_leads_mapping() if hasattr(self, 'db') else {}
        
        col_cli_candidates = [c for c in df.columns if str(c).strip().lower() in ['cliente', 'nome do cliente', 'nome cliente']]
        if col_cli_candidates:
            col_cli = col_cli_candidates[0]
        else:
            col_cli = next((
                c for c in df.columns 
                if ('cliente' in c.lower() or ('nome' in c.lower() and 'consultor' not in c.lower() and 'loja' not in c.lower() and 'conta' not in c.lower()))
                and not any(x in c.lower() for x in ['contat', 'após', 'apos', 'dealer', 'serviço', 'servico', 'pesquisa', 'origem', 'resposta', 'tipo', 'sexo', 'categoria', 'segmento', '?', 'coment', 'atendido'])
            ), None)
        col_fone = next((c for c in df.columns if any(k in c.lower() for k in ['tel', 'cel', 'fone'])), None)
        col_os = next((c for c in df.columns if 'ordens de servi' in c.lower() or 'os' == c.lower()), None)
        col_cat = next((c for c in df.columns if 'categoria' in c.lower()), None) or next((c for c in df.columns if 'segmento' in c.lower()), None)
        col_data = 'Data de Resposta' if 'Data de Resposta' in df.columns else next((c for c in df.columns if 'data' in c.lower() and 'resposta' in c.lower()), None)
        col_cons = 'Consultor_Nome' if 'Consultor_Nome' in df.columns else next((c for c in df.columns if 'consultor' in c.lower()), None)
        col_loja = 'Loja_Nome' if 'Loja_Nome' in df.columns else next((c for c in df.columns if 'loja' in c.lower() or 'concession' in c.lower()), None)

        def get_val_pilar(row, c_name):
            if c_name in df.columns and pd.notna(row.get(c_name)):
                try:
                    n = float(str(row.get(c_name)).replace(',', '.'))
                    if n >= 0:
                        return f"{int(round(n)) if n.is_integer() else n:.1f}"
                except:
                    pass
            return "-"

        for _, r in df.iterrows():
            nota_raw = r.get(col_nps) if col_nps and col_nps in df.columns else None
            status_tipo, nota_val = DashboardComparativoScreen._classificar_recomendacao(nota_raw)

            os_full = str(r.get(col_os, '')).strip() if col_os else ''
            os_num = os_full.split('-')[-1] if '-' in os_full else (os_full or str(r.get('OS', '-')))
            data_r = str(r.get(col_data, '-')) if col_data else '-'
            cons_r = str(r.get(col_cons, '-')) if col_cons else '-'
            loja_r = str(r.get(col_loja, '-')) if col_loja else '-'
            
            # Validação e Enriquecimento do Cliente via Cruzamento de O.S.
            cli_r = str(r.get(col_cli, '')).strip() if col_cli else ''
            
            lead_info = self.db.find_lead(
                os_full,
                os_num,
                str(r.get('id', '')).strip(),
                tipo="TSI"
            )

            if lead_info:
                nome_cruzado = str(lead_info.get('cliente', '')).strip()
                if nome_cruzado and nome_cruzado.upper() not in ['N/D', 'NONE', 'S/N', 'N/A', '-', '']:
                    if not cli_r or cli_r.lower() in ['nan', 'none', '-', '', 'sim', 'não', 'nao', 'n/d', 's/n'] or cli_r.startswith("Cliente (O.S.") or cli_r == "Cliente Auditado":
                        cli_r = nome_cruzado

            if not cli_r or cli_r.lower() in ['nan', 'none', '-', '', 'sim', 'não', 'nao', 'n/d', 's/n']:
                cli_r = f"Cliente (O.S. #{os_num})" if os_num != '-' else "Cliente Auditado"

            # Categoria do Produto (Baixa, Scooter, Média, Alta...)
            cat_r = str(r.get(col_cat, '')).strip() if col_cat else ''
            if cat_r.lower() in ['nan', 'none', '-', '', 'hda']:
                cat_r = ""

            fone_r = str(r.get(col_fone, '')).strip() if col_fone else ''
            if fone_r.lower() in ['nan', 'none', 's/n', '-', '']:
                fone_r = ""
                
            if not fone_r and lead_info:
                fone_cruzado = str(lead_info.get('telefone', '')).strip()
                if fone_cruzado and fone_cruzado.lower() not in ['nan', 'none', 's/n', 'n/d', '-', '']:
                    fone_r = fone_cruzado

            # Verbalizações
            comms = []
            cols_comms_map = [
                ('Motivo satisfação geral', 'Geral'),
                ('Comentário conclusão final', 'Conclusão'),
                ('Motivo insatisfação consultor', 'Consultor'),
                ('Motivo insatisfação qualidade', 'Qualidade'),
                ('Motivo insatisfação entrega', 'Entrega'),
                ('Motivo insatisfação instalações e infra', 'Instalações'),
                ('Motivo insatisfação custo beneficio', 'Custo/Benefício')
            ]
            for col_c, rotulo in cols_comms_map:
                if col_c in df.columns:
                    val_c = str(r.get(col_c, '')).strip()
                    if val_c and val_c not in ['-', 'nan', 'None', '']:
                        comms.append(f"<b>{rotulo}:</b> {val_c}")

            tem_coment = len(comms) > 0
            motivo_txt = " &bull; ".join(comms) if comms else "Sem verbalização registrada pelo cliente."

            notas_pilares = {
                'Geral': get_val_pilar(r, 'Avaliação satisfação geral'),
                'Agendamento': get_val_pilar(r, 'Avaliação satisfação agendamento'),
                'Recepção': get_val_pilar(r, 'Avaliação satisfação recepção'),
                'Consultor': get_val_pilar(r, 'Avaliação satisfação consultor'),
                'Qualidade': get_val_pilar(r, 'Avaliação satisfação qualidade'),
                'Entrega': get_val_pilar(r, 'Avaliação satisfação entrega'),
                'Custo/Benefício': get_val_pilar(r, 'Avaliação satisfação custo benefício')
            }

            resp_item = {
                'tipo': 'TSI',
                'status': status_tipo,
                'nota': nota_val,
                'data': data_r,
                'cliente': cli_r,
                'telefone': fone_r,
                'os': os_num,
                'categoria': cat_r,
                'consultor': cons_r,
                'loja': loja_r,
                'comentario': motivo_txt,
                'tem_comentario': tem_coment,
                'notas_pilares': notas_pilares
            }
            responses_list.append(resp_item)

            if status_tipo == "DETRATOR":
                detratores_list.append({
                    'data': data_r,
                    'cliente': cli_r,
                    'telefone': fone_r or '-',
                    'os': os_num,
                    'categoria': cat_r,
                    'nota': nota_val,
                    'motivo': motivo_txt[:140]
                })

        metrics = {
            'nps': nps_score,
            'tsi': tsi_score,
            'top2box': top2box,
            'total_respostas': total_respostas,
            'promotores_count': promotores,
            'neutros_count': neutros,
            'detratores_count': detratores,
            'promotores_pct': (promotores / total_nps * 100) if total_nps else 0.0,
            'neutros_pct': (neutros / total_nps * 100) if total_nps else 0.0,
            'detratores_pct': (detratores / total_nps * 100) if total_nps else 0.0,
            'sem_nota_count': sem_nota_count,
            'saas_enviados': total_saas_enviados,
            'saas_taxa_resp': taxa_resp,
            'dimensoes': dimensoes,
            'dimensoes_detalhes': dimensoes_detalhes,
            'distribuicao_lojas': distribuicao_lojas,
            'distribuicao_segmentos': distribuicao_segmentos
        }
        return metrics, ranking, detratores_list, responses_list

    def _calcular_metricas_ssi(self):
        if self.df_ssi.empty:
            return {}, [], [], [], []

        df = self.df_ssi.copy()
        loja_sel = self.combo_loja.currentText()
        mes_sel = self.combo_mes.currentText()

        col_loja = 'Loja' if 'Loja' in df.columns else next((c for c in df.columns if 'concession' in c.lower() or 'conta' in c.lower()), None)
        if loja_sel != "Todas as Unidades" and col_loja:
            df = df[df[col_loja].astype(str) == loja_sel]

        col_data = 'Data de resposta SSI 2W' if 'Data de resposta SSI 2W' in df.columns else ('Data de Resposta' if 'Data de Resposta' in df.columns else next((c for c in df.columns if 'data' in str(c).lower() and 'resposta' in str(c).lower()), None))
        if not col_data:
            col_data = next((c for c in df.columns if 'data' in str(c).lower() and 'envio' not in str(c).lower() and 'ssi' in str(c).lower()), None)
        if mes_sel != "Todos" and col_data:
            try:
                p_mes, p_ano = mes_sel.split('/')
                pattern = f"(?:{p_mes}/{p_ano}|{p_ano}-{p_mes})"
                df = df[df[col_data].astype(str).str.contains(pattern, regex=True)]
            except Exception:
                df = df[df[col_data].astype(str).str.contains(mes_sel, regex=False)]
        
        cons_sel = getattr(self, "combo_consultor", None)
        if cons_sel and cons_sel.currentText() != "Todos" and 'Consultor_Nome' in df.columns:
            df = df[df['Consultor_Nome'] == cons_sel.currentText()]

        total_respostas = len(df)
        if total_respostas == 0:
            return {}, [], [], [], []

        # O SSI oficial corresponde ao Top2Box de Satisfação Geral. A
        # recomendação continua sendo auditada separadamente como NPS.
        resumo_recomendacao = recommendation_summary(df)
        col_nps = ssi_raw_column(df, 'recommendation')
        promotores = resumo_recomendacao['promoters']
        neutros = resumo_recomendacao['neutrals']
        detratores = resumo_recomendacao['detractors']
        total_nps = resumo_recomendacao['valid']
        sem_nota_count = total_respostas - total_nps
        nps_score = resumo_recomendacao['nps']
        ssi_score = calculate_ssi_percentage(df, 'satisfaction')
        satisfacao_geral = ssi_score

        # Indicadores oficiais já calculados pelo MyHonda.
        col_geral = ssi_raw_column(df, 'satisfaction')
        col_rec = ssi_raw_column(df, 'repurchase')
        col_ent = ssi_raw_column(df, 'delivery')
        recompra_pct = calculate_ssi_percentage(df, 'repurchase')
        entrega_pct = calculate_ssi_percentage(df, 'delivery')
        recomendacao_top2 = calculate_ssi_percentage(df, 'recommendation')

        # Dimensões SSI
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

        # Modalidade de Compra
        modalidades = []
        col_mod = next((c for c in df.columns if 'modalidade' in c.lower()), None)
        if col_mod:
            for mod_nome, group in df.groupby(col_mod):
                m_qtd = len(group)
                m_resumo = recommendation_summary(group)
                m_ssi = calculate_ssi_percentage(group, 'satisfaction')
                modalidades.append({
                    'nome': str(mod_nome), 'qtd': m_qtd,
                    'ssi': m_ssi, 'nps': m_resumo['nps']
                })
            modalidades.sort(key=lambda x: x['qtd'], reverse=True)

        # Detratores e Lista Completa SSI
        detratores_list = []
        responses_list = []
        
        # Obtém o mapeamento de leads (cruzamento Posse/Chassi -> Nome / Telefone da lista de reenvio/envio)
        leads_map = self.db.get_leads_mapping() if hasattr(self, 'db') else {}
        
        col_cli_candidates = [c for c in df.columns if str(c).strip().lower() in ['cliente', 'nome do cliente', 'nome cliente']]
        if col_cli_candidates:
            col_cli = col_cli_candidates[0]
        else:
            col_cli = next((c for c in df.columns if 'cliente' == c.lower() or ('cliente' in c.lower() and 'sexo' not in c.lower() and 'contat' not in c.lower())), None)
        col_fone = next((c for c in df.columns if any(k in c.lower() for k in ['tel', 'cel', 'fone'])), None)
        col_posse = next((c for c in df.columns if 'posse' in c.lower() and 'name' in c.lower()), None)
        col_mod_moto = next((c for c in df.columns if 'modelo' in c.lower() and 'ano' not in c.lower()), 'Modelo')
        col_ano = next((c for c in df.columns if 'ano' in c.lower() and 'modelo' in c.lower()), None)

        def get_ssi_pilar(row, c_cand):
            c_found = next((c for c in df.columns if c_cand in c.lower()), None)
            if c_found and pd.notna(row.get(c_found)):
                try:
                    n = float(str(row.get(c_found)).replace(',', '.'))
                    if n >= 0:
                        return f"{int(round(n)) if n.is_integer() else n:.1f}"
                except:
                    pass
            return "-"

        for _, r in df.iterrows():
            nota_raw = r.get(col_nps) if col_nps and col_nps in df.columns else None
            status_tipo, nota_val = DashboardComparativoScreen._classificar_recomendacao(nota_raw)

            posse_str = str(r.get(col_posse, '-')).strip() if col_posse else '-'
            chassi_val = posse_str.split('-')[-1] if '-' in posse_str else posse_str
            posse_num = posse_str.split('-')[0] if '-' in posse_str else posse_str
            data_r = str(r.get(col_data, '-')) if col_data else '-'
            cli_r = str(r.get(col_cli, '')).strip() if col_cli else ''
            
            lead_info = self.db.find_lead(
                posse_str,
                chassi_val,
                posse_num,
                str(r.get('id', '')).strip(),
                tipo="SSI"
            )

            if lead_info:
                nome_cruzado = str(lead_info.get('cliente', '')).strip()
                if nome_cruzado and nome_cruzado.upper() not in ['N/D', 'NONE', 'S/N', 'N/A', '-', '']:
                    if not cli_r or cli_r.lower() in ['nan', 'none', '-', '', 'sim', 'não', 'nao', 'n/d', 's/n'] or cli_r.startswith("Comprador (") or cli_r == "Comprador Auditado":
                        cli_r = nome_cruzado

            if not cli_r or cli_r.lower() in ['nan', 'none', '-', '']:
                cli_r = f"Comprador ({chassi_val})" if chassi_val != '-' else "Comprador Auditado"

            fone_r = str(r.get(col_fone, '')).strip() if col_fone else ''
            if fone_r.lower() in ['nan', 'none', 's/n', '-', '']:
                fone_r = ""
                
            if not fone_r and lead_info:
                fone_cruzado = str(lead_info.get('telefone', '')).strip()
                if fone_cruzado and fone_cruzado.lower() not in ['nan', 'none', 's/n', 'n/d', '-', '']:
                    fone_r = fone_cruzado

            modelo_r = str(r.get(col_mod_moto, '-'))
            ano_r = format_model_year(r.get(col_ano, '')) if col_ano else ''
            if ano_r and ano_r not in ['-', 'nan', 'None']:
                modelo_r = f"{modelo_r} ({ano_r})"

            modalidade_r = str(r.get(col_mod, '-')) if col_mod else '-'
            loja_r = str(r.get('Loja', '-')) if 'Loja' in df.columns else '-'

            # Verbalizações SSI
            comms = []
            for col_c in df.columns:
                if 'coment' in col_c.lower():
                    val_c = str(r.get(col_c, '')).strip()
                    if val_c and val_c not in ['-', 'nan', 'None', '']:
                        clean_c = col_c.replace('Comentários ', '').replace('Comentário ', '')
                        comms.append(f"<b>{clean_c}:</b> {val_c}")

            tem_coment = len(comms) > 0
            motivo_txt = " &bull; ".join(comms) if comms else "Sem verbalização registrada pelo cliente."

            col_rec_val = r.get(col_rec) if col_rec else None
            rec_str = "-" if pd.isna(col_rec_val) or str(col_rec_val).strip() in ['', '-'] else str(col_rec_val)

            notas_pilares = {
                'Exp. Compra': get_ssi_pilar(r, 'experiência compra') if get_ssi_pilar(r, 'experiência compra') != '-' else get_ssi_pilar(r, 'satisfação geral'),
                'Atendimento': get_ssi_pilar(r, 'atendimento do vendedor'),
                'Negociação': get_ssi_pilar(r, 'negociação geral'),
                'Instalações': get_ssi_pilar(r, 'conforto das instalações'),
                'Entrega': get_ssi_pilar(r, 'entrega motocicleta'),
                'Recompra': rec_str
            }

            resp_item = {
                'tipo': 'SSI',
                'status': status_tipo,
                'nota': nota_val,
                'data': data_r,
                'cliente': cli_r,
                'telefone': fone_r,
                'chassi': chassi_val,
                'modelo': modelo_r,
                'modalidade': modalidade_r,
                'loja': loja_r,
                'comentario': motivo_txt,
                'tem_comentario': tem_coment,
                'notas_pilares': notas_pilares
            }
            responses_list.append(resp_item)

            if status_tipo == "DETRATOR":
                detratores_list.append({
                    'data': data_r,
                    'cliente': cli_r,
                    'telefone': fone_r or '-',
                    'modelo': modelo_r,
                    'chassi': chassi_val,
                    'nota': nota_val,
                    'motivo': motivo_txt[:140]
                })

        # Ranking Consultores
        ranking = []
        if 'Consultor_Nome' in df.columns:
            for cons_nome, group in df.groupby('Consultor_Nome'):
                if str(cons_nome).strip().lower() in ['desconhecido', 'não identificado', 'nao identificado', '', 'nan']: continue
                c_total = len(group)
                c_resumo = recommendation_summary(group)
                c_ssi = calculate_ssi_percentage(group, 'satisfaction')
                c_top = calculate_ssi_percentage(group, 'recommendation')
                c_pilares = {}
                for pilar_nome, metric_key in dim_map.items():
                    c_pilares[pilar_nome] = calculate_ssi_percentage(group, metric_key)
                ranking.append({
                    'nome': cons_nome,
                    'respostas': c_total,
                    'ssi': c_ssi,
                    'tsi': c_ssi,
                    'nps': c_resumo['nps'],
                    'media': c_top,
                    'pilares': c_pilares
                })
            ranking.sort(key=lambda x: x['respostas'], reverse=True)

        _, taxa_resp = self._calcular_participacao_whatsapp(df, "SSI")
        metrics = {
            'nps': nps_score,
            'ssi': ssi_score,
            'recomendacao_top2': recomendacao_top2,
            'satisfacao_geral': satisfacao_geral,
            'total_respostas': total_respostas,
            'promotores_count': promotores,
            'neutros_count': neutros,
            'detratores_count': detratores,
            'promotores_pct': (promotores / total_nps * 100) if total_nps else 0.0,
            'neutros_pct': (neutros / total_nps * 100) if total_nps else 0.0,
            'detratores_pct': (detratores / total_nps * 100) if total_nps else 0.0,
            'sem_nota_count': sem_nota_count,
            'recompra_pct': recompra_pct,
            'entrega_pct': entrega_pct,
            'saas_taxa_resp': taxa_resp,
            'dimensoes': dimensoes
        }
        return metrics, modalidades, ranking, detratores_list, responses_list

    def _obter_filtros_ativos_webview(self) -> dict:
        """
        Consulta o DOM do QWebEngineView ativo para extrair os filtros de status
        selecionados (múltipla seleção) e o termo digitado na caixa de pesquisa.
        """
        try:
            js_code = """
            (function() {
                const activeBtns = Array.from(document.querySelectorAll('.btn-filter.active'));
                let activeStatuses = activeBtns.map(b => b.getAttribute('data-status'));
                const searchInput = document.getElementById('search-box');
                const termo = searchInput ? searchInput.value : '';
                return JSON.stringify({
                    statuses: activeStatuses,
                    termo: termo
                });
            })();
            """
            loop = QEventLoop()
            res_dict = {"statuses": ["TODOS"], "termo": ""}
            
            def callback(res):
                nonlocal res_dict
                try:
                    if res:
                        res_dict = json.loads(res)
                except Exception as e:
                    print("Erro ao decodificar filtros do webview:", e)
                loop.quit()
                
            self.web_view.page().runJavaScript(js_code, callback)
            QTimer.singleShot(400, loop.quit)
            loop.exec()
            return res_dict
        except Exception as e:
            print("Erro ao obter filtros ativos do webview:", e)
            return {"statuses": ["TODOS"], "termo": ""}

    def _filtrar_respostas_por_estado(self, responses: list, filtros: dict = None) -> tuple:
        """
        Filtra a lista de respostas conforme os status e termo de pesquisa ativos no Dashboard.
        Retorna (lista_filtrada, descricao_do_filtro).
        """
        if not filtros:
            return responses, "Todos os Feedbacks"
        statuses = filtros.get("statuses", ["TODOS"])
        termo = (filtros.get("termo") or "").lower().strip()
        
        is_todos = ("TODOS" in statuses) or (len(statuses) == 0)
        has_com_filtro = "COMENTARIOS" in statuses
        status_cats = [s for s in statuses if s in ["PROMOTOR", "NEUTRO", "DETRATOR", "SEM_NOTA"]]
        
        rotulos_filtros = []
        if "PROMOTOR" in status_cats: rotulos_filtros.append("Promotores")
        if "NEUTRO" in status_cats: rotulos_filtros.append("Neutros")
        if "DETRATOR" in status_cats: rotulos_filtros.append("Detratores")
        if "SEM_NOTA" in status_cats: rotulos_filtros.append("Sem nota")
        if has_com_filtro: rotulos_filtros.append("Com Feedback")
        if termo: rotulos_filtros.append(f'Busca: "{termo}"')
        
        filtro_desc = " • ".join(rotulos_filtros) if rotulos_filtros else "Todos os Feedbacks"
        
        filtradas = []
        for r in responses:
            st = r.get("status", "")
            has_com = bool(r.get("tem_comentario", False))
            
            match_status = False
            if is_todos:
                match_status = True
            elif status_cats:
                match_status = st in status_cats
            elif has_com_filtro:
                match_status = True
                
            if has_com_filtro and not has_com:
                match_status = False
                
            search_text = (
                f"{r.get('cliente', '')} {r.get('os', '')} {r.get('chassi', '')} {r.get('modelo', '')} {r.get('categoria', '')} {r.get('telefone', '')} {r.get('consultor', '')} {r.get('vendedor', '')} {r.get('modalidade', '')} {r.get('loja', '')} {r.get('comentario', '')}"
            ).lower()
            
            match_termo = (termo == "") or (termo in search_text)
            
            if match_status and match_termo:
                filtradas.append(r)
                
        return filtradas, filtro_desc

    def atualizar_dashboard(self):
        dept_idx = self.combo_dept.currentIndex()
        if dept_idx == 0:
            metrics, ranking, _, responses = self._calcular_metricas_tsi()
            html = self._render_tsi_html(metrics, ranking, responses)
        else:
            metrics, modalidades, ranking, _, responses = self._calcular_metricas_ssi()
            html = self._render_ssi_html(metrics, modalidades, ranking, responses)

        self.web_view.setHtml(html)

    @staticmethod
    def _formatar_verbalizacao_pdf(texto):
        """No PDF, apresenta cada verbalização de pilar em sua própria linha."""
        valor = str(texto or "Sem verbalização registrada pelo cliente.")
        valor = re.sub(r'\s*(?:&bull;|•)\s*', '<br>', valor, flags=re.IGNORECASE)
        valor = re.sub(r'(?:<br>\s*){2,}', '<br>', valor, flags=re.IGNORECASE)
        return valor

    def _render_tsi_html(self, metrics, ranking, responses, is_pdf: bool = False, loja_nome: str = "Todas as Unidades", mes_ref: str = "Todos", filtros_respostas: dict = None):
        if not metrics:
            return """
            <!DOCTYPE html>
            <html>
            <body style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif; background:#F8FAFC; text-align:center; padding:40px; color:#64748B;'>
                <h3>Nenhum dado encontrado para os filtros selecionados.</h3>
                <p>Verifique a concessionária ou o mês selecionado no painel acima.</p>
            </body>
            </html>
            """

        tsi = metrics.get('tsi', metrics.get('nps', 0.0))
        tsi_color = "#16A34A" if tsi >= 75 else ("#2563EB" if tsi >= 50 else "#DC2626")
        top2box = metrics.get('top2box', 0.0)
        total_resp = metrics.get('total_respostas', 0)
        saas_taxa = metrics.get('saas_taxa_resp', 0.0)
        
        promotores_cnt = metrics.get('promotores_count', 0)
        neutros_cnt = metrics.get('neutros_count', 0)
        detratores_cnt = metrics.get('detratores_count', 0)
        sem_nota_cnt = metrics.get('sem_nota_count', 0)
        
        promotores_pct = metrics.get('promotores_pct', 0.0)
        neutros_pct = metrics.get('neutros_pct', 0.0)
        detratores_pct = metrics.get('detratores_pct', 0.0)

        coments_cnt = sum(1 for r in responses if r.get('tem_comentario'))

        ranking_pilares = list(metrics.get('dimensoes', {}).keys())
        ranking_pilar_min_width = "46px" if is_pdf else "72px"
        ranking_table_min_width = "100%" if is_pdf else "1050px"
        ranking_table_font_size = "7px" if is_pdf else "10px"
        ranking_pilar_headers = "".join(
            f"<th title='{nome}' style='padding: 6px 4px; text-align: center; min-width: {ranking_pilar_min_width}; white-space: normal;'>{nome}</th>"
            for nome in ranking_pilares
        )
        rows_ranking = ""
        ranking_list = ranking if is_pdf else ranking[:8]
        for c in ranking_list:
            pilar_cells = ""
            for pilar_nome in ranking_pilares:
                pilar_valor = c.get('pilares', {}).get(pilar_nome)
                pilar_base = c.get('pilares_contagens', {}).get(pilar_nome, {})
                pilar_validas = int(pilar_base.get('validas', 0))
                pilar_top2 = int(pilar_base.get('top2', 0))
                pilar_texto = "-" if pilar_valor is None else f"{pilar_valor:.1f}%<br><span style='font-size: 0.85em; font-weight: 500; color: #64748B;'>({pilar_top2}/{pilar_validas})</span>"
                pilar_cor = "#94A3B8" if pilar_valor is None else ("#16A34A" if pilar_valor >= 85 else ("#2563EB" if pilar_valor >= 70 else "#DC2626"))
                pilar_cells += f"<td style='padding: 6px 5px; text-align: center; font-weight: 600; color: {pilar_cor};'>{pilar_texto}</td>"
            rows_ranking += f"""
            <tr style='border-bottom: 1px solid #E2E8F0;'>
                <td class='sticky-col' style='padding: 6px 8px; font-weight: 600; color: #1E293B;'>{c.get('nome')}</td>
                <td style='padding: 6px 8px; text-align: center; color: #475569;'>{c.get('respostas')}</td>
                <td style='padding: 6px 8px; text-align: center; font-weight: bold; color: #2563EB;'>{c.get('tsi', c.get('nps', 0.0)):.1f}</td>
                <td style='padding: 6px 8px; text-align: center; color: #059669; font-weight: 600;'>{c.get('media'):.1f}%</td>
                {pilar_cells}
            </tr>
            """
        if not rows_ranking:
            rows_ranking = f"<tr><td colspan='{4 + len(ranking_pilares)}' style='padding: 10px; text-align: center; color: #94A3B8;'>Nenhum consultor registrado no período.</td></tr>"

        dim_html = ""
        for k, v in metrics.get('dimensoes', {}).items():
            c_dim = "#16A34A" if v >= 85 else ("#2563EB" if v >= 70 else "#DC2626")
            detalhe_dim = metrics.get('dimensoes_detalhes', {}).get(k, {})
            dim_top2 = int(detalhe_dim.get('top2', 0))
            dim_validas = int(detalhe_dim.get('validas', 0))
            dim_base = f" <span style='font-size: 10px; font-weight: 600; color: #64748B;'>({dim_top2}/{dim_validas})</span>" if dim_validas else ""
            dim_html += f"""
            <div style='margin-bottom: 8px;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px;'>
                    <span style='font-size: 11px; color: #334155; font-weight: 600;'>{k}</span>
                    <span style='font-size: 12px; font-weight: bold; color: {c_dim};'>{v:.1f}%{dim_base}</span>
                </div>
                <div style='background-color: #E2E8F0; height: 5px; border-radius: 3px; overflow: hidden;'>
                    <div style='background-color: {c_dim}; width: {v:.1f}%; height: 100%; border-radius: 3px;'></div>
                </div>
            </div>
            """

        def render_distribuicao(itens, vazio):
            if not itens:
                return f"<tr><td colspan='3' style='padding: 8px; text-align: center; color: #94A3B8;'>{vazio}</td></tr>"
            return "".join(
                f"""
                <tr style='border-bottom: 1px solid #E2E8F0;'>
                    <td style='padding: 6px 4px; color: #334155; font-weight: 600;'>{item.get('nome')}</td>
                    <td style='padding: 6px 4px; text-align: center; color: #0F172A; font-weight: 700;'>{item.get('respostas')}</td>
                    <td style='padding: 6px 4px; text-align: center; color: #2563EB; font-weight: 700;'>{item.get('tsi', 0.0):.1f}%</td>
                </tr>
                """
                for item in itens
            )

        rows_lojas = render_distribuicao(metrics.get('distribuicao_lojas', []), "Nenhuma loja identificada.")
        rows_segmentos = render_distribuicao(metrics.get('distribuicao_segmentos', []), "Nenhum segmento identificado.")

        responses_para_cards = responses
        filtro_desc = "Todos os Feedbacks"
        if is_pdf:
            responses_para_cards, filtro_desc = self._filtrar_respostas_por_estado(responses, filtros_respostas)

        # Construção da Lista de Clientes & Verbalizações Auditadas
        cards_respostas_html = ""
        for r in responses_para_cards:
            st = r.get('status', 'NEUTRO')
            nota = r.get('nota', 0)
            tem_c = "true" if r.get('tem_comentario') else "false"
            
            if st == "PROMOTOR":
                badge_st = f"<span class='status-pill status-promotor'>🟢 PROMOTOR • Nota {nota}</span>"
                border_color = "#10B981"
            elif st == "NEUTRO":
                badge_st = f"<span class='status-pill status-neutro'>🟡 NEUTRO • Nota {nota}</span>"
                border_color = "#F59E0B"
            elif st == "DETRATOR":
                badge_st = f"<span class='status-pill status-detrator'>🔴 DETRATOR • Nota {nota}</span>"
                border_color = "#EF4444"
            else:
                badge_st = "<span class='status-pill status-sem-nota'>⚪ SEM NOTA DE RECOMENDAÇÃO</span>"
                border_color = "#94A3B8"

            # Telefone ocultado no relatório conforme solicitação
            fone_badge = ""
            os_badge = f"<span class='meta-tag'>🏷️ O.S.: <b>{r.get('os')}</b></span>" if r.get('os') and r.get('os') != '-' else ""
            cat_badge = f"<span class='meta-tag'>🏍️ Categoria: <b>{r.get('categoria')}</b></span>" if r.get('categoria') else ""
            cons_badge = f"<span class='meta-tag'>👨‍🔧 Consultor: <b>{r.get('consultor')}</b></span>" if r.get('consultor') and r.get('consultor') != '-' else ""
            loja_badge = f"<span class='meta-tag'>🏢 {r.get('loja')}</span>" if r.get('loja') and r.get('loja') != '-' else ""

            # Tags com as notas individuais dos pilares
            pilares_tags = ""
            for p_nome, p_val in r.get('notas_pilares', {}).items():
                if p_val != "-":
                    pilares_tags += f"<span class='pilar-badge'>{p_nome}: <b>{p_val}</b></span>"

            search_text = f"{r.get('cliente')} {r.get('os')} {r.get('categoria', '')} {r.get('consultor')} {r.get('comentario')}".lower().replace('"', '&quot;')

            if is_pdf:
                comentario_pdf = self._formatar_verbalizacao_pdf(r.get('comentario'))
                cards_respostas_html += f"""
            <div class="resp-card pdf-response-card" style="border-left-color: {border_color};">
                <div class="resp-header">
                    <div class="resp-meta-left">
                        <span class="resp-client-name">👤 {r.get('cliente')}</span>
                        <span class="meta-tag">📅 {r.get('data')}</span>
                    </div>
                </div>
                <div class="pdf-score-row">
                    <div class="resp-pillars-tags">{pilares_tags if pilares_tags else "<span style='color:#94A3B8;font-size:10px;'>Padrão Geral</span>"}</div>
                    <div class="pdf-general-score">{badge_st}</div>
                </div>
                <div class="pdf-verbatim-row">
                    <div class="resp-verbatim-title">💬 Verbalização / Comentário:</div>
                    <div class="resp-verbatim-text">{comentario_pdf}</div>
                </div>
            </div>
            """
            else:
                cards_respostas_html += f"""
            <div class="resp-card" data-status="{st}" data-has-comment="{tem_c}" data-search="{search_text}" style="border-left-color: {border_color};">
                <!-- Linha 1: Cabeçalho com dados e status -->
                <div class="resp-header">
                    <div class="resp-meta-left">
                        <span class="resp-client-name">👤 {r.get('cliente')}</span>
                        <span class="meta-tag">📅 {r.get('data')}</span>
                        {os_badge}
                        {cat_badge}
                        {cons_badge}
                        {loja_badge}
                    </div>
                    <div>
                        {badge_st}
                    </div>
                </div>
                <!-- Linha 2: Verbalização e Notas dos Pilares -->
                <div class="resp-body">
                    <div class="resp-verbatim">
                        <div class="resp-verbatim-title">💬 Verbalização / Comentário:</div>
                        <div class="resp-verbatim-text">{r.get('comentario')}</div>
                    </div>
                    <div class="resp-pillars">
                        <div class="resp-pillars-title">📊 Notas dos Pilares:</div>
                        <div class="resp-pillars-tags">
                            {pilares_tags if pilares_tags else "<span style='color:#94A3B8; font-size:10px;'>Padrão Geral</span>"}
                        </div>
                    </div>
                </div>
            </div>
            """

        if not cards_respostas_html:
            cards_respostas_html = "<div style='padding: 20px; text-align: center; color: #94A3B8; font-size: 11px;'>Nenhum registro encontrado para os filtros aplicados.</div>"

        import datetime
        data_hora_emissao = datetime.datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
        periodo_label = mes_ref if (mes_ref and mes_ref != "Todos") else "Histórico Consolidado (Todos os Períodos)"

        header_pdf_html = f"""
        <div class="header-box">
            <div>
                <span class="dept-badge">PÓS-VENDAS & OFICINA (TSI)</span>
                <h1 class="logo-title">RELATÓRIO DE QUALIDADE TSI</h1>
                <div class="store-name">{loja_nome}</div>
            </div>
            <div class="meta-info">
                <div class="meta-badge">📅 Período: {periodo_label}</div><br>
                <b>Data de Extração:</b> {data_hora_emissao}<br>
                <b>Sistema:</b> SaaS Intelligence
            </div>
        </div>
        """ if is_pdf else ""

        footer_pdf_html = """
        <table class="footer-table">
            <tr>
                <td style="width: 50%; text-align: center;">
                    <div class="sig-line">Gerente de Pós-Vendas / Oficina</div>
                </td>
                <td style="width: 50%; text-align: center;">
                    <div class="sig-line">Diretoria Executiva</div>
                </td>
            </tr>
            <tr>
                <td colspan="2" style="text-align: center; padding-top: 8px; font-size: 7.5pt; color: #94A3B8;">
                    Documento gerado automaticamente pelo SaaS Intelligence. Métricas auditadas de qualidade.
                </td>
            </tr>
        </table>
        """ if is_pdf else ""

        desc_filtro_html = f"<div style='font-size: 8pt; color: #2563EB; font-weight: 700; margin-top: 3px;'>🔍 Filtro Aplicado: {filtro_desc}</div>" if (filtro_desc and filtro_desc != "Todos os Feedbacks") else ""
        feedback_top_content = f"""
        <div class="feedback-title">
            <span>📋 Auditoria de Respostas & Verbalizações dos Clientes</span>
            <span class="badge-count">{len(responses_para_cards)} de {len(responses)} registros</span>
        </div>
        <div style="font-size: 8.5pt; color: #64748B; font-weight: 600;">
            Consolidado Geral de Feedbacks & Pilares da Oficina
        </div>
        {desc_filtro_html}
        """ if is_pdf else f"""
        <div class="feedback-title">
            <span>📋 Respostas & Verbalizações dos Clientes</span>
            <span class="badge-count" id="lbl-count-visiveis">{len(responses)} exibidas</span>
        </div>
        <div class="filter-buttons">
            <input type="text" id="search-box" class="search-input" placeholder="🔍 Buscar cliente, O.S., telefone..." oninput="pesquisarRespostas()">
            <button class="btn-filter active" data-status="TODOS" onclick="toggleFiltro('TODOS', this)">Todos ({total_resp})</button>
            <button class="btn-filter" data-status="PROMOTOR" onclick="toggleFiltro('PROMOTOR', this)">Promotores ({promotores_cnt})</button>
            <button class="btn-filter" data-status="NEUTRO" onclick="toggleFiltro('NEUTRO', this)">Neutros ({neutros_cnt})</button>
            <button class="btn-filter" data-status="DETRATOR" onclick="toggleFiltro('DETRATOR', this)">Detratores ({detratores_cnt})</button>
            <button class="btn-filter" data-status="SEM_NOTA" onclick="toggleFiltro('SEM_NOTA', this)">Sem nota ({sem_nota_cnt})</button>
            <button class="btn-filter" data-status="COMENTARIOS" onclick="toggleFiltro('COMENTARIOS', this)">Com Verbalização ({coments_cnt})</button>
        </div>
        """

        container_scroll_style = "max-height: none; overflow: visible;" if is_pdf else "max-height: 480px; overflow-y: auto; padding-right: 4px;"
        body_bg = "#FFFFFF" if is_pdf else "#F8FAFC"
        body_pad = "0px" if is_pdf else "12px 14px"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{ size: A4 portrait; margin: 8mm; }}
                * {{ box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                html, body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
                    background: {body_bg}; 
                    margin: 0; 
                    padding: {body_pad}; 
                    color: #1E293B; 
                }}
                .header-box {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-bottom: 2px solid #E2E8F0;
                    padding-bottom: 10px;
                    margin-bottom: 12px;
                    page-break-inside: avoid;
                }}
                .dept-badge {{
                    background: #1E40AF;
                    color: #FFFFFF;
                    font-size: 7.5pt;
                    font-weight: bold;
                    padding: 3px 8px;
                    border-radius: 4px;
                    text-transform: uppercase;
                    display: inline-block;
                }}
                .logo-title {{
                    font-size: 15pt;
                    font-weight: 800;
                    color: #0F172A;
                    margin: 4px 0 2px 0;
                    letter-spacing: -0.3px;
                }}
                .store-name {{
                    font-size: 10pt;
                    font-weight: bold;
                    color: #475569;
                }}
                .meta-info {{
                    text-align: right;
                    font-size: 8pt;
                    color: #475569;
                }}
                .meta-badge {{
                    background-color: #EFF6FF;
                    color: #1D4ED8;
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 8pt;
                    display: inline-block;
                    margin-bottom: 3px;
                }}
                .roi-box {{ 
                    background: linear-gradient(135deg, #1E293B, #0F172A); 
                    color: white; 
                    border-radius: 8px; 
                    padding: 12px 16px; 
                    margin-bottom: 12px; 
                    page-break-inside: avoid;
                }}
                .grid-kpis {{ 
                    display: grid; 
                    grid-template-columns: repeat(5, 1fr); 
                    gap: 10px; 
                    margin-bottom: 12px; 
                    page-break-inside: avoid;
                }}
                .card {{ 
                    background: #FFFFFF; 
                    border: 1px solid #E2E8F0; 
                    border-radius: 8px; 
                    padding: 10px 14px; 
                    box-shadow: 0 1px 2px rgba(0,0,0,0.03); 
                    page-break-inside: avoid;
                }}
                .kpi-title {{ 
                    font-size: 10px; 
                    font-weight: 700; 
                    color: #64748B; 
                    text-transform: uppercase; 
                    letter-spacing: 0.4px; 
                }}
                .kpi-num {{ 
                    font-size: 20px; 
                    font-weight: 800; 
                    margin: 3px 0; 
                }}
                .kpi-desc {{ 
                    font-size: 10px; 
                    color: #94A3B8; 
                }}
                .two-col {{ 
                    display: grid; 
                    grid-template-columns: 1fr 1fr; 
                    gap: 12px; 
                    margin-bottom: 12px; 
                    page-break-inside: avoid;
                }}
                .tsi-analysis-grid {{
                    display: grid;
                    grid-template-columns: minmax(0, 3fr) minmax(310px, 2fr);
                    gap: 12px;
                    margin-bottom: 12px;
                    align-items: stretch;
                    page-break-inside: avoid;
                }}
                .distribution-block + .distribution-block {{
                    margin-top: 12px;
                    padding-top: 10px;
                    border-top: 1px solid #E2E8F0;
                }}
                .distribution-title {{
                    font-size: 11px;
                    font-weight: 800;
                    color: #334155;
                    margin-bottom: 5px;
                }}
                .consultant-table-wrap {{
                    overflow-x: auto;
                    width: 100%;
                    scrollbar-color: #94A3B8 #E2E8F0;
                }}
                .consultant-table thead th {{
                    position: sticky;
                    top: 0;
                    z-index: 2;
                    background: #F1F5F9;
                }}
                .consultant-table .sticky-col {{
                    position: sticky;
                    left: 0;
                    z-index: 1;
                    background: #FFFFFF;
                    min-width: 150px;
                }}
                .consultant-table thead .sticky-col {{
                    z-index: 3;
                    background: #F1F5F9;
                }}
                @media screen and (max-width: 900px) {{
                    .tsi-analysis-grid {{ grid-template-columns: 1fr; }}
                }}
                
                /* Componente de Respostas & Verbalizações */
                .feedback-section {{
                    background: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-radius: 8px;
                    padding: 14px 16px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
                    margin-bottom: 14px;
                }}
                .feedback-top-bar {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    flex-wrap: wrap;
                    gap: 10px;
                    margin-bottom: 12px;
                    padding-bottom: 10px;
                    border-bottom: 1px solid #E2E8F0;
                }}
                .feedback-title {{
                    font-size: 13px;
                    font-weight: 800;
                    color: #0F172A;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }}
                .badge-count {{
                    background: #EFF6FF;
                    color: #2563EB;
                    font-size: 10px;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-weight: 700;
                }}
                .filter-buttons {{
                    display: flex;
                    gap: 6px;
                    align-items: center;
                }}
                .btn-filter {{
                    background: #F1F5F9;
                    border: 1px solid #CBD5E1;
                    color: #475569;
                    padding: 4px 10px;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s;
                }}
                .btn-filter:hover {{
                    background: #E2E8F0;
                }}
                .btn-filter.active {{
                    background: #2563EB;
                    color: #FFFFFF;
                    border-color: #2563EB;
                }}
                .search-input {{
                    background: #F8FAFC;
                    border: 1px solid #CBD5E1;
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 11px;
                    color: #1E293B;
                    outline: none;
                    width: 180px;
                }}
                .search-input:focus {{
                    border-color: #2563EB;
                    background: #FFFFFF;
                }}
                
                .resp-card {{
                    background: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-left-width: 4px;
                    border-radius: 6px;
                    padding: 10px 12px;
                    margin-bottom: 8px;
                    box-shadow: 0 1px 2px rgba(0,0,0,0.02);
                    page-break-inside: avoid;
                }}
                .pdf-score-row {{
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    gap: 10px;
                    padding: 7px 0;
                    border-bottom: 1px solid #E2E8F0;
                }}
                .pdf-score-row .resp-pillars-tags {{ flex: 1; }}
                .pdf-general-score {{ flex: 0 0 auto; margin-left: auto; }}
                .pdf-verbatim-row {{ padding-top: 7px; }}
                .pdf-verbatim-row .resp-verbatim-text {{ line-height: 1.5; }}
                .resp-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    flex-wrap: wrap;
                    gap: 8px;
                    padding-bottom: 6px;
                    border-bottom: 1px solid #F1F5F9;
                }}
                .resp-meta-left {{
                    display: flex;
                    align-items: center;
                    flex-wrap: wrap;
                    gap: 6px;
                }}
                .resp-client-name {{
                    font-size: 12px;
                    font-weight: 700;
                    color: #0F172A;
                    margin-right: 4px;
                }}
                .meta-tag {{
                    background: #F1F5F9;
                    color: #475569;
                    font-size: 10.5px;
                    padding: 2px 7px;
                    border-radius: 4px;
                    font-weight: 500;
                }}
                .status-pill {{
                    font-size: 10.5px;
                    font-weight: 800;
                    padding: 3px 8px;
                    border-radius: 5px;
                }}
                .status-promotor {{ background: #DCFCE7; color: #15803D; }}
                .status-neutro {{ background: #FEF3C7; color: #B45309; }}
                .status-detrator {{ background: #FEE2E2; color: #B91C1C; }}
                .status-sem-nota {{ background: #E2E8F0; color: #475569; }}
                
                .resp-body {{
                    display: flex;
                    gap: 12px;
                    margin-top: 8px;
                    align-items: stretch;
                }}
                .resp-verbatim {{
                    background: #F8FAFC;
                    border: 1px solid #E2E8F0;
                    border-radius: 6px;
                    padding: 6px 10px;
                    flex: 1;
                }}
                .resp-verbatim-title {{
                    font-size: 10px;
                    font-weight: 700;
                    color: #64748B;
                    margin-bottom: 2px;
                    text-transform: uppercase;
                }}
                .resp-verbatim-text {{
                    font-size: 11.5px;
                    color: #1E293B;
                    line-height: 1.35;
                }}
                .resp-pillars {{
                    background: #F8FAFC;
                    border: 1px solid #E2E8F0;
                    border-radius: 6px;
                    padding: 6px 10px;
                    min-width: 250px;
                    max-width: 320px;
                }}
                .resp-pillars-title {{
                    font-size: 10px;
                    font-weight: 700;
                    color: #64748B;
                    margin-bottom: 4px;
                    text-transform: uppercase;
                }}
                .resp-pillars-tags {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 4px;
                }}
                .pilar-badge {{
                    background: #FFFFFF;
                    border: 1px solid #CBD5E1;
                    color: #334155;
                    font-size: 10px;
                    padding: 1px 6px;
                    border-radius: 4px;
                }}
                .footer-table {{
                    width: 100%;
                    margin-top: 18px;
                    border-top: 1px solid #CBD5E1;
                    padding-top: 10px;
                    page-break-inside: avoid;
                }}
                .sig-line {{
                    border-top: 1px solid #94A3B8;
                    width: 75%;
                    margin: 20px auto 4px auto;
                    text-align: center;
                    font-size: 8pt;
                    font-weight: bold;
                    color: #334155;
                }}
            </style>
            <script>
                function toggleFiltro(status, btn) {{
                    const todosBtn = document.querySelector('.btn-filter[data-status="TODOS"]');
                    
                    if (status === 'TODOS') {{
                        document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
                        btn.classList.add('active');
                    }} else {{
                        if (todosBtn) todosBtn.classList.remove('active');
                        btn.classList.toggle('active');
                        
                        const activeFilters = document.querySelectorAll('.btn-filter.active');
                        if (activeFilters.length === 0) {{
                            if (todosBtn) todosBtn.classList.add('active');
                        }}
                    }}
                    
                    pesquisarRespostas();
                }}
                
                function pesquisarRespostas() {{
                    const activeBtns = Array.from(document.querySelectorAll('.btn-filter.active'));
                    let activeStatuses = activeBtns.map(b => b.getAttribute('data-status'));
                    if (activeStatuses.length === 0 || activeStatuses.includes('TODOS')) {{
                        activeStatuses = ['TODOS'];
                    }}
                    
                    const termo = (document.getElementById('search-box').value || '').toLowerCase().trim();
                    aplicarFiltrosMultiplos(activeStatuses, termo);
                }}
                
                function aplicarFiltrosMultiplos(activeStatuses, termo) {{
                    const cards = document.querySelectorAll('.resp-card');
                    let visiveis = 0;
                    
                    const isTodos = activeStatuses.includes('TODOS');
                    const hasComFiltro = activeStatuses.includes('COMENTARIOS');
                    const statusCategorias = activeStatuses.filter(s => s === 'PROMOTOR' || s === 'NEUTRO' || s === 'DETRATOR' || s === 'SEM_NOTA');
                    
                    cards.forEach(card => {{
                        const cardStatus = card.getAttribute('data-status');
                        const cardHasCom = card.getAttribute('data-has-comment') === 'true';
                        const cardSearch = card.getAttribute('data-search') || '';
                        
                        let matchStatus = false;
                        if (isTodos) {{
                            matchStatus = true;
                        }} else if (statusCategorias.length > 0) {{
                            matchStatus = statusCategorias.includes(cardStatus);
                        }} else if (hasComFiltro) {{
                            matchStatus = true;
                        }}
                        
                        if (hasComFiltro && !cardHasCom) {{
                            matchStatus = false;
                        }}
                        
                        let matchTermo = termo === '' || cardSearch.includes(termo);
                        
                        if (matchStatus && matchTermo) {{
                            card.style.display = 'block';
                            visiveis++;
                        }} else {{
                            card.style.display = 'none';
                        }}
                    }});
                    
                    const lblCount = document.getElementById('lbl-count-visiveis');
                    if (lblCount) {{
                        lblCount.innerText = visiveis + ' exibidas';
                    }}
                }}
            </script>
        </head>
        <body>
            {header_pdf_html}

            <!-- Banner ROI SaaS -->
            <div class="roi-box">
                <div style="font-size: 10px; font-weight: 700; color: #38BDF8; text-transform: uppercase; margin-bottom: 2px;">📊 Relatório Gerencial Geral - Pós-Vendas (TSI)</div>
                <div style="font-size: 16px; font-weight: 800; margin-bottom: 4px;">Participação das respostas via WhatsApp: <span style="color:#38BDF8;">{saas_taxa:.1f}%</span></div>
                <div style="font-size: 11px; color: #94A3B8; line-height: 1.3;">
                    Percentual calculado somente com os registros do departamento, loja, mês e consultor selecionados que puderam ser vinculados ao histórico de disparos.
                </div>
            </div>

            <!-- 5 Cards no Topo: 1º Pesquisas Auditadas, 2º Índice TSI, 3º Promotores, 4º Neutros, 5º Detratores -->
            <div class="grid-kpis">
                <!-- Card 1: Pesquisas Auditadas -->
                <div class="card" style="border-top: 3px solid #1E3A8A;">
                    <div class="kpi-title">Pesquisas Auditadas</div>
                    <div class="kpi-num" style="color: #0F172A;">{total_resp}</div>
                    <div class="kpi-desc">100% Base Auditada</div>
                </div>
                <!-- Card 2: Índice TSI -->
                <div class="card" style="border-top: 3px solid {tsi_color};">
                    <div class="kpi-title">Índice TSI (%)</div>
                    <div class="kpi-num" style="color: {tsi_color};">{tsi:.1f}%</div>
                    <div class="kpi-desc">Meta Honda: ≥ 75.0</div>
                </div>
                <!-- Card 3: Promotores -->
                <div class="card" style="border-top: 3px solid #10B981;">
                    <div class="kpi-title">Promotores</div>
                    <div class="kpi-num" style="color: #10B981;">{promotores_cnt} <span style="font-size: 13px; font-weight: normal;">({promotores_pct:.1f}%)</span></div>
                    <div class="kpi-desc">Notas 9 e 10 (Satisfeitos)</div>
                </div>
                <!-- Card 4: Neutros -->
                <div class="card" style="border-top: 3px solid #F59E0B;">
                    <div class="kpi-title">Neutros</div>
                    <div class="kpi-num" style="color: #F59E0B;">{neutros_cnt} <span style="font-size: 13px; font-weight: normal;">({neutros_pct:.1f}%)</span></div>
                    <div class="kpi-desc">Notas 7 e 8 (Passivos)</div>
                </div>
                <!-- Card 5: Detratores -->
                <div class="card" style="border-top: 3px solid #EF4444;">
                    <div class="kpi-title">Detratores</div>
                    <div class="kpi-num" style="color: #EF4444;">{detratores_cnt} <span style="font-size: 13px; font-weight: normal;">({detratores_pct:.1f}%)</span></div>
                    <div class="kpi-desc">Notas 0 a 6 (Atenção)</div>
                </div>
            </div>

            <!-- Gráficos e Tabelas Centrais -->
            <div class="tsi-analysis-grid">
                <div class="card">
                    <div style="font-size: 12px; font-weight: 800; margin-bottom: 10px; color: #0F172A;">📊 Pilares da Oficina (Top2Box)</div>
                    {dim_html}
                </div>
                <div class="card">
                    <div style="font-size: 12px; font-weight: 800; margin-bottom: 10px; color: #0F172A;">📋 Distribuição das Respostas</div>
                    <div class="distribution-block">
                        <div class="distribution-title">Por Loja</div>
                        <table style="width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 10px;">
                            <colgroup><col style="width:60%;"><col style="width:20%;"><col style="width:20%;"></colgroup>
                            <thead><tr style="background:#F8FAFC; color:#64748B;"><th style="padding:5px 4px; text-align:left;">Loja</th><th style="padding:5px 4px; text-align:center;">Resp.</th><th style="padding:5px 4px; text-align:center;">TSI</th></tr></thead>
                            <tbody>{rows_lojas}</tbody>
                        </table>
                    </div>
                    <div class="distribution-block">
                        <div class="distribution-title">Por Segmento da Motocicleta</div>
                        <table style="width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 10px;">
                            <colgroup><col style="width:60%;"><col style="width:20%;"><col style="width:20%;"></colgroup>
                            <thead><tr style="background:#F8FAFC; color:#64748B;"><th style="padding:5px 4px; text-align:left;">Segmento</th><th style="padding:5px 4px; text-align:center;">Resp.</th><th style="padding:5px 4px; text-align:center;">TSI</th></tr></thead>
                            <tbody>{rows_segmentos}</tbody>
                        </table>
                    </div>
                </div>
            </div>
            <div class="card" style="margin-bottom: 12px;">
                <div style="font-size: 12px; font-weight: 800; margin-bottom: 10px; color: #0F172A;">🏆 Desempenho por Consultor Técnico</div>
                <div class="consultant-table-wrap">
                    <table class="consultant-table" style="width: 100%; min-width: {ranking_table_min_width}; border-collapse: separate; border-spacing: 0; font-size: {ranking_table_font_size};">
                        <thead>
                            <tr style="background: #F1F5F9; color: #475569; text-align: left;">
                                <th class="sticky-col" style="padding: 6px 8px; border-radius: 4px 0 0 4px;">Consultor</th>
                                <th style="padding: 6px 8px; text-align: center;">Resp.</th>
                                <th style="padding: 6px 8px; text-align: center;">TSI</th>
                                <th style="padding: 6px 8px; text-align: center;">Top2Box</th>
                                {ranking_pilar_headers}
                            </tr>
                        </thead>
                        <tbody>
                            {rows_ranking}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Seção Completa: Clientes, Verbalizações & Notas dos Pilares -->
            <div class="feedback-section">
                <div class="feedback-top-bar">
                    {feedback_top_content}
                </div>
                
                <div style="{container_scroll_style}">
                    {cards_respostas_html}
                </div>
            </div>

            {footer_pdf_html}
        </body>
        </html>
        """

    def _render_ssi_html(self, metrics, modalidades, ranking, responses, is_pdf: bool = False, loja_nome: str = "Todas as Unidades", mes_ref: str = "Todos", filtros_respostas: dict = None):
        if not metrics:
            return """
            <!DOCTYPE html>
            <html>
            <body style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif; background:#F8FAFC; text-align:center; padding:40px; color:#64748B;'>
                <h3>Nenhum dado encontrado para os filtros selecionados.</h3>
                <p>Verifique a concessionária ou o mês selecionado no painel acima.</p>
            </body>
            </html>
            """

        ssi = metrics.get('ssi', metrics.get('nps', 0.0))
        nps_recomendacao = metrics.get('nps', 0.0)
        ssi_color = "#16A34A" if ssi >= 85 else ("#2563EB" if ssi >= 70 else "#DC2626")
        total_resp = metrics.get('total_respostas', 0)
        saas_taxa = metrics.get('saas_taxa_resp', 0.0)
        
        promotores_cnt = metrics.get('promotores_count', 0)
        neutros_cnt = metrics.get('neutros_count', 0)
        detratores_cnt = metrics.get('detratores_count', 0)
        sem_nota_cnt = metrics.get('sem_nota_count', 0)
        
        promotores_pct = metrics.get('promotores_pct', 0.0)
        neutros_pct = metrics.get('neutros_pct', 0.0)
        detratores_pct = metrics.get('detratores_pct', 0.0)

        coments_cnt = sum(1 for r in responses if r.get('tem_comentario'))

        rows_mod = ""
        for m in modalidades:
            rows_mod += f"""
            <tr style='border-bottom: 1px solid #E2E8F0;'>
                <td style='padding: 6px 8px; font-weight: 600; color: #1E293B;'>{m.get('nome')}</td>
                <td style='padding: 6px 8px; text-align: center; color: #475569;'>{m.get('qtd')}</td>
                <td style='padding: 6px 8px; text-align: center; font-weight: bold; color: #2563EB;'>{m.get('ssi', 0.0):.1f}</td>
                <td style='padding: 6px 8px; text-align: center; font-weight: bold; color: #7C3AED;'>{m.get('nps', 0.0):.1f}</td>
            </tr>
            """
        if not rows_mod:
            rows_mod = "<tr><td colspan='4' style='padding: 10px; text-align: center; color: #94A3B8;'>Nenhuma modalidade registrada no período.</td></tr>"

        ranking_pilares = list(metrics.get('dimensoes', {}).keys())
        ranking_pilar_min_width = "56px" if is_pdf else "84px"
        ranking_table_min_width = "100%" if is_pdf else "920px"
        ranking_table_font_size = "7.5px" if is_pdf else "10px"
        ranking_pilar_headers = "".join(
            f"<th title='{nome}' style='padding: 6px 4px; text-align: center; min-width: {ranking_pilar_min_width}; white-space: normal;'>{nome}</th>"
            for nome in ranking_pilares
        )
        rows_ranking = ""
        ranking_list = ranking if is_pdf else ranking[:8]
        for c in ranking_list:
            pilar_cells = ""
            for pilar_nome in ranking_pilares:
                pilar_valor = c.get('pilares', {}).get(pilar_nome)
                pilar_texto = "-" if pilar_valor is None else f"{pilar_valor:.1f}%"
                pilar_cor = "#94A3B8" if pilar_valor is None else ("#16A34A" if pilar_valor >= 85 else ("#2563EB" if pilar_valor >= 70 else "#DC2626"))
                pilar_cells += f"<td style='padding: 6px 5px; text-align: center; font-weight: 600; color: {pilar_cor};'>{pilar_texto}</td>"
            rows_ranking += f"""
            <tr style='border-bottom: 1px solid #E2E8F0;'>
                <td style='padding: 6px 8px; font-weight: 600; color: #1E293B;'>{c.get('nome')}</td>
                <td style='padding: 6px 8px; text-align: center; color: #475569;'>{c.get('respostas')}</td>
                <td style='padding: 6px 8px; text-align: center; font-weight: bold; color: #2563EB;'>{c.get('ssi', 0.0):.1f}</td>
                <td style='padding: 6px 8px; text-align: center; color: #059669; font-weight: 600;'>{c.get('media', 0.0):.1f}%</td>
                <td style='padding: 6px 8px; text-align: center; color: #7C3AED; font-weight: 600;'>{c.get('nps', 0.0):.1f}</td>
                {pilar_cells}
            </tr>
            """
        if not rows_ranking:
            rows_ranking = f"<tr><td colspan='{5 + len(ranking_pilares)}' style='padding: 10px; text-align: center; color: #94A3B8;'>Nenhum vendedor registrado no período.</td></tr>"

        dim_html = ""
        for k, v in metrics.get('dimensoes', {}).items():
            c_dim = "#16A34A" if v >= 85 else ("#2563EB" if v >= 70 else "#DC2626")
            dim_html += f"""
            <div style='margin-bottom: 8px;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px;'>
                    <span style='font-size: 11px; color: #334155; font-weight: 600;'>{k}</span>
                    <span style='font-size: 12px; font-weight: bold; color: {c_dim};'>{v:.1f}%</span>
                </div>
                <div style='background-color: #E2E8F0; height: 5px; border-radius: 3px; overflow: hidden;'>
                    <div style='background-color: {c_dim}; width: {v:.1f}%; height: 100%; border-radius: 3px;'></div>
                </div>
            </div>
            """

        responses_para_cards = responses
        filtro_desc = "Todos os Feedbacks"
        if is_pdf:
            responses_para_cards, filtro_desc = self._filtrar_respostas_por_estado(responses, filtros_respostas)

        cards_respostas_html = ""
        for r in responses_para_cards:
            st = r.get('status', 'NEUTRO')
            nota = r.get('nota', 0)
            tem_c = "true" if r.get('tem_comentario') else "false"
            
            if st == "PROMOTOR":
                badge_st = f"<span class='status-pill status-promotor'>🟢 PROMOTOR • Nota {nota}</span>"
                border_color = "#10B981"
            elif st == "NEUTRO":
                badge_st = f"<span class='status-pill status-neutro'>🟡 NEUTRO • Nota {nota}</span>"
                border_color = "#F59E0B"
            elif st == "DETRATOR":
                badge_st = f"<span class='status-pill status-detrator'>🔴 DETRATOR • Nota {nota}</span>"
                border_color = "#EF4444"
            else:
                badge_st = "<span class='status-pill status-sem-nota'>⚪ SEM NOTA DE RECOMENDAÇÃO</span>"
                border_color = "#94A3B8"

            chassi_badge = f"<span class='meta-tag'>🏷️ Chassi: <b>{r.get('chassi')}</b></span>" if r.get('chassi') and r.get('chassi') != '-' else ""
            mod_badge = f"<span class='meta-tag'>🏍️ <b>{r.get('modelo')}</b></span>" if r.get('modelo') and r.get('modelo') != '-' else ""
            modalidade_badge = f"<span class='meta-tag'>💳 {r.get('modalidade')}</span>" if r.get('modalidade') and r.get('modalidade') != '-' else ""
            loja_badge = f"<span class='meta-tag'>🏢 {r.get('loja')}</span>" if r.get('loja') and r.get('loja') != '-' else ""

            pilares_tags = ""
            for p_nome, p_val in r.get('notas_pilares', {}).items():
                if p_val != "-":
                    pilares_tags += f"<span class='pilar-badge'>{p_nome}: <b>{p_val}</b></span>"

            search_text = f"{r.get('cliente')} {r.get('chassi')} {r.get('modelo')} {r.get('modalidade')} {r.get('comentario')}".lower().replace('"', '&quot;')

            if is_pdf:
                comentario_pdf = self._formatar_verbalizacao_pdf(r.get('comentario'))
                cards_respostas_html += f"""
            <div class="resp-card pdf-response-card" style="border-left-color: {border_color};">
                <div class="resp-header">
                    <div class="resp-meta-left">
                        <span class="resp-client-name">👤 {r.get('cliente')}</span>
                        <span class="meta-tag">📅 {r.get('data')}</span>
                    </div>
                </div>
                <div class="pdf-score-row">
                    <div class="resp-pillars-tags">{pilares_tags if pilares_tags else "<span style='color:#94A3B8;font-size:10px;'>Padrão Geral</span>"}</div>
                    <div class="pdf-general-score">{badge_st}</div>
                </div>
                <div class="pdf-verbatim-row">
                    <div class="resp-verbatim-title">💬 Verbalização / Feedback do Comprador:</div>
                    <div class="resp-verbatim-text">{comentario_pdf}</div>
                </div>
            </div>
            """
            else:
                cards_respostas_html += f"""
            <div class="resp-card" data-status="{st}" data-has-comment="{tem_c}" data-search="{search_text}" style="border-left-color: {border_color};">
                <div class="resp-header">
                    <div class="resp-meta-left">
                        <span class="resp-client-name">👤 {r.get('cliente')}</span>
                        <span class="meta-tag">📅 {r.get('data')}</span>
                        {chassi_badge}
                        {mod_badge}
                        {modalidade_badge}
                        {loja_badge}
                    </div>
                    <div>
                        {badge_st}
                    </div>
                </div>
                <div class="resp-body">
                    <div class="resp-verbatim">
                        <div class="resp-verbatim-title">💬 Verbalização / Feedback do Comprador:</div>
                        <div class="resp-verbatim-text">{r.get('comentario')}</div>
                    </div>
                    <div class="resp-pillars">
                        <div class="resp-pillars-title">📊 Avaliação das Etapas:</div>
                        <div class="resp-pillars-tags">
                            {pilares_tags if pilares_tags else "<span style='color:#94A3B8; font-size:10px;'>Padrão Geral</span>"}
                        </div>
                    </div>
                </div>
            </div>
            """

        if not cards_respostas_html:
            cards_respostas_html = "<div style='padding: 20px; text-align: center; color: #94A3B8; font-size: 11px;'>Nenhum registro encontrado para os filtros aplicados.</div>"

        import datetime
        data_hora_emissao = datetime.datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
        periodo_label = mes_ref if (mes_ref and mes_ref != "Todos") else "Histórico Consolidado (Todos os Períodos)"

        header_pdf_html = f"""
        <div class="header-box">
            <div>
                <span class="dept-badge-ssi" style="background:#B91C1C; color:#FFFFFF; font-size:7.5pt; font-weight:bold; padding:3px 8px; border-radius:4px; text-transform:uppercase; display:inline-block;">COMERCIAL & VENDAS (SSI)</span>
                <h1 class="logo-title">RELATÓRIO DE QUALIDADE SSI</h1>
                <div class="store-name">{loja_nome}</div>
            </div>
            <div class="meta-info">
                <div class="meta-badge" style="background:#FEF2F2; color:#B91C1C;">📅 Período: {periodo_label}</div><br>
                <b>Data de Extração:</b> {data_hora_emissao}<br>
                <b>Sistema:</b> SaaS Intelligence
            </div>
        </div>
        """ if is_pdf else ""

        footer_pdf_html = """
        <table class="footer-table">
            <tr>
                <td style="width: 50%; text-align: center;">
                    <div class="sig-line">Gerente Comercial / Vendas</div>
                </td>
                <td style="width: 50%; text-align: center;">
                    <div class="sig-line">Diretoria Executiva</div>
                </td>
            </tr>
            <tr>
                <td colspan="2" style="text-align: center; padding-top: 8px; font-size: 7.5pt; color: #94A3B8;">
                    Documento gerado automaticamente pelo SaaS Intelligence. Métricas auditadas de qualidade.
                </td>
            </tr>
        </table>
        """ if is_pdf else ""

        desc_filtro_html = f"<div style='font-size: 8pt; color: #B91C1C; font-weight: 700; margin-top: 3px;'>🔍 Filtro Aplicado: {filtro_desc}</div>" if (filtro_desc and filtro_desc != "Todos os Feedbacks") else ""
        feedback_top_content = f"""
        <div class="feedback-title">
            <span>📋 Auditoria de Respostas & Verbalizações dos Clientes</span>
            <span class="badge-count" style="background:#FEF2F2; color:#B91C1C;">{len(responses_para_cards)} de {len(responses)} registros</span>
        </div>
        <div style="font-size: 8.5pt; color: #64748B; font-weight: 600;">
            Consolidado Geral de Feedbacks & Pilares do Processo Comercial
        </div>
        {desc_filtro_html}
        """ if is_pdf else f"""
        <div class="feedback-title">
            <span>📋 Compradores & Feedbacks Auditados</span>
            <span class="badge-count" id="lbl-count-visiveis">{len(responses)} exibidas</span>
        </div>
        <div class="filter-buttons">
            <input type="text" id="search-box" class="search-input" placeholder="🔍 Buscar cliente, chassi, modelo..." oninput="pesquisarRespostas()">
            <button class="btn-filter active" data-status="TODOS" onclick="toggleFiltro('TODOS', this)">Todos ({len(responses)})</button>
            <button class="btn-filter" data-status="PROMOTOR" onclick="toggleFiltro('PROMOTOR', this)">Promotores ({promotores_cnt})</button>
            <button class="btn-filter" data-status="NEUTRO" onclick="toggleFiltro('NEUTRO', this)">Neutros ({neutros_cnt})</button>
            <button class="btn-filter" data-status="DETRATOR" onclick="toggleFiltro('DETRATOR', this)">Detratores ({detratores_cnt})</button>
            <button class="btn-filter" data-status="SEM_NOTA" onclick="toggleFiltro('SEM_NOTA', this)">Sem nota ({sem_nota_cnt})</button>
            <button class="btn-filter" data-status="COMENTARIOS" onclick="toggleFiltro('COMENTARIOS', this)">Com Feedback ({coments_cnt})</button>
        </div>
        """

        container_scroll_style = "max-height: none; overflow: visible;" if is_pdf else "max-height: 480px; overflow-y: auto; padding-right: 4px;"
        body_bg = "#FFFFFF" if is_pdf else "#F8FAFC"
        body_pad = "0px" if is_pdf else "12px 14px"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{ size: A4 portrait; margin: 8mm; }}
                * {{ box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                html, body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
                    background: {body_bg}; 
                    margin: 0; 
                    padding: {body_pad}; 
                    color: #1E293B; 
                }}
                .header-box {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-bottom: 2px solid #E2E8F0;
                    padding-bottom: 10px;
                    margin-bottom: 12px;
                    page-break-inside: avoid;
                }}
                .logo-title {{
                    font-size: 15pt;
                    font-weight: 800;
                    color: #0F172A;
                    margin: 4px 0 2px 0;
                    letter-spacing: -0.3px;
                }}
                .store-name {{
                    font-size: 10pt;
                    font-weight: bold;
                    color: #475569;
                }}
                .meta-info {{
                    text-align: right;
                    font-size: 8pt;
                    color: #475569;
                }}
                .meta-badge {{
                    background-color: #EFF6FF;
                    color: #1D4ED8;
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 8pt;
                    display: inline-block;
                    margin-bottom: 3px;
                }}
                .roi-box {{ 
                    background: linear-gradient(135deg, #7F1D1D, #991B1B); 
                    color: white; 
                    border-radius: 8px; 
                    padding: 12px 16px; 
                    margin-bottom: 12px; 
                    page-break-inside: avoid;
                }}
                .grid-kpis {{ 
                    display: grid; 
                    grid-template-columns: repeat(6, minmax(0, 1fr)); 
                    gap: 10px; 
                    margin-bottom: 12px; 
                    page-break-inside: avoid;
                }}
                .card {{ 
                    background: #FFFFFF; 
                    border: 1px solid #E2E8F0; 
                    border-radius: 8px; 
                    padding: 10px 14px; 
                    box-shadow: 0 1px 2px rgba(0,0,0,0.03); 
                    page-break-inside: avoid;
                }}
                .kpi-title {{ 
                    font-size: 10px; 
                    font-weight: 700; 
                    color: #64748B; 
                    text-transform: uppercase; 
                    letter-spacing: 0.4px; 
                }}
                .kpi-num {{ 
                    font-size: 20px; 
                    font-weight: 800; 
                    margin: 3px 0; 
                }}
                .kpi-desc {{ 
                    font-size: 10px; 
                    color: #94A3B8; 
                }}
                .two-col {{ 
                    display: grid; 
                    grid-template-columns: 1fr 1fr; 
                    gap: 12px; 
                    margin-bottom: 12px; 
                    page-break-inside: avoid;
                }}
                
                /* Componente de Respostas & Verbalizações */
                .feedback-section {{
                    background: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-radius: 8px;
                    padding: 14px 16px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
                    margin-bottom: 14px;
                }}
                .feedback-top-bar {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    flex-wrap: wrap;
                    gap: 10px;
                    margin-bottom: 12px;
                    padding-bottom: 10px;
                    border-bottom: 1px solid #E2E8F0;
                }}
                .feedback-title {{
                    font-size: 13px;
                    font-weight: 800;
                    color: #0F172A;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }}
                .badge-count {{
                    background: #EFF6FF;
                    color: #2563EB;
                    font-size: 10px;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-weight: 700;
                }}
                .filter-buttons {{
                    display: flex;
                    gap: 6px;
                    align-items: center;
                }}
                .btn-filter {{
                    background: #F1F5F9;
                    border: 1px solid #CBD5E1;
                    color: #475569;
                    padding: 4px 10px;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s;
                }}
                .btn-filter:hover {{
                    background: #E2E8F0;
                }}
                .btn-filter.active {{
                    background: #2563EB;
                    color: #FFFFFF;
                    border-color: #2563EB;
                }}
                .search-input {{
                    background: #F8FAFC;
                    border: 1px solid #CBD5E1;
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 11px;
                    color: #1E293B;
                    outline: none;
                    width: 180px;
                }}
                .search-input:focus {{
                    border-color: #2563EB;
                    background: #FFFFFF;
                }}
                
                .resp-card {{
                    background: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-left-width: 4px;
                    border-radius: 6px;
                    padding: 10px 12px;
                    margin-bottom: 8px;
                    box-shadow: 0 1px 2px rgba(0,0,0,0.02);
                    page-break-inside: avoid;
                }}
                .pdf-score-row {{
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    gap: 10px;
                    padding: 7px 0;
                    border-bottom: 1px solid #E2E8F0;
                }}
                .pdf-score-row .resp-pillars-tags {{ flex: 1; }}
                .pdf-general-score {{ flex: 0 0 auto; margin-left: auto; }}
                .pdf-verbatim-row {{ padding-top: 7px; }}
                .pdf-verbatim-row .resp-verbatim-text {{ line-height: 1.5; }}
                .resp-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    flex-wrap: wrap;
                    gap: 8px;
                    padding-bottom: 6px;
                    border-bottom: 1px solid #F1F5F9;
                }}
                .resp-meta-left {{
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    flex-wrap: wrap;
                }}
                .resp-client-name {{
                    font-weight: 800;
                    color: #1E293B;
                    font-size: 11px;
                }}
                .meta-tag {{
                    font-size: 10px;
                    color: #64748B;
                    background: #F1F5F9;
                    padding: 2px 6px;
                    border-radius: 4px;
                }}
                .status-pill {{
                    font-size: 10.5px;
                    font-weight: 800;
                    padding: 3px 8px;
                    border-radius: 5px;
                }}
                .status-promotor {{ background: #DCFCE7; color: #15803D; }}
                .status-neutro {{ background: #FEF3C7; color: #B45309; }}
                .status-detrator {{ background: #FEE2E2; color: #B91C1C; }}
                .status-sem-nota {{ background: #E2E8F0; color: #475569; }}
                
                .resp-body {{
                    display: flex;
                    gap: 12px;
                    margin-top: 8px;
                    align-items: stretch;
                }}
                .resp-verbatim {{
                    background: #F8FAFC;
                    border: 1px solid #E2E8F0;
                    border-radius: 6px;
                    padding: 6px 10px;
                    flex: 1;
                }}
                .resp-verbatim-title {{
                    font-size: 10px;
                    font-weight: 700;
                    color: #64748B;
                    margin-bottom: 2px;
                    text-transform: uppercase;
                }}
                .resp-verbatim-text {{
                    font-size: 11.5px;
                    color: #1E293B;
                    line-height: 1.35;
                }}
                .resp-pillars {{
                    background: #F8FAFC;
                    border: 1px solid #E2E8F0;
                    border-radius: 6px;
                    padding: 6px 10px;
                    min-width: 250px;
                    max-width: 320px;
                }}
                .resp-pillars-title {{
                    font-size: 10px;
                    font-weight: 700;
                    color: #64748B;
                    margin-bottom: 4px;
                    text-transform: uppercase;
                }}
                .resp-pillars-tags {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 4px;
                }}
                .pilar-badge {{
                    background: #FFFFFF;
                    border: 1px solid #CBD5E1;
                    color: #334155;
                    font-size: 10px;
                    padding: 1px 6px;
                    border-radius: 4px;
                }}
                .footer-table {{
                    width: 100%;
                    margin-top: 18px;
                    border-top: 1px solid #CBD5E1;
                    padding-top: 10px;
                    page-break-inside: avoid;
                }}
                .sig-line {{
                    border-top: 1px solid #94A3B8;
                    width: 75%;
                    margin: 20px auto 4px auto;
                    text-align: center;
                    font-size: 8pt;
                    font-weight: bold;
                    color: #334155;
                }}
            </style>
            <script>
                function toggleFiltro(status, btn) {{
                    const todosBtn = document.querySelector('.btn-filter[data-status="TODOS"]');
                    
                    if (status === 'TODOS') {{
                        document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
                        btn.classList.add('active');
                    }} else {{
                        if (todosBtn) todosBtn.classList.remove('active');
                        btn.classList.toggle('active');
                        
                        const activeFilters = document.querySelectorAll('.btn-filter.active');
                        if (activeFilters.length === 0) {{
                            if (todosBtn) todosBtn.classList.add('active');
                        }}
                    }}
                    
                    pesquisarRespostas();
                }}
                
                function pesquisarRespostas() {{
                    const activeBtns = Array.from(document.querySelectorAll('.btn-filter.active'));
                    let activeStatuses = activeBtns.map(b => b.getAttribute('data-status'));
                    if (activeStatuses.length === 0 || activeStatuses.includes('TODOS')) {{
                        activeStatuses = ['TODOS'];
                    }}
                    
                    const termo = (document.getElementById('search-box').value || '').toLowerCase().trim();
                    aplicarFiltrosMultiplos(activeStatuses, termo);
                }}
                
                function aplicarFiltrosMultiplos(activeStatuses, termo) {{
                    const cards = document.querySelectorAll('.resp-card');
                    let visiveis = 0;
                    
                    const isTodos = activeStatuses.includes('TODOS');
                    const hasComFiltro = activeStatuses.includes('COMENTARIOS');
                    const statusCategorias = activeStatuses.filter(s => s === 'PROMOTOR' || s === 'NEUTRO' || s === 'DETRATOR' || s === 'SEM_NOTA');
                    
                    cards.forEach(card => {{
                        const cardStatus = card.getAttribute('data-status');
                        const cardHasCom = card.getAttribute('data-has-comment') === 'true';
                        const cardSearch = card.getAttribute('data-search') || '';
                        
                        let matchStatus = false;
                        if (isTodos) {{
                            matchStatus = true;
                        }} else if (statusCategorias.length > 0) {{
                            matchStatus = statusCategorias.includes(cardStatus);
                        }} else if (hasComFiltro) {{
                            matchStatus = true;
                        }}
                        
                        if (hasComFiltro && !cardHasCom) {{
                            matchStatus = false;
                        }}
                        
                        let matchTermo = termo === '' || cardSearch.includes(termo);
                        
                        if (matchStatus && matchTermo) {{
                            card.style.display = 'block';
                            visiveis++;
                        }} else {{
                            card.style.display = 'none';
                        }}
                    }});
                    
                    const lblCount = document.getElementById('lbl-count-visiveis');
                    if (lblCount) {{
                        lblCount.innerText = visiveis + ' exibidas';
                    }}
                }}
            </script>
        </head>
        <body>
            {header_pdf_html}

            <!-- Banner ROI SaaS -->
            <div class="roi-box">
                <div style="font-size: 10px; font-weight: 700; color: #FCA5A5; text-transform: uppercase; margin-bottom: 2px;">📊 Relatório Gerencial Geral - Comercial & Vendas (SSI)</div>
                <div style="font-size: 16px; font-weight: 800; margin-bottom: 4px;">Participação das respostas via WhatsApp: <span style="color:#FCA5A5;">{saas_taxa:.1f}%</span></div>
                <div style="font-size: 11px; color: #FECACA; line-height: 1.3;">
                    Percentual calculado somente com os registros da loja, mês e vendedor selecionados que puderam ser vinculados ao histórico de disparos.
                </div>
            </div>

            <!-- SSI oficial e NPS de recomendação são indicadores distintos. -->
            <div class="grid-kpis">
                <!-- Card 1: Compradores Auditados -->
                <div class="card" style="border-top: 3px solid #1E3A8A;">
                    <div class="kpi-title">Compradores Auditados</div>
                    <div class="kpi-num" style="color: #0F172A;">{total_resp}</div>
                    <div class="kpi-desc">100% Base Auditada</div>
                </div>
                <!-- Card 2: Índice SSI -->
                <div class="card" style="border-top: 3px solid {ssi_color};">
                    <div class="kpi-title">Índice SSI (%)</div>
                    <div class="kpi-num" style="color: {ssi_color};">{ssi:.1f}%</div>
                    <div class="kpi-desc">Satisfação Geral • Meta Honda: ≥ 85.0</div>
                </div>
                <!-- Card 3: NPS de Recomendação -->
                <div class="card" style="border-top: 3px solid #7C3AED;">
                    <div class="kpi-title">NPS Recomendação</div>
                    <div class="kpi-num" style="color: #7C3AED;">{nps_recomendacao:.1f}</div>
                    <div class="kpi-desc">Promotores menos Detratores</div>
                </div>
                <!-- Card 4: Promotores -->
                <div class="card" style="border-top: 3px solid #10B981;">
                    <div class="kpi-title">Promotores</div>
                    <div class="kpi-num" style="color: #10B981;">{promotores_cnt} <span style="font-size: 13px; font-weight: normal;">({promotores_pct:.1f}%)</span></div>
                    <div class="kpi-desc">Notas 9 e 10 (Satisfeitos)</div>
                </div>
                <!-- Card 5: Neutros -->
                <div class="card" style="border-top: 3px solid #F59E0B;">
                    <div class="kpi-title">Neutros</div>
                    <div class="kpi-num" style="color: #F59E0B;">{neutros_cnt} <span style="font-size: 13px; font-weight: normal;">({neutros_pct:.1f}%)</span></div>
                    <div class="kpi-desc">Notas 7 e 8 (Passivos)</div>
                </div>
                <!-- Card 6: Detratores -->
                <div class="card" style="border-top: 3px solid #EF4444;">
                    <div class="kpi-title">Detratores</div>
                    <div class="kpi-num" style="color: #EF4444;">{detratores_cnt} <span style="font-size: 13px; font-weight: normal;">({detratores_pct:.1f}%)</span></div>
                    <div class="kpi-desc">Notas 0 a 6 (Atenção)</div>
                </div>
            </div>

            <!-- Gráficos e Tabelas Centrais -->
            <div class="two-col">
                <div class="card">
                    <div style="font-size: 12px; font-weight: 800; margin-bottom: 10px; color: #0F172A;">🎯 Pilares do Processo Comercial</div>
                    {dim_html}
                </div>
                <div class="card">
                    <div style="font-size: 12px; font-weight: 800; margin-bottom: 10px; color: #0F172A;">💳 Desempenho por Modalidade</div>
                    <table style="width: 100%; border-collapse: collapse; font-size: 11px;">
                        <thead>
                            <tr style="background: #F1F5F9; color: #475569; text-align: left;">
                                <th style="padding: 6px 8px; border-radius: 4px 0 0 4px;">Modalidade</th>
                                <th style="padding: 6px 8px; text-align: center;">Resp.</th>
                                <th style="padding: 6px 8px; text-align: center;">SSI</th>
                                <th style="padding: 6px 8px; text-align: center; border-radius: 0 4px 4px 0;">NPS</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows_mod}
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card" style="margin-bottom: 12px;">
                <div style="font-size: 12px; font-weight: 800; margin-bottom: 10px; color: #0F172A;">🏆 Desempenho por Vendedor</div>
                <div style="overflow-x: auto; width: 100%;">
                <table style="width: 100%; min-width: {ranking_table_min_width}; border-collapse: collapse; font-size: {ranking_table_font_size};">
                    <thead>
                        <tr style="background: #F1F5F9; color: #475569; text-align: left;">
                            <th style="padding: 6px 8px; border-radius: 4px 0 0 4px;">Vendedor</th>
                            <th style="padding: 6px 8px; text-align: center;">Resp.</th>
                            <th style="padding: 6px 8px; text-align: center;">SSI</th>
                            <th style="padding: 6px 8px; text-align: center;">Recomendação T2B</th>
                            <th style="padding: 6px 8px; text-align: center;">NPS</th>
                            {ranking_pilar_headers}
                        </tr>
                    </thead>
                    <tbody>
                        {rows_ranking}
                    </tbody>
                </table>
                </div>
            </div>

            <!-- Seção Completa: Compradores, Feedbacks & Notas dos Pilares -->
            <div class="feedback-section">
                <div class="feedback-top-bar">
                    {feedback_top_content}
                </div>
                
                <div style="{container_scroll_style}">
                    {cards_respostas_html}
                </div>
            </div>

            {footer_pdf_html}
        </body>
        </html>
        """

    def exportar_pdf_executivo(self):
        dept_idx = self.combo_dept.currentIndex()
        loja_nome = self.combo_loja.currentText()
        mes_ref = self.combo_mes.currentText()

        dept_sigla = "TSI" if dept_idx == 0 else "SSI"
        dept_desc = "Pós-Vendas (TSI)" if dept_idx == 0 else "Vendas (SSI)"

        default_filename = f"Relatorio_Qualidade_{dept_sigla}_{mes_ref.replace('/', '-')}.pdf"
        filepath, _ = QFileDialog.getSaveFileName(self, f"Salvar Relatório de Qualidade {dept_sigla}", default_filename, "PDF Files (*.pdf)")
        
        if not filepath:
            return

        # Captura os filtros ativos no painel web (Neutros, Detratores, Promotores, Busca etc.)
        filtros_webview = self._obter_filtros_ativos_webview()

        if dept_idx == 0:
            metrics, ranking, detratores, responses = self._calcular_metricas_tsi()
            html = self._render_tsi_html(metrics, ranking, responses, is_pdf=True, loja_nome=loja_nome, mes_ref=mes_ref, filtros_respostas=filtros_webview)
        else:
            metrics, modalidades, ranking, detratores, responses = self._calcular_metricas_ssi()
            html = self._render_ssi_html(metrics, modalidades, ranking, responses, is_pdf=True, loja_nome=loja_nome, mes_ref=mes_ref, filtros_respostas=filtros_webview)

        sucesso = PDFReportGenerator.generate_comparativo_pdf(filepath, html)

        if sucesso:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Relatório Gerado com Sucesso")
            msg_box.setText(f"O Relatório de Qualidade {dept_sigla} foi gerado com sucesso!")
            msg_box.setInformativeText(f"Arquivo salvo em:\n{filepath}\n\nDeseja abrir o arquivo agora?")
            btn_abrir = msg_box.addButton("Abrir PDF", QMessageBox.ButtonRole.AcceptRole)
            btn_ok = msg_box.addButton("Fechar", QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()

            if msg_box.clickedButton() == btn_abrir:
                QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))
        else:
            QMessageBox.critical(self, "Erro na Geração", "Não foi possível gerar o arquivo PDF.")
