import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from src.core.updater import (
    Updater,
    build_silent_installer_command,
    build_update_assistant_command,
    validate_installer_file,
)
from update_completion_helper import installer_command


class UpdaterSecurityTests(unittest.TestCase):
    def test_release_build_filters_external_native_runtime(self):
        build_script = Path("build_release.py").read_text(encoding="utf-8")
        self.assertIn("codex-runtimes", build_script)
        self.assertIn("a.binaries = [entry for entry in a.binaries", build_script)

    def test_version_comparison_normalizes_missing_segments(self):
        updater = Updater("1.8")
        self.assertTrue(updater._versao_maior("1.8.1", "1.8"))
        self.assertFalse(updater._versao_maior("1.8.0", "1.8"))
        self.assertTrue(updater._versao_maior("v2.0.0", "1.99.99"))

    def test_sha256_reference_has_expected_format(self):
        with tempfile.TemporaryDirectory() as folder:
            installer = os.path.join(folder, "installer.exe")
            with open(installer, "wb") as file:
                file.write(b"safe-installer-test")
            with open(installer, "rb") as file:
                checksum = hashlib.sha256(file.read()).hexdigest()
            self.assertEqual(len(checksum), 64)
            self.assertTrue(all(character in "0123456789abcdef" for character in checksum))
            self.assertGreater(os.path.getsize(installer), 0)

    def test_silent_install_command_installs_without_user_interaction(self):
        command = build_silent_installer_command(r"C:\Temp\installer.exe")
        self.assertEqual(command[0], r"C:\Temp\installer.exe")
        self.assertIn("/VERYSILENT", command)
        self.assertIn("/SUPPRESSMSGBOXES", command)
        self.assertIn("/CLOSEAPPLICATIONS", command)
        self.assertIn("/FORCECLOSEAPPLICATIONS", command)
        self.assertTrue(any(argument.startswith("/LOG=") for argument in command))

    def test_update_assistant_waits_instead_of_reopening_desktop(self):
        with tempfile.TemporaryDirectory() as folder:
            helper = os.path.join(folder, "SaaS Update Assistant.exe")
            installer = os.path.join(folder, "installer.exe")
            open(helper, "wb").close()
            command = build_update_assistant_command(
                installer, "1.9.6", parent_pid=1234, helper_path=helper
            )
        self.assertEqual(command[0], helper)
        self.assertIn("--installer", command)
        self.assertIn("--parent-pid", command)
        self.assertNotIn("SaaS Assistente PRO.exe", command)

    def test_completion_helper_uses_same_safe_installer_flags(self):
        command = installer_command(r"C:\Temp\installer.exe")
        self.assertIn("/VERYSILENT", command)
        self.assertIn("/NORESTART", command)
        self.assertIn("/FORCECLOSEAPPLICATIONS", command)
        self.assertTrue(any(argument.startswith("/LOG=") for argument in command))

    def test_installer_validation_rejects_non_windows_file(self):
        with tempfile.TemporaryDirectory() as folder:
            fake_installer = os.path.join(folder, "fake.exe")
            with open(fake_installer, "wb") as file:
                file.write(b"NO" + (b"x" * 110_000))
            with open(fake_installer, "rb") as file:
                checksum = hashlib.sha256(file.read()).hexdigest()
            with self.assertRaisesRegex(RuntimeError, "não é um instalador Windows"):
                validate_installer_file(fake_installer, checksum)

    def test_installer_validation_accepts_matching_pe_signature(self):
        with tempfile.TemporaryDirectory() as folder:
            installer = os.path.join(folder, "valid.exe")
            with open(installer, "wb") as file:
                file.write(b"MZ" + (b"x" * 110_000))
            with open(installer, "rb") as file:
                checksum = hashlib.sha256(file.read()).hexdigest()
            self.assertEqual(validate_installer_file(installer, checksum), checksum)
