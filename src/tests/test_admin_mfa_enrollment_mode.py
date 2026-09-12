from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class AdminMfaEnrollmentModeTests(unittest.TestCase):
    def test_enrollment_mode_does_not_open_admin_api_before_deployment(self):
        source = (ROOT / "admin_secure_login.py").read_text("utf-8")
        start = source.index("def _finish_access")
        end = source.index("def _open_panel", start)
        finish_access = source[start:end]
        self.assertIn("if self.enroll_only", finish_access)
        self.assertLess(
            finish_access.index("if self.enroll_only"),
            finish_access.index("confirm_admin_access"),
        )
        self.assertIn('"--enroll-only" in sys.argv', source)

    def test_enrollment_success_waits_for_explicit_confirmation(self):
        source = (ROOT / "admin_secure_login.py").read_text("utf-8")
        finish_start = source.index("def _finish_access")
        finish_end = source.index("def _show_enrollment_success", finish_start)
        enroll_branch = source[finish_start:finish_end]
        success_start = finish_end
        success_end = source.index("def _open_panel", success_start)
        success_screen = source[success_start:success_end]

        self.assertIn("self._show_enrollment_success()", enroll_branch)
        self.assertNotIn("self.destroy()", enroll_branch)
        self.assertIn('text="Concluir"', success_screen)
        self.assertIn("command=self.destroy", success_screen)


if __name__ == "__main__":
    unittest.main()
