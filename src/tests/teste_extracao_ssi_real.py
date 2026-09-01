import sys
import os
import json
import re
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QTextEdit
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtCore import QUrl, QTimer
from bs4 import BeautifulSoup

class SSITestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LABORATÓRIO: Extração SSI Real")
        self.setGeometry(100, 100, 1200, 800)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # Botões de controle
        self.btn_login = QPushButton("0. Fazer Login (myHonda)")
        self.btn_login.clicked.connect(self.abrir_login)
        self.layout.addWidget(self.btn_login)
        
        self.btn_iniciar = QPushButton("1. Abrir Relatório SSI")
        self.btn_iniciar.clicked.connect(self.abrir_relatorio)
        self.btn_iniciar.setEnabled(False)
        self.layout.addWidget(self.btn_iniciar)
        
        self.btn_filtros = QPushButton("2. Injetar Filtros")
        self.btn_filtros.clicked.connect(self.injetar_filtros)
        self.btn_filtros.setEnabled(False)
        self.layout.addWidget(self.btn_filtros)
        
        self.btn_extrair = QPushButton("3. Extrair Tabela (Sem Pandas)")
        self.btn_extrair.clicked.connect(self.extrair_tabela)
        self.btn_extrair.setEnabled(False)
        self.layout.addWidget(self.btn_extrair)
        
        # Log de saída (tamanho fixo pequeno)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFixedHeight(100)
        self.layout.addWidget(self.log_output)
        
        # Navegador 100% Independente (Sessão Limpa só para o Laboratório)
        self.profile = QWebEngineProfile() # Off-the-record real
        self.page = QWebEnginePage(self.profile, self)
        self.browser = QWebEngineView()
        self.browser.setPage(self.page)
        
        # Força o navegador a ocupar todo o resto do espaço
        from PyQt6.QtWidgets import QSizePolicy
        self.browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.layout.addWidget(self.browser)
        
        self.browser.loadFinished.connect(self.on_load_finished)
        
    def log(self, text):
        self.log_output.append(text)
        print(text)

    def abrir_login(self):
        url = "https://myhonda.my.site.com/concessionaria/login"
        self.log(f"Abrindo tela de login: {url}")
        self.browser.setUrl(QUrl(url))
        self.log("Por favor, faça o login. Quando terminar, clique no botão 1.")
        self.btn_iniciar.setEnabled(True)

    def abrir_relatorio(self):
        url = "https://myhonda.my.site.com/concessionaria/00OKk000000JHzc"
        self.log(f"Abrindo URL: {url}")
        self.browser.setUrl(QUrl(url))
        self.btn_filtros.setEnabled(True)

    def on_load_finished(self, ok):
        if ok:
            self.log("Página carregada. Se você já estiver logado, a tabela deve aparecer em breve.")

    def injetar_filtros(self):
        self.log("Injetando script de filtros...")
        script_filtros = """
        (function() {
            try {
                function selectOptionByText(selectTag, textMatch) {
                    for (let i = 0; i < selectTag.options.length; i++) {
                        if (selectTag.options[i].text.includes(textMatch)) {
                            selectTag.selectedIndex = i;
                            let event = new Event('change', { bubbles: true });
                            selectTag.dispatchEvent(event);
                            return true;
                        }
                    }
                    return false;
                }
                
                let selects = document.querySelectorAll('select');
                let changedAny = false;
                
                // O layout padrão tem 4 selects fixos:
                // 0: Resumir informações por
                // 1: Mostrar
                // 2: Campo de data
                // 3: Intervalo
                
                if (selects.length >= 4) {
                    if (selectOptionByText(selects[0], 'Concessionária de vendas: Número da conta') || 
                        selectOptionByText(selects[0], 'Concessionária de vendas: Nome da conta')) changedAny = true;
                        
                    if (selectOptionByText(selects[1], 'Todos os relações de posses') || 
                        selectOptionByText(selects[1], 'Todas as relações de posses')) changedAny = true;
                        
                    if (selectOptionByText(selects[2], 'Data de resposta SSI 2W')) changedAny = true;
                    if (selectOptionByText(selects[3], 'Este mês')) changedAny = true;
                }
                
                if (changedAny) {
                    let allBtns = document.querySelectorAll('input[type="submit"], input[type="button"], button, input.btn');
                    for (let i = 0; i < allBtns.length; i++) {
                        let btn = allBtns[i];
                        let text = (btn.value || btn.innerText || btn.title || "").toLowerCase();
                        if (text.includes('executar')) {
                            btn.click();
                            return "FILTROS_APLICADOS_E_BOTAO_CLICADO";
                        }
                    }
                    return "FILTROS_APLICADOS_MAS_BOTAO_NAO_ENCONTRADO";
                }
                return "JA_CONFIGURADO_OU_NAO_ENCONTRADO";
            } catch(e) { return "ERRO: " + e; }
        })();
        """
        self.browser.page().runJavaScript(script_filtros, self.resultado_filtros)

    def resultado_filtros(self, res):
        self.log(f"Resultado da injeção de filtros: {res}")
        self.log("Aguarde a página recarregar a tabela (se os filtros mudaram), e então clique em Extrair Tabela.")
        self.btn_extrair.setEnabled(True)

    def extrair_tabela(self):
        self.log("Buscando HTML completo da página e iframes...")
        script_html = """
            (function() {
                var htmlFinal = document.documentElement.outerHTML;
                var frames = document.querySelectorAll('iframe');
                for (var i = 0; i < frames.length; i++) {
                    try {
                        var doc = frames[i].contentDocument || frames[i].contentWindow.document;
                        if (doc) htmlFinal += doc.documentElement.outerHTML;
                    } catch(e) { } 
                }
                return htmlFinal;
            })();
        """
        self.browser.page().runJavaScript(script_html, self.processar_html)

    def processar_html(self, html_content):
        self.log(f"HTML obtido. Tamanho: {len(html_content)} bytes. Analisando com BeautifulSoup...")
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            novos_registros = []
            linhas_all = soup.find_all("tr")
            header_row = soup.find("tr", class_="headerRow")
            
            if not header_row:
                self.log("ERRO: Linha de cabeçalho (class='headerRow') não encontrada. A tabela ainda não carregou.")
                return
                
            headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
            self.log(f"Cabeçalhos encontrados ({len(headers)}): {headers[:5]}...")
            
            current_loja = "Desconhecida"
            
            for linha in linhas_all:
                texto_linha = linha.get_text(separator=" ", strip=True)
                
                # Identifica a linha de agrupamento da concessionária
                if "Concessionária de vendas: Número da conta:" in texto_linha:
                    match = re.search(r'Número da conta:\s*(\d+)', texto_linha)
                    if match:
                        current_loja = match.group(1)
                
                classes = linha.get("class", [])
                if "even" in classes or "odd" in classes:
                    celulas = [td.get_text(strip=True) for td in linha.find_all(["td", "th"])]
                    if len(celulas) == len(headers):
                        registro = dict(zip(headers, celulas))
                        # Força a gravação da loja se houver agrupamento
                        if current_loja != "Desconhecida" or "Concessionária de vendas: Número da conta" not in registro:
                            registro["Concessionária de vendas: Número da conta"] = current_loja
                            
                        novos_registros.append(registro)
            
            self.log(f"SUCESSO! {len(novos_registros)} registros extraídos com segurança.")
            
            if novos_registros:
                # Salva no arquivo de teste
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                app_data_dir = os.path.join(base_dir, "app_data")
                os.makedirs(app_data_dir, exist_ok=True)
                
                out_path = os.path.join(app_data_dir, "historico_ssi_teste.json")
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(novos_registros, f, ensure_ascii=False, indent=4)
                    
                self.log(f"Arquivo salvo em: {out_path}")
                self.log("Teste finalizado com sucesso! Nenhuma memória estourada.")
                
        except Exception as e:
            self.log(f"ERRO FATAL durante a extração manual: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SSITestWindow()
    win.show()
    sys.exit(app.exec())
