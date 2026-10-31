"""
Outil de nettoyage du dossier de travail (sources, compilations, paquets, logs…)

Logique pure, sans GTK : l'interface (GTK4) appelle scan() puis clean().
Aucune action ne nécessite les droits root : seul le dossier de travail de
l'utilisateur est concerné.

Règles de sécurité :
- Seuls des chemins situés DANS le dossier de travail peuvent être supprimés.
- Ne sont jamais supprimés : les dossiers utilisés via /usr/src ou
  /lib/modules/*/build (DKMS), les sources et headers du kernel en cours
  d'exécution (uname -r). La protection est recalculée au moment de supprimer.
- Les clés MOK ne sont listées que sur demande explicite (include_keys=True).
- Les profils, historiques et le journal en cours ne sont jamais listés.

Utilisation en ligne de commande (lecture seule) :
    python3 -m core.cleanup_manager [--keys]
"""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from utils import paths

log = logging.getLogger(__name__)

# Ordre d'affichage + sélection par défaut (clés i18n : cleanup.category.<nom>)
CATEGORIES = {
    'build_objects':   True,   # make clean dans un arbre de sources
    'archives':        True,   # tarballs et sous-produits de bindeb-pkg
    'logs':            True,
    'driver_downloads': True,
    'sources':         False,  # arbre de sources complet
    'headers':         False,
    'packages':        False,
    'driver_backups':  False,
    'config_backups':  False,
    'secureboot_keys': False,
}

# Raisons (clés i18n : cleanup.reason.<code>)
REASON_USR_SRC = 'linked_usr_src'          # protégé
REASON_RUNNING = 'running_kernel'          # protégé
REASON_ACTIVE_BUILD = 'active_build'       # information
REASON_INSTALLED = 'installed_kernel'      # information
REASON_KEYS = 'secureboot_keys'            # avertissement

# Fichiers produits par la compilation (estimation de l'espace libéré par make clean)
BUILD_OUTPUT_SUFFIXES = ('.o', '.ko', '.a', '.mod', '.mod.c', '.mod.o', '.cmd', '.d', '.lds', '.order', '.symvers.tmp')
BUILD_OUTPUT_NAMES = ('vmlinux', 'vmlinux.o', 'vmlinux.a', 'bzImage', 'System.map.tmp')

ARCHIVE_SUFFIXES = ('.tar', '.tar.xz', '.tar.gz', '.tar.bz2', '.tar.zst', '.buildinfo', '.changes')


@dataclass
class CleanupItem:
    category: str
    path: Path
    size: int                    # octets (estimation pour build_objects)
    action: str = 'delete'       # 'delete' ou 'make_clean'
    protected: bool = False      # jamais supprimable
    reason: str = ''             # code de raison (voir REASON_*)
    selected: bool = False       # sélection par défaut proposée à l'interface

    @property
    def name(self):
        return self.path.name


# ==================== Utilitaires ====================

def human_size(size):
    """Taille lisible (ex: 1.4 Go). Unités françaises."""
    for unit in ('o', 'Ko', 'Mo', 'Go'):
        if size < 1024 or unit == 'Go':
            return f"{size:.0f} {unit}" if unit == 'o' else f"{size:.1f} {unit}"
        size /= 1024


def tree_size(path, predicate=None):
    """Taille d'un fichier ou d'un dossier (sans suivre les liens symboliques)"""
    path = Path(path)
    try:
        if path.is_symlink() or path.is_file():
            return path.lstat().st_size
    except OSError:
        return 0
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for name in filenames:
            if predicate and not predicate(name):
                continue
            try:
                total += os.lstat(os.path.join(dirpath, name)).st_size
            except OSError:
                pass
    return total


def _is_build_output(name):
    return name.endswith(BUILD_OUTPUT_SUFFIXES) or name in BUILD_OUTPUT_NAMES


def _realpath(path):
    return Path(os.path.realpath(path))


def _contains(parent, child):
    """True si child est parent ou se trouve dedans (chemins réels)"""
    try:
        return child == parent or child.is_relative_to(parent)
    except ValueError:
        return False


# ==================== Gestionnaire ====================

