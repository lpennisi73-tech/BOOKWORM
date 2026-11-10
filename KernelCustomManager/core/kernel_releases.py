"""
Versions du kernel publiées sur kernel.org (branches stable, mainline et longterm)

Lecture de https://www.kernel.org/releases.json, sans GTK. Les appels réseau sont
bloquants : les lancer dans un thread (run_task).

    python3 -m core.kernel_releases      # affiche les versions publiées
"""

import json
import logging
import re
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

log = logging.getLogger(__name__)

RELEASES_URL = "https://www.kernel.org/releases.json"
CDN_URL = "https://cdn.kernel.org/pub/linux/kernel"
MAINLINE_URL = "https://git.kernel.org/torvalds/t"

# Branches proposées, dans l'ordre d'affichage (linux-next n'a pas d'archive)
BRANCHES = ("stable", "mainline", "longterm")

# 7.3, 7.3.3 ou 7.4-rc2
VERSION_RE = re.compile(r'^\d+\.\d+(\.\d+)?(-rc\d+)?$')

# Seuls serveurs depuis lesquels une archive est téléchargée (redirections comprises)
ALLOWED_HOSTS = ("cdn.kernel.org", "git.kernel.org", "www.kernel.org", "kernel.org")
ARCHIVE_SUFFIXES = (".tar.xz", ".tar.gz")

_cache = None


@dataclass(frozen=True)
class KernelRelease:
    branch: str      # stable, mainline ou longterm
    version: str     # 7.3.3, 7.4-rc2…
    source: str      # URL de l'archive
    eol: bool        # fin de vie : plus de correctifs
    date: str        # date de publication (AAAA-MM-JJ)

    @property
    def series(self):
        return series_of(self.version)


def is_valid_version(version):
    return bool(VERSION_RE.match(version))


def is_prerelease(version):
    """Version candidate (-rcN) : archive sur git.kernel.org, sans somme de contrôle"""
    return "-rc" in version


def series_of(version):
    """Série d'une version : 7.3.3 → 7.3, 7.4-rc2 → 7.4"""
    return ".".join(version.split("-")[0].split(".")[:2])


def is_allowed_url(url):
    """URL https d'une archive .tar.xz ou .tar.gz hébergée par kernel.org"""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return (parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS
            and parts.path.endswith(ARCHIVE_SUFFIXES))


def source_url(version):
    """URL de l'archive d'une version saisie à la main"""
    if is_prerelease(version):
        return f"{MAINLINE_URL}/linux-{version}.tar.gz"
    return f"{CDN_URL}/v{version.split('.')[0]}.x/linux-{version}.tar.xz"


def checksums_url(url):
    """URL de sha256sums.asc pour une archive du CDN (None ailleurs : pas de somme publiée)"""
    parts = urlsplit(url)
    if parts.hostname != "cdn.kernel.org":
        return None
    return f"https://cdn.kernel.org{parts.path.rsplit('/', 1)[0]}/sha256sums.asc"


def parse_checksums(text, filename):
    """Somme SHA-256 de filename dans le contenu de sha256sums.asc (None si absente)"""
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1] == filename and re.fullmatch(r'[0-9a-f]{64}', fields[0]):
            return fields[0]
    return None


def fetch_checksum(url, timeout=20):
    """Somme SHA-256 publiée pour l'archive url (None si kernel.org n'en publie pas)"""
    sums_url = checksums_url(url)
    if not sums_url:
        return None
    with urllib.request.urlopen(sums_url, timeout=timeout) as response:
        text = response.read().decode("ascii", errors="replace")
    return parse_checksums(text, urlsplit(url).path.rsplit("/", 1)[1])


def parse_releases(data):
    """Liste de KernelRelease à partir du contenu de releases.json, triée par branche"""
    releases = []
    for item in data.get("releases", []):
        branch = item.get("moniker")
        version = str(item.get("version") or "")
        source = item.get("source") or ""
        if branch not in BRANCHES or not is_valid_version(version) or not is_allowed_url(source):
            continue
        releases.append(KernelRelease(
            branch=branch, version=version, source=source, eol=bool(item.get("iseol")),
            date=str((item.get("released") or {}).get("isodate") or ""),
        ))
    # Tri stable : kernel.org donne déjà les versions de la plus récente à la plus ancienne
    releases.sort(key=lambda r: BRANCHES.index(r.branch))
    return releases


def fetch_releases(timeout=10):
    """Lit releases.json (lève une exception en cas d'échec) et met le cache à jour"""
    global _cache
    with urllib.request.urlopen(RELEASES_URL, timeout=timeout) as response:
        data = json.loads(response.read().decode())
    _cache = parse_releases(data)
    return _cache


def get_releases(refresh=False):
    """Versions publiées : une seule lecture par session, [] si kernel.org est injoignable"""
    if _cache is not None and not refresh:
        return _cache
    try:
        return fetch_releases()
    except Exception as e:
        log.warning(f"Unable to read {RELEASES_URL}: {e}")
        return []


def find_release(releases, version):
    return next((r for r in releases if r.version == version), None)


def latest_for(releases, release):
    """
    Version la plus récente de la même branche et de la même série que release.
    Si la série n'est plus publiée (ex. mainline passé de 7.4 à 7.5-rc1), la
    version la plus récente de la branche encore maintenue.
    """
    same_branch = [r for r in releases if r.branch == release.branch]
    for candidate in same_branch:
        if candidate.series == release.series:
            return candidate
    return next((r for r in same_branch if not r.eol), same_branch[0] if same_branch else None)


if __name__ == "__main__":
    for item in fetch_releases():
        print(f"{item.branch:<9} {item.version:<12} {item.date}{'  EOL' if item.eol else ''}\n"
              f"          {item.source}")
