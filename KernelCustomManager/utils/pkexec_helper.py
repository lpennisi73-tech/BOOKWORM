"""
Accès aux opérations privilégiées via pkexec

Toutes les opérations root passent par deux programmes installés (root:root) :
- kernelcustom-helper           : liste blanche d'actions (policy auth_admin_keep)
- kernelcustom-nvidia-installer : installeur NVIDIA .run (policy auth_admin)

Ne JAMAIS appeler pkexec directement ailleurs dans l'application,
ni avec `bash -c` ou `shell=True`.
"""

import subprocess
from pathlib import Path

from utils.paths import HELPER_DIR


# Codes de retour de pkexec
PKEXEC_DISMISSED = 126   # dialogue d'authentification annulé
PKEXEC_NOT_AUTHORIZED = 127


class PkexecHelper:
    """Lance les actions du helper privilégié"""

    HELPER_PATH = str(HELPER_DIR / "kernelcustom-helper")
    NVIDIA_INSTALLER_PATH = str(HELPER_DIR / "kernelcustom-nvidia-installer")

    NOT_INSTALLED_MSG = (
        "Le helper privilégié n'est pas installé "
        f"({HELPER_DIR}). Installez le paquet kernelcustom-manager."
    )

    # ---------- Bas niveau ----------

    @staticmethod
    def is_helper_installed():
        return Path(PkexecHelper.HELPER_PATH).is_file()

    @staticmethod
    def command(action, *args, program=None):
        """Ligne de commande pkexec pour une action (liste d'arguments)"""
        return ["pkexec", program or PkexecHelper.HELPER_PATH, action] + [str(a) for a in args]

    @staticmethod
    def _error_message(returncode, stderr):
        if returncode == PKEXEC_DISMISSED:
            return "Authentification annulée"
        if returncode == PKEXEC_NOT_AUTHORIZED:
            return "Authentification refusée"
        return (stderr or "").strip() or f"Échec (code {returncode})"

    @staticmethod
    def run(action, *args, program=None, input=None, timeout=None):
        """
        Exécute une action et attend la fin.
        Retourne (success, stdout, message_erreur)
        """
        program = program or PkexecHelper.HELPER_PATH
        if not Path(program).is_file():
            return False, "", PkexecHelper.NOT_INSTALLED_MSG
        try:
            result = subprocess.run(
                PkexecHelper.command(action, *args, program=program),
                capture_output=True, text=True, input=input, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            return False, "", "Délai dépassé"
        if result.returncode == 0:
            return True, result.stdout, ""
        return False, result.stdout, PkexecHelper._error_message(result.returncode, result.stderr)

    @staticmethod
    def stream(action, *args, on_line=None, program=None):
        """
        Exécute une action en lisant sa sortie ligne par ligne (stderr fusionné).
        on_line(ligne) est appelé pour chaque ligne.
        Retourne (success, toutes_les_lignes, message_erreur)
        """
        program = program or PkexecHelper.HELPER_PATH
        if not Path(program).is_file():
            return False, [], PkexecHelper.NOT_INSTALLED_MSG
        process = subprocess.Popen(
            PkexecHelper.command(action, *args, program=program),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        lines = []
        for line in process.stdout:
            line = line.rstrip("\n")
            lines.append(line)
            if on_line:
                on_line(line)
        process.wait()
        if process.returncode == 0:
            return True, lines, ""
        return False, lines, PkexecHelper._error_message(process.returncode, "\n".join(lines[-20:]))

    # ---------- Paquets ----------

    @staticmethod
    def install_packages(*deb_files):
        """Installe des paquets kernel .deb locaux (dépendances résolues par apt)"""
        return PkexecHelper.run("install-debs", *deb_files)

    @staticmethod
    def apt_install(*packages, update=False):
        """Installe des paquets depuis les dépôts Debian"""
        return PkexecHelper.run("apt-install", *(["--update"] if update else []), *packages)

    @staticmethod
    def remove_packages(*packages, autoremove=True):
        """Purge des paquets (le helper refuse le kernel en cours d'exécution)"""
        return PkexecHelper.run("remove-packages", *(["--autoremove"] if autoremove else []), *packages)

    @staticmethod
    def reboot():
        return PkexecHelper.run("reboot")

    # ---------- MOK / SecureBoot ----------

    @staticmethod
    def mokutil_diagnose():
        return PkexecHelper.run("mokutil-diagnose")

    @staticmethod
    def mokutil_import(key_file, password=None):
        """Import d'une clé MOK ; password est envoyé à mokutil sur stdin (2 fois)"""
        stdin = f"{password}\n{password}\n" if password else None
        return PkexecHelper.run("mokutil-import", key_file, input=stdin)

    @staticmethod
    def mokutil_delete(key_file):
        return PkexecHelper.run("mokutil-delete", key_file)

    @staticmethod
    def mokutil_reset():
        return PkexecHelper.run("mokutil-reset")

    @staticmethod
    def terminal_command(action, *args):
        """
        Commande pour une action interactive lancée dans un terminal
        (mokutil demande un mot de passe temporaire) : le terminal attend Entrée à la fin.
        """
        return PkexecHelper.command(action, "--wait", *args)

    # ---------- NVIDIA ----------

    @staticmethod
    def nvidia(action, *args, timeout=None):
        """Actions de l'installeur NVIDIA : run, schedule, cancel, uninstall"""
        return PkexecHelper.run(action, *args, program=PkexecHelper.NVIDIA_INSTALLER_PATH, timeout=timeout)
