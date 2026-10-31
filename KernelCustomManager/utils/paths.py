"""
Chemins de l'application (source unique)

Fonctionne aussi bien depuis le dépôt git que depuis le paquet installé
(/usr/lib/kernelcustom-manager) : les fichiers du programme sont localisés
par rapport à ce module, les données utilisateur suivent la spécification XDG.

Ne pas coder de chemin en dur ailleurs dans l'application.
"""

import logging
import os
import shutil
from pathlib import Path

APP_ID = "kernelcustom-manager"          # nom du paquet, des dossiers et du helper
APPLICATION_ID = "com.kernelcustom.manager"  # id D-Bus / GTK (.desktop, icône, polkit)

log = logging.getLogger(__name__)

# ==================== Fichiers du programme ====================

APP_DIR = Path(__file__).resolve().parent.parent
TRANSLATIONS_DIR = APP_DIR / "translations"
# Thème d'icônes local (icône com.kernelcustom.manager), utilisé depuis le dépôt git.
# Installé, le paquet place les icônes dans /usr/share/icons/hicolor.
ICONS_DIR = APP_DIR / "data" / "icons"
BUILD_RUNNER = APP_DIR / "core" / "build_runner.py"

# Helpers privilégiés : chemin FIXE, référencé par la policy polkit
HELPER_DIR = Path("/usr/libexec") / APP_ID

# ==================== Données utilisateur (XDG) ====================


def _xdg(variable, default):
    value = os.environ.get(variable, "")
    # La spécification impose un chemin absolu, sinon on ignore la variable
    return Path(value) if value.startswith("/") else Path.home() / default


def data_dir():
    """
    Dossier de travail : sources, compilations, paquets, clés MOK, historiques…
    ~/.local/share/kernelcustom-manager (KCM_DATA_DIR pour les tests)
    """
    override = os.environ.get("KCM_DATA_DIR")
    if override:
        return Path(override)
    return _xdg("XDG_DATA_HOME", ".local/share") / APP_ID


def config_dir():
    """Préférences (langue…) : ~/.config/kernelcustom-manager"""
    return _xdg("XDG_CONFIG_HOME", ".config") / APP_ID


def debug_log_file():
    return data_dir() / "logs" / "kernelcustom-manager.log"


# ==================== Migration depuis la v2.x ====================

LEGACY_DATA_DIR = Path.home() / "KernelCustomManager" / "build"
USR_SRC = Path("/usr/src")


def _points_into(target, directory):
    try:
        return Path(target).is_absolute() and Path(target).is_relative_to(directory)
    except ValueError:
        return False


def _rewrite_symlinks(root, old, new, max_depth=2):
    """
    Réécrit les liens symboliques absolus qui pointaient dans l'ancien dossier
    (ex: build/linux -> .../sources/linux-6.16.9). Profondeur limitée : on ne
    parcourt pas l'intérieur des arbres de sources (liens relatifs, inchangés).
    """
    rewritten = 0
    for dirpath, dirnames, filenames in os.walk(root):
        depth = len(Path(dirpath).relative_to(root).parts)
        if depth >= max_depth:
            dirnames[:] = []
        for name in dirnames + filenames:
            path = Path(dirpath) / name
            if not path.is_symlink():
                continue
            target = os.readlink(path)
            if _points_into(target, old):
                path.unlink()
                path.symlink_to(new / Path(target).relative_to(old))
                rewritten += 1
    return rewritten


def _usr_src_links_into(directory):
    """Liens de /usr/src (créés pour DKMS) qui pointent dans directory"""
    links = []
    try:
        entries = list(USR_SRC.iterdir())
    except OSError:
        return links
    for entry in entries:
        if entry.is_symlink() and _points_into(os.readlink(entry), directory):
            links.append(entry)
    return links


def migrate_legacy_data():
    """
    Déplace ~/KernelCustomManager/build vers le dossier XDG (une seule fois).

    - Les liens symboliques internes sont réécrits vers le nouvel emplacement.
    - Si des liens de /usr/src (DKMS) pointent vers l'ancien dossier, un lien
      de compatibilité ~/KernelCustomManager/build -> nouveau dossier est laissé
      pour qu'ils restent valides (les recréer demanderait les droits root).

    Retourne un message (str) décrivant la migration, ou None si rien à faire.
    """
    old = LEGACY_DATA_DIR
    new = data_dir()

    if old.is_symlink() or not old.is_dir():
        return None
    if new.exists() and any(new.iterdir()):
        log.warning(f"Migration ignorée : {new} existe déjà et n'est pas vide (ancien dossier conservé : {old})")
        return None

    new.parent.mkdir(parents=True, exist_ok=True)
    if new.exists():
        new.rmdir()

    try:
        os.rename(old, new)          # même système de fichiers : instantané
    except OSError:
        shutil.move(str(old), new)   # sinon copie + suppression

    rewritten = _rewrite_symlinks(new, old, new)
    message = f"Dossier de travail déplacé : {old} → {new}"
    if rewritten:
        message += f"\n{rewritten} lien(s) symbolique(s) mis à jour."

    dkms_links = _usr_src_links_into(old)
    if dkms_links:
        old.symlink_to(new)
        message += (
            f"\nDes liens de /usr/src pointent encore vers l'ancien dossier "
            f"({', '.join(l.name for l in dkms_links)}) : un lien de compatibilité "
            f"{old} → {new} a été créé. Recréez ces liens depuis l'onglet Sources "
            f"pour pouvoir le supprimer."
        )
    else:
        try:
            old.parent.rmdir()  # ~/KernelCustomManager s'il est vide
        except OSError:
            pass

    log.info(message)
    return message
