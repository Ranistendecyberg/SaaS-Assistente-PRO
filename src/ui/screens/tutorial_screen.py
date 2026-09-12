from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame
from PyQt6.QtCore import Qt

class TutorialScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Título
        lbl_titulo = QLabel("📘 Guia de Uso e Primeiros Passos")
        lbl_titulo.setStyleSheet("font-size: 24px; font-weight: bold; color: #0F172A;")
        layout.addWidget(lbl_titulo)
        
        lbl_sub = QLabel("Aprenda como utilizar todos os recursos do Assistente PRO para gerenciar, disparar pesquisas e acompanhar seus resultados.")
        lbl_sub.setStyleSheet("font-size: 14px; color: #475569; margin-bottom: 15px;")
        layout.addWidget(lbl_sub)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(15)
        
        passos = [
            ("💬 1. Conexão do Motor WhatsApp", 
             "Local onde você faz a leitura do QR Code com o aplicativo WhatsApp no seu celular para conectar o sistema. Todas as mensagens serão enviadas de forma automática por aqui.<br><br>"
             "<b>💡 Dica de Ouro:</b> De preferência, utilize sempre o WhatsApp oficial de atendimento da concessionária."),
            
            ("📄 2. Gerar Lista de Reenvio e Disparos", 
             "Para gerar a lista de clientes elegíveis e realizar os disparos das pesquisas de satisfação:<br><br>"
             "<b>1. Login myHonda:</b> Faça o login seguro na sua conta do myHonda no painel ao lado.<br>"
             "<b>2. Indicadores de Status:</b> Acompanhe os indicadores superiores. Assim que as bases forem carregadas, a lista de clientes aparecerá automaticamente.<br>"
             "<b>3. Seleção de Pesquisa:</b> Escolha no menu o tipo desejado: <b>Pesquisas SSI (Vendas)</b> ou <b>Pesquisas TSI (Pós-Vendas)</b>.<br>"
             "<b>4. Busca e Seleção:</b> Busque o cliente pelo nome e marque somente a pesquisa autorizada por ele.<br>"
             "<b>5. Envio individual:</b> Clique em <b>▶ Enviar Pesquisa Selecionada</b>. Por segurança, o sistema permite somente um cliente por vez.<br><br>"
             "<b>🛡️ Proteção contra Envios Duplicados:</b> O sistema identifica automaticamente quem já respondeu à pesquisa ou quem já recebeu mensagem recente, evitando envios repetidos para o mesmo cliente."),
              
            ("✉️ 3. Editor de Mensagens & Modelos de Campanhas", 
             "Personalize e salve diferentes modelos de mensagens para usar em suas campanhas:<br><br>"
             "<b>• Modelos Prontos:</b> Selecione no menu superior modelos já cadastrados (como <i>Mensagem Padrão</i>, <i>Campanha Sorteio de Revisão</i>, <i>Agradecimento Pós-Vendas</i>, etc.). O texto é carregado na hora.<br>"
             "<b>• Salvar Novo Modelo:</b> Escreva o texto que desejar e clique em <b>➕ Salvar Novo</b> para criar um novo modelo personalizado que ficará salvo para sempre no sistema.<br>"
             "<b>• Salvar Alterações:</b> Edite o texto de qualquer modelo e clique em <b>💾 Salvar</b> para atualizar as alterações.<br>"
             "<b>• Variáveis Dinâmicas:</b> Use os botões <b>+ [NOME]</b> e <b>+ [LINK]</b>. No momento do disparo, o sistema substitui automaticamente o nome do cliente e gera o link oficial criptografado da pesquisa Medallia."),
             
            ("📊 4. Relatórios & Dashboards (TSI e SSI)", 
             "Acompanhe o nível de satisfação dos seus clientes e o desempenho da equipe com gráficos interativos e em tempo real:<br><br>"
             "<b>• Visão Geral:</b> Visualize rapidamente o Volume Total de Pesquisas, a Nota Média Geral e o índice <b>Top2Box</b>.<br>"
             "<b>• O que é Top2Box?</b> É a porcentagem (%) de pesquisas que receberam notas de excelência (notas 9 ou 10) em relação ao total de avaliações recebidas.<br>"
             "<b>• Desempenho por Consultor:</b> Gráficos individuais por consultor com a linha de meta de 90%, facilitando a identificação dos destaques da equipe.<br>"
             "<b>• Evolução Histórica:</b> Gráficos comparativos que mostram a evolução mês a mês do volume de pesquisas e do índice de satisfação ao longo do ano.<br>"
             "<b>• Filtros Dinâmicos:</b> Filtre as análises por Concessionária, Consultor e Período (Mês Atual ou Ano Completo)."),
            
            ("⚙️ 5. Configurações de Concessionárias", 
             "Cadastre os códigos das suas concessionárias e seus respectivos nomes comerciais.<br><br>"
             "<b>💡 Por que é importante?</b> Com as lojas cadastradas, todos os filtros e relatórios dos Dashboards exibirão automaticamente os nomes amigáveis das concessionárias em vez de apenas números de códigos."),
            
            ("💳 6. Conta empresarial e cobrança",
             "<b>• Cobrança consolidada:</b> Consulte a assinatura empresarial e gere PIX ou boleto pela área Conta Empresarial.<br>"
             "<b>• Validar Chave de Acesso:</b> Insira chaves promocionais ou de cortesia para resgatar dias extras no seu plano.")
        ]
        
        for titulo, desc in passos:
            frame = QFrame()
            frame.setStyleSheet("background-color: white; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px;")
            flayout = QVBoxLayout(frame)
            flayout.setSpacing(8)
            
            lbl_t = QLabel(titulo)
            lbl_t.setStyleSheet("font-size: 16px; font-weight: bold; color: #2563EB; border: none;")
            flayout.addWidget(lbl_t)
            
            lbl_d = QLabel(desc)
            lbl_d.setStyleSheet("font-size: 13px; color: #334155; line-height: 1.4; border: none;")
            lbl_d.setWordWrap(True)
            flayout.addWidget(lbl_d)
            
            content_layout.addWidget(frame)
            
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
