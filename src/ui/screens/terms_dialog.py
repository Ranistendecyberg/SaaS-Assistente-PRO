import sys
import os
import json
import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QCheckBox, QFrame)
from PyQt6.QtCore import Qt
from src.core.paths import get_base_dir

class TermsDialog(QDialog):
    """
    Diálogo para exibição e aceite dos Termos de Uso e Isenção de Responsabilidade.
    Modos:
    - apenas_leitura=False: Modo de primeiro acesso, obriga o usuário a concordar para prosseguir.
    - apenas_leitura=True: Modo de consulta (ex: chamado pela tela Sobre o Sistema).
    """
    def __init__(self, parent=None, apenas_leitura=False):
        super().__init__(parent)
        self.apenas_leitura = apenas_leitura
        self.termo_aceito = False
        
        self.setWindowTitle("Termos de Uso e Licença - SaaS Assistente PRO")
        self.setFixedSize(700, 620)
        self.setModal(True)
        
        # Desabilitar botão de fechar no primeiro acesso se for obrigatório
        if not self.apenas_leitura:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
            
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # Cabeçalho
        lbl_titulo = QLabel("Termos de Uso e Isenção de Responsabilidade")
        lbl_titulo.setStyleSheet("font-size: 18px; font-weight: bold; color: #1E293B;")
        lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_titulo)
        
        lbl_sub = QLabel("Por favor, leia atentamente as condições de licenciamento e uso do software.")
        lbl_sub.setStyleSheet("font-size: 13px; color: #64748B;")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_sub)
        
        # Área de Texto dos Termos
        self.txt_termos = QTextEdit()
        self.txt_termos.setReadOnly(True)
        self.txt_termos.setStyleSheet("""
            QTextEdit {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                color: #334155;
                line-height: 1.4;
            }
        """)
        
        # Carregar arquivo de termos
        conteudo_termos = self.carregar_texto_termos()
        self.txt_termos.setPlainText(conteudo_termos)
        layout.addWidget(self.txt_termos)
        
        # Rodapé / Ações
        if not self.apenas_leitura:
            self.chk_concordo = QCheckBox("Declaro que li, compreendi e concordo com todos os termos e condições acima.")
            self.chk_concordo.setStyleSheet("font-size: 12px; font-weight: bold; color: #1E293B; margin-top: 5px;")
            self.chk_concordo.stateChanged.connect(self.ao_mudar_checkbox)
            layout.addWidget(self.chk_concordo)
            
            btn_layout = QHBoxLayout()
            
            self.btn_recusar = QPushButton("Recusar e Sair")
            self.btn_recusar.setStyleSheet("""
                QPushButton {
                    background-color: #EF4444;
                    color: white;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 10px 20px;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #DC2626; }
            """)
            self.btn_recusar.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_recusar.clicked.connect(self.recusar)
            btn_layout.addWidget(self.btn_recusar)
            
            self.btn_aceitar = QPushButton("Concordar e Continuar")
            self.btn_aceitar.setEnabled(False)
            self.btn_aceitar.setStyleSheet("""
                QPushButton {
                    background-color: #10B981;
                    color: white;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 10px 20px;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #059669; }
                QPushButton:disabled { background-color: #9CA3AF; color: #E5E7EB; }
            """)
            self.btn_aceitar.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_aceitar.clicked.connect(self.aceitar)
            btn_layout.addWidget(self.btn_aceitar)
            
            layout.addLayout(btn_layout)
        else:
            btn_fechar = QPushButton("Fechar")
            btn_fechar.setStyleSheet("""
                QPushButton {
                    background-color: #3B82F6;
                    color: white;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 10px 20px;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #2563EB; }
            """)
            btn_fechar.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_fechar.clicked.connect(self.accept)
            layout.addWidget(btn_fechar, alignment=Qt.AlignmentFlag.AlignCenter)

    def carregar_texto_termos(self) -> str:
        candidatos = [
            os.path.join(getattr(sys, '_MEIPASS', ''), 'src', 'assets', 'termos_de_uso.txt'),
            os.path.join(getattr(sys, '_MEIPASS', ''), 'termos_de_uso.txt'),
            os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'termos_de_uso.txt'),
            os.path.join(os.path.dirname(sys.executable), 'src', 'assets', 'termos_de_uso.txt'),
            os.path.join(os.getcwd(), 'src', 'assets', 'termos_de_uso.txt'),
            os.path.join(get_base_dir(), 'src', 'assets', 'termos_de_uso.txt')
        ]
        for caminho in candidatos:
            if caminho and os.path.exists(caminho):
                try:
                    with open(caminho, "r", encoding="utf-8") as f:
                        return f.read()
                except:
                    pass
        return "Termos de Uso e Licença de Software - SaaS Assistente PRO."

    def ao_mudar_checkbox(self, state):
        self.btn_aceitar.setEnabled(self.chk_concordo.isChecked())

    def aceitar(self):
        self.termo_aceito = True
        self.salvar_aceite_local()
        self.accept()

    def recusar(self):
        self.termo_aceito = False
        self.reject()

    def salvar_aceite_local(self):
        try:
            base_dir = get_base_dir()
            app_data_dir = os.path.join(base_dir, "app_data")
            os.makedirs(app_data_dir, exist_ok=True)
            caminho_aceite = os.path.join(app_data_dir, "termos_aceito.json")
            
            dados = {
                "aceito": True,
                "data_hora": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "versao_termos": "2.0.0"
            }
            with open(caminho_aceite, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=4)
        except Exception as e:
            print(f"Erro ao salvar aceite dos termos: {e}")

    @staticmethod
    def verificar_aceite_previo() -> bool:
        """Verifica se os termos já foram aceitos nesta máquina."""
        try:
            base_dir = get_base_dir()
            caminho_aceite = os.path.join(base_dir, "app_data", "termos_aceito.json")
            if os.path.exists(caminho_aceite):
                with open(caminho_aceite, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    return dados.get("aceito", False)
        except:
            pass
        return False
