"""
Lancement d'une commande dans un émulateur de terminal

La commande est toujours une LISTE d'arguments (jamais `bash -c` avec du texte
interpolé) : aucun risque d'injection via un nom de fichier ou un suffixe.
"""

import subprocess
import sys

from utils.paths import BUILD_RUNNER

# (commande, séparateur avant la commande à exécuter)
TERMINALS = [
    ["ptyxis", "--"],
    ["gnome-terminal", "--"],
    ["kgx", "--"],
    ["konsole", "-e"],
    ["xfce4-terminal", "-x"],
    ["xterm", "-e"],
]


def launch_in_terminal(argv):
    """
    Lance argv dans le premier terminal disponible.
    Retourne le Popen du terminal, ou None si aucun terminal n'est installé.
    Attention : certains terminaux (gnome-terminal) rendent la main immédiatement.
    """
    for terminal in TERMINALS:
        try:
            return subprocess.Popen(terminal + [str(a) for a in argv])
        except FileNotFoundError:
            continue
    return None


def build_runner_command(*args):
    """Commande pour core/build_runner.py (script autonome, python -I)"""
    return [sys.executable, "-I", str(BUILD_RUNNER)] + [str(a) for a in args]
