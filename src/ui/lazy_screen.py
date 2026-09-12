"""Proxy de carregamento sob demanda (lazy) para telas PyQt6.

Permite que `MainWindow.setup_screens()` registre todas as rotas no
`QStackedWidget` sem instanciar telas pesadas antes do primeiro acesso.
A tela real é criada na primeira vez em que o widget se torna visível.

Uso típico
----------
    stack.addWidget(LazyScreen(ExtractionScreen))
    # ExtractionScreen.__init__ NÃO é chamado aqui

    # Quando o usuário navega para essa rota:
    # → showEvent dispara → ExtractionScreen é criada → layout substituído
    
Callbacks pós-inicialização
---------------------------
Registre funções que dependem da tela já instanciada usando `on_ready`:

    lazy = LazyScreen(ExtractionScreen)
    lazy.on_ready(lambda screen: screen.algum_sinal.connect(slot))
"""

from __future__ import annotations

from typing import Callable, List, Optional, Type

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget


class LazyScreen(QWidget):
    """Wrapper que instancia `screen_class` na primeira exibição."""

    def __init__(
        self,
        screen_class: Type[QWidget],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._screen_class = screen_class
        self._screen_instance: Optional[QWidget] = None
        self._ready_callbacks: List[Callable[[QWidget], None]] = []
        self._initialized = False

        # Layout que receberá a tela real quando instanciada
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

    def on_ready(self, callback: Callable[[QWidget], None]) -> None:
        """Registra um callback executado imediatamente após a tela ser criada.

        Se a tela já estiver pronta, o callback é executado imediatamente.
        """
        if self._initialized and self._screen_instance is not None:
            callback(self._screen_instance)
        else:
            self._ready_callbacks.append(callback)

    def screen(self) -> Optional[QWidget]:
        """Retorna a instância da tela real, ou None se ainda não criada."""
        return self._screen_instance

    def _ensure_initialized(self) -> None:
        """Cria a tela real se ainda não foi feito."""
        if self._initialized:
            return
        self._initialized = True
        try:
            instance = self._screen_class()
            self._screen_instance = instance
            self.layout().addWidget(instance)
            # Executar callbacks registrados
            for callback in self._ready_callbacks:
                try:
                    callback(instance)
                except Exception as exc:
                    import logging
                    logging.warning(
                        f"LazyScreen callback falhou para {self._screen_class.__name__}: {exc}"
                    )
            self._ready_callbacks.clear()
        except Exception as exc:
            import logging
            logging.error(
                f"LazyScreen: falha ao instanciar {self._screen_class.__name__}: {exc}"
            )

    # ------------------------------------------------------------------
    # Intercept Qt events
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:  # type: ignore[override]
        """Instancia a tela real na primeira exibição."""
        self._ensure_initialized()
        super().showEvent(event)
