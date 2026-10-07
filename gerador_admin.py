"""Entrada do Gerador Administrativo seguro (Supabase + MFA)."""

import os
import sys
import traceback


def _run_build_smoke_test():
    """Confere dependências empacotadas sem abrir login ou acessar o servidor."""
    try:
        import customtkinter
        import qrcode
        from PIL import Image, ImageTk
        import admin_secure_login
        import admin_supabase
        import admin_window_utils
        import supabase_admin_app
        return 0
    except BaseException:
        log_path = os.environ.get("SAAS_ADMIN_SMOKE_LOG", "").strip()
        if log_path:
            with open(log_path, "w", encoding="utf-8") as log:
                log.write(traceback.format_exc())
        return 1


if __name__ == "__main__":
    if "--build-smoke-test" in sys.argv:
        raise SystemExit(_run_build_smoke_test())
    from admin_secure_login import run
    run()
