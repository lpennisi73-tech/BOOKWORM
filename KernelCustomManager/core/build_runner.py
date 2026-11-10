#!/usr/bin/python3
"""
KernelCustom Manager - exécution de la compilation dans un terminal

Remplace le script bash généré auparavant. Lancé SANS privilèges dans un émulateur
de terminal, avec une liste d'arguments (aucun `bash -c`) :

    python3 -I build_runner.py compile <job.json>
    python3 -I build_runner.py nconfig <linux_dir> <message_fin>

Ce fichier est autonome (aucun import de l'application). Le job JSON contient :
    linux_dir, jobs, localversion, log_file, repo_dir, status_file,
    sign (null ou {"key": ..., "cert": ...}), messages (textes déjà traduits),
    olddefconfig (true si l'application a modifié le .config),
    distcc (null ou {"cc": "distcc <compilateur>", "hosts": "..."})

Le fichier status_file permet à l'application de suivre la compilation,
même quand le terminal rend la main immédiatement (gnome-terminal) :
    {"state": "running", "pid": ...}  puis  {"state": "done", "returncode": ..., "packages": [...]}
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SIGN_FILE_CANDIDATES = (
    "scripts/sign-file",  # arbre de compilation (relatif à linux_dir)
    f"/usr/src/linux-headers-{os.uname().release}/scripts/sign-file",
    f"/lib/modules/{os.uname().release}/build/scripts/sign-file",
)


def write_status(path, **data):
    tmp = Path(f"{path}.tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(path)


def wait_enter(message):
    try:
        input(f"\n{message}")
    except EOFError:
        pass


def run_logged(cmd, cwd, log_file, append):
    """Exécute cmd en affichant ET en enregistrant la sortie (équivalent de `| tee`)"""
    sys.stdout.flush()  # les print() précédents doivent apparaître avant la sortie de make
    with open(log_file, "ab" if append else "wb") as log:
        try:
            process = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except FileNotFoundError:
            message = f"❌ {cmd[0]} introuvable : installez build-essential (sudo apt install build-essential)\n"
            sys.stdout.write(message)
            log.write(message.encode())
            return 127
        for chunk in iter(lambda: process.stdout.read1(65536), b""):
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            log.write(chunk)
        return process.wait()


def sign_modules(linux_dir, key, cert, msg):
    """Signe les modules .ko de l'arbre de compilation (avant bindeb-pkg)"""
    print(f"\n=================================\n{msg['signing_header']}\n=================================")
    sign_file = next((Path(linux_dir, c) for c in SIGN_FILE_CANDIDATES if Path(linux_dir, c).is_file()), None)
    if not sign_file:
        print("❌ Error: sign-file tool not found")
        return False

    modules = sorted(Path(linux_dir).rglob("*.ko"))
    total = len(modules)
    print(f"📦 {msg['found_modules']}: {total}\n")
    if total == 0:
        print(f"⚠️  {msg['no_modules']}")
        return True

    failed = 0
    for index, module in enumerate(modules, 1):
        if total <= 50 or index % 10 == 0 or index == total:
            print(f"\r🔏 [{index:3d}/{total:3d}] {module.name:<50}", end="", flush=True)
        result = subprocess.run([str(sign_file), "sha256", key, cert, str(module)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode != 0:
            failed += 1
            print(f"\n  ⚠️  {msg['sign_failed']}: {module.name}")
    print("\n")
    if failed:
        print(f"⚠️  {msg['signed_with_errors']}: {total - failed}/{total}")
    else:
        print(f"✅ {msg['all_signed']}: {total}")
    print("=================================\n")
    return True


def config_enabled(linux_dir, option):
    try:
        return f"\n{option}=y\n" in Path(linux_dir, ".config").read_text(errors="replace")
    except OSError:
        return False


def compile_kernel(job):
    msg = job["messages"]
    linux_dir = job["linux_dir"]
    status_file = job["status_file"]
    make_vars = [f"LOCALVERSION={job['localversion']}"] if job["localversion"] else []

    # distcc : même CC pour les deux étapes, sinon bindeb-pkg recompilerait tout
    distcc = job.get("distcc")
    if distcc:
        make_vars.append(f"CC={distcc['cc']}")
        if distcc.get("hosts"):
            os.environ["DISTCC_HOSTS"] = distcc["hosts"]

    write_status(status_file, state="running", pid=os.getpid())
    for line in msg["header"]:
        print(line)

    def finish(returncode):
        packages = []
        if returncode == 0:
            print(f"\n=================================\n{msg['success']}\n\n{msg['moving_packages']}")
            repo_dir = Path(job["repo_dir"])
            repo_dir.mkdir(parents=True, exist_ok=True)
            for deb in sorted(Path(linux_dir).resolve().parent.glob("*.deb")):
                shutil.move(str(deb), repo_dir / deb.name)
                packages.append(deb.name)
                print(f"✓ {deb.name} moved")
            print("=================================")
        else:
            print(f"\n=================================\n{msg['failed']}\nReturn code: {returncode}\n=================================")
        write_status(status_file, state="done", returncode=returncode, packages=packages)
        wait_enter(msg["press_enter"])
        return returncode

    if distcc and config_enabled(linux_dir, "CONFIG_GCC_PLUGINS"):
        print(f"⚠️  {msg['distcc_plugins']}")

    # Étape 0 : le .config a été modifié par l'application. make le remet en cohérence
    # ici, sinon la compilation poserait des questions dans le terminal
    append = False
    if job.get("olddefconfig"):
        code = run_logged(["make", "olddefconfig"] + make_vars, linux_dir, job["log_file"], append)
        if code != 0:
            return finish(code)
        append = True

    # Étape 1 : compilation
    print(f"\n{msg['compiling_modules']}")
    code = run_logged(["make", f"-j{job['jobs']}"] + make_vars, linux_dir, job["log_file"], append)
    if code != 0:
        return finish(code)

    # Étape 1b : signature SecureBoot (avant bindeb-pkg)
    if job.get("sign"):
        if not sign_modules(linux_dir, job["sign"]["key"], job["sign"]["cert"], msg):
            return finish(1)

    # Étape 2 : paquets .deb
    print(f"\n{msg['creating_package']}")
    # Pas de « fakeroot make » : bindeb-pkg gère lui-même les droits (Rules-Requires-Root: no,
    # ou dpkg-buildpackage -rfakeroot sur les anciens kernels). Un fakeroot englobant est
    # inutile et casse distcc (« libfakeroot internal error: payload not recognized! »)
    cmd = ["make", f"-j{job['jobs']}", "bindeb-pkg"] + make_vars
    return finish(run_logged(cmd, linux_dir, job["log_file"], append=True))


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "compile":
        job = json.loads(Path(sys.argv[2]).read_text())
        sys.exit(compile_kernel(job))
    if len(sys.argv) >= 4 and sys.argv[1] == "nconfig":
        code = subprocess.run(["make", "nconfig"], cwd=sys.argv[2]).returncode
        wait_enter(sys.argv[3])
        sys.exit(code)
    print(__doc__, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
