import os
import json
import urllib.parse
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from src.core.telemetry import anonymous_id, record_event

class PaginaSilenciosa(QWebEnginePage):
    """Suprime alertas/confirmações de JavaScript do WhatsApp Web."""
    def javaScriptConfirm(self, securityOrigin, msg):
        return True
    def javaScriptAlert(self, securityOrigin, msg):
        pass

class WhatsAppScreen(QWidget):
    sig_message_sent = pyqtSignal(bool) # Emite quando apertar Enviar ou der Timeout (Disparo em lote)
    sig_login_status_result = pyqtSignal(bool) # Emite True se logado no WhatsApp, False se na tela de QR code
    sig_link_individual_enviado = pyqtSignal(dict) # Emite quando o link individual for enviado com sucesso

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        header_layout = QHBoxLayout()
        title = QLabel("WhatsApp Web - Atendimento & Disparos")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #0F172A;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # O envio individual é iniciado exclusivamente pela lista de clientes.
        # O botão permanece visível como orientação, mas nunca é habilitado
        # nesta tela, evitando associação com uma conversa diferente da ativa.
        self.btn_enviar_link = QPushButton("🛡️ Envio disponível na Lista de Clientes")
        self.btn_enviar_link.setEnabled(False)
        self.btn_enviar_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_enviar_link.setStyleSheet("""
            QPushButton { background-color: #10B981; color: white; font-weight: bold; border-radius: 6px; padding: 8px 16px; font-size: 13px; border: 1px solid #059669; }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background-color: #F1F5F9; color: #94A3B8; border: 1px solid #CBD5E1; }
        """)
        self.btn_enviar_link.setToolTip("Selecione um cliente na lista e use Enviar Pesquisa Selecionada.")
        header_layout.addWidget(self.btn_enviar_link)
        
        btn_reload = QPushButton("🔄 Recarregar WhatsApp")
        btn_reload.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reload.setStyleSheet("background-color: white; border: 1px solid #CBD5E1; border-radius: 6px; padding: 8px 16px; color: #475569; font-weight: bold; font-size: 13px;")
        header_layout.addWidget(btn_reload)
        layout.addLayout(header_layout)
        
        browser_container = QWidget()
        browser_container.setStyleSheet("background-color: white; border: 1px solid #E2E8F0; border-radius: 8px;")
        browser_layout = QVBoxLayout(browser_container)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        
        self.web_view = QWebEngineView()
        from src.core.paths import get_base_dir
        storage_path = os.path.join(get_base_dir(), "app_data", "whatsapp")
        self.profile = QWebEngineProfile("WhatsAppProfile", self.web_view)
        self.profile.setPersistentStoragePath(storage_path)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        self.page = PaginaSilenciosa(self.profile, self.web_view)
        self.web_view.setPage(self.page)
        
        self.web_view.setUrl(QUrl("https://web.whatsapp.com/"))
        browser_layout.addWidget(self.web_view)
        layout.addWidget(browser_container)
        
        btn_reload.clicked.connect(self.web_view.reload)
        
        self.click_timer = QTimer(self)
        self.click_timer.timeout.connect(self.tentar_clicar_enviar)
        self.tentativas_click = 0
        self.modo_envio = "LOTE"
        self.cliente_ativo = None
        self._navigation_generation = 0
        self._send_loading = False
        self._click_pending = False
        self.web_view.loadFinished.connect(self._on_send_loaded)

    def _on_send_loaded(self, ok):
        if self._send_loading and ok and self.web_view.url().toString() == getattr(self, '_send_url', ''):
            self._send_loading = False
        
    def check_login_status(self):
        script = """
            (function() {
                // Se a lista de conversas (#pane-side) ou o topo (#app) estiverem carregados com as conversas.
                // O modo mais seguro de saber se não estamos na tela de login é ver se existe a barra lateral de conversas.
                let pane = document.getElementById('pane-side');
                if (pane) return true;
                
                // Outra forma é verificar o localStorage
                let wid = window.localStorage.getItem('last-wid') || window.localStorage.getItem('last-wid-md');
                if (wid) return true;
                
                return false;
            })();
        """
        self.web_view.page().runJavaScript(script, self._on_login_status_checked)
        
    def _on_login_status_checked(self, is_logged_in):
        record_event("whatsapp", "LOGIN_CHECK", logged_in=bool(is_logged_in))
        self.sig_login_status_result.emit(bool(is_logged_in))

    def abrir_conversa_cliente(self, phone, nome, link_pesquisa, mensagem_template, item_data):
        """Abre o WhatsApp Web na conversa com o cliente sem enviar o link automaticamente."""
        self.click_timer.stop()
        self._navigation_generation = getattr(self, '_navigation_generation', 0) + 1
        self.cliente_ativo = {
            'phone': phone,
            'nome': nome,
            'link': link_pesquisa,
            'mensagem': mensagem_template,
            'item': item_data
        }
        self.modo_envio = "INDIVIDUAL"
        
        # Abre o chat do número limpo
        url = f"https://web.whatsapp.com/send?phone={phone}"
        self.web_view.stop()
        self.web_view.setUrl(QUrl(url))

    def enviar_link_pesquisa_ativo(self):
        """Dispara a mensagem com o link de pesquisa no chat do cliente ativo."""
        if not self.cliente_ativo:
            return
            
        phone = self.cliente_ativo.get('phone', '')
        mensagem = self.cliente_ativo.get('mensagem', '')
        
        if not mensagem or not phone:
            return
            
        self.modo_envio = "INDIVIDUAL"
        self.btn_enviar_link.setText("⏳ Enviando Link...")
        self.btn_enviar_link.setEnabled(False)
        
        self.send_message(phone, mensagem, modo="INDIVIDUAL")

    def send_message(self, phone, message, modo="LOTE"):
        """Injeta a API do wa.me e começa a caçar o botão de enviar."""
        self.click_timer.stop()
        self._navigation_generation += 1
        self._click_pending = False
        self._send_loading = True
        self.modo_envio = modo
        self._telemetry_contact_ref = anonymous_id(phone)
        record_event("whatsapp", "SEND_STARTED", mode=modo, contact_ref=self._telemetry_contact_ref)
        encoded_msg = urllib.parse.quote(message)
        url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_msg}"
        self._send_url = url
        self._expected_message = message
        self.web_view.stop()
        self.web_view.setUrl(QUrl(url))
        
        self.tentativas_click = 0
        self.click_timer.start(2000) # Checa a cada 2 segundos se a conversa abriu

    def tentar_clicar_enviar(self):
        if self._click_pending:
            return
        self.tentativas_click += 1
        if self.tentativas_click > 20: # 40 segundos de timeout
            self.click_timer.stop()
            print(f"[WPP] Timeout! Botão de enviar não apareceu para este número.")
            record_event("whatsapp", "SEND_BUTTON_TIMEOUT", "ERROR", mode=self.modo_envio, contact_ref=getattr(self, '_telemetry_contact_ref', ''), attempts=self.tentativas_click)
            if self.modo_envio == "INDIVIDUAL":
                self.btn_enviar_link.setText("⚠️ Falha ao Enviar")
                self.btn_enviar_link.setEnabled(True)
            else:
                self.sig_message_sent.emit(False)
            return
            
        if self._send_loading:
            return
        js_click = """
        (function() {
            if (window.location.href !== EXPECTED_URL) return "NOT_FOUND";
            const composer = document.querySelector('#main footer [contenteditable="true"]');
            if (!composer || composer.innerText.trim() !== EXPECTED_MESSAGE.trim()) return "NOT_FOUND";
            function dispatchMouseEvents(el) {
                var opts = {bubbles: true, cancelable: true, view: window};
                el.dispatchEvent(new MouseEvent('mousedown', opts));
                el.dispatchEvent(new MouseEvent('mouseup', opts));
                el.dispatchEvent(new MouseEvent('click', opts));
            }
            
            // 1. Checa se o WhatsApp abriu o modal de número inválido
            let dialogs = document.querySelectorAll('div[role="dialog"], div[data-animate-modal-popup="true"]');
            for (let i = 0; i < dialogs.length; i++) {
                let dlg = dialogs[i];
                let txt = (dlg.innerText || "").toLowerCase();
                if (txt.includes("inválido") || txt.includes("invalido") || txt.includes("invalid") || 
                    txt.includes("não está no whatsapp") || txt.includes("not on whatsapp")) {
                    let okBtn = dlg.querySelector('button, div[role="button"]');
                    if (okBtn) {
                        dispatchMouseEvents(okBtn);
                    }
                    return "INVALID_PHONE";
                }
            }
            
            // 2. Procura botão de enviar
            let btn = document.querySelector('#main footer span[data-icon="send"]');
            if (btn) {
                let clickable = btn.closest('button') || btn.closest('div[role="button"]');
                if (clickable) {
                    dispatchMouseEvents(clickable);
                    return "SENT";
                }
            }
            let btn2 = document.querySelector('#main footer button[aria-label="Enviar"]') || document.querySelector('#main footer div[aria-label="Enviar"]');
            if (btn2) {
                dispatchMouseEvents(btn2);
                return "SENT";
            }
            let btn3 = document.querySelector('#main footer button[aria-label="Send"]') || document.querySelector('#main footer div[aria-label="Send"]');
            if (btn3) {
                dispatchMouseEvents(btn3);
                return "SENT";
            }
            return "NOT_FOUND";
        })();
        """
        js_click = js_click.replace('EXPECTED_URL', json.dumps(self._send_url)).replace('EXPECTED_MESSAGE', json.dumps(self._expected_message))
        generation = self._navigation_generation
        self._click_pending = True
        self.web_view.page().runJavaScript(js_click, lambda status: self._finish_click(generation, status))

    def _finish_click(self, generation, status):
        if generation != self._navigation_generation:
            return
        self._click_pending = False
        self.callback_click(status)

    def callback_click(self, status):
        if status == "SENT" or status is True:
            self.click_timer.stop()
            print("[WPP] Mensagem enviada com sucesso!")
            record_event("whatsapp", "SEND_CONFIRMED", mode=self.modo_envio, contact_ref=getattr(self, '_telemetry_contact_ref', ''), attempts=self.tentativas_click)
            if self.modo_envio == "INDIVIDUAL":
                self.btn_enviar_link.setText("✅ Link Enviado!")
                self.btn_enviar_link.setEnabled(False)
                if self.cliente_ativo and 'item' in self.cliente_ativo:
                    self.sig_link_individual_enviado.emit(self.cliente_ativo['item'])
            else:
                self.sig_message_sent.emit(True)
                
        elif status == "INVALID_PHONE":
            self.click_timer.stop()
            print("[WPP] Detectado número inválido no WhatsApp Web. Pulando...")
            record_event("whatsapp", "INVALID_PHONE", "WARN", mode=self.modo_envio, contact_ref=getattr(self, '_telemetry_contact_ref', ''))
            if self.modo_envio == "INDIVIDUAL":
                self.btn_enviar_link.setText("❌ Número Inválido")
                self.btn_enviar_link.setEnabled(False)
            else:
                self.sig_message_sent.emit(False)
