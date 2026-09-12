import os
import sys
import shutil
import subprocess
import hashlib
import json
import re

def main():
    versao = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower().lstrip("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+", versao):
        raise SystemExit("Uso: python build_release.py 1.9.1")
    cwd = os.path.abspath(os.path.dirname(__file__))
    os.chdir(cwd)
    scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
    # O runtime de documentos do ambiente de desenvolvimento adiciona DLLs de
    # Poppler/libheif ao PATH. Elas não pertencem ao Desktop e podem substituir
    # o UCRT/ICU correto durante a carga do Qt WebEngine.
    clean_path = [
        entry for entry in os.environ.get("PATH", "").split(os.pathsep)
        if "\\.cache\\codex-runtimes\\" not in entry.lower()
    ]
    os.environ["PATH"] = os.pathsep.join([scripts_dir, *clean_path])
    
    print(f"=== INICIANDO BUILD OFICIAL v{versao} ===")
    
    # 0. Limpeza
    print("\n[0/4] Limpando pastas temporárias...")
    for folder in ["build", ".pyarmor"]:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder, ignore_errors=True)
            except Exception as e:
                print(f"Aviso ao remover {folder}: {e}")
                
    spec_to_remove = f"SaaS Assistente PRO v{versao}.spec"
    if os.path.exists(spec_to_remove):
        try:
            os.remove(spec_to_remove)
        except Exception:
            pass

    # 1. Update version
    print("\n[1/4] Atualizando controle de versão e instalador...")
    subprocess.run([sys.executable, "update_version.py", versao], check=True)

    # 2. Assistente independente: instala e reabre o SaaS após o processo anterior sair.
    print("\n[2/4] Gerando Assistente de Atualização...")
    helper_dist = os.path.join(cwd, "dist_update_helper")
    helper_work = os.path.join(cwd, "build_update_helper")
    helper_exe = os.path.join(helper_dist, "SaaS Update Assistant.exe")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--windowed", "--icon=logo.ico",
        "--name", "SaaS Update Assistant",
        "--distpath", helper_dist, "--workpath", helper_work,
        "update_completion_helper.py",
    ], check=True)
    if not os.path.isfile(helper_exe):
        raise FileNotFoundError(f"Assistente de atualização não encontrado: {helper_exe}")

    # 3. pyi-makespec. O atualizador seguro está integrado ao aplicativo principal.
    print(f"\n[3/4] Gerando spec para SaaS Assistente PRO v{versao}...")
    makespec_cmd = [
        sys.executable, "-m", "PyInstaller.utils.cliutils.makespec",
        "--splash", os.path.join("src", "assets", "icon.png"),
        "--onefile",
        "--windowed",
        "--icon=logo.ico",
        "--add-data", "logo.ico;.",
        "--add-data", f"{os.path.join('src', 'assets')};{os.path.join('src', 'assets')}",
        "--add-binary", f"{helper_exe};.",
        "--name", f"SaaS Assistente PRO v{versao}",
        "--paths", cwd,
        os.path.join("src", "main.py")
    ]
    subprocess.run(makespec_cmd, check=True)

    # Defesa adicional: mesmo que o PATH externo volte a ser contaminado,
    # nunca empacotar bibliotecas nativas do runtime auxiliar do ambiente.
    generated_spec = os.path.join(cwd, f"SaaS Assistente PRO v{versao}.spec")
    with open(generated_spec, "r", encoding="utf-8") as spec_file:
        spec_text = spec_file.read()
    filter_code = (
        "\n# Remove DLLs externas do runtime de documentos (Poppler/libheif).\n"
        "a.binaries = [entry for entry in a.binaries "
        "if '\\\\.cache\\\\codex-runtimes\\\\' not in str(entry[1]).lower()]\n\n"
    )
    if "pyz = PYZ(a.pure)" not in spec_text:
        raise RuntimeError("Não foi possível aplicar o filtro seguro ao arquivo spec.")
    spec_text = spec_text.replace("pyz = PYZ(a.pure)", filter_code + "pyz = PYZ(a.pure)", 1)
    with open(generated_spec, "w", encoding="utf-8") as spec_file:
        spec_file.write(spec_text)

    # 3. PyArmor gen --pack
    print(f"\n[4/4] Ofuscando código e empacotando com PyArmor...")
    pyarmor_cmd = [
        sys.executable, "-m", "pyarmor.cli", "gen",
        "--pack", f"SaaS Assistente PRO v{versao}.spec",
        os.path.join("src", "main.py")
    ]
    subprocess.run(pyarmor_cmd, check=True)

    # 5. Inno Setup
    print("\n[5/5] Compilando Instalador Oficial Inno Setup...")
    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe"
    ]
    iscc_bin = next((p for p in iscc_paths if os.path.exists(p)), None)
    if not iscc_bin:
        raise FileNotFoundError("Compilador Inno Setup (ISCC.exe) não foi encontrado.")
        
    subprocess.run([iscc_bin, "criador_instalador.iss"], check=True)

    installer = os.path.join(cwd, "dist", f"Instalador_SaaS_Assistente_PRO_v{versao}.exe")
    if not os.path.exists(installer):
        raise FileNotFoundError(f"Instalador não encontrado: {installer}")
    digest = hashlib.sha256()
    with open(installer, "rb") as release_file:
        for block in iter(lambda: release_file.read(1024 * 1024), b""):
            digest.update(block)
    manifest = {
        "version": versao,
        "filename": os.path.basename(installer),
        "sha256": digest.hexdigest(),
        "size_bytes": os.path.getsize(installer),
    }
    manifest_path = os.path.join(cwd, "dist", f"release_v{versao}.json")
    with open(manifest_path, "w", encoding="utf-8") as manifest_file:
        json.dump(manifest, manifest_file, ensure_ascii=False, indent=2)

    print("\n=======================================================")
    print(f"BUILD v{versao} CONCLUÍDO COM SUCESSO!")
    print(f"Instalador gerado em: dist\\Instalador_SaaS_Assistente_PRO_v{versao}.exe")
    print(f"SHA-256: {manifest['sha256']}")
    print(f"Manifesto: dist\\release_v{versao}.json")
    print("=======================================================\n")

if __name__ == "__main__":
    main()
