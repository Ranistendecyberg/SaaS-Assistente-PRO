import unittest

from supabase_admin_app import _normalize_report_id


class AdminReportIdTests(unittest.TestCase):
    def test_preserva_id_de_15_caracteres(self):
        self.assertEqual(_normalize_report_id("00OVP000008YZJh"), "00OVP000008YZJh")

    def test_extrai_id_de_link_classico(self):
        self.assertEqual(
            _normalize_report_id(
                "https://myhonda.my.site.com/concessionaria/00OVP000008YZJh"
            ),
            "00OVP000008YZJh",
        )

    def test_extrai_id_de_18_caracteres_do_link_moderno(self):
        self.assertEqual(
            _normalize_report_id(
                "https://myhonda.my.site.com/leads/s/report/00O4M000004CsIiUAK/relatorio"
            ),
            "00O4M000004CsIiUAK",
        )

    def test_aceita_link_em_markdown(self):
        self.assertEqual(
            _normalize_report_id(
                "[Relatório](https://myhonda.my.site.com/concessionaria/00OVP000008YZJh)"
            ),
            "00OVP000008YZJh",
        )

    def test_permite_campo_vazio(self):
        self.assertEqual(_normalize_report_id(""), "")

    def test_rejeita_valor_sem_id_de_relatorio(self):
        with self.assertRaises(ValueError):
            _normalize_report_id("https://myhonda.my.site.com/concessionaria/login")


if __name__ == "__main__":
    unittest.main()
