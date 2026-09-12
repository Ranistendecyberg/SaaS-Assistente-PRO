from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class AdminVisualDesignTests(unittest.TestCase):
    def test_panel_uses_light_cards_and_grouped_navigation(self):
        source = (ROOT / "supabase_admin_app.py").read_text("utf-8")
        self.assertIn('BG = "#F4F7FB"', source)
        self.assertIn('CARD = "#FFFFFF"', source)
        self.assertIn('SIDEBAR = "#0F1B33"', source)
        self.assertIn('"CLIENTES E LICENÇAS"', source)
        self.assertIn('"SISTEMA E SUPORTE"', source)
        self.assertIn('Por computador', source)
        self.assertIn('Por empresa', source)
        self.assertIn('"Auditoria e diagnósticos"', source)

    def test_machine_and_company_scopes_are_explained_without_losing_actions(self):
        source = (ROOT / "supabase_admin_app.py").read_text("utf-8")
        self.assertIn("Cada linha representa um computador", source)
        self.assertIn("Cada assinatura reúne uma empresa inteira", source)
        self.assertIn("Editar assinatura da empresa", source)
        self.assertIn("Bloquear / liberar esta máquina", source)
        self.assertIn("def open_selected_enterprise_device", source)
        self.assertIn("self.client_tree.selection_set(hardware)", source)

    def test_message_limits_are_easy_to_find_and_explain_sequential_sending(self):
        source = (ROOT / "supabase_admin_app.py").read_text("utf-8")
        self.assertIn('"Licença e envios"', source)
        self.assertIn('text="LIMITES DE ENVIO"', source)
        self.assertIn('"Clientes permitidos por disparo"', source)
        self.assertIn("o sistema envia um por vez, em sequência", source)

    def test_kpis_are_hidden_on_task_specific_pages(self):
        source = (ROOT / "supabase_admin_app.py").read_text("utf-8")
        self.assertIn('if key in {"clients", "enterprises"}', source)
        self.assertIn("self.kpi_frame.pack_forget()", source)

    def test_login_uses_labels_and_security_explanation(self):
        source = (ROOT / "admin_secure_login.py").read_text("utf-8")
        self.assertIn('ctk.set_appearance_mode("light")', source)
        self.assertIn('text="E-mail administrativo"', source)
        self.assertIn('text="Senha"', source)
        self.assertIn('Sua senha não é armazenada', source)

    def test_windows_are_centered_after_layout_without_forced_maximize(self):
        panel = (ROOT / "supabase_admin_app.py").read_text("utf-8")
        login = (ROOT / "admin_secure_login.py").read_text("utf-8")
        helper = (ROOT / "admin_window_utils.py").read_text("utf-8")

        self.assertNotIn('self.state("zoomed")', panel)
        self.assertIn("center_window(self, width, height)", panel)
        self.assertIn("center_window(self, 520, 620)", login)
        self.assertIn("MonitorFromWindow", helper)
        self.assertIn("rcWork", helper)
        self.assertIn("window._get_window_scaling()", helper)
        self.assertIn("physical_width", helper)
        self.assertIn("max_width_fraction", helper)


if __name__ == "__main__":
    unittest.main()
