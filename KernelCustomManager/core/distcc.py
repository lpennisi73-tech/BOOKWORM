"""
Compilation distribuée avec distcc (sans GTK)

Le kernel est compilé avec `make CC="distcc <compilateur>"`. Les hôtes viennent du
champ de l'application (variable DISTCC_HOSTS) ou, s'il est vide, de la
configuration de distcc (~/.distcc/hosts, /etc/distcc/hosts).
"""

import re
import shutil
import subprocess

# localhost/8 192.168.1.20/16,lzo @hote user@hote:/usr/bin/distccd [::1]:3632 --randomize
HOSTS_RE = re.compile(r'^[\w@.:/,\[\]=+ -]*$')

# Nombre de tâches par hôte quand il n'est pas précisé (défaut de distcc)
DEFAULT_SLOTS = 4


def is_available():
    return shutil.which("distcc") is not None


def compiler():
    """
    Nom du compilateur à passer à distcc. Nom complet et versionné
    (x86_64-linux-gnu-gcc-16) : chaque machine utilise ainsi la même version de GCC,
    au lieu de son « gcc » par défaut. Le compilateur doit être installé partout.
    """
    try:
        machine = subprocess.run(["gcc", "-dumpmachine"], capture_output=True, text=True).stdout.strip()
        major = subprocess.run(["gcc", "-dumpversion"], capture_output=True, text=True).stdout.strip().split(".")[0]
    except OSError:
        return "gcc"
    for name in (f"{machine}-gcc-{major}", f"gcc-{major}"):
        if machine and major and shutil.which(name):
            return name
    return "gcc"


def is_valid_hosts(hosts):
    return bool(HOSTS_RE.match(hosts))


def suggested_jobs(hosts):
    """Nombre de tâches pour make -j : somme des limites /N des hôtes (0 si aucun hôte)"""
    total = 0
    for host in hosts.split():
        if host.startswith("--"):
            continue  # option (--randomize, --localslots=…)
        limit = re.search(r'/(\d+)', host.split(",")[0])
        total += int(limit.group(1)) if limit else DEFAULT_SLOTS
    return total
