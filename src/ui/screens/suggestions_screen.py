from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget



from PyQt6.QtCore import QThread, pyqtSignal

class SuggestionThread(QThread):
    finished = pyqtSignal(bool)
    
    def __init__(self, text):
        super().__init__()
        self.text = text
        
    def run(self):
        try:
            from src.core.license_manager import LicenseManager
            LicenseManager().secure_backend.send_suggestion(self.text)
            self.finished.emit(True)
        except Exception:
            self.finished.emit(False)

class SuggestionsScreen(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        title = QLabel("💡 Sugestões de Melhorias")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1E293B;")
        layout.addWidget(title)

        description = QLabel(
            "Tem alguma ideia de como podemos melhorar o SaaS Assistente PRO? "
            "Encontrou algum problema? Descreva abaixo e nossa equipe avaliará sua sugestão."
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 14px; color: #475569;")
        layout.addWidget(description)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Escreva sua sugestão aqui...")
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding: 15px;
                font-size: 14px;
                color: #334155;
            }
        """)
        layout.addWidget(self.text_edit)

        self.btn_send = QPushButton("📤 Enviar Sugestão")
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.setStyleSheet("""
            QPushButton { background-color: #3B82F6; color: white; font-size: 14px;
                          font-weight: bold; padding: 15px; border-radius: 8px; }
            QPushButton:hover { background-color: #2563EB; }
            QPushButton:disabled { background-color: #94A3B8; }
        """)
        self.btn_send.clicked.connect(self.enviar_sugestao)
        layout.addWidget(self.btn_send, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addStretch()


    def enviar_sugestao(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Aviso", "Escreva uma sugestão antes de enviar.")
            return

        self.btn_send.setEnabled(False)
        self.btn_send.setText("Enviando...")
        
        self.thread = SuggestionThread(text)
        self.thread.finished.connect(self.on_sugestao_finished)
        self.thread.start()

    def on_sugestao_finished(self, success):
        if success:
            QMessageBox.information(self, "Sucesso", "Muito obrigado! Sua sugestão foi enviada com sucesso.")
            self.text_edit.clear()
        else:
            QMessageBox.warning(
                self, "Erro de Conexão",
                "Não foi possível enviar. Verifique sua internet e tente novamente.",
            )
        self.btn_send.setEnabled(True)
        self.btn_send.setText("📤 Enviar Sugestão")
