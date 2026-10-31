"""
Gestion des sources kernel dans /usr/src/ (remplace manage_kernel_sources.sh)

La recherche des dossiers se fait ici, côté utilisateur. Les modifications de
/usr/src passent par le helper privilégié (actions sources-install,
sources-link et sources-remove), qui revalide tous les chemins.
"""

import os
from pathlib import Path

from utils.i18n import _ as tr
from utils.pkexec_helper import PkexecHelper

USR_SRC = Path("/usr/src")


class SourcesManager:
    """Sources téléchargées (dossier de travail) ↔ /usr/src"""

    def __init__(self, sources_dir):
        self.sources_dir = Path(sources_dir)

    # ==================== Listes ====================

    def list_available(self):
        """Versions présentes dans le dossier de travail (linux-X.Y.Z*, hors headers)"""
        if not self.sources_dir.is_dir():
            return []
        return sorted(
            d.name[len("linux-"):]
            for d in self.sources_dir.glob("linux-*")
            if d.is_dir() and not d.name.startswith("linux-headers-")
        )

    @staticmethod
    def active_version():
        """Version pointée par /usr/src/linux (ou '')"""
        link = USR_SRC / "linux"
        if not link.is_symlink():
            return ""
        return Path(os.readlink(link)).name.removeprefix("linux-")

    @staticmethod
    def list_installed():
        """
        Sources dans /usr/src : liste de dicts {version, is_link, active}
        (les vrais headers système linux-headers-* ne sont pas listés)
        """
        active = SourcesManager.active_version()
        installed = []
        for entry in sorted(USR_SRC.glob("linux-[0-9]*")):
            if entry.is_dir() or entry.is_symlink():
                version = entry.name.removeprefix("linux-")
                installed.append({
                    'version': version,
                    'is_link': entry.is_symlink(),
                    'active': version == active,
                })
        return installed

    # ==================== Recherche ====================

    def find_source_dir(self, version):
        """Dossier des sources : linux-<version> exact, sinon le premier linux-<version>*"""
        exact = self.sources_dir / f"linux-{version}"
        if exact.is_dir():
            return exact
        for candidate in sorted(self.sources_dir.glob(f"linux-{version}*")):
            if candidate.is_dir() and not candidate.name.startswith("linux-headers-"):
                return candidate
        return None

    def find_headers_dir(self, full_version, src_path):
        """Headers générés pour full_version (à côté des sources ou dans sources_dir)"""
        for parent in (Path(src_path).parent, self.sources_dir):
            candidate = parent / f"linux-headers-{full_version}"
            if candidate.is_dir():
                return candidate
        return None

    # ==================== Actions (via le helper) ====================

    def install(self, version):
        """Copie les sources (et les headers s'ils existent) dans /usr/src"""
        src = self.find_source_dir(version)
        if not src:
            return False, tr("sources.not_found", version=version, dir=self.sources_dir)
        args = [src]
        headers = self.find_headers_dir(src.name.removeprefix("linux-"), src)
        if headers:
            args += ["--headers", headers]
        success, _, error = PkexecHelper.run("sources-install", *args)
        return success, error

    def link(self, base_version, full_version=None):
        """
        Crée /usr/src/linux-<full_version> -> sources (recommandé pour DKMS)
        full_version: version avec suffixe (ex: 6.16.9-kernelcustom), défaut = base_version
        """
        src = self.find_source_dir(base_version)
        if not src:
            return False, tr("sources.not_found", version=base_version, dir=self.sources_dir)
        full_version = full_version or base_version
        args = [src, full_version]
        headers = self.find_headers_dir(full_version, src)
        if headers:
            args += ["--headers", headers]
        success, stdout, error = PkexecHelper.run("sources-link", *args)
        if success and "HEADERS_MISSING:" in stdout:
            return True, tr("sources.headers_missing", version=full_version)
        return success, error

    @staticmethod
    def remove(version):
        """Supprime /usr/src/linux-<version> (lien ou copie). Les vrais headers système sont conservés."""
        success, _, error = PkexecHelper.run("sources-remove", version)
        return success, error
