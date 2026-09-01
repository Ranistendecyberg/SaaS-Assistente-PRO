import os
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QLineEdit, QFormLayout, 
                             QMessageBox, QFrame, QSplitter)
from PyQt6.QtCore import Qt

class ConfigScreen(QWidget):
    def __init__(self):
        super().__init__()
        from src.core.paths import get_base_dir
        self.config_path = os.path.join(get_base_dir(), "app_data", "config.json")
        self.config_data = {"lojas": [], "consultores": []}
        self.load_config()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 15, 30, 30)
        layout.setSpacing(15)
        lbl_titulo = QLabel("⚙️ Configurações de Lojas e Equipe")
        lbl_titulo.setStyleSheet("color: #1E293B; font-size: 24px; font-weight: 800;")
        layout.addWidget(lbl_titulo)
        
        # Splitter para dividir tela em duas colunas (Lojas e Consultores)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- PAINEL LOJAS ---
        painel_lojas = QFrame()
        painel_lojas.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #E2E8F0;")
        layout_lojas = QVBoxLayout(painel_lojas)
        
        lbl_lojas = QLabel("🏢 Concessionárias Cadastradas")
        lbl_lojas.setStyleSheet("font-weight: bold; color: #475569; font-size: 14px; border: none;")
        layout_lojas.addWidget(lbl_lojas)
        
        self.lista_lojas = QListWidget()
        self.lista_lojas.setStyleSheet("border: 1px solid #CBD5E1; border-radius: 4px;")
        layout_lojas.addWidget(self.lista_lojas)
        
        form_lojas = QFormLayout()
        self.in_loja_nome = QLineEdit()
        self.in_loja_cnpj = QLineEdit()
        self.in_loja_cnpj.setPlaceholderText("Somente números")
        self.in_loja_meta_tsi = QLineEdit()
        self.in_loja_meta_tsi.setPlaceholderText("Ex: 15")
        form_lojas.addRow("Nome da Loja:", self.in_loja_nome)
        form_lojas.addRow("Código:", self.in_loja_cnpj)
        form_lojas.addRow("Meta TSI:", self.in_loja_meta_tsi)
        layout_lojas.addLayout(form_lojas)
        
        btn_add_loja = QPushButton("➕ Adicionar Loja")
        btn_add_loja.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        btn_add_loja.clicked.connect(self.add_loja)
        layout_lojas.addWidget(btn_add_loja)
        
        btn_del_loja = QPushButton("🗑️ Remover Selecionada")
        btn_del_loja.setStyleSheet("background-color: #EF4444; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        btn_del_loja.clicked.connect(self.del_loja)
        layout_lojas.addWidget(btn_del_loja)
        
        btn_edit_loja = QPushButton("💾 Salvar Alterações")
        btn_edit_loja.setStyleSheet("background-color: #F59E0B; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        btn_edit_loja.clicked.connect(self.edit_loja)
        layout_lojas.addWidget(btn_edit_loja)
        
        self.lista_lojas.itemClicked.connect(self.on_loja_clicked)
        
        splitter.addWidget(painel_lojas)
        
        # --- PAINEL CONSULTORES ---
        painel_consultores = QFrame()
        painel_consultores.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #E2E8F0;")
        layout_cons = QVBoxLayout(painel_consultores)
        
        lbl_cons = QLabel("👥 Consultores de Venda/Serviço")
        lbl_cons.setStyleSheet("font-weight: bold; color: #475569; font-size: 14px; border: none;")
        layout_cons.addWidget(lbl_cons)
        
        self.lista_cons = QListWidget()
        self.lista_cons.setStyleSheet("border: 1px solid #CBD5E1; border-radius: 4px;")
        layout_cons.addWidget(self.lista_cons)
        
        form_cons = QFormLayout()
        self.in_cons_nome = QLineEdit()
        self.in_cons_cpf = QLineEdit()
        self.in_cons_cpf.setPlaceholderText("Somente números")
        form_cons.addRow("Nome Consultores / Vendedores:", self.in_cons_nome)
        form_cons.addRow("CPF:", self.in_cons_cpf)
        layout_cons.addLayout(form_cons)
        
        btn_add_cons = QPushButton("➕ Adicionar Consultor")
        btn_add_cons.setStyleSheet("background-color: #10B981; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        btn_add_cons.clicked.connect(self.add_consultor)
        layout_cons.addWidget(btn_add_cons)
        
        btn_del_cons = QPushButton("🗑️ Remover Selecionado")
        btn_del_cons.setStyleSheet("background-color: #EF4444; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        btn_del_cons.clicked.connect(self.del_consultor)
        layout_cons.addWidget(btn_del_cons)
        
        btn_edit_cons = QPushButton("💾 Salvar Alterações")
        btn_edit_cons.setStyleSheet("background-color: #F59E0B; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        btn_edit_cons.clicked.connect(self.edit_consultor)
        layout_cons.addWidget(btn_edit_cons)
        
        self.lista_cons.itemClicked.connect(self.on_cons_clicked)
        
        splitter.addWidget(painel_consultores)
        # Define os tamanhos iniciais do splitter (50% / 50%)
        splitter.setSizes([500, 500])
        
        layout.addWidget(splitter, 1) # O 1 faz o splitter puxar todo o espaço vertical disponível
        
        # --- PAINEL MANUTENÇÃO ---
        painel_manutencao = QFrame()
        painel_manutencao.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #E2E8F0; margin-top: 10px;")
        layout_manutencao = QHBoxLayout(painel_manutencao)
        
        lbl_manutencao = QLabel("🛠️ Manutenção do Sistema:")
        lbl_manutencao.setStyleSheet("font-weight: bold; color: #475569; font-size: 14px; border: none;")
        layout_manutencao.addWidget(lbl_manutencao)
        
        layout_manutencao.addStretch()
        
        btn_limpar_historico = QPushButton("🧹 Limpar Histórico de Envios")
        btn_limpar_historico.setStyleSheet("background-color: #F59E0B; color: white; font-weight: bold; padding: 8px 15px; border-radius: 4px;")
        btn_limpar_historico.setToolTip("Apaga a memória de quem já recebeu mensagem, permitindo reenviar para os mesmos clientes.")
        btn_limpar_historico.clicked.connect(self.limpar_historico)
        layout_manutencao.addWidget(btn_limpar_historico)
        
        layout.addWidget(painel_manutencao)
        
        self.refresh_lists()

    def load_config(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config_data = json.load(f)
            except Exception:
                pass

    def save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Erro ao salvar: {e}")

    def refresh_lists(self):
        self.lista_lojas.clear()
        for loja in self.config_data.get("lojas", []):
            meta = loja.get('meta_tsi', '0')
            self.lista_lojas.addItem(f"{loja['nome']} (Código: {loja['cnpj']} | Meta TSI: {meta})")
            
        self.lista_cons.clear()
        for cons in self.config_data.get("consultores", []):
            self.lista_cons.addItem(f"{cons['nome']} (CPF: {cons['cpf']})")

    def add_loja(self):
        nome = self.in_loja_nome.text().strip()
        cnpj = self.in_loja_cnpj.text().strip()
        meta = self.in_loja_meta_tsi.text().strip()
        if not nome or not cnpj:
            QMessageBox.warning(self, "Aviso", "Preencha o Nome e o Código.")
            return
        self.config_data.setdefault("lojas", []).append({"nome": nome, "cnpj": cnpj, "meta_tsi": meta})
        self.save_config()
        self.refresh_lists()
        self.in_loja_nome.clear()
        self.in_loja_cnpj.clear()
        self.in_loja_meta_tsi.clear()

    def del_loja(self):
        row = self.lista_lojas.currentRow()
        if row >= 0:
            del self.config_data["lojas"][row]
            self.save_config()
            self.refresh_lists()
            
    def limpar_historico(self):
        resposta = QMessageBox.question(
            self,
            "Limpar Histórico de Envios?",
            "Isso apagará a memória do sistema sobre quem já recebeu mensagens.\n\n"
            "Todos os clientes da lista voltarão a aparecer como 'Não Enviado', "
            "permitindo que você dispare mensagens para eles novamente.\n\n"
            "Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if resposta == QMessageBox.StandardButton.Yes:
            from src.core.database import DatabaseManager
            db = DatabaseManager()
            sucesso = db.clear_sent_history()
            
            if sucesso:
                QMessageBox.information(
                    self, 
                    "Sucesso", 
                    "Histórico de envios limpo com sucesso!\n\n"
                    "Os clientes já podem receber mensagens novamente."
                )
            else:
                QMessageBox.warning(self, "Erro", "Não foi possível limpar o histórico.")

    def add_consultor(self):
        nome = self.in_cons_nome.text().strip()
        cpf_raw = self.in_cons_cpf.text().strip()
        
        if not nome or not cpf_raw:
            QMessageBox.warning(self, "Aviso", "Preencha o Nome e o CPF.")
            return
            
        import re
        # Remove tudo que não for número (pontos, traços, espaços)
        cpf_numeros = re.sub(r'\D', '', cpf_raw)
        
        # Preenche com zeros à esquerda até dar 20 caracteres
        cpf_formatado = cpf_numeros.zfill(20)
        
        self.config_data.setdefault("consultores", []).append({"nome": nome, "cpf": cpf_formatado})
        self.save_config()
        self.refresh_lists()
        self.in_cons_nome.clear()
        self.in_cons_cpf.clear()

    def del_consultor(self):
        row = self.lista_cons.currentRow()
        if row >= 0:
            del self.config_data["consultores"][row]
            self.save_config()
            self.refresh_lists()

    def on_loja_clicked(self, item):
        idx = self.lista_lojas.row(item)
        if idx >= 0 and idx < len(self.config_data.get("lojas", [])):
            loja = self.config_data["lojas"][idx]
            self.in_loja_nome.setText(loja.get("nome", ""))
            self.in_loja_cnpj.setText(loja.get("cnpj", ""))
            self.in_loja_meta_tsi.setText(str(loja.get("meta_tsi", "15")))

    def edit_loja(self):
        row = self.lista_lojas.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Aviso", "Selecione uma loja para editar.")
            return
            
        nome = self.in_loja_nome.text().strip()
        cnpj = self.in_loja_cnpj.text().strip()
        meta = self.in_loja_meta_tsi.text().strip()
        if not nome or not cnpj:
            QMessageBox.warning(self, "Aviso", "Nome e Código são obrigatórios.")
            return
            
        if "lojas" not in self.config_data:
            self.config_data["lojas"] = []
            
        self.config_data["lojas"][row] = {"nome": nome, "cnpj": cnpj, "meta_tsi": meta}
        self.save_config()
        self.refresh_lists()
        self.in_loja_nome.clear()
        self.in_loja_cnpj.clear()
        self.in_loja_meta_tsi.clear()
        QMessageBox.information(self, "Sucesso", "Loja editada com sucesso!")

    def on_cons_clicked(self, item):
        idx = self.lista_cons.row(item)
        if idx >= 0 and idx < len(self.config_data.get("consultores", [])):
            cons = self.config_data["consultores"][idx]
            self.in_cons_nome.setText(cons.get("nome", ""))
            self.in_cons_cpf.setText(cons.get("cpf", ""))

    def edit_consultor(self):
        row = self.lista_cons.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um consultor para editar.")
            return
            
        nome = self.in_cons_nome.text().strip()
        cpf = self.in_cons_cpf.text().strip()
        if not nome or not cpf:
            QMessageBox.warning(self, "Aviso", "Nome e CPF são obrigatórios.")
            return
            
        if "consultores" not in self.config_data:
            self.config_data["consultores"] = []
            
        self.config_data["consultores"][row] = {"nome": nome, "cpf": cpf}
        self.save_config()
        self.refresh_lists()
        self.in_cons_nome.clear()
        self.in_cons_cpf.clear()
        QMessageBox.information(self, "Sucesso", "Consultor editado com sucesso!")
