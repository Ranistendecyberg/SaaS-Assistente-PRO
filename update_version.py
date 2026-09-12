"""Atualiza de forma coordenada a versão do Desktop e do instalador."""

from __future__ import annotations

import re
import sys
from pathlib import Path


VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")


def update_release_version(version: str, root: Path | None = None) -> None:
    normalized = str(version or "").strip().lower().lstrip("v")
    if not VERSION_PATTERN.fullmatch(normalized):
        raise ValueError("Versão inválida. Use o formato 2.0.0.")

    project_root = Path(root or Path(__file__).resolve().parent)
    version_path = project_root / "src" / "version.py"
    installer_path = project_root / "criador_instalador.iss"

    version_path.write_text(f'__version__ = "{normalized}"\n', encoding="utf-8")

    content = installer_path.read_text(encoding="utf-8")
    content = re.sub(r"^AppVersion=.*$", f"AppVersion={normalized}", content, flags=re.MULTILINE)
    content = re.sub(
        r"^OutputBaseFilename=.*$",
        f"OutputBaseFilename=Instalador_SaaS_Assistente_PRO_v{normalized}",
        content,
        flags=re.MULTILINE,
    )
    content = re.sub(
        r'^Source: "dist\\SaaS Assistente PRO[^\"]*\.exe"',
        lambda _match: f'Source: "dist\\SaaS Assistente PRO v{normalized}.exe"',
        content,
        flags=re.MULTILINE,
    )
    installer_path.write_text(content, encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python update_version.py 2.0.0")
        return 1
    try:
        update_release_version(sys.argv[1])
    except (OSError, ValueError) as error:
        print(error)
        return 1
    print(f"Versão preparada: {sys.argv[1].strip().lower().lstrip('v')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
