"""Assistente independente que instala a atualização e reabre o SaaS."""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import time


SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
MB_OK = 0x00000000
MB_ICONINFORMATION = 0x00000040
MB_ICONERROR = 0x00000010
MB_SETFOREGROUND = 0x00010000


def wait_for_process_exit(pid: int, timeout_seconds: int = 60) -> bool:
    """Espera o SaaS liberar o executável instalado antes de iniciar o Inno Setup."""
    if pid <= 0:
        return True
    if os.name != "nt":
        time.sleep(1.5)
        return True
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return True
    try:
        result = kernel32.WaitForSingleObject(handle, timeout_seconds * 1000)
        return result == WAIT_OBJECT_0
    finally:
        kernel32.CloseHandle(handle)


def installer_command(installer_path: str) -> list[str]:
    log_path = os.path.join(
        os.environ.get("TEMP", ""), "SaaS_Intelligence_Update", "install.log"
    )
    return [
        installer_path,
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/SP-",
        "/CLOSEAPPLICATIONS",
        "/FORCECLOSEAPPLICATIONS",
        f"/LOG={log_path}",
    ]


def show_message(text: str, title: str, error: bool = False) -> None:
    style = MB_OK | MB_SETFOREGROUND | (MB_ICONERROR if error else MB_ICONINFORMATION)
    ctypes.windll.user32.MessageBoxW(None, text, title, style)


def launch_updated_app(launch_path: str) -> bool:
    """Abre a instalação recém-atualizada e encerra o assistente."""
    normalized_path = os.path.abspath(launch_path)
    if not os.path.isfile(normalized_path):
        return False
    subprocess.Popen(
        [normalized_path],
        cwd=os.path.dirname(normalized_path),
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    return True


def run_update(installer_path: str, version: str, parent_pid: int, launch_path: str) -> int:
    if not wait_for_process_exit(parent_pid):
        show_message(
            "O SaaS ainda não foi totalmente encerrado. Aguarde alguns segundos e "
            "tente a atualização novamente.",
            "Atualização não iniciada",
            error=True,
        )
        return 2
    if not os.path.isfile(installer_path):
        show_message(
            "O instalador baixado não foi encontrado. Faça o download novamente.",
            "Falha na atualização",
            error=True,
        )
        return 3

    completed = subprocess.run(installer_command(installer_path), close_fds=True)
    if completed.returncode != 0:
        show_message(
            f"O instalador terminou com o código {completed.returncode}. "
            "O sistema ainda não deve ser aberto. Entre em contato com o suporte.",
            "Falha na atualização",
            error=True,
        )
        return completed.returncode or 4

    try:
        if not launch_updated_app(launch_path):
            raise FileNotFoundError(launch_path)
    except Exception:
        show_message(
            f"A versão {version} foi instalada, mas o sistema não conseguiu abrir "
            "automaticamente. Abra o SaaS Assistente PRO pelo atalho da Área de Trabalho.",
            "Atualização instalada",
            error=True,
        )
        return 5

    try:
        os.remove(installer_path)
    except OSError:
        pass
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Assistente de conclusão da atualização")
    parser.add_argument("--installer", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--parent-pid", type=int, default=0)
    parser.add_argument("--launch-path", required=True)
    args = parser.parse_args()
    return run_update(args.installer, args.version, args.parent_pid, args.launch_path)


if __name__ == "__main__":
    sys.exit(main())
