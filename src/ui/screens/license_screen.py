from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QStackedWidget, QWidget, QMessageBox, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QGuiApplication, QPixmap, QImage
from src.core.license_manager import LicenseManager
import qrcode
from PIL import Image, ImageQt
from decimal import Decimal, InvalidOperation


def _confirmed_pix_amount(value):
    """Somente o valor monetário válido retornado pelo servidor pode ser exibido."""
    if isinstance(value, bool):
        raise ValueError("Valor do PIX inválido")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Valor do PIX não confirmado") from None
    if not amount.is_finite() or not 0 < amount <= Decimal("99999999.99"):
        raise ValueError("Valor do PIX inválido")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Valor do PIX com precisão inválida")
    return amount


def _pix_currency(amount):
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

class WorkerThread(QThread):
    result_ready = pyqtSignal(object)
    
    def __init__(self, func):
        super().__init__()
        self.func = func
        
    def run(self):
        res = self.func()
        self.result_ready.emit(res)

class LicenseScreen(QDialog):
    """
    Tela de bloqueio para licenciamento. 
    Se a licença for válida/trial, fecha silenciosamente.
    Se estiver vencida, obriga o usuário a pagar o PIX ou inserir chave.
    """
    
    def __init__(self, parent=None, modo=None):
        super().__init__(parent)
        self.setWindowTitle("Ativação do Sistema - SaaS Assistente PRO")
        self.setFixedSize(500, 600)
        
        self.manager = LicenseManager()
        self.payment_id = None
        self.timer_pix = QTimer(self)
        self.timer_pix.timeout.connect(self.checar_pagamento_pix)
        
        # Manter referências das threads para não serem destruídas
        self.workers = []
        
        self.setup_ui()
        
        self.modo_startup = (modo is None)
        
        if modo == "pix":
            self.buscar_status_silencioso(auto_gerar_pix=True)
        elif modo == "chave":
            self.stack.setCurrentIndex(3)
            self.buscar_status_silencioso()
        else:
            self.verificar_status_inicial()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        # Título
        self.lbl_title = QLabel("SaaS Assistente PRO")
        self.lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1E293B;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.lbl_title)
        
        self.lbl_subtitle = QLabel("Verificando licença...")
        self.lbl_subtitle.setStyleSheet("font-size: 14px; color: #64748B;")
        self.lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.lbl_subtitle)
        
        # Stacked Widget para alternar entre "Vencido/Opções", "PIX", "Chave"
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)
        
        # Pagina 0: Carregando
        page_loading = QWidget()
        self.stack.addWidget(page_loading)
        
        # Pagina 1: Opções de Pagamento (Bloqueado)
        page_blocked = QWidget()
        layout_blocked = QVBoxLayout(page_blocked)
        layout_blocked.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_block = QLabel("Verificando status...")
        self.lbl_block.setStyleSheet("font-size: 18px; font-weight: bold; color: #64748B;")
        self.lbl_block.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_blocked.addWidget(self.lbl_block)
        
        # Banner de Aviso de Reajuste ou Notificação do Admin
        self.lbl_aviso_reajuste = QLabel("")
        self.lbl_aviso_reajuste.setStyleSheet("background-color: #EFF6FF; color: #1D4ED8; border: 1px solid #93C5FD; border-radius: 6px; padding: 10px; font-size: 12px; font-weight: 500;")
        self.lbl_aviso_reajuste.setWordWrap(True)
        self.lbl_aviso_reajuste.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_aviso_reajuste.hide()
        layout_blocked.addWidget(self.lbl_aviso_reajuste)
        
        self.valor_pix = None
        self._gerando_pix = False
        
        self.btn_pix = QPushButton("Consultar valor e gerar PIX")
        self.btn_pix.setStyleSheet("background-color: #10B981; color: white; padding: 15px; border-radius: 8px; font-weight: bold; font-size: 14px;")
        self.btn_pix.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pix.clicked.connect(self.gerar_pix)
        layout_blocked.addWidget(self.btn_pix)
        
        btn_chave = QPushButton("Tenho uma Chave de Ativação")
        btn_chave.setStyleSheet("background-color: #3B82F6; color: white; padding: 15px; border-radius: 8px; font-weight: bold; font-size: 14px;")
        btn_chave.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_chave.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        layout_blocked.addWidget(btn_chave)
        
        self.stack.addWidget(page_blocked)
        
        # Pagina 2: PIX Checkout
        page_pix = QWidget()
        layout_pix = QVBoxLayout(page_pix)
        layout_pix.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_pix_amount = QLabel("")
        self.lbl_pix_amount.setStyleSheet("font-size: 18px; font-weight: bold; color: #1E293B; margin-bottom: 10px;")
        self.lbl_pix_amount.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_pix.addWidget(self.lbl_pix_amount)
        
        self.lbl_qr = QLabel()
        self.lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr.setFixedSize(250, 250)
        self.lbl_qr.setStyleSheet("background-color: #F1F5F9; border-radius: 10px;")
        layout_pix.addWidget(self.lbl_qr, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_pix_status = QLabel("Aguardando pagamento...")
        self.lbl_pix_status.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 14px;")
        self.lbl_pix_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_pix.addWidget(self.lbl_pix_status)
        
        self.str_copia_cola = ""
        btn_copiar = QPushButton("Copiar PIX Copia e Cola")
        btn_copiar.setStyleSheet("background-color: #475569; color: white; padding: 10px; border-radius: 5px; font-weight: bold;")
        btn_copiar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copiar.clicked.connect(self.copiar_pix)
        layout_pix.addWidget(btn_copiar)
        
        btn_voltar_pix = QPushButton("Voltar")
        btn_voltar_pix.setStyleSheet("background-color: transparent; color: #64748B; text-decoration: underline; border: none;")
        btn_voltar_pix.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_voltar_pix.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        layout_pix.addWidget(btn_voltar_pix)
        
        self.stack.addWidget(page_pix)
        
        # Pagina 3: Ativacao por Chave Manual
        page_chave = QWidget()
        layout_chave = QVBoxLayout(page_chave)
        layout_chave.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_instrucao = QLabel("Insira sua chave de acesso (Ex: PRO-12345):")
        lbl_instrucao.setStyleSheet("font-size: 14px; color: #334155;")
        layout_chave.addWidget(lbl_instrucao)
        
        self.input_chave = QLineEdit()
        self.input_chave.setPlaceholderText("Cole a chave aqui...")
        self.input_chave.setStyleSheet("padding: 15px; font-size: 16px; border: 2px solid #CBD5E1; border-radius: 8px;")
        self.input_chave.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_chave.addWidget(self.input_chave)
        
        self.btn_validar_chave = QPushButton("Validar Chave")
        self.btn_validar_chave.setStyleSheet("background-color: #3B82F6; color: white; padding: 15px; border-radius: 8px; font-weight: bold; font-size: 14px;")
        self.btn_validar_chave.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_validar_chave.clicked.connect(self.ativar_chave)
        layout_chave.addWidget(self.btn_validar_chave)
        
        btn_voltar_chave = QPushButton("Voltar")
        btn_voltar_chave.setStyleSheet("background-color: transparent; color: #64748B; text-decoration: underline; border: none;")
        btn_voltar_chave.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_voltar_chave.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        layout_chave.addWidget(btn_voltar_chave)
        
        self.stack.addWidget(page_chave)

    def execute_async(self, func, callback):
        worker = WorkerThread(func)
        worker.result_ready.connect(callback)
        self.workers.append(worker)
        worker.start()

    def verificar_status_inicial(self):
        self.stack.setCurrentIndex(0)
        
        def task():
            return self.manager.validar_licenca()
            
        def on_done(dados):
            status = dados.get("status")
            dias = dados.get("dias_restantes", 0)
            
            if status == "trial" or status == "ativa":
                msg_dias = f"Dias restantes: {dias}" if dias > 1 else "Último dia de validade (expira hoje às 22h)."
                QMessageBox.information(self, "Licença Válida", f"Acesso liberado!\n{msg_dias}")
                self.accept() 
            else:
                self.btn_pix.setText("Consultar valor e gerar PIX")
                
                aviso_reajuste = dados.get("aviso_reajuste", "").strip()
                if aviso_reajuste:
                    self.lbl_aviso_reajuste.setText(f"📢 {aviso_reajuste}")
                    self.lbl_aviso_reajuste.show()
                else:
                    self.lbl_aviso_reajuste.hide()
                    
                self.lbl_block.setText("Sua licença expirou.")
                self.lbl_block.setStyleSheet("font-size: 18px; font-weight: bold; color: #EF4444;")
                self.lbl_subtitle.setText(f"Máquina: {self.manager.get_hardware_id()}")
                self.stack.setCurrentIndex(1)
                
        self.execute_async(task, on_done)
        
    def buscar_status_silencioso(self, auto_gerar_pix=False):
        def task():
            return self.manager.validar_licenca()
            
        def on_done(dados):
            status = dados.get("status")
            dias = dados.get("dias_restantes", 0)
            
            aviso_reajuste = dados.get("aviso_reajuste", "").strip()
            if aviso_reajuste:
                self.lbl_aviso_reajuste.setText(f"📢 {aviso_reajuste}")
                self.lbl_aviso_reajuste.show()
            else:
                self.lbl_aviso_reajuste.hide()
            
            texto_dias = f"{dias} dias restantes" if dias > 1 else "Último dia (expira hoje às 22h)" if dias == 1 else "0 dias"
            
            if status == "trial":
                self.lbl_block.setText(f"Você está em fase de testes.\n({texto_dias})")
                self.lbl_block.setStyleSheet("font-size: 18px; font-weight: bold; color: #F59E0B;")
            elif status == "ativa":
                self.lbl_block.setText(f"Sua licença está ativa.\n({texto_dias})")
                self.lbl_block.setStyleSheet("font-size: 18px; font-weight: bold; color: #10B981;")
            else:
                self.lbl_block.setText("Sua licença expirou.")
                self.lbl_block.setStyleSheet("font-size: 18px; font-weight: bold; color: #EF4444;")
                
            self.btn_pix.setText("Consultar valor e gerar PIX")
                
            self.lbl_subtitle.setText(f"Máquina: {self.manager.get_hardware_id()}")
            
            if auto_gerar_pix:
                self.gerar_pix()
            
        self.execute_async(task, on_done)

    def gerar_pix(self, checked=False):
        if self._gerando_pix:
            return
        self._gerando_pix = True
        self.btn_pix.setEnabled(False)
        self.timer_pix.stop()
        self.payment_id = None
        self.str_copia_cola = ""
        self.valor_pix = None
        self.stack.setCurrentIndex(2)
        self.lbl_pix_amount.setText("Consultando valor atualizado…")
        self.lbl_pix_amount.setStyleSheet("font-size: 18px; font-weight: bold; color: #1E293B; margin-bottom: 10px;")
            
        self.lbl_pix_status.setText("Gerando PIX...")
        self.lbl_pix_status.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 14px;")
        self.lbl_qr.clear()
        
        def task():
            return self.manager.gerar_pix()
            
        def on_done(res):
            self._gerando_pix = False
            self.btn_pix.setEnabled(True)
            if not res.get("sucesso"):
                self.lbl_pix_amount.setText("Valor não confirmado")
                QMessageBox.critical(self, "Erro", res.get("mensagem", "Falha ao gerar PIX."))
                self.stack.setCurrentIndex(1)
                return

            try:
                amount = _confirmed_pix_amount(res.get("amount"))
            except ValueError:
                self.lbl_pix_amount.setText("Valor não confirmado")
                QMessageBox.critical(
                    self, "PIX não confirmado",
                    "O servidor não confirmou um valor válido para este PIX.\n"
                    "Nenhum código será exibido. Tente novamente ou contate o suporte.",
                )
                self.stack.setCurrentIndex(1)
                return

            self.valor_pix = amount
            self.lbl_pix_amount.setText(f"Pagamento Mensalidade: {_pix_currency(amount)}")
                
            self.payment_id = res["payment_id"]
            self.str_copia_cola = res["qr_code_str"]
            
            # Gerar imagem do QR Code
            qr = qrcode.QRCode(box_size=8)
            qr.add_data(self.str_copia_cola)
            qr.make()
            img_pil = qr.make_image(fill_color="black", back_color="white").resize((250, 250))
            
            # Converter PIL para QPixmap
            qim = ImageQt.ImageQt(img_pil)
            pixmap = QPixmap.fromImage(qim)
            self.lbl_qr.setPixmap(pixmap)
            
            self.lbl_pix_status.setText("Aguardando pagamento pelo seu Banco...")
            self.timer_pix.start(5000) # Checa a cada 5 segundos
            
        self.execute_async(task, on_done)

    def copiar_pix(self):
        if self.str_copia_cola:
            QGuiApplication.clipboard().setText(self.str_copia_cola)
            QMessageBox.information(self, "Copiado", "Código Copia e Cola salvo na área de transferência!")

    def checar_pagamento_pix(self):
        if not self.payment_id: return
        
        def task():
            return self.manager.verificar_pagamento(self.payment_id)
            
        def on_done(aprovado):
            if aprovado:
                self.timer_pix.stop()
                self.lbl_pix_status.setText("✅ Pagamento Aprovado!")
                self.lbl_pix_status.setStyleSheet("color: #10B981; font-weight: bold; font-size: 16px;")
                
                # A confirmação no Supabase já aplica a renovação de forma atômica.
                
                QMessageBox.information(self, "Sucesso", "Pagamento reconhecido! Licença renovada por 30 dias.")
                self.accept()
                
        self.execute_async(task, on_done)

    def ativar_chave(self):
        chave = self.input_chave.text()
        if not chave: return
        
        self.btn_validar_chave.setEnabled(False)
        self.btn_validar_chave.setText("Validando...")
        
        def task():
            return self.manager.ativar_chave(chave)
            
        def on_done(res):
            self.btn_validar_chave.setEnabled(True)
            self.btn_validar_chave.setText("ATIVAR")
            
            if res.get("sucesso"):
                QMessageBox.information(self, "Sucesso", res["mensagem"])
                self.accept()
            else:
                QMessageBox.warning(self, "Erro", res["mensagem"])
                
        self.execute_async(task, on_done)

    def closeEvent(self, event):
        # Se a janela fechar sem accept(), interrompe a aplicação apenas se for a tela de trava inicial
        if hasattr(self, 'modo_startup') and self.modo_startup:
            if self.result() != QDialog.DialogCode.Accepted:
                import sys
                sys.exit(0)
        super().closeEvent(event)
