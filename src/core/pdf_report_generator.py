import os
import sys
import datetime
import re
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPageSize, QPageLayout
from PyQt6.QtCore import QMarginsF, QEventLoop

class PDFReportGenerator:
    """
    Gerador de Relatórios Executivos em PDF de alta definição e fidelidade visual.
    Utiliza motor Chromium (QWebEnginePage) para renderização vetorial perfeita,
    respeitando margens exatas, cores, cards de KPI, gráficos de pilares,
    feedbacks e verbalizações completas dos clientes.
    """

    @staticmethod
    def _render_html_to_pdf(html_content: str, output_path: str) -> bool:
        """
        Renderiza HTML em PDF A4 de alta definição com margens calibradas em 8mm.
        """
        try:
            from PyQt6.QtWebEngineCore import QWebEnginePage
            
            # Assegura que o diretório de destino existe
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

            app = QApplication.instance()
            if not app:
                app = QApplication(sys.argv)

            page = QWebEnginePage()
            page.setHtml(html_content)

            # Aguarda o carregamento do DOM
            load_loop = QEventLoop()
            page.loadFinished.connect(lambda ok: load_loop.quit())
            load_loop.exec()

            # Configura layout de página A4 com margens otimizadas de 8mm
            layout = QPageLayout(
                QPageSize(QPageSize.PageSizeId.A4),
                QPageLayout.Orientation.Portrait,
                QMarginsF(8.0, 8.0, 8.0, 8.0),
                QPageLayout.Unit.Millimeter
            )

            # Imprime via Chromium
            pdf_loop = QEventLoop()
            sucesso_flag = [False]

            def on_pdf_finished(path, success):
                sucesso_flag[0] = success
                pdf_loop.quit()

            page.pdfPrintingFinished.connect(on_pdf_finished)
            page.printToPdf(output_path, layout)
            pdf_loop.exec()

            return sucesso_flag[0] and os.path.exists(output_path) and os.path.getsize(output_path) > 0

        except Exception as e:
            print(f"[PDF_GEN] Erro ao renderizar PDF via WebEngine: {e}")
            return False

    @classmethod
    def generate_comparativo_pdf(cls, output_pdf_path: str, html_content: str) -> bool:
        """
        Gera o PDF que é o espelho exato do Relatório Gerencial Geral.
        """
        return cls._render_html_to_pdf(html_content, output_pdf_path)

    @classmethod
    def generate_tsi_report(cls, output_pdf_path: str, loja_nome: str, mes_ref: str, metrics: dict, ranking_consultores: list, detratores: list) -> bool:
        """
        Gera Relatório Executivo do Pós-Vendas (TSI) com layout moderno e proporcional.
        """
        try:
            tsi = metrics.get('tsi', metrics.get('nps', 0.0))
            tsi_color = "#16A34A" if tsi >= 75 else ("#2563EB" if tsi >= 50 else "#DC2626")
            
            top2box = metrics.get('top2box', 0.0)
            total_resp = metrics.get('total_respostas', 0)
            
            promotores_pct = metrics.get('promotores_pct', 0.0)
            neutros_pct = metrics.get('neutros_pct', 0.0)
            detratores_pct = metrics.get('detratores_pct', 0.0)
            
            promotores_count = metrics.get('promotores_count', int(round((promotores_pct / 100.0) * total_resp)))
            neutros_count = metrics.get('neutros_count', int(round((neutros_pct / 100.0) * total_resp)))
            detratores_count = metrics.get('detratores_count', total_resp - promotores_count - neutros_count if (promotores_count + neutros_count <= total_resp) else int(round((detratores_pct / 100.0) * total_resp)))
            if detratores_count < 0: detratores_count = 0
            
            saas_taxa_resp = metrics.get('saas_taxa_resp', 0.0)
            
            # Linhas de Consultores
            rows_ranking = ""
            for cons in ranking_consultores:
                nome = cons.get('nome', 'N/D')
                resp = cons.get('respostas', 0)
                nps_c = cons.get('tsi', cons.get('nps', 0.0))
                media = cons.get('media', 0.0)
                c_color = "#16A34A" if nps_c >= 75 else ("#2563EB" if nps_c >= 50 else "#DC2626")
                rows_ranking += f"""
                <tr style="border-bottom: 1px solid #E2E8F0;">
                    <td style="padding: 6px 8px; font-weight: 600; color: #1E293B;">{nome}</td>
                    <td style="padding: 6px 8px; text-align: center; color: #475569;">{resp}</td>
                    <td style="padding: 6px 8px; text-align: center; font-weight: bold; color: {c_color};">{nps_c:.1f}</td>
                    <td style="padding: 6px 8px; text-align: center; color: #059669; font-weight: 600;">{media:.1f}%</td>
                </tr>
                """
            if not rows_ranking:
                rows_ranking = "<tr><td colspan='4' style='padding: 10px; text-align:center; color:#94A3B8;'>Nenhum consultor registrado no período selecionado.</td></tr>"

            # Linhas de Detratores
            rows_detratores = ""
            for d in detratores[:12]:
                data_d = d.get('data', '-')
                cli = d.get('cliente', 'Cliente Auditado')
                fone = d.get('telefone', '')
                if not fone or fone in ['S/N', 'N/D', 'None', '-']:
                    fone_html = "<span style='color: #94A3B8; font-size: 8.5pt;'>-</span>"
                else:
                    fone_clean = re.sub(r'\D', '', str(fone))
                    if len(fone_clean) == 11:
                        fone_fmt = f"({fone_clean[:2]}) {fone_clean[2:7]}-{fone_clean[7:]}"
                    elif len(fone_clean) == 10:
                        fone_fmt = f"({fone_clean[:2]}) {fone_clean[2:6]}-{fone_clean[6:]}"
                    else:
                        fone_fmt = str(fone)
                    fone_html = f"<span style='background:#EFF6FF; color:#1E40AF; padding:2px 6px; border-radius:4px; font-weight:600; font-size:8pt;'>📞 {fone_fmt}</span>"
                
                os_num = d.get('os', '-')
                cat_prod = d.get('categoria', '')
                os_html = f"<span style='background:#F1F5F9; color:#475569; padding:2px 6px; border-radius:4px; font-weight:600; font-size:8pt;'>{os_num}</span>"
                if cat_prod:
                    os_html += f"<br><span style='font-size: 7.5pt; color: #64748B;'>{cat_prod}</span>"
                nota = d.get('nota', 0)
                motivo = d.get('motivo', 'Sem detalhes')
                
                rows_detratores += f"""
                <tr style="border-bottom: 1px solid #E2E8F0;">
                    <td style="padding: 6px 8px; text-align: center; color: #475569; font-size: 8.5pt;">{data_d}</td>
                    <td style="padding: 6px 8px; font-weight: 700; color: #0F172A;">{cli}</td>
                    <td style="padding: 6px 8px; text-align: center;">{fone_html}</td>
                    <td style="padding: 6px 8px; text-align: center;">{os_html}</td>
                    <td style="padding: 6px 8px; text-align: center;"><span style="background:#FEE2E2; color:#B91C1C; font-weight:800; font-size:8.5pt; padding:2px 6px; border-radius:4px;">Nota {nota}</span></td>
                    <td style="padding: 6px 8px; color: #334155; font-size: 8.5pt;">{motivo}</td>
                </tr>
                """
            if not rows_detratores:
                rows_detratores = "<tr><td colspan='6' style='text-align:center; color:#16A34A; font-weight: bold; padding: 12px;'>🎉 Parabéns! Nenhum cliente detrator identificado no período.</td></tr>"

            # Dimensões TSI
            dim_html = ""
            dimensoes = metrics.get('dimensoes', {})
            for dim_nome, dim_val in dimensoes.items():
                cor_dim = "#16A34A" if dim_val >= 85 else ("#2563EB" if dim_val >= 70 else "#DC2626")
                dim_html += f"""
                <div style='margin-bottom: 7px;'>
                    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;'>
                        <span style='font-size: 9pt; color: #334155; font-weight: 600;'>{dim_nome}</span>
                        <span style='font-size: 9.5pt; font-weight: bold; color: {cor_dim};'>{dim_val:.1f}%</span>
                    </div>
                    <div style='background-color: #E2E8F0; height: 5px; border-radius: 3px; overflow: hidden;'>
                        <div style='background-color: {cor_dim}; width: {dim_val:.1f}%; height: 100%; border-radius: 3px;'></div>
                    </div>
                </div>
                """

            data_hora_emissao = datetime.datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
            periodo_label = mes_ref if (mes_ref and mes_ref != "Todos") else "Histórico Consolidado (Todos os Períodos)"
            
            html = f"""<!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    @page {{ size: A4 portrait; margin: 8mm; }}
                    * {{ box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        color: #1E293B;
                        background: #FFFFFF;
                        margin: 0;
                        padding: 0;
                        font-size: 9pt;
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
                        border-radius: 6px;
                        padding: 10px 14px;
                        margin-bottom: 12px;
                        page-break-inside: avoid;
                    }}
                    .grid-kpis {{
                        display: grid;
                        grid-template-columns: repeat(5, 1fr);
                        gap: 8px;
                        margin-bottom: 12px;
                        page-break-inside: avoid;
                    }}
                    .card {{
                        background: #FFFFFF;
                        border: 1px solid #E2E8F0;
                        border-radius: 6px;
                        padding: 8px 10px;
                        page-break-inside: avoid;
                    }}
                    .kpi-title {{
                        font-size: 8pt;
                        font-weight: 700;
                        color: #64748B;
                        text-transform: uppercase;
                    }}
                    .kpi-num {{
                        font-size: 16pt;
                        font-weight: 800;
                        margin: 2px 0;
                    }}
                    .kpi-desc {{
                        font-size: 7.5pt;
                        color: #94A3B8;
                    }}
                    .two-col {{
                        display: grid;
                        grid-template-columns: 1fr 1fr;
                        gap: 10px;
                        margin-bottom: 12px;
                        page-break-inside: avoid;
                    }}
                    .section-title {{
                        font-size: 10pt;
                        font-weight: 800;
                        color: #0F172A;
                        border-left: 4px solid #2563EB;
                        padding-left: 6px;
                        margin-bottom: 8px;
                        text-transform: uppercase;
                    }}
                    .data-table {{
                        width: 100%;
                        border-collapse: collapse;
                        font-size: 8.5pt;
                    }}
                    .data-table th {{
                        background-color: #1E3A8A;
                        color: #FFFFFF;
                        font-weight: 700;
                        padding: 6px 8px;
                        text-align: left;
                        font-size: 8pt;
                        text-transform: uppercase;
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
            </head>
            <body>
                <div class="header-box">
                    <div>
                        <div class="dept-badge">Pós-Vendas & Oficina (TSI)</div>
                        <h1 class="logo-title">RELATÓRIO DE QUALIDADE TSI</h1>
                        <div class="store-name">{loja_nome}</div>
                    </div>
                    <div class="meta-info">
                        <div class="meta-badge">📅 Período: {periodo_label}</div><br>
                        <b>Data de Extração:</b> {data_hora_emissao}<br>
                        <b>Sistema:</b> SaaS Intelligence
                    </div>
                </div>

                <div class="roi-box">
                    <div style="font-size: 8pt; font-weight: 700; color: #38BDF8; text-transform: uppercase;">📊 Relatório Gerencial Geral — Pós-Vendas (TSI)</div>
                    <div style="font-size: 13pt; font-weight: 800; margin: 2px 0;">Taxa de Engajamento via WhatsApp: <span style="color:#38BDF8;">{saas_taxa_resp:.1f}%</span></div>
                    <div style="font-size: 8pt; color: #94A3B8;">Pesquisas enviadas via WhatsApp garantem velocidade de resposta e atingimento das metas de auditoria da montadora.</div>
                </div>

                <div class="grid-kpis">
                    <div class="card" style="border-top: 3px solid #1E3A8A;">
                        <div class="kpi-title">Pesquisas</div>
                        <div class="kpi-num" style="color: #0F172A;">{total_resp}</div>
                        <div class="kpi-desc">100% Base Auditada</div>
                    </div>
                    <div class="card" style="border-top: 3px solid {tsi_color};">
                        <div class="kpi-title">Índice TSI (%)</div>
                        <div class="kpi-num" style="color: {tsi_color};">{tsi:.1f}%</div>
                        <div class="kpi-desc">Meta: ≥ 75.0</div>
                    </div>
                    <div class="card" style="border-top: 3px solid #10B981;">
                        <div class="kpi-title">Promotores</div>
                        <div class="kpi-num" style="color: #10B981;">{promotores_count} <span style="font-size: 9pt; font-weight: normal;">({promotores_pct:.1f}%)</span></div>
                        <div class="kpi-desc">Notas 9 e 10</div>
                    </div>
                    <div class="card" style="border-top: 3px solid #F59E0B;">
                        <div class="kpi-title">Neutros</div>
                        <div class="kpi-num" style="color: #F59E0B;">{neutros_count} <span style="font-size: 9pt; font-weight: normal;">({neutros_pct:.1f}%)</span></div>
                        <div class="kpi-desc">Notas 7 e 8</div>
                    </div>
                    <div class="card" style="border-top: 3px solid #EF4444;">
                        <div class="kpi-title">Detratores</div>
                        <div class="kpi-num" style="color: #EF4444;">{detratores_count} <span style="font-size: 9pt; font-weight: normal;">({detratores_pct:.1f}%)</span></div>
                        <div class="kpi-desc">Notas 0 a 6</div>
                    </div>
                </div>

                <div class="two-col">
                    <div class="card">
                        <div class="section-title">📊 Pilares da Oficina (Top2Box)</div>
                        {dim_html}
                    </div>
                    <div class="card">
                        <div class="section-title">🏆 Desempenho por Consultor</div>
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Consultor</th>
                                    <th style="width: 45px; text-align: center;">Resp.</th>
                                    <th style="width: 45px; text-align: center;">TSI</th>
                                    <th style="width: 55px; text-align: center;">Top2Box</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows_ranking}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="card" style="margin-bottom: 12px;">
                    <div class="section-title">Ocorrências Críticas & Detratores (Ação Imediata do Gestor)</div>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th style="width: 65px; text-align: center;">Data</th>
                                <th>Cliente</th>
                                <th style="width: 110px; text-align: center;">Contato</th>
                                <th style="width: 85px; text-align: center;">O.S. / Categoria</th>
                                <th style="width: 50px; text-align: center;">Nota</th>
                                <th>Motivo / Apontamento</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows_detratores}
                        </tbody>
                    </table>
                </div>

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
                        <td colspan="2" style="text-align: center; padding-top: 8px; font-size: 7pt; color: #94A3B8;">
                            Documento gerado automaticamente pelo SaaS Intelligence. Métricas auditadas de qualidade.
                        </td>
                    </tr>
                </table>
            </body>
            </html>"""

            return cls._render_html_to_pdf(html, output_pdf_path)
        except Exception as e:
            print(f"[PDF_GEN] Erro ao gerar relatório TSI: {e}")
            return False

    @classmethod
    def generate_ssi_report(cls, output_pdf_path: str, loja_nome: str, mes_ref: str, metrics: dict, modalidade_dist: list, detratores: list) -> bool:
        """
        Gera Relatório Executivo do Comercial/Vendas (SSI) com layout moderno e proporcional.
        """
        try:
            ssi = metrics.get('ssi', metrics.get('nps', 0.0))
            nps_recomendacao = metrics.get('nps', 0.0)
            ssi_color = "#16A34A" if ssi >= 85 else ("#2563EB" if ssi >= 70 else "#DC2626")
            
            total_resp = metrics.get('total_respostas', 0)
            satisfacao_geral = metrics.get('satisfacao_geral', 0.0)
            recompra_pct = metrics.get('recompra_pct', 0.0)
            
            promotores_pct = metrics.get('promotores_pct', 0.0)
            neutros_pct = metrics.get('neutros_pct', 0.0)
            detratores_pct = metrics.get('detratores_pct', 0.0)
            
            promotores_count = metrics.get('promotores_count', int(round((promotores_pct / 100.0) * total_resp)))
            neutros_count = metrics.get('neutros_count', int(round((neutros_pct / 100.0) * total_resp)))
            detratores_count = metrics.get('detratores_count', total_resp - promotores_count - neutros_count if (promotores_count + neutros_count <= total_resp) else int(round((detratores_pct / 100.0) * total_resp)))
            if detratores_count < 0: detratores_count = 0
            
            # Modalidades
            rows_mod = ""
            for m in modalidade_dist:
                nome_m = m.get('nome', 'N/D')
                qtd_m = m.get('qtd', 0)
                nps_m = m.get('ssi', m.get('nps', 0.0))
                recomendacao_nps_m = m.get('nps', 0.0)
                m_color = "#16A34A" if nps_m >= 75 else ("#2563EB" if nps_m >= 50 else "#DC2626")
                rows_mod += f"""
                <tr style="border-bottom: 1px solid #E2E8F0;">
                    <td style="padding: 6px 8px; font-weight: 600; color: #1E293B;">{nome_m}</td>
                    <td style="padding: 6px 8px; text-align: center; color: #475569;">{qtd_m}</td>
                    <td style="padding: 6px 8px; text-align: center; font-weight: bold; color: {m_color};">{nps_m:.1f}</td>
                    <td style="padding: 6px 8px; text-align: center; font-weight: bold; color: #7C3AED;">{recomendacao_nps_m:.1f}</td>
                </tr>
                """
            if not rows_mod:
                rows_mod = "<tr><td colspan='4' style='padding: 10px; text-align:center; color:#94A3B8;'>Nenhuma modalidade registrada no período.</td></tr>"

            # Dimensões SSI
            dim_html = ""
            dimensoes = metrics.get('dimensoes', {})
            for dim_nome, dim_val in dimensoes.items():
                cor_dim = "#16A34A" if dim_val >= 85 else ("#2563EB" if dim_val >= 70 else "#DC2626")
                dim_html += f"""
                <div style='margin-bottom: 7px;'>
                    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;'>
                        <span style='font-size: 9pt; color: #334155; font-weight: 600;'>{dim_nome}</span>
                        <span style='font-size: 9.5pt; font-weight: bold; color: {cor_dim};'>{dim_val:.1f}%</span>
                    </div>
                    <div style='background-color: #E2E8F0; height: 5px; border-radius: 3px; overflow: hidden;'>
                        <div style='background-color: {cor_dim}; width: {dim_val:.1f}%; height: 100%; border-radius: 3px;'></div>
                    </div>
                </div>
                """

            # Detratores SSI
            rows_detratores = ""
            for d in detratores[:12]:
                data_d = d.get('data', '-')
                cli = d.get('cliente', 'Cliente Auditado')
                fone = d.get('telefone', '')
                if not fone or fone in ['S/N', 'N/D', 'None', '-']:
                    fone_html = "<span style='color: #94A3B8; font-size: 8.5pt;'>-</span>"
                else:
                    fone_clean = re.sub(r'\D', '', str(fone))
                    if len(fone_clean) == 11:
                        fone_fmt = f"({fone_clean[:2]}) {fone_clean[2:7]}-{fone_clean[7:]}"
                    elif len(fone_clean) == 10:
                        fone_fmt = f"({fone_clean[:2]}) {fone_clean[2:6]}-{fone_clean[6:]}"
                    else:
                        fone_fmt = str(fone)
                    fone_html = f"<span style='background:#EFF6FF; color:#1E40AF; padding:2px 6px; border-radius:4px; font-weight:600; font-size:8pt;'>📞 {fone_fmt}</span>"

                modelo = d.get('modelo', '-')
                chassi = d.get('chassi', '-')
                nota = d.get('nota', 0)
                motivo = d.get('motivo', 'Sem detalhes')
                
                rows_detratores += f"""
                <tr style="border-bottom: 1px solid #E2E8F0;">
                    <td style="padding: 6px 8px; text-align: center; color: #475569; font-size: 8.5pt;">{data_d}</td>
                    <td style="padding: 6px 8px; font-weight: 700; color: #0F172A;">{cli}</td>
                    <td style="padding: 6px 8px; text-align: center;">{fone_html}</td>
                    <td style="padding: 6px 8px; text-align: center; font-size: 8pt; color: #334155;">{modelo}</td>
                    <td style="padding: 6px 8px; text-align: center;"><span style="background:#F1F5F9; color:#475569; padding:2px 6px; border-radius:4px; font-weight:600; font-size:8pt;">{chassi}</span></td>
                    <td style="padding: 6px 8px; text-align: center;"><span style="background:#FEE2E2; color:#B91C1C; font-weight:800; font-size:8.5pt; padding:2px 6px; border-radius:4px;">Nota {nota}</span></td>
                    <td style="padding: 6px 8px; color: #334155; font-size: 8.5pt;">{motivo}</td>
                </tr>
                """
            if not rows_detratores:
                rows_detratores = "<tr><td colspan='7' style='text-align:center; color:#16A34A; font-weight: bold; padding: 12px;'>🎉 Parabéns! Nenhum cliente detrator identificado em Vendas no período.</td></tr>"

            data_hora_emissao = datetime.datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
            periodo_label = mes_ref if (mes_ref and mes_ref != "Todos") else "Histórico Consolidado (Todos os Períodos)"

            html = f"""<!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    @page {{ size: A4 portrait; margin: 8mm; }}
                    * {{ box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        color: #1E293B;
                        background: #FFFFFF;
                        margin: 0;
                        padding: 0;
                        font-size: 9pt;
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
                    .dept-badge-ssi {{
                        background: #B91C1C;
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
                        background-color: #FEF2F2;
                        color: #B91C1C;
                        padding: 2px 8px;
                        border-radius: 4px;
                        font-weight: bold;
                        font-size: 8pt;
                        display: inline-block;
                        margin-bottom: 3px;
                    }}
                    .grid-kpis {{
                        display: grid;
                        grid-template-columns: repeat(6, 1fr);
                        gap: 8px;
                        margin-bottom: 12px;
                        page-break-inside: avoid;
                    }}
                    .card {{
                        background: #FFFFFF;
                        border: 1px solid #E2E8F0;
                        border-radius: 6px;
                        padding: 8px 10px;
                        page-break-inside: avoid;
                    }}
                    .kpi-title {{
                        font-size: 8pt;
                        font-weight: 700;
                        color: #64748B;
                        text-transform: uppercase;
                    }}
                    .kpi-num {{
                        font-size: 16pt;
                        font-weight: 800;
                        margin: 2px 0;
                    }}
                    .kpi-desc {{
                        font-size: 7.5pt;
                        color: #94A3B8;
                    }}
                    .two-col {{
                        display: grid;
                        grid-template-columns: 1fr 1fr;
                        gap: 10px;
                        margin-bottom: 12px;
                        page-break-inside: avoid;
                    }}
                    .section-title {{
                        font-size: 10pt;
                        font-weight: 800;
                        color: #0F172A;
                        border-left: 4px solid #DC2626;
                        padding-left: 6px;
                        margin-bottom: 8px;
                        text-transform: uppercase;
                    }}
                    .data-table {{
                        width: 100%;
                        border-collapse: collapse;
                        font-size: 8.5pt;
                    }}
                    .data-table th {{
                        background-color: #991B1B;
                        color: #FFFFFF;
                        font-weight: 700;
                        padding: 6px 8px;
                        text-align: left;
                        font-size: 8pt;
                        text-transform: uppercase;
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
            </head>
            <body>
                <div class="header-box">
                    <div>
                        <div class="dept-badge-ssi">Comercial & Vendas (SSI)</div>
                        <h1 class="logo-title">RELATÓRIO DE QUALIDADE SSI</h1>
                        <div class="store-name">{loja_nome}</div>
                    </div>
                    <div class="meta-info">
                        <div class="meta-badge">📅 Período: {periodo_label}</div><br>
                        <b>Data de Extração:</b> {data_hora_emissao}<br>
                        <b>Sistema:</b> SaaS Intelligence
                    </div>
                </div>

                <div class="grid-kpis">
                    <div class="card" style="border-top: 3px solid #1E3A8A;">
                        <div class="kpi-title">Compradores</div>
                        <div class="kpi-num" style="color: #0F172A;">{total_resp}</div>
                        <div class="kpi-desc">100% Base Auditada</div>
                    </div>
                    <div class="card" style="border-top: 3px solid {ssi_color};">
                        <div class="kpi-title">Índice SSI (%)</div>
                        <div class="kpi-num" style="color: {ssi_color};">{ssi:.1f}%</div>
                        <div class="kpi-desc">Satisfação Geral • Meta: ≥ 85.0</div>
                    </div>
                    <div class="card" style="border-top: 3px solid #7C3AED;">
                        <div class="kpi-title">NPS Recomendação</div>
                        <div class="kpi-num" style="color: #7C3AED;">{nps_recomendacao:.1f}</div>
                        <div class="kpi-desc">Promotores menos Detratores</div>
                    </div>
                    <div class="card" style="border-top: 3px solid #10B981;">
                        <div class="kpi-title">Promotores</div>
                        <div class="kpi-num" style="color: #10B981;">{promotores_count} <span style="font-size: 9pt; font-weight: normal;">({promotores_pct:.1f}%)</span></div>
                        <div class="kpi-desc">Notas 9 e 10</div>
                    </div>
                    <div class="card" style="border-top: 3px solid #F59E0B;">
                        <div class="kpi-title">Neutros</div>
                        <div class="kpi-num" style="color: #F59E0B;">{neutros_count} <span style="font-size: 9pt; font-weight: normal;">({neutros_pct:.1f}%)</span></div>
                        <div class="kpi-desc">Notas 7 e 8</div>
                    </div>
                    <div class="card" style="border-top: 3px solid #EF4444;">
                        <div class="kpi-title">Detratores</div>
                        <div class="kpi-num" style="color: #EF4444;">{detratores_count} <span style="font-size: 9pt; font-weight: normal;">({detratores_pct:.1f}%)</span></div>
                        <div class="kpi-desc">Notas 0 a 6</div>
                    </div>
                </div>

                <div class="two-col">
                    <div class="card">
                        <div class="section-title">🎯 Pilares do Processo Comercial</div>
                        {dim_html}
                    </div>
                    <div class="card">
                        <div class="section-title">💳 Desempenho por Modalidade</div>
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Modalidade</th>
                                    <th style="width: 50px; text-align: center;">Resp.</th>
                                    <th style="width: 50px; text-align: center;">SSI</th>
                                    <th style="width: 50px; text-align: center;">NPS</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows_mod}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="card" style="margin-bottom: 12px;">
                    <div class="section-title">Feedbacks & Detratores na Jornada de Compra (Ação do Gestor)</div>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th style="width: 65px; text-align: center;">Data</th>
                                <th>Cliente</th>
                                <th style="width: 105px; text-align: center;">Contato</th>
                                <th>Modelo</th>
                                <th style="width: 110px; text-align: center;">Chassi</th>
                                <th style="width: 45px; text-align: center;">Nota</th>
                                <th>Comentário / Detalhes</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows_detratores}
                        </tbody>
                    </table>
                </div>

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
                        <td colspan="2" style="text-align: center; padding-top: 8px; font-size: 7pt; color: #94A3B8;">
                            Documento gerado automaticamente pelo SaaS Intelligence. Métricas auditadas de qualidade.
                        </td>
                    </tr>
                </table>
            </body>
            </html>"""

            return cls._render_html_to_pdf(html, output_pdf_path)
        except Exception as e:
            print(f"[PDF_GEN] Erro ao gerar relatório SSI: {e}")
            return False
