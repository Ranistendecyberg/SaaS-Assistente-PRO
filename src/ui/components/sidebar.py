from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QSpacerItem, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal

class Sidebar(QWidget):
    navigation_requested = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self.setFixedWidth(260)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: #0F172A; color: white; border-right: 1px solid #1E293B;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 20, 15, 15) # Margem menor no rodapé para ele grudar embaixo
        layout.setSpacing(10)
        
        # Logo/Title
        title = QLabel("ASSISTENTE PRO")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white; padding-bottom: 20px; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        self.buttons = []
        
        # Operação Principal
        op_label = QLabel("OPERAÇÃO PRINCIPAL")
        op_label.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold; margin-top: 10px; border: none;")
        layout.addWidget(op_label)
        
        btn_extracao = self.create_nav_button("📄 Gera Lista Reenvio", 0)
        btn_wpp = self.create_nav_button("💬 Motor WhatsApp", 1)
        btn_relatorios = self.create_nav_button("📊 Relatórios / Dashboard", 2)
        layout.addWidget(btn_extracao)
        layout.addWidget(btn_wpp)
        layout.addWidget(btn_relatorios)
        
        # Sistema de Gestão
        gestao_label = QLabel("SISTEMA DE GESTÃO")
        gestao_label.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold; margin-top: 20px; border: none;")
        layout.addWidget(gestao_label)
        
        btn_config = self.create_nav_button("⚙️ Configuração de Lojas", 3)
        btn_conta = self.create_nav_button("🏢 Conta Empresarial", 9)
        btn_licenca = self.create_nav_button("🔑 Validar Chave de Acesso", 5)
        layout.addWidget(btn_config)
        layout.addWidget(btn_conta)
        layout.addWidget(btn_licenca)
        
        # Ajuda & Suporte
        ajuda_label = QLabel("AJUDA & SUPORTE")
        ajuda_label.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold; margin-top: 20px; border: none;")
        layout.addWidget(ajuda_label)
        
        btn_tutorial = self.create_nav_button("📘 Tutorial do Sistema", 6)
        btn_sugestoes = self.create_nav_button("💡 Sugestões de Melhoria", 7)
        btn_sobre = self.create_nav_button("ℹ️ Sobre o Sistema", 8)
        layout.addWidget(btn_tutorial)
        layout.addWidget(btn_sugestoes)
        layout.addWidget(btn_sobre)
        
        # Spacer para empurrar o rodapé para baixo
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
        # Rodapé - Créditos (Adaptado para SaaS)
        rodape = QWidget()
        rodape.setStyleSheet("background-color: #1E293B; border-radius: 8px; border: none;")
        rodape_layout = QVBoxLayout(rodape)
        rodape_layout.setContentsMargins(15, 15, 15, 15)
        self.creditos = QLabel("💰 Plano: Carregando...")
        self.creditos.setStyleSheet("color: #22C55E; font-weight: bold; border: none;")
        self.wpp_diario = QLabel("📱 Envios: Ilimitados")
        self.wpp_diario.setStyleSheet("color: #3B82F6; font-weight: bold; border: none;")
        rodape_layout.addWidget(self.creditos)
        rodape_layout.addWidget(self.wpp_diario)
        layout.addWidget(rodape)
        
        # Inicia a busca da licença assincronamente
        self.workers = []
        self.buscar_status_licenca()
        
        # Seleciona o primeiro botão por padrão
        self.set_active_button(6)
        
    def buscar_status_licenca(self):
        from src.core.license_manager import LicenseManager
        from PyQt6.QtCore import QThread, pyqtSignal
        
        class LicenseWorker(QThread):
            result_ready = pyqtSignal(object)
            def run(self):
                mgr = LicenseManager()
                res = mgr.validar_licenca()
                self.result_ready.emit(res)
                
        worker = LicenseWorker()
        worker.result_ready.connect(self.atualizar_label_licenca)
        self.workers.append(worker)
        worker.start()
        
    def atualizar_label_licenca(self, dados):
        if not dados:
            self.creditos.setText("💰 Plano: Erro")
            self.creditos.setStyleSheet("color: #EF4444; font-weight: bold; border: none;")
            return
            
        dias = dados.get("dias_restantes", 0)
        status = dados.get("status", "vencida")
        extras = dados.get("mensagens_extras", 0)
        
        texto_dias = f"{dias} dias" if dias > 1 else "Último dia (até 22h)" if dias == 1 else "0 dias"
        
        if status == "trial":
            self.creditos.setText(f"💰 Teste Grátis: {texto_dias}")
            self.creditos.setStyleSheet("color: #F59E0B; font-weight: bold; border: none;")
        elif status == "ativa":
            self.creditos.setText(f"💰 Plano PRO: {texto_dias}")
            self.creditos.setStyleSheet("color: #22C55E; font-weight: bold; border: none;")
        else:
            self.creditos.setText("💰 Plano: Vencido")
            self.creditos.setStyleSheet("color: #EF4444; font-weight: bold; border: none;")
            
        if extras > 0:
            self.wpp_diario.setText(f"📱 Bônus de Licença: {extras} msgs")
            self.wpp_diario.setStyleSheet("color: #8B5CF6; font-weight: bold; border: none;")
        elif status in ["trial", "ativa"]:
            enviadas = dados.get("enviadas_hoje", 0)
            limite = dados.get("limite_diario", 6)
            self.wpp_diario.setText(f"📱 Envios Hoje: {enviadas}/{limite}")
            if enviadas >= limite:
                self.wpp_diario.setStyleSheet("color: #EF4444; font-weight: bold; border: none;")
            else:
                self.wpp_diario.setStyleSheet("color: #3B82F6; font-weight: bold; border: none;")
        else:
            self.wpp_diario.setText("📱 Envios: Bloqueado")
            self.wpp_diario.setStyleSheet("color: #EF4444; font-weight: bold; border: none;")
        
    def create_nav_button(self, text, index):
        btn = QPushButton(text)
        btn.setProperty("nav_index", index)
        # O estilo padrão será definido no método set_active_button
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _, idx=index: self.handle_nav_click(idx))
        self.buttons.append(btn)
        return btn
        
    def handle_nav_click(self, index):
        self.set_active_button(index)
        self.navigation_requested.emit(index)
        
    def set_active_button(self, index):
        for btn in self.buttons:
            if btn.property("nav_index") == index:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2563EB;
                        color: white;
                        text-align: left;
                        padding: 10px 15px;
                        border: none;
                        border-radius: 6px;
                        font-size: 13px;
                        font-weight: bold;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #CBD5E1;
                        text-align: left;
                        padding: 10px 15px;
                        border: none;
                        border-radius: 6px;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background-color: #1E293B;
                        color: white;
                    }
                """)
