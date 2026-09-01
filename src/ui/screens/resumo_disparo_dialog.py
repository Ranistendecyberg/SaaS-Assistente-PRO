from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QApplication)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QColor
import os
import sys

class ResumoDisparoDialog(QDialog):
    """
    Modal executivo exibido ao término do lote de disparos,
    apresentando os clientes que não puderam ser contatados (sem fone ou número inválido).
    """
    def __init__(self, parent=None, clientes_com_erro=None):
        super().__init__(parent)
        self.setWindowTitle("Resumo do Disparo - Clientes Não Notificados")
        self.setFixedSize(680, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("background-color: #FFFFFF;")
        
        icon_path = os.path.join(sys._MEIPASS, 'logo.ico') if getattr(sys, 'frozen', False) else os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logo.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.clientes = clientes_com_erro or []
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        
        # Cabeçalho
        header_frame = QFrame()
        header_frame.setStyleSheet("background: transparent; border: none;")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        
        lbl_titulo = QLabel("⚠️ Resumo de Envios Não Concluídos")
        lbl_titulo.setStyleSheet("font-size: 18px; font-weight: 800; color: #0F172A;")
        header_layout.addWidget(lbl_titulo)
        
        total_erros = len(self.clientes)
        lbl_subtitulo = QLabel(f"Identificamos {total_erros} cliente(s) que não receberam a pesquisa devido a inconsistências de cadastro no myHonda:")
        lbl_subtitulo.setStyleSheet("font-size: 13px; color: #64748B;")
        lbl_subtitulo.setWordWrap(True)
        header_layout.addWidget(lbl_subtitulo)
        
        layout.addWidget(header_frame)
        
        # Tabela de Clientes
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(4)
        self.tabela.setHorizontalHeaderLabels(["Cliente", "Tipo", "Telefone", "Motivo"])
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        self.tabela.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                alternate-background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                gridline-color: #F1F5F9;
                font-size: 12px;
                color: #1E293B;
            }
            QHeaderView::section {
                background-color: #0F172A;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 10px;
                border: none;
            }
            QTableWidget::item {
                padding: 6px;
            }
        """)
        
        self.popular_tabela()
        layout.addWidget(self.tabela, 1)
        
        # Rodapé de Ações
        footer_layout = QHBoxLayout()
        
        btn_copiar = QPushButton("📋 Copiar Lista")
        btn_copiar.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #334155;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                border: 1px solid #CBD5E1;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
            }
        """)
        btn_copiar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copiar.clicked.connect(self.copiar_lista)
        footer_layout.addWidget(btn_copiar)
        
        footer_layout.addStretch()
        
        btn_fechar = QPushButton("Entendido")
        btn_fechar.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 28px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        btn_fechar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_fechar.clicked.connect(self.accept)
        footer_layout.addWidget(btn_fechar)
        
        layout.addLayout(footer_layout)

    def popular_tabela(self):
        self.tabela.setRowCount(len(self.clientes))
        for row, item in enumerate(self.clientes):
            nome = item.get("cliente", "Desconhecido").title()
            tipo = item.get("tipo", "-")
            fone = item.get("telefone", "S/N") or "S/N"
            motivo = item.get("motivo", "Não enviado")
            
            item_nome = QTableWidgetItem(nome)
            item_tipo = QTableWidgetItem(tipo)
            item_tipo.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            item_fone = QTableWidgetItem(fone)
            item_fone.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            item_motivo = QTableWidgetItem(motivo)
            item_motivo.setForeground(QColor("#DC2626")) # Vermelho executivo
            
            self.tabela.setItem(row, 0, item_nome)
            self.tabela.setItem(row, 1, item_tipo)
            self.tabela.setItem(row, 2, item_fone)
            self.tabela.setItem(row, 3, item_motivo)

    def copiar_lista(self):
        linhas = ["CLIENTES NÃO NOTIFICADOS (ERRO / SEM FONE):"]
        for c in self.clientes:
            linhas.append(f"- {c.get('cliente', '')} | {c.get('tipo', '')} | Fone: {c.get('telefone', 'S/N')} | Motivo: {c.get('motivo', '')}")
        texto = "\n".join(linhas)
        QApplication.clipboard().setText(texto)

    @classmethod
    def exibir_se_houver(cls, parent=None, clientes_com_erro=None):
        if clientes_com_erro and len(clientes_com_erro) > 0:
            dialog = cls(parent=parent, clientes_com_erro=clientes_com_erro)
            dialog.exec()
