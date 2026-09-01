"""Prévia manual SEM REDE: python -m src.tests.preview_admin_pricing.

Todos os dados e salvamentos desta janela são fictícios e ficam só na memória.
"""
from admin_supabase import AdminSession
from supabase_admin_app import SupabaseAdminApp
import customtkinter as ctk


class OfflinePricingPreview(SupabaseAdminApp):
    def __init__(self):
        self.preview_system = {
            "current_version": "1.9.4", "minimum_version": "0.0.0",
            "default_monthly_price": 250, "installer_url": "https://example.com/instalador.exe",
            "installer_sha256": "a" * 64, "update_required": False,
            "maintenance_mode": False,
        }
        super().__init__(AdminSession("", "", {}))
        self.title("TESTE LOCAL SEM REDE - Preços do Gerador Admin")
        self._show_page("system")
        self.after(300, self.resize_preview)

    def resize_preview(self):
        self.state("normal")
        self.geometry("1280x800+40+40")

    def _request(self, action, **payload):
        if action == "list_installations":
            return {"installations": []}
        if action == "list_keys":
            return {"keys": []}
        if action == "update_system_config":
            self.preview_system.update(payload)
        elif action != "get_system_config":
            raise RuntimeError("Ação não disponível na prévia offline")
        return {"ok": True, "system": dict(self.preview_system)}

    def _show_error(self, error):
        print(repr(error), flush=True)
        self.status.configure(text=f"Erro na prévia: {error}")

    def _run(self, operation, on_success, busy="", on_error=None):
        # Sem I/O nesta prévia: callbacks locais no ciclo da interface.
        def execute():
            try:
                on_success(operation())
                self.status.configure(text="TESTE LOCAL · SEM REDE")
            except Exception as error:
                (on_error or self._show_error)(error)
        self.after(0, execute)


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    OfflinePricingPreview().mainloop()
