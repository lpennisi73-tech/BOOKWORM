"""
Module de gestion des kernels
Logique métier pour télécharger, compiler, installer les kernels
"""

import hashlib
import json
import logging
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from core import kernel_releases
from utils import paths
from utils.i18n import _ as tr
from utils.i18n import format_size

log = logging.getLogger(__name__)


# Nom de profil : lettres (accents compris), chiffres, espace, point, tiret, plus et
# souligné, 64 caractères au plus. Il doit commencer par une lettre ou un chiffre :
# pas de « / », de « .. » ni de fichier caché, le profil reste dans profiles/
PROFILE_NAME_RE = re.compile(r'^[^\W_][\w .+-]{0,63}$')


def is_valid_profile_name(name):
    return bool(PROFILE_NAME_RE.match(name)) and not name.endswith(" ")


class DownloadError(Exception):
    """Échec du téléchargement ou de l'extraction (message déjà traduit)"""


class DownloadCancelled(Exception):
    """Téléchargement interrompu par l'utilisateur"""


class KernelManager:
    """Classe principale pour gérer les kernels"""
    
    def __init__(self, base_dir=None):
        if base_dir is None:
            self.base_dir = paths.data_dir()
        else:
            self.base_dir = Path(base_dir)
        
        # Structure de dossiers
        self.repo_dir = self.base_dir / "kernels_repo"
        self.log_dir = self.base_dir / "logs"
        self.archive_dir = self.base_dir / "archive"
        self.sources_dir = self.base_dir / "sources"
        self.templates_dir = self.base_dir / "templates"
        self.configs_dir = self.base_dir / "configs"
        self.profiles_dir = self.base_dir / "profiles"
        self.history_file = self.base_dir / "compilation_history.json"

        # Notifications : fonction (title, message, urgency) fournie par l'interface
        # (Gio.Notification). Le cœur reste sans dépendance GTK.
        self.notifier = None
        
        # Créer tous les dossiers
        for directory in [self.repo_dir, self.log_dir, self.archive_dir, 
                         self.sources_dir, self.templates_dir, self.configs_dir,
                         self.profiles_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Initialiser l'historique
        if not self.history_file.exists():
            self._save_history([])
    
    def _save_history(self, history):
        """Sauvegarde l'historique"""
        with open(self.history_file, 'w') as f:
            json.dump(history, f, indent=2)
    
    def _load_history(self):
        """Charge l'historique"""
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except Exception:
            return []
    
    def add_compilation_to_history(self, kernel_version, suffix, success, duration, packages):
        """Ajoute une compilation à l'historique"""
        history = self._load_history()
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'kernel_version': kernel_version,
            'suffix': suffix,
            'success': success,
            'duration_seconds': duration,
            'packages': packages
        }
        
        history.insert(0, entry)
        history = history[:50]
        self._save_history(history)
        return entry
    
    def get_compilation_history(self):
        """Récupère l'historique"""
        return self._load_history()
    
    def backup_config(self, kernel_version, suffix=""):
        """Sauvegarde la configuration actuelle"""
        linux_dir = self.base_dir / "linux"
        config_file = linux_dir / ".config"
        
        if not config_file.exists():
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_name = f"config-{kernel_version}{suffix}-{timestamp}"
        backup_path = self.configs_dir / backup_name
        
        shutil.copy(config_file, backup_path)
        return backup_path
    
    def save_profile(self, profile_name, description=""):
        """Sauvegarde un profil (False si le nom est invalide ou s'il n'y a pas de .config)"""
        if not is_valid_profile_name(profile_name):
            return False

        linux_dir = self.base_dir / "linux"
        config_file = linux_dir / ".config"

        if not config_file.exists():
            return False
        
        profile_data = {
            'name': profile_name,
            'description': description,
            'created': datetime.now().isoformat()
        }
        
        config_path = self.profiles_dir / f"{profile_name}.config"
        shutil.copy(config_file, config_path)
        
        meta_path = self.profiles_dir / f"{profile_name}.json"
        with open(meta_path, 'w') as f:
            json.dump(profile_data, f, indent=2)
        
        return True
    
    def profile_exists(self, profile_name):
        """Un profil de ce nom existe-t-il déjà ?"""
        return (is_valid_profile_name(profile_name)
                and (self.profiles_dir / f"{profile_name}.json").exists())

    def load_profile(self, profile_name):
        """Charge un profil"""
        config_path = self.profiles_dir / f"{profile_name}.config"
        linux_dir = self.base_dir / "linux"
        
        if not config_path.exists():
            return False

        return self._apply_config(config_path)
    
    def get_profiles(self):
        """Liste tous les profils"""
        profiles = []
        
        for meta_file in self.profiles_dir.glob("*.json"):
            try:
                with open(meta_file, 'r') as f:
                    profile_data = json.load(f)
                    profiles.append(profile_data)
            except Exception:
                continue
        
        return sorted(profiles, key=lambda x: x['created'], reverse=True)
    
    def export_config(self, destination):
        """Exporte la config actuelle"""
        linux_dir = self.base_dir / "linux"
        config_file = linux_dir / ".config"
        
        if not config_file.exists():
            return False
        
        shutil.copy(config_file, destination)
        return True
    
    def import_config(self, source):
        """Importe une configuration"""
        if not Path(source).is_file():
            return False

        return self._apply_config(source)

    def _apply_config(self, source):
        """
        Copie source vers le .config de l'arbre actif puis `make olddefconfig`.
        False s'il n'y a pas d'arbre actif ou si make échoue (bloquant : à lancer dans un thread)
        """
        linux_dir = self.base_dir / "linux"
        if not linux_dir.is_dir():
            return False
        try:
            shutil.copy(source, linux_dir / ".config")
            result = subprocess.run(["make", "olddefconfig"], cwd=str(linux_dir),
                                    capture_output=True, text=True)
        except OSError as e:  # make absent, fichier illisible…
            log.warning(f"Unable to apply config {source}: {e}")
            return False
        if result.returncode != 0:
            log.warning(f"make olddefconfig failed ({result.returncode}): {result.stderr.strip()[-500:]}")
            return False
        return True
    
    def send_notification(self, title, message, urgency="normal"):
        """Envoie une notification système (urgency : low, normal, critical)"""
        if self.notifier is None:
            return
        try:
            self.notifier(title, message, urgency)
        except Exception:
            pass

    def get_installed_kernels(self):
        """Liste les kernels installés"""
        try:
            result = subprocess.run(
                ["dpkg", "-l"],
                capture_output=True,
                text=True,
                check=True
            )
            
            kernels = []
            for line in result.stdout.splitlines():
                if line.startswith("ii") and "linux-image-" in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        kernels.append({
                            'package': parts[1],
                            'version': parts[2]
                        })
            
            return kernels
        except Exception:
            return []
    
    def get_local_packages(self):
        """Liste les paquets .deb locaux"""
        packages = []
        for deb_file in self.repo_dir.glob("linux-image-*.deb"):
            packages.append({
                'name': deb_file.name,
                'path': deb_file,
                'size': format_size(deb_file.stat().st_size)
            })
        return packages
    
    # ==================== Sources ====================

    def source_tree(self, version):
        """Dossier des sources linux-<version> du dossier de travail (None s'il n'existe pas)"""
        tree = self.sources_dir / f"linux-{version}"
        return tree if tree.is_dir() else None

    def active_version(self):
        """Version de l'arbre actif (cible du lien linux), None s'il n'y en a pas"""
        link = self.base_dir / "linux"
        if not link.is_dir():
            return None
        return link.resolve().name.removeprefix("linux-")

    def activate_sources(self, version):
        """Fait de linux-<version> l'arbre actif (lien linux). False si les sources sont absentes"""
        tree = self.source_tree(version)
        if tree is None:
            return False
        link = self.base_dir / "linux"
        # is_symlink() et non exists() : un lien cassé (arbre supprimé) doit être remplacé
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            raise DownloadError(tr("download.error.link_not_symlink", path=link))
        link.symlink_to(tree)
        return True

    def download_kernel(self, version, url=None, progress=None, cancelled=None, replace=False):
        """
        Télécharge et extrait les sources d'un kernel, puis en fait l'arbre actif.

        url        : archive à télécharger (défaut : déduite de la version)
        progress   : fonction (fraction, message) ; fraction None = durée inconnue
        cancelled  : fonction sans argument, True pour interrompre
        replace    : remplace un arbre linux-<version> existant (son .config est conservé)

        Lève DownloadCancelled ou DownloadError (message traduit). L'archive est
        extraite dans un dossier temporaire : un échec ne laisse aucun arbre incomplet.
        """
        if not kernel_releases.is_valid_version(version):
            raise DownloadError(tr("message.error.invalid_version"))
        url = url or kernel_releases.source_url(version)
        if not kernel_releases.is_allowed_url(url):
            raise DownloadError(tr("download.error.bad_url", url=url))

        target = self.sources_dir / f"linux-{version}"
        if target.exists() and not replace:
            raise DownloadError(tr("download.error.exists", version=version))

        archive = self.sources_dir / f"linux-{version}.tar.part"
        staging = self.sources_dir / f".extract-linux-{version}"

        def check():
            if cancelled and cancelled():
                raise DownloadCancelled()

        def report(fraction, message=None):
            if progress:
                progress(fraction, message)

        try:
            shutil.rmtree(staging, ignore_errors=True)  # reste d'un téléchargement interrompu
            digest = self._fetch_archive(version, url, archive, report, check)
            self._verify_checksum(url, digest, report)
            check()

            report(None, tr("download.extracting"))
            staging.mkdir(parents=True)
            self._extract_archive(archive, staging, check)
            trees = [entry for entry in staging.iterdir() if entry.is_dir()]
            if len(trees) != 1 or not (trees[0] / "Makefile").is_file():
                raise DownloadError(tr("download.error.extract", error=tr("download.error.unexpected_content")))

            check()  # dernier point d'annulation : la suite modifie l'arbre existant
            config = None
            if target.exists():
                if (target / ".config").is_file():
                    config = (target / ".config").read_bytes()
                shutil.rmtree(target)
            trees[0].rename(target)
            if config is not None:
                (target / ".config").write_bytes(config)

            self.activate_sources(version)
            log.info(f"Kernel sources linux-{version} downloaded from {url}")
            return True
        except DownloadCancelled:
            log.info(f"Download of linux-{version} cancelled")
            raise
        except DownloadError as e:
            log.warning(f"Download of linux-{version} failed: {e}")
            raise
        except OSError as e:
            log.warning(f"Download of linux-{version} failed: {e}")
            raise DownloadError(tr("download.error.io", error=e)) from e
        finally:
            archive.unlink(missing_ok=True)
            shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def _fetch_archive(version, url, dest, report, check):
        """Télécharge url dans dest par blocs (annulable, même si la taille est inconnue)"""
        request = urllib.request.Request(url, headers={"User-Agent": "kernelcustom-manager"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response, open(dest, "wb") as out:
                # Après une éventuelle redirection, toujours sur kernel.org
                if not kernel_releases.is_allowed_url(response.url):
                    raise DownloadError(tr("download.error.bad_url", url=response.url))
                total = int(response.headers.get("Content-Length") or 0)
                sha256 = hashlib.sha256()
                received = 0
                last_report = 0.0
                while True:
                    check()
                    block = response.read(256 * 1024)
                    if not block:
                        break
                    out.write(block)
                    sha256.update(block)
                    received += len(block)
                    now = time.monotonic()
                    if now - last_report >= 0.2:
                        last_report = now
                        if total:
                            report(received / total)
                        else:
                            # git.kernel.org génère l'archive à la volée : taille inconnue
                            report(None, tr("download.received", version=version, size=format_size(received)))
                if received == 0:
                    # Déjà observé sur git.kernel.org : réponse 200 sans contenu
                    raise DownloadError(tr("download.error.empty"))
                if total and received != total:
                    raise DownloadError(tr("download.error.incomplete"))
                if total:
                    report(1.0)
                return sha256.hexdigest()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise DownloadError(tr("download.error.not_found", version=version)) from e
            raise DownloadError(tr("download.error.http", code=e.code, reason=e.reason)) from e
        except urllib.error.URLError as e:
            raise DownloadError(tr("download.error.network", error=e.reason)) from e
        except TimeoutError as e:
            raise DownloadError(tr("download.error.network", error=e)) from e

    @staticmethod
    def _verify_checksum(url, digest, report):
        """
        Compare la somme SHA-256 de l'archive à sha256sums.asc de kernel.org (lu en
        HTTPS, signature PGP non vérifiée). Les pré-versions n'ont pas de somme publiée.
        """
        if not kernel_releases.checksums_url(url):
            log.info(f"No published checksum for {url} (sha256 {digest})")
            return
        report(None, tr("download.verifying"))
        try:
            expected = kernel_releases.fetch_checksum(url)
        except OSError as e:
            raise DownloadError(tr("download.error.checksum_unavailable", error=e)) from e
        if expected is None:
            raise DownloadError(tr("download.error.checksum_unavailable",
                                   error=tr("download.error.checksum_missing")))
        if expected != digest:
            log.warning(f"Checksum mismatch for {url}: expected {expected}, got {digest}")
            raise DownloadError(tr("download.error.checksum_mismatch"))
        log.info(f"Checksum verified for {url} (sha256 {digest})")

    @staticmethod
    def _extract_archive(archive, dest, check):
        """tar -xf (xz ou gzip détecté par tar), interrompu si check() lève une exception"""
        try:
            process = subprocess.Popen(["tar", "-xf", str(archive), "-C", str(dest)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except FileNotFoundError as e:
            raise DownloadError(tr("download.error.extract", error=e)) from e
        while True:
            try:
                _, stderr = process.communicate(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                try:
                    check()
                except DownloadCancelled:
                    process.kill()
                    process.communicate()
                    raise
        if process.returncode != 0:
            error = stderr.decode(errors="replace").strip().splitlines()[-1:] or [f"tar: {process.returncode}"]
            raise DownloadError(tr("download.error.extract", error=error[0]))
