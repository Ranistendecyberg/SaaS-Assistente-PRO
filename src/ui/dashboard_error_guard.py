"""Protecao para falhas Python durante a abertura dos paineis."""

from __future__ import annotations

from datetime import datetime
from functools import wraps
import os
import traceback


def record_dashboard_error(screen, action, error):
    diagnostic_id = datetime.now().strftime("%Y%m%d%H%M%S%f")[-10:]
    try:
        from src.core.paths import get_base_dir

        log_dir = os.path.join(get_base_dir(), "app_data")
        os.makedirs(log_dir, exist_ok=True)
        frames = traceback.extract_tb(error.__traceback__)
        locations = " > ".join(
            f"{os.path.basename(frame.filename)}:{frame.lineno}:{frame.name}"
            for frame in frames[-8:]
        )
        line = (
            f"{datetime.now().astimezone().isoformat(timespec='seconds')} "
            f"id={diagnostic_id} tela={screen} acao={action} "
            f"erro={type(error).__name__} locais={locations}\n"
        )
        with open(os.path.join(log_dir, "dashboard_errors.log"), "a", encoding="utf-8") as file:
            file.write(line)
    except Exception:
        pass
    return diagnostic_id


def protect_dashboard_action(action):
    """Evita que excecoes de dados/relatorios cheguem ao sys.excepthook global."""

    def decorate(function):
        @wraps(function)
        def guarded(self, *args, **kwargs):
            try:
                return function(self, *args, **kwargs)
            except Exception as error:
                diagnostic_id = record_dashboard_error(
                    type(self).__name__, action, error,
                )
                if hasattr(self, "_is_loading_filters"):
                    self._is_loading_filters = False
                view = getattr(self, "web_view", None)
                if view is not None:
                    try:
                        view.setHtml(
                            "<!doctype html><html><body style='font-family:Segoe UI, sans-serif;"
                            "padding:28px;color:#334155;background:#F8FAFC'>"
                            "<h2>Não foi possível carregar este painel.</h2>"
                            "<p>O restante do sistema continua disponível. Clique em "
                            "<b>Atualizar Painel</b> para tentar novamente.</p>"
                            f"<p style='color:#64748B'>Código de diagnóstico: {diagnostic_id}</p>"
                            "</body></html>"
                        )
                    except Exception:
                        pass
                return None

        return guarded

    return decorate