class CleanupManager:
    """Inventaire et suppression des éléments du dossier de travail"""

    def __init__(self, base_dir=None, usr_src=Path("/usr/src"), modules_dir=Path("/lib/modules"),
                 running_release=None):
        self.base_dir = Path(base_dir) if base_dir else paths.data_dir()
        self.usr_src = Path(usr_src)
        self.modules_dir = Path(modules_dir)
        self.running_release = running_release or os.uname().release

        self.sources_dir = self.base_dir / "sources"
        self.repo_dir = self.base_dir / "kernels_repo"
        self.log_dir = self.base_dir / "logs"
        self.drivers_dir = self.base_dir / "drivers"
        self.driver_backups_dir = self.base_dir / "drivers_backup"
        self.configs_dir = self.base_dir / "configs"
        self.keys_dir = self.base_dir / "secureboot" / "keys"

    # ---------- Protection ----------

    def _system_link_targets(self):
        """Cibles réelles des liens de /usr/src et de /lib/modules/*/build|source"""
        targets = set()
        candidates = []
        try:
            candidates += [e for e in self.usr_src.iterdir() if e.is_symlink()]
        except OSError:
            pass
        try:
            for kernel in self.modules_dir.iterdir():
                candidates += [kernel / "build", kernel / "source"]
        except OSError:
            pass
        for link in candidates:
            if link.is_symlink():
                targets.add(_realpath(link))
        return targets

    def _is_running_kernel_dir(self, path):
        """Sources linux-<v> ou headers linux-headers-<v> du kernel en cours"""
        name = path.name
        release = self.running_release
        if name.startswith("linux-headers-"):
            return name[len("linux-headers-"):] == release
        if name.startswith("linux-"):
            version = name[len("linux-"):]
            return release == version or release.startswith((version + "-", version + "+"))
        return False

    def protection(self, path, link_targets=None):
        """Retourne (protégé, raison)"""
        real = _realpath(path)
        targets = self._system_link_targets() if link_targets is None else link_targets
        for target in targets:
            # Le dossier est utilisé (directement ou en partie) par un lien système
            if _contains(real, target) or _contains(target, real):
                return True, REASON_USR_SRC
        if self._is_running_kernel_dir(path):
            return True, REASON_RUNNING
        return False, ''

    def _active_build_dir(self):
        link = self.base_dir / "linux"
        return _realpath(link) if link.is_symlink() else None

    def _installed_kernel_packages(self):
        """Noms des paquets linux-image/headers installés (dpkg)"""
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f", "${binary:Package} ${db:Status-Status}\n", "linux-image-*", "linux-headers-*"],
                capture_output=True, text=True
            )
        except FileNotFoundError:
            return set()
        return {line.split()[0].split(":")[0] for line in result.stdout.splitlines()
                if line.endswith(" installed")}

    # ---------- Inventaire ----------

    def scan(self, include_keys=False):
        """Liste les éléments nettoyables, triés par catégorie puis par taille décroissante"""
        targets = self._system_link_targets()
        active_build = self._active_build_dir()
        items = []

        def add(category, path, size, **kwargs):
            item = CleanupItem(category, Path(path), size, **kwargs)
            if 'selected' not in kwargs:
                item.selected = CATEGORIES[category] and not item.protected
            items.append(item)

        # Sources, objets de compilation et headers
        if self.sources_dir.is_dir():
            for entry in sorted(self.sources_dir.iterdir()):
                if entry.is_symlink():
                    continue
                if entry.is_dir() and entry.name.startswith("linux-headers-"):
                    protected, reason = self.protection(entry, targets)
                    add('headers', entry, tree_size(entry), protected=protected, reason=reason)
                elif entry.is_dir() and entry.name.startswith("linux-"):
                    protected, reason = self.protection(entry, targets)
                    if not reason and active_build == _realpath(entry):
                        reason = REASON_ACTIVE_BUILD
                    add('sources', entry, tree_size(entry), protected=protected, reason=reason)
                    # make clean conserve .config et de quoi compiler des modules externes :
                    # possible même sur un arbre utilisé par DKMS
                    objects = tree_size(entry, _is_build_output)
                    if objects:
                        add('build_objects', entry, objects, action='make_clean')
                elif entry.is_file() and entry.name.endswith(ARCHIVE_SUFFIXES):
                    add('archives', entry, tree_size(entry))

        # Paquets .deb compilés
        if self.repo_dir.is_dir():
            installed = self._installed_kernel_packages()
            for deb in sorted(self.repo_dir.glob("*.deb")):
                package = deb.name.split("_")[0]
                add('packages', deb, tree_size(deb),
                    reason=REASON_INSTALLED if package in installed else '')

        # Logs de compilation (pas le journal de l'application en cours d'écriture)
        if self.log_dir.is_dir():
            current_log = _realpath(paths.debug_log_file())
            for entry in sorted(self.log_dir.iterdir()):
                if entry.is_file() and _realpath(entry) != current_log:
                    add('logs', entry, tree_size(entry))

        # Pilotes téléchargés et sauvegardes
        if self.drivers_dir.is_dir():
            for entry in sorted(self.drivers_dir.iterdir()):
                add('driver_downloads', entry, tree_size(entry))
        if self.driver_backups_dir.is_dir():
            for entry in sorted(self.driver_backups_dir.iterdir()):
                add('driver_backups', entry, tree_size(entry))
        if self.configs_dir.is_dir():
            for entry in sorted(self.configs_dir.iterdir()):
                add('config_backups', entry, tree_size(entry))

        # Clés MOK : uniquement sur demande explicite, jamais sélectionnées
        if include_keys and self.keys_dir.is_dir():
            for entry in sorted(self.keys_dir.iterdir()):
                add('secureboot_keys', entry, tree_size(entry), reason=REASON_KEYS, selected=False)

        order = list(CATEGORIES)
        items.sort(key=lambda i: (order.index(i.category), -i.size, i.name))
        return items

    @staticmethod
    def summary(items):
        """{catégorie: (nombre, taille)} pour les éléments non protégés"""
        result = {}
        for item in items:
            if item.protected:
                continue
            count, size = result.get(item.category, (0, 0))
            result[item.category] = (count + 1, size + item.size)
        return result

    # ---------- Suppression ----------

    def _check_deletable(self, item, link_targets):
        """Revalidation juste avant l'action (l'état a pu changer depuis scan())"""
        path = item.path
        if not path.exists() and not path.is_symlink():
            raise ValueError("n'existe plus")
        # Le chemin lui-même (sans suivre un éventuel lien final) doit être dans le dossier de travail
        parent = _realpath(path.parent)
        base = _realpath(self.base_dir)
        if not _contains(base, parent) or path.name in ("", ".", ".."):
            raise ValueError("hors du dossier de travail")
        if _realpath(path) == base:
            raise ValueError("refus de supprimer le dossier de travail")
        if item.category == 'secureboot_keys':
            return  # demandé explicitement par l'utilisateur
        if _contains(_realpath(self.keys_dir), _realpath(path)):
            raise ValueError("clés SecureBoot : utilisez la catégorie dédiée")
        if item.action == 'delete':
            protected, reason = self.protection(path, link_targets)
            if protected:
                raise ValueError(f"protégé ({reason})")

    def clean(self, items, progress_callback=None):
        """
        Supprime/nettoie les éléments donnés (les éléments protégés sont ignorés).
        progress_callback(index, total, item) est appelé avant chaque élément.
        Retourne dict: freed (octets), done (list[CleanupItem]), errors (list[(item, message)])
        """
        link_targets = self._system_link_targets()
        active_build = self._active_build_dir()
        todo = [i for i in items if not i.protected]
        freed, done, errors = 0, [], []

        for index, item in enumerate(todo, 1):
            if progress_callback:
                progress_callback(index, len(todo), item)
            try:
                self._check_deletable(item, link_targets)
                if item.action == 'make_clean':
                    before = tree_size(item.path, _is_build_output)
                    result = subprocess.run(["make", "clean"], cwd=item.path,
                                            capture_output=True, text=True)
                    if result.returncode != 0:
                        raise RuntimeError(result.stderr.strip()[-500:] or "make clean a échoué")
                    freed += max(before - tree_size(item.path, _is_build_output), 0)
                else:
                    size = tree_size(item.path)
                    was_active = active_build is not None and _realpath(item.path) == active_build
                    if item.path.is_dir() and not item.path.is_symlink():
                        shutil.rmtree(item.path)
                    else:
                        item.path.unlink()
                    freed += size
                    # Le lien build/linux pointait vers l'arbre supprimé
                    if was_active:
                        (self.base_dir / "linux").unlink(missing_ok=True)
                done.append(item)
                log.info(f"Nettoyage: {item.category} {item.path}")
            except FileNotFoundError as e:
                errors.append((item, "make introuvable (installez build-essential)" if item.action == 'make_clean' else str(e)))
            except (OSError, ValueError, RuntimeError) as e:
                errors.append((item, str(e)))
                log.warning(f"Nettoyage impossible {item.path}: {e}")

        return {'freed': freed, 'done': done, 'errors': errors}


# ==================== Ligne de commande (lecture seule) ====================

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Inventaire du dossier de travail KernelCustom Manager")
    parser.add_argument("--keys", action="store_true", help="inclure les clés SecureBoot")
    args = parser.parse_args(argv)

    manager = CleanupManager()
    items = manager.scan(include_keys=args.keys)
    print(f"Dossier de travail : {manager.base_dir}\n")
    for item in items:
        flags = "🔒" if item.protected else ("☑" if item.selected else "☐")
        reason = f"  ({item.reason})" if item.reason else ""
        print(f"{flags} {item.category:<17} {human_size(item.size):>10}  {item.name}{reason}")
    total = sum(size for _, size in CleanupManager.summary([i for i in items if i.selected]).values())
    print(f"\nSélection par défaut : {human_size(total)} libérables")


if __name__ == "__main__":
    main()
