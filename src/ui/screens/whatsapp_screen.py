import os
import json
import urllib.parse
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QLineEdit,
    QTextEdit, QFrame, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from src.core.telemetry import anonymous_id, record_event
from src.core.developer_access import DeveloperAccessGuard

class PaginaSilenciosa(QWebEnginePage):
    """Suprime alertas/confirmações de JavaScript do WhatsApp Web."""
    def javaScriptConfirm(self, securityOrigin, msg):
        return True
    def javaScriptAlert(self, securityOrigin, msg):
        pass

class WhatsAppScreen(QWidget):
    sig_message_sent = pyqtSignal(bool) # Emite quando apertar Enviar ou der Timeout (Disparo em lote)
    sig_phone_unavailable = pyqtSignal(str, str) # Telefone confirmado pelo WhatsApp e modo
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

        self.diagnostic_panel = QFrame()
        self.diagnostic_panel.setStyleSheet(
            "QFrame { background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; }"
            "QLabel { border: none; background: transparent; color: #1E3A8A; }"
            "QLineEdit, QTextEdit { background: white; color: #0F172A; border: 1px solid #93C5FD; border-radius: 6px; padding: 7px; }"
        )
        diagnostic_layout = QVBoxLayout(self.diagnostic_panel)
        diagnostic_title = QLabel("🧪 Teste diagnóstico de envio")
        diagnostic_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        diagnostic_layout.addWidget(diagnostic_title)
        diagnostic_help = QLabel(
            "Disponível somente durante o diagnóstico de 24 horas. Não altera pesquisas nem consome franquia."
        )
        diagnostic_help.setWordWrap(True)
        diagnostic_layout.addWidget(diagnostic_help)
        diagnostic_fields = QHBoxLayout()
        self.diagnostic_phone = QLineEdit()
        self.diagnostic_phone.setPlaceholderText("Número com DDD, por exemplo: 85999999999")
        self.diagnostic_phone.setMaxLength(16)
        diagnostic_fields.addWidget(self.diagnostic_phone, 1)
        self.btn_diagnostic_send = QPushButton("Executar teste")
        self.btn_diagnostic_send.setEnabled(False)
        self.btn_diagnostic_send.clicked.connect(self.send_diagnostic_message)
        diagnostic_fields.addWidget(self.btn_diagnostic_send)
        diagnostic_layout.addLayout(diagnostic_fields)
        self.diagnostic_message = QTextEdit()
        self.diagnostic_message.setPlaceholderText("Mensagem de teste")
        self.diagnostic_message.setPlainText("Teste diagnóstico do SaaS Assistente PRO.")
        self.diagnostic_message.setMaximumHeight(64)
        diagnostic_layout.addWidget(self.diagnostic_message)
        self.diagnostic_status = QLabel("Verificando autorização de diagnóstico…")
        self.diagnostic_status.setWordWrap(True)
        diagnostic_layout.addWidget(self.diagnostic_status)
        self.diagnostic_panel.setVisible(False)
        layout.addWidget(self.diagnostic_panel)
        
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
        self._awaiting_confirmation = False
        self._last_probe_status = ""
        self.web_view.loadFinished.connect(self._on_send_loaded)
        self.diagnostic_shortcut = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        self.diagnostic_shortcut.activated.connect(self.toggle_diagnostic_panel)

    def _on_send_loaded(self, ok):
        current_url = self.web_view.url()
        if self._send_loading and ok and current_url.host().lower() == "web.whatsapp.com":
            self._send_loading = False

    def toggle_diagnostic_panel(self):
        if self.diagnostic_panel.isVisible():
            self.diagnostic_panel.setVisible(False)
            self.btn_diagnostic_send.setEnabled(False)
            return
        autorizado, motivo = DeveloperAccessGuard.authorization_status(force=True)
        if not autorizado:
            texto = (
                "Não foi possível confirmar a autorização no servidor. Verifique a internet e tente novamente."
                if motivo == "DIAGNOSTIC_AUTHORIZATION_UNAVAILABLE" else
                "Autorize o diagnóstico por 24 horas neste computador pelo Gerador Admin."
            )
            QMessageBox.warning(self, "Acesso protegido", texto)
            return
        bloqueio = DeveloperAccessGuard.remaining_lock_seconds()
        if bloqueio:
            QMessageBox.warning(self, "Acesso temporariamente bloqueado", f"Aguarde {bloqueio // 60 + 1} minuto(s) para tentar novamente.")
            return
        senha, ok = QInputDialog.getText(
            self, "Modo Desenvolvedor / Diagnóstico",
            "Digite a senha de administrador:", QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        acesso, resultado = DeveloperAccessGuard.verify_password(senha)
        if not acesso:
            mensagem = "Acesso bloqueado por 15 minutos após tentativas incorretas." if resultado == "LOCKED" else "Senha incorreta. As tentativas são limitadas."
            QMessageBox.warning(self, "Acesso Negado", mensagem)
            return
        self.diagnostic_panel.setVisible(True)
        self.btn_diagnostic_send.setEnabled(True)
        self.diagnostic_status.setText("✅ Diagnóstico autorizado. Faça somente um envio controlado.")

    @staticmethod
    def _normalize_test_phone(value):
        digits = "".join(char for char in str(value or "") if char.isdigit())
        while digits.startswith("0"):
            digits = digits[1:]
        if len(digits) in (10, 11):
            digits = "55" + digits
        if len(digits) not in (12, 13) or not digits.startswith("55"):
            return ""
        return digits

    def send_diagnostic_message(self):
        autorizado, _motivo = DeveloperAccessGuard.authorization_status()
        if not autorizado or not self.diagnostic_panel.isVisible():
            self.diagnostic_panel.setVisible(False)
            self.btn_diagnostic_send.setEnabled(False)
            QMessageBox.warning(
                self, "Diagnóstico não autorizado",
                "Ative novamente o modo desenvolvedor com Ctrl+Shift+D.",
            )
            return
        phone = self._normalize_test_phone(self.diagnostic_phone.text())
        message = self.diagnostic_message.toPlainText().strip()
        if not phone or not message:
            QMessageBox.warning(
                self, "Dados para teste",
                "Informe um número brasileiro válido com DDD e uma mensagem de teste.",
            )
            return
        self.btn_diagnostic_send.setEnabled(False)
        self.diagnostic_status.setText("⏳ Abrindo a conversa para o teste…")
        record_event("whatsapp", "DIAGNOSTIC_TEST_STARTED", contact_ref=anonymous_id(phone))
        self.send_message(phone, message, modo="DIAGNOSTICO")
        
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
        self._awaiting_confirmation = False
        self._last_probe_status = "LOADING"
        self.modo_envio = modo
        self._send_phone = phone
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
            event_name = "SEND_CONFIRMATION_TIMEOUT" if self._awaiting_confirmation else "SEND_BUTTON_TIMEOUT"
            record_event(
                "whatsapp", event_name, "ERROR", mode=self.modo_envio,
                contact_ref=getattr(self, '_telemetry_contact_ref', ''),
                attempts=self.tentativas_click, last_probe=self._last_probe_status,
                loading=self._send_loading,
            )
            if self.modo_envio == "INDIVIDUAL":
                self.btn_enviar_link.setText("⚠️ Falha ao Enviar")
                self.btn_enviar_link.setEnabled(True)
            elif self.modo_envio == "DIAGNOSTICO":
                self.diagnostic_status.setText(
                    "❌ O WhatsApp não confirmou o envio. A mensagem foi mantida para análise."
                )
                self.btn_diagnostic_send.setEnabled(True)
            else:
                self.sig_message_sent.emit(False)
            return
            
        if self._send_loading:
            return
        if self._awaiting_confirmation:
            self._verify_send_confirmation()
            return
        js_click = r"""
        (function() {
            const normalize = value => (value || "").normalize("NFKC").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
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
                if (txt.includes("não está no whatsapp") || txt.includes("not on whatsapp") ||
                    txt.includes("isn't on whatsapp") || txt.includes("não tem uma conta do whatsapp") ||
                    /n[uú]mero de telefone.{0,100}(inv[aá]lido|n[aã]o.{0,20}v[aá]lido)/.test(txt) ||
                    /phone number.{0,100}(invalid|isn't valid|is not valid)/.test(txt)) {
                    let okBtn = dlg.querySelector('button, div[role="button"]');
                    if (okBtn) {
                        dispatchMouseEvents(okBtn);
                    }
                    return {status: "INVALID_PHONE", reason: "INVALID_PHONE_DIALOG"};
                }
            }
            
            // 2. Procura botão de enviar
            const composer = document.querySelector('#main footer [contenteditable="true"]');
            if (!composer) return {status: "NOT_FOUND", reason: "COMPOSER_NOT_FOUND"};
            if (normalize(composer.innerText) !== normalize(EXPECTED_MESSAGE)) {
                return {status: "NOT_FOUND", reason: "MESSAGE_MISMATCH", composer_length: normalize(composer.innerText).length};
            }
            let btn = document.querySelector('#main footer span[data-icon="send"]');
            if (btn) {
                let clickable = btn.closest('button') || btn.closest('div[role="button"]');
                if (clickable) {
                    dispatchMouseEvents(clickable);
                    return {status: "CLICKED", selector: "DATA_ICON_SEND"};
                }
            }
            let btn2 = document.querySelector('#main footer button[aria-label="Enviar"]') || document.querySelector('#main footer div[aria-label="Enviar"]');
            if (btn2) {
                dispatchMouseEvents(btn2);
                return {status: "CLICKED", selector: "ARIA_LABEL_PT"};
            }
            let btn3 = document.querySelector('#main footer button[aria-label="Send"]') || document.querySelector('#main footer div[aria-label="Send"]');
            if (btn3) {
                dispatchMouseEvents(btn3);
                return {status: "CLICKED", selector: "ARIA_LABEL_EN"};
            }
            return {status: "NOT_FOUND", reason: "SEND_BUTTON_NOT_FOUND"};
        })();
        """
        js_click = js_click.replace('EXPECTED_MESSAGE', json.dumps(self._expected_message))
        generation = self._navigation_generation
        self._click_pending = True
        self.web_view.page().runJavaScript(js_click, lambda status: self._finish_click(generation, status))

    def _finish_click(self, generation, status):
        if generation != self._navigation_generation:
            return
        self._click_pending = False
        self.callback_click(status)

    def callback_click(self, status):
        details = status if isinstance(status, dict) else {}
        status_name = details.get("status") if details else status
        self._last_probe_status = details.get("reason") or status_name or "NO_RESULT"
        if status_name in ("CLICKED", "SENT", True):
            self._awaiting_confirmation = True
            record_event(
                "whatsapp", "SEND_CLICK_ATTEMPTED", mode=self.modo_envio,
                contact_ref=getattr(self, '_telemetry_contact_ref', ''),
                attempts=self.tentativas_click, selector=details.get("selector", "legacy"),
            )
            if self.modo_envio == "DIAGNOSTICO":
                self.diagnostic_status.setText("⏳ Clique executado. Confirmando o envio no WhatsApp…")
        elif status_name == "CONFIRMED":
            self.click_timer.stop()
            self._awaiting_confirmation = False
            print("[WPP] Mensagem enviada com sucesso!")
            record_event(
                "whatsapp", "SEND_CONFIRMED", mode=self.modo_envio,
                contact_ref=getattr(self, '_telemetry_contact_ref', ''),
                attempts=self.tentativas_click,
                composer_cleared=bool(details.get("composer_cleared")),
                outgoing_match=bool(details.get("outgoing_match")),
            )
            if self.modo_envio == "INDIVIDUAL":
                self.btn_enviar_link.setText("✅ Link Enviado!")
                self.btn_enviar_link.setEnabled(False)
                if self.cliente_ativo and 'item' in self.cliente_ativo:
                    self.sig_link_individual_enviado.emit(self.cliente_ativo['item'])
            elif self.modo_envio == "DIAGNOSTICO":
                self.diagnostic_status.setText("✅ Envio confirmado pelo WhatsApp. Nenhuma pesquisa ou franquia foi alterada.")
                self.btn_diagnostic_send.setEnabled(True)
            else:
                self.sig_message_sent.emit(True)
                
        elif status_name == "INVALID_PHONE":
            self.click_timer.stop()
            if self.modo_envio != "DIAGNOSTICO":
                self.sig_phone_unavailable.emit(self._send_phone, self.modo_envio)
            print("[WPP] Detectado número inválido no WhatsApp Web. Pulando...")
            record_event("whatsapp", "INVALID_PHONE", "WARN", mode=self.modo_envio, contact_ref=getattr(self, '_telemetry_contact_ref', ''))
            if self.modo_envio == "INDIVIDUAL":
                self.btn_enviar_link.setText("❌ Número Inválido")
                self.btn_enviar_link.setEnabled(False)
            elif self.modo_envio == "DIAGNOSTICO":
                self.diagnostic_status.setText("❌ O WhatsApp informou que o número é inválido.")
                self.btn_diagnostic_send.setEnabled(True)
            else:
                self.sig_message_sent.emit(False)

    def _verify_send_confirmation(self):
        js_verify = r"""
        (function() {
            const normalize = value => (value || "").normalize("NFKC").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
            const expected = normalize(EXPECTED_MESSAGE);
            const composer = document.querySelector('#main footer [contenteditable="true"]');
            const composerText = normalize(composer ? composer.innerText : "");
            const outgoing = Array.from(document.querySelectorAll('#main [data-testid="msg-container"], #main .message-out'));
            const outgoingMatch = outgoing.slice(-8).some(node => normalize(node.innerText).includes(expected));
            if (composer && composerText.length === 0) {
                return {status: "CONFIRMED", composer_cleared: true, outgoing_match: outgoingMatch};
            }
            return {status: "NOT_CONFIRMED", reason: composer ? "DRAFT_REMAINS" : "COMPOSER_NOT_FOUND_AFTER_CLICK", outgoing_match: outgoingMatch};
        })();
        """.replace('EXPECTED_MESSAGE', json.dumps(self._expected_message))
        generation = self._navigation_generation
        self._click_pending = True
        self.web_view.page().runJavaScript(js_verify, lambda status: self._finish_click(generation, status))
