from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QTextEdit)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QFont
import os
import sys

class ComunicadoDialog(QDialog):
    """
    Modal moderno e executivo para exibição de Comunicados / Avisos de Reajuste
    enviados pela administração via Gerador Admin / Firebase.
    """
    def __init__(self, parent=None, titulo="📢 Comunicado da Administração", mensagem=""):
        super().__init__(parent)
        self.setWindowTitle("Comunicado do Sistema")
        self.setFixedSize(540, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("background-color: #FFFFFF;")
        
        icon_path = os.path.join(sys._MEIPASS, 'logo.ico') if getattr(sys, 'frozen', False) else os.path.join(os.path.dirname(__file__), '..', '..', '..', 'logo.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)
        
        # Cabeçalho
        header_frame = QFrame()
        header_frame.setStyleSheet("background: transparent; border: none;")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        
        lbl_icone_titulo = QLabel(titulo)
        lbl_icone_titulo.setStyleSheet("font-size: 20px; font-weight: 800; color: #1E293B;")
        lbl_icone_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(lbl_icone_titulo)
        
        lbl_subtitulo = QLabel("Mensagem oficial da equipe de gestão do SaaS Assistente PRO:")
        lbl_subtitulo.setStyleSheet("font-size: 13px; color: #64748B;")
        lbl_subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(lbl_subtitulo)
        
        layout.addWidget(header_frame)
        
        # Card de Conteúdo do Comunicado
        card_conteudo = QFrame()
        card_conteudo.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-left: 4px solid #F59E0B;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout(card_conteudo)
        card_layout.setContentsMargins(18, 18, 18, 18)
        
        txt_msg = QTextEdit()
        txt_msg.setReadOnly(True)
        txt_msg.setPlainText(mensagem)
        txt_msg.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                border: none;
                color: #334155;
                font-size: 14px;
                line-height: 1.5;
                font-family: 'Segoe UI', sans-serif;
            }
        """)
        card_layout.addWidget(txt_msg)
        
        layout.addWidget(card_conteudo, 1)
        
        # Botão de Ação / Fechar
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_fechar = QPushButton("Entendido e Ciente")
        btn_fechar.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 12px 36px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
            QPushButton:pressed {
                background-color: #1E40AF;
            }
        """)
        btn_fechar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_fechar.clicked.connect(self.accept)
        btn_layout.addWidget(btn_fechar)
        
        layout.addLayout(btn_layout)

    @classmethod
    def exibir_se_houver(cls, parent=None, mensagem=""):
        """Exibe o diálogo caso haja mensagem válida não lida/confirmada."""
        msg = (mensagem or "").strip()
        if not msg:
            return
            
        from src.core.database import DatabaseManager
        db = DatabaseManager()
        if db.is_comunicado_lido(msg):
            return # Já foi marcado como entendido e ciente, não emite mais o alerta
            
        dialog = cls(parent=parent, mensagem=msg)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            db.marcar_comunicado_lido(msg)
