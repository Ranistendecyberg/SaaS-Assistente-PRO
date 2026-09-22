import hashlib
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from src.core.updater import (
    DownloadWorker,
    Updater,
    build_silent_installer_command,
    build_update_assistant_command,
    create_update_ssl_context,
    resolve_installed_app_path,
    stage_update_assistant,
    validate_installer_file,
)
from update_completion_helper import installer_command, launch_updated_app


class UpdaterSecurityTests(unittest.TestCase):
    def test_update_ssl_context_combines_certifi_and_windows_trust(self):
        context = mock.Mock()
        windows_certificate = b"windows-corporate-root"
        with (
            mock.patch("src.core.updater.certifi.where", return_value="certifi-ca.pem"),
            mock.patch("src.core.updater.ssl.create_default_context", return_value=context) as create,
            mock.patch(
                "src.core.updater.ssl.enum_certificates",
                return_value=[(windows_certificate, "x509_asn", True)],
                create=True,
            ) as enum_certificates,
            mock.patch(
                "src.core.updater.ssl.DER_cert_to_PEM_cert",
                return_value="-----BEGIN CERTIFICATE-----\ntrusted\n-----END CERTIFICATE-----\n",
            ),
        ):
            result = create_update_ssl_context()

        self.assertIs(result, context)
        create.assert_called_once_with(cafile="certifi-ca.pem")
        self.assertEqual(enum_certificates.call_count, 2)
        context.load_verify_locations.assert_called_once()
        self.assertIn("trusted", context.load_verify_locations.call_args.kwargs["cadata"])
        self.assertEqual(context.minimum_version, __import__("ssl").TLSVersion.TLSv1_2)

    def test_download_uses_explicit_verified_ssl_context(self):
        worker = DownloadWorker("https://example.com/update.exe", "2.1.8", "0" * 64)
        verified_context = object()
        with (
            mock.patch(
                "src.core.updater.create_update_ssl_context",
                return_value=verified_context,
            ),
            mock.patch(
                "src.core.updater.urllib.request.urlopen",
                side_effect=RuntimeError("interromper antes da gravação"),
            ) as urlopen,
        ):
            worker.run()

        self.assertIs(urlopen.call_args.kwargs["context"], verified_context)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 30)

    def test_release_build_filters_external_native_runtime(self):
        build_script = Path("build_release.py").read_text(encoding="utf-8")
        self.assertIn("codex-runtimes", build_script)
        self.assertIn("a.binaries = [entry for entry in a.binaries", build_script)

    def test_version_comparison_normalizes_missing_segments(self):
        updater = Updater("1.8")
        self.assertTrue(updater._versao_maior("1.8.1", "1.8"))
        self.assertFalse(updater._versao_maior("1.8.0", "1.8"))
        self.assertTrue(updater._versao_maior("v2.0.0", "1.99.99"))

    def test_final_version_is_newer_than_beta(self):
        updater = Updater("2.0.0-beta.1")
        self.assertTrue(updater._versao_maior("2.0.0", "2.0.0-beta.1"))
        self.assertTrue(updater._versao_maior("2.0.0-beta.2", "2.0.0-beta.1"))
        self.assertFalse(updater._versao_maior("2.0.0-beta.1", "2.0.0"))

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

    def test_update_assistant_receives_installed_app_to_reopen(self):
        with tempfile.TemporaryDirectory() as folder:
            helper = os.path.join(folder, "SaaS Update Assistant.exe")
            installer = os.path.join(folder, "installer.exe")
            open(helper, "wb").close()
            command = build_update_assistant_command(
                installer, "2.0.0", parent_pid=1234, helper_path=helper,
                launch_path=r"C:\Program Files\SaaS\SaaS Assistente PRO.exe",
            )
        self.assertEqual(command[0], helper)
        self.assertIn("--installer", command)
        self.assertIn("--parent-pid", command)
        self.assertIn("--launch-path", command)
        self.assertIn(r"C:\Program Files\SaaS\SaaS Assistente PRO.exe", command)

    def test_update_assistant_is_staged_outside_onefile_directory(self):
        with tempfile.TemporaryDirectory() as onefile_dir, tempfile.TemporaryDirectory() as staging_dir:
            bundled_helper = os.path.join(onefile_dir, "SaaS Update Assistant.exe")
            with open(bundled_helper, "wb") as helper_file:
                helper_file.write(b"MZ" + (b"helper" * 64))

            staged_helper = stage_update_assistant(
                helper_path=bundled_helper,
                staging_dir=staging_dir,
                parent_pid=4321,
            )

            self.assertEqual(os.path.dirname(staged_helper), os.path.abspath(staging_dir))
            self.assertNotEqual(os.path.dirname(staged_helper), os.path.abspath(onefile_dir))
            self.assertEqual(Path(staged_helper).read_bytes(), Path(bundled_helper).read_bytes())

    def test_update_shutdown_does_not_bypass_qt_cleanup(self):
        source = Path("src/core/updater.py").read_text(encoding="utf-8")
        self.assertNotIn("os._exit(0)", source)
        self.assertIn("staged_assistant = stage_update_assistant", source)

    def test_ota_check_runs_after_qt_event_loop_starts(self):
        source = Path("src/main.py").read_text(encoding="utf-8")
        scheduled = source.index("QTimer.singleShot(500")
        event_loop = source.index("return app.exec()")
        self.assertLess(scheduled, event_loop)

    def test_default_launch_path_targets_per_user_installation(self):
        path = resolve_installed_app_path()
        self.assertTrue(path.endswith(os.path.join("SaaS Assistente PRO", "SaaS Assistente PRO.exe")))

    def test_helper_launches_updated_executable(self):
        with tempfile.TemporaryDirectory() as folder:
            executable = os.path.join(folder, "SaaS Assistente PRO.exe")
            open(executable, "wb").close()
            with mock.patch("update_completion_helper.subprocess.Popen") as popen:
                self.assertTrue(launch_updated_app(executable))
            popen.assert_called_once()

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
