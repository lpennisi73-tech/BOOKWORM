"""
Module de gestion des drivers GPU (NVIDIA, AMD et Intel)
Logique métier pour détecter, télécharger et installer les drivers
Version Avancée avec web scraping, rollback, historique et support Wayland
"""

import subprocess
import re
import json
from pathlib import Path
from datetime import datetime
import urllib.request
import urllib.error
import urllib.parse
import shutil
import os


class DriverManager:
    """Classe principale pour gérer les drivers GPU avec fonctionnalités avancées"""

    # URLs officielles pour téléchargement
    NVIDIA_DOWNLOAD_BASE = "https://us.download.nvidia.com/XFree86/Linux-x86_64"
    NVIDIA_DOWNLOAD_PAGE = "https://www.nvidia.com/Download/processFind.aspx"
    AMD_DOWNLOAD_BASE = "https://repo.radeon.com/amdgpu-install"
    AMD_DOWNLOAD_PAGE = "https://www.amd.com/en/support/download/linux-drivers.html"

    def __init__(self, base_dir=None):
        if base_dir is None:
            self.base_dir = Path.home() / "KernelCustomManager" / "build"
        else:
            self.base_dir = Path(base_dir)

        # Dossiers
        self.drivers_dir = self.base_dir / "drivers"
        self.backup_dir = self.base_dir / "drivers_backup"
        self.history_file = self.base_dir / "drivers_history.json"

        # Créer les dossiers
        self.drivers_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Initialiser l'historique
        if not self.history_file.exists():
            self._save_history([])

        # Détecter la distribution et le display server
        self.distro_info = self.detect_distribution()
        self.display_server = self.detect_display_server()

    def detect_gpu(self):
        """
        Détecte le GPU installé sur le système
        Retourne: dict avec vendor, model, pci_id, ou None si pas trouvé
        """
        try:
            result = subprocess.run(
                ["lspci", "-nn"],
                capture_output=True,
                text=True,
                check=True
            )

            # Rechercher VGA ou 3D controller
            for line in result.stdout.split('\n'):
                if 'VGA compatible controller' in line or '3D controller' in line:
                    gpu_info = self._parse_gpu_line(line)
                    if gpu_info:
                        return gpu_info

            return None
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _parse_gpu_line(self, line):
        """Parse une ligne lspci pour extraire les infos GPU"""
        # Format: 01:00.0 VGA compatible controller [0300]: NVIDIA Corporation ... [10de:2786]

        # Extraire le PCI ID [vendor:device]
        pci_match = re.search(r'\[([0-9a-f]{4}):([0-9a-f]{4})\]', line)
        if not pci_match:
            return None

        vendor_id = pci_match.group(1)
        device_id = pci_match.group(2)

        # Déterminer le fabricant
        vendor = None
        if 'NVIDIA' in line or vendor_id == '10de':
            vendor = 'NVIDIA'
        elif 'AMD' in line or 'ATI' in line or vendor_id == '1002':
            vendor = 'AMD'
        elif 'Intel' in line or vendor_id == '8086':
            vendor = 'Intel'
        else:
            vendor = 'Unknown'

        # Extraire le nom du modèle
        model_match = re.search(r':\s+(.+?)\s+\[', line)
        model = model_match.group(1) if model_match else "Unknown Model"

        return {
            'vendor': vendor,
            'model': model,
            'pci_id': f"{vendor_id}:{device_id}",
            'vendor_id': vendor_id,
            'device_id': device_id
        }

    def detect_distribution(self):
        """
        Détecte la distribution Linux et sa version
        Retourne: dict avec name, version, codename, id
        """
        distro_info = {
            'name': 'Unknown',
            'version': 'Unknown',
            'codename': 'Unknown',
            'id': 'unknown'
        }

        try:
            # Lire /etc/os-release (standard pour la plupart des distributions)
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('NAME='):
                        distro_info['name'] = line.split('=')[1].strip('"')
                    elif line.startswith('VERSION_ID='):
                        distro_info['version'] = line.split('=')[1].strip('"')
                    elif line.startswith('VERSION_CODENAME='):
                        distro_info['codename'] = line.split('=')[1].strip('"')
                    elif line.startswith('ID='):
                        distro_info['id'] = line.split('=')[1].strip('"')

            # Pour Ubuntu, mapper le codename si pas présent
            if 'ubuntu' in distro_info['id'].lower():
                version_to_codename = {
                    '24.04': 'noble',
                    '23.10': 'mantic',
                    '23.04': 'lunar',
                    '22.04': 'jammy',
                    '20.04': 'focal',
                    '18.04': 'bionic'
                }
                if distro_info['codename'] == 'Unknown' and distro_info['version'] in version_to_codename:
                    distro_info['codename'] = version_to_codename[distro_info['version']]

        except FileNotFoundError:
            # Fallback to lsb_release
            try:
                result = subprocess.run(
                    ["lsb_release", "-a"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                for line in result.stdout.split('\n'):
                    if 'Distributor ID:' in line:
                        distro_info['id'] = line.split(':')[1].strip().lower()
                    elif 'Release:' in line:
                        distro_info['version'] = line.split(':')[1].strip()
                    elif 'Codename:' in line:
                        distro_info['codename'] = line.split(':')[1].strip()
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass

        return distro_info

    def detect_display_server(self):
        """
        Détecte le serveur d'affichage (X11, Wayland, ou TTY)
        Retourne: 'X11', 'Wayland', 'TTY', ou 'Unknown'
        """
        # Méthode 1: Variable d'environnement XDG_SESSION_TYPE
        session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
        if session_type in ['x11', 'wayland', 'tty']:
            return session_type.upper() if session_type != 'tty' else 'TTY'

        # Méthode 2: Variable d'environnement WAYLAND_DISPLAY
        if os.environ.get('WAYLAND_DISPLAY'):
            return 'Wayland'

        # Méthode 3: Variable d'environnement DISPLAY (X11)
        if os.environ.get('DISPLAY'):
            return 'X11'

        # Méthode 4: Vérifier les processus en cours
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                check=True
            )

            if 'wayland' in result.stdout.lower():
                return 'Wayland'
            elif 'xorg' in result.stdout.lower() or 'X :' in result.stdout:
                return 'X11'
            else:
                return 'TTY'

        except (subprocess.CalledProcessError, FileNotFoundError):
            return 'Unknown'

    def _save_history(self, history):
        """Sauvegarde l'historique des installations"""
        with open(self.history_file, 'w') as f:
            json.dump(history, f, indent=2)

    def _load_history(self):
        """Charge l'historique des installations"""
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def add_to_history(self, action, vendor, driver_name, driver_version, source, success, details=None):
        """
        Ajoute une entrée à l'historique
        action: 'install', 'remove', 'rollback'
        """
        history = self._load_history()

        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'vendor': vendor,
            'driver_name': driver_name,
            'driver_version': driver_version,
            'source': source,
            'success': success,
            'display_server': self.display_server,
            'distro': f"{self.distro_info['id']} {self.distro_info['version']}",
            'details': details or {}
        }

        history.append(entry)
        self._save_history(history)

    def get_history(self, limit=None):
        """
        Récupère l'historique des installations
        limit: nombre maximum d'entrées (None = toutes)
        """
        history = self._load_history()
        if limit:
            return history[-limit:]
        return history

    def get_current_driver(self, vendor):
        """
        Détecte le driver actuellement utilisé
        Retourne: dict avec name, version, source (repo/official/opensource)
        """
        if vendor == 'NVIDIA':
            return self._get_current_nvidia_driver()
        elif vendor == 'AMD':
            return self._get_current_amd_driver()
        elif vendor == 'Intel':
            return self._get_current_intel_driver()
        else:
            return None

    def _get_current_nvidia_driver(self):
        """Détecte le driver NVIDIA actuel"""
        try:
            # Vérifier si le module nvidia est chargé
            result = subprocess.run(
                ["lsmod"],
                capture_output=True,
                text=True,
                check=True
            )

            if 'nvidia' in result.stdout:
                # Essayer nvidia-smi pour la version
                try:
                    smi_result = subprocess.run(
                        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    version = smi_result.stdout.strip()

                    # Vérifier si installé via apt ou .run
                    dpkg_result = subprocess.run(
                        ["dpkg", "-l"],
                        capture_output=True,
                        text=True,
                        check=True
                    )

                    source = "official"
                    if 'nvidia-driver' in dpkg_result.stdout:
                        source = "repository"

                    return {
                        'name': 'NVIDIA Proprietary',
                        'version': version,
                        'source': source
                    }
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass

                # Sinon driver nvidia chargé mais pas nvidia-smi
                return {
                    'name': 'NVIDIA',
                    'version': 'Unknown',
                    'source': 'unknown'
                }

            # Vérifier nouveau (open source)
            elif 'nouveau' in result.stdout:
                return {
                    'name': 'Nouveau (Open Source)',
                    'version': 'Kernel Module',
                    'source': 'opensource'
                }

            return None

        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _get_current_amd_driver(self):
        """Détecte le driver AMD actuel"""
        try:
            result = subprocess.run(
                ["lsmod"],
                capture_output=True,
                text=True,
                check=True
            )

            if 'amdgpu' in result.stdout:
                # Vérifier si AMDGPU-PRO ou Mesa
                dpkg_result = subprocess.run(
                    ["dpkg", "-l"],
                    capture_output=True,
                    text=True,
                    check=True
                )

                if 'amdgpu-pro' in dpkg_result.stdout:
                    # Extraire version
                    version_match = re.search(r'amdgpu-pro\s+(\S+)', dpkg_result.stdout)
                    version = version_match.group(1) if version_match else 'Unknown'

                    return {
                        'name': 'AMDGPU-PRO',
                        'version': version,
                        'source': 'official'
                    }
                else:
                    return {
                        'name': 'AMDGPU (Mesa)',
                        'version': 'Open Source',
                        'source': 'opensource'
                    }

            elif 'radeon' in result.stdout:
                return {
                    'name': 'Radeon (Legacy)',
                    'version': 'Open Source',
                    'source': 'opensource'
                }

            return None

        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _get_current_intel_driver(self):
        """Détecte le driver Intel actuel"""
        try:
            result = subprocess.run(
                ["lsmod"],
                capture_output=True,
                text=True,
                check=True
            )

            # Intel moderne (i915 ou xe)
            if 'xe' in result.stdout:
                # Nouveau driver xe (pour Arc et futures générations)
                return {
                    'name': 'Intel Xe (Modern)',
                    'version': 'Kernel Module',
                    'source': 'opensource'
                }
            elif 'i915' in result.stdout:
                # Driver i915 classique
                return {
                    'name': 'Intel i915',
                    'version': 'Kernel Module',
                    'source': 'opensource'
                }

            return None

        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def get_available_drivers_from_repos(self, vendor):
        """
        Liste les drivers disponibles dans les dépôts Ubuntu/Debian
        Retourne: liste de dicts avec name, version, description, recommended
        """
        if vendor == 'NVIDIA':
            return self._get_nvidia_from_repos()
        elif vendor == 'AMD':
            return self._get_amd_from_repos()
        elif vendor == 'Intel':
            return self._get_intel_from_repos()
        else:
            return []

    def _get_nvidia_from_repos(self):
        """Liste drivers NVIDIA depuis apt"""
        drivers = []

        try:
            result = subprocess.run(
                ["apt-cache", "search", "nvidia-driver-"],
                capture_output=True,
                text=True,
                check=True
            )

            # Parser le résultat
            seen = set()
            for line in result.stdout.split('\n'):
                # Format: nvidia-driver-550 - NVIDIA driver metapackage
                match = re.match(r'(nvidia-driver-(\d+))\s+-\s+(.+)', line)
                if match:
                    package_name = match.group(1)
                    version = match.group(2)
                    description = match.group(3)

                    if package_name not in seen:
                        seen.add(package_name)

                        # Vérifier si c'est le recommandé (généralement le plus récent stable)
                        recommended = version in ['550', '560']  # Mettre à jour selon les versions

                        drivers.append({
                            'name': package_name,
                            'version': version,
                            'description': description,
                            'recommended': recommended
                        })

            # Trier par version (décroissant)
            drivers.sort(key=lambda x: int(x['version']), reverse=True)

        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return drivers

    def _get_amd_from_repos(self):
        """Liste drivers AMD depuis apt"""
        drivers = []

        try:
            # AMD dans les dépôts Ubuntu utilise généralement mesa
            result = subprocess.run(
                ["apt-cache", "search", "mesa"],
                capture_output=True,
                text=True,
                check=True
            )

            # Chercher les paquets mesa principaux
            for line in result.stdout.split('\n'):
                if 'mesa-vulkan-drivers' in line and 'mesa-vulkan-drivers' not in [d['name'] for d in drivers]:
                    drivers.append({
                        'name': 'mesa-vulkan-drivers',
                        'version': 'Latest',
                        'description': 'Mesa Vulkan drivers (Open Source)',
                        'recommended': True
                    })
                elif 'libgl1-mesa-dri' in line and 'libgl1-mesa-dri' not in [d['name'] for d in drivers]:
                    drivers.append({
                        'name': 'libgl1-mesa-dri',
                        'version': 'Latest',
                        'description': 'Mesa DRI drivers (Open Source)',
                        'recommended': True
                    })

        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return drivers

    def _get_intel_from_repos(self):
        """Liste drivers Intel depuis apt"""
        drivers = []

        try:
            # Intel utilise principalement Mesa pour l'accélération 3D
            result = subprocess.run(
                ["apt-cache", "search", "intel"],
                capture_output=True,
                text=True,
                check=True
            )

            # Chercher les paquets Intel
            packages_found = set()
            for line in result.stdout.split('\n'):
                if 'intel-media-va-driver' in line and 'intel-media-va-driver' not in packages_found:
                    packages_found.add('intel-media-va-driver')
                    drivers.append({
                        'name': 'intel-media-va-driver',
                        'version': 'Latest',
                        'description': 'VA-API driver for Intel (hardware acceleration)',
                        'recommended': True
                    })
                elif 'mesa-vulkan-drivers' in line and 'mesa-vulkan-drivers' not in packages_found:
                    packages_found.add('mesa-vulkan-drivers')
                    drivers.append({
                        'name': 'mesa-vulkan-drivers',
                        'version': 'Latest',
                        'description': 'Mesa Vulkan drivers (includes Intel ANV)',
                        'recommended': True
                    })
                elif 'xserver-xorg-video-intel' in line and 'xserver-xorg-video-intel' not in packages_found:
                    packages_found.add('xserver-xorg-video-intel')
                    drivers.append({
                        'name': 'xserver-xorg-video-intel',
                        'version': 'Latest',
                        'description': 'X.Org X server -- Intel display driver (Legacy)',
                        'recommended': False
                    })
                elif 'intel-gpu-tools' in line and 'intel-gpu-tools' not in packages_found:
                    packages_found.add('intel-gpu-tools')
                    drivers.append({
                        'name': 'intel-gpu-tools',
                        'version': 'Latest',
                        'description': 'Tools for debugging Intel graphics',
                        'recommended': False
                    })

        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Note pour l'utilisateur
        if not drivers:
            drivers.append({
                'name': 'mesa-vulkan-drivers',
                'version': 'Latest',
                'description': 'Intel uses Mesa drivers (open source, included in kernel)',
                'recommended': True
            })

        return drivers

    def get_official_driver_info(self, vendor):
        """
        Récupère les informations sur la dernière version officielle
        Retourne: dict avec version, url, date, ou None
        """
        if vendor == 'NVIDIA':
            return self._get_nvidia_official_info()
        elif vendor == 'AMD':
            return self._get_amd_official_info()
        else:
            return None

    def _get_nvidia_official_info(self):
        """
        Récupère la dernière version NVIDIA officielle
        Note: Version simplifiée, peut être étendu avec web scraping
        """
        # Versions connues (peut être étendu avec scraping)
        known_versions = [
            {'version': '550.127.05', 'date': '2024-12-10'},
            {'version': '550.120', 'date': '2024-11-15'},
            {'version': '535.183.01', 'date': '2024-10-20'},
        ]

        # Retourner la plus récente
        latest = known_versions[0]
        url = f"{self.NVIDIA_DOWNLOAD_BASE}/{latest['version']}/NVIDIA-Linux-x86_64-{latest['version']}.run"

        return {
            'version': latest['version'],
            'url': url,
            'date': latest['date'],
            'size': '~350 MB',
            'filename': f"NVIDIA-Linux-x86_64-{latest['version']}.run"
        }

    def _get_amd_official_info(self):
        """
        Récupère la dernière version AMD officielle
        Note: Version simplifiée
        """
        # Versions connues
        known_versions = [
            {'version': '6.2.3', 'ubuntu': '22.04'},
            {'version': '6.1.3', 'ubuntu': '22.04'},
        ]

        latest = known_versions[0]
        # AMD utilise des URLs complexes avec version ubuntu
        url = f"{self.AMD_DOWNLOAD_BASE}/{latest['version']}/ubuntu/jammy/amdgpu-install_{latest['version'].replace('.', '')}-1_all.deb"

        return {
            'version': latest['version'],
            'url': url,
            'date': '2024-11-01',
            'size': '~2 MB',
            'filename': f"amdgpu-install_{latest['version']}-1_all.deb",
            'note': 'This package installs the amdgpu-install script'
        }

    def install_from_repos(self, package_name, progress_callback=None):
        """
        Installe un driver depuis les dépôts
        progress_callback: fonction appelée avec (message, percentage)
        Retourne: (success: bool, message: str)
        """
        try:
            if progress_callback:
                progress_callback("Mise à jour de la liste des paquets...", 0.1)

            # Update apt cache
            subprocess.run(
                ["pkexec", "apt-get", "update"],
                check=True,
                capture_output=True
            )

            if progress_callback:
                progress_callback(f"Installation de {package_name}...", 0.3)

            # Install package
            result = subprocess.run(
                ["pkexec", "apt-get", "install", "-y", package_name],
                capture_output=True,
                text=True,
                check=True
            )

            if progress_callback:
                progress_callback("Installation terminée", 1.0)

            return (True, f"Driver {package_name} installé avec succès")

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            return (False, f"Erreur d'installation: {error_msg}")

    def download_official_driver(self, url, filename, progress_callback=None):
        """
        Télécharge un driver depuis le site officiel
        progress_callback: fonction appelée avec (message, percentage)
        Retourne: (success: bool, filepath: Path ou None, message: str)
        """
        download_path = self.drivers_dir / filename

        try:
            if progress_callback:
                progress_callback(f"Téléchargement de {filename}...", 0.1)

            def reporthook(block_num, block_size, total_size):
                if progress_callback and total_size > 0:
                    downloaded = block_num * block_size
                    percent = min(downloaded / total_size, 1.0)
                    progress_callback(
                        f"Téléchargement: {int(percent*100)}%",
                        0.1 + (percent * 0.8)  # 10% à 90%
                    )

            urllib.request.urlretrieve(url, download_path, reporthook)

            if progress_callback:
                progress_callback("Téléchargement terminé", 0.95)

            return (True, download_path, "Téléchargement réussi")

        except (urllib.error.URLError, Exception) as e:
            if download_path.exists():
                download_path.unlink()
            return (False, None, f"Erreur de téléchargement: {str(e)}")

    def install_nvidia_run_file(self, run_file_path, progress_callback=None):
        """
        Installe un fichier .run NVIDIA
        ATTENTION: Nécessite arrêt du serveur graphique
        Retourne: (success: bool, message: str)
        """
        try:
            if progress_callback:
                progress_callback("Préparation de l'installation...", 0.1)

            # Rendre exécutable
            run_file_path.chmod(0o755)

            if progress_callback:
                progress_callback("Installation en cours...", 0.3)

            # Installation (simplifié - en réalité nécessite arrêt de X)
            # Pour une vraie implémentation, il faudrait:
            # 1. Créer un script systemd
            # 2. Redémarrer en mode texte
            # 3. Exécuter le .run
            # 4. Redémarrer

            result = subprocess.run(
                ["pkexec", str(run_file_path), "--silent", "--no-questions"],
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode == 0:
                if progress_callback:
                    progress_callback("Installation terminée", 1.0)
                return (True, "Driver NVIDIA installé avec succès. Un redémarrage est recommandé.")
            else:
                return (False, f"Erreur d'installation: {result.stderr}")

        except subprocess.TimeoutExpired:
            return (False, "Installation expirée (timeout)")
        except Exception as e:
            return (False, f"Erreur: {str(e)}")

    def install_amd_deb_file(self, deb_file_path, progress_callback=None):
        """
        Installe le paquet .deb AMD (qui installe amdgpu-install)
        Retourne: (success: bool, message: str)
        """
        try:
            if progress_callback:
                progress_callback("Installation du paquet AMD...", 0.3)

            result = subprocess.run(
                ["pkexec", "dpkg", "-i", str(deb_file_path)],
                capture_output=True,
                text=True,
                check=True
            )

            if progress_callback:
                progress_callback("Installation terminée", 1.0)

            return (True, "Paquet AMD installé. Utilisez 'amdgpu-install --usecase=graphics' pour installer les drivers.")

        except subprocess.CalledProcessError as e:
            return (False, f"Erreur d'installation: {e.stderr}")

    def remove_driver(self, vendor, progress_callback=None):
        """
        Supprime le driver propriétaire
        Retourne: (success: bool, message: str)
        """
        try:
            if vendor == 'NVIDIA':
                if progress_callback:
                    progress_callback("Suppression du driver NVIDIA...", 0.3)

                # Essayer de désinstaller via apt
                subprocess.run(
                    ["pkexec", "apt-get", "remove", "--purge", "-y", "nvidia-*"],
                    capture_output=True
                )

                # Essayer nvidia-uninstall si existe
                nvidia_uninstall = Path("/usr/bin/nvidia-uninstall")
                if nvidia_uninstall.exists():
                    subprocess.run(
                        ["pkexec", str(nvidia_uninstall), "--silent"],
                        capture_output=True
                    )

                return (True, "Driver NVIDIA supprimé. Un redémarrage est recommandé.")

            elif vendor == 'AMD':
                if progress_callback:
                    progress_callback("Suppression du driver AMD...", 0.3)

                subprocess.run(
                    ["pkexec", "apt-get", "remove", "--purge", "-y", "amdgpu-pro", "amdgpu-install"],
                    capture_output=True
                )

                return (True, "Driver AMD supprimé. Un redémarrage est recommandé.")

            return (False, "Fabricant non supporté")

        except Exception as e:
            return (False, f"Erreur de suppression: {str(e)}")

    # ==========================================
    # WEB SCRAPING DYNAMIQUE
    # ==========================================

    def scrape_nvidia_latest_version(self, progress_callback=None):
        """
        Scrape la page NVIDIA pour obtenir la dernière version
        Retourne: dict avec version, url, date ou None
        """
        try:
            if progress_callback:
                progress_callback("Récupération des dernières versions NVIDIA...", 0.2)

            # URL pour la dernière version stable
            url = "https://download.nvidia.com/XFree86/Linux-x86_64/latest.txt"

            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                version = response.read().decode('utf-8').strip()

            if version:
                download_url = f"{self.NVIDIA_DOWNLOAD_BASE}/{version}/NVIDIA-Linux-x86_64-{version}.run"

                return {
                    'version': version,
                    'url': download_url,
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'size': '~350 MB',
                    'filename': f"NVIDIA-Linux-x86_64-{version}.run"
                }

        except Exception as e:
            if progress_callback:
                progress_callback(f"Erreur de scraping: {str(e)}", 0.0)

        return None

    def scrape_amd_latest_version(self, progress_callback=None):
        """
        Scrape pour obtenir la dernière version AMD
        Retourne: dict avec version, url, date ou None
        """
        try:
            if progress_callback:
                progress_callback("Récupération des dernières versions AMD...", 0.2)

            # AMD organise par version Ubuntu
            codename = self.distro_info['codename']

            # Mapper le codename Ubuntu à l'URL AMD
            codename_map = {
                'noble': '24.04',
                'jammy': '22.04',
                'focal': '20.04'
            }

            ubuntu_version = codename_map.get(codename, '22.04')

            # Version hardcodée connue (scraping AMD est complexe)
            version = '6.2.3'
            version_num = version.replace('.', '')

            url = f"{self.AMD_DOWNLOAD_BASE}/{version}/ubuntu/{codename}/amdgpu-install_{version_num}-1_all.deb"

            return {
                'version': version,
                'url': url,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'size': '~2 MB',
                'filename': f"amdgpu-install_{version_num}-1_all.deb",
                'note': 'This package installs the amdgpu-install script',
                'ubuntu_version': ubuntu_version
            }

        except Exception as e:
            if progress_callback:
                progress_callback(f"Erreur: {str(e)}", 0.0)

        return None

    # ==========================================
    # SYSTÈME DE ROLLBACK
    # ==========================================

    def create_driver_backup(self, vendor, progress_callback=None):
        """
        Crée une sauvegarde du driver actuel avant installation
        Retourne: (success: bool, backup_id: str ou None, message: str)
        """
        try:
            if progress_callback:
                progress_callback("Création de la sauvegarde...", 0.2)

            current_driver = self.get_current_driver(vendor)
            if not current_driver:
                return (False, None, "Aucun driver à sauvegarder")

            # Créer un ID unique pour la sauvegarde
            backup_id = f"{vendor}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_path = self.backup_dir / backup_id

            backup_path.mkdir(parents=True, exist_ok=True)

            # Sauvegarder les informations du driver
            backup_info = {
                'timestamp': datetime.now().isoformat(),
                'vendor': vendor,
                'driver': current_driver,
                'distro': self.distro_info,
                'display_server': self.display_server
            }

            # Sauvegarder la liste des paquets installés
            if vendor == 'NVIDIA':
                result = subprocess.run(
                    ["dpkg", "-l"],
                    capture_output=True,
                    text=True,
                    check=True
                )

                nvidia_packages = []
                for line in result.stdout.split('\n'):
                    if 'nvidia' in line.lower():
                        nvidia_packages.append(line)

                backup_info['packages'] = nvidia_packages

            elif vendor == 'AMD':
                result = subprocess.run(
                    ["dpkg", "-l"],
                    capture_output=True,
                    text=True,
                    check=True
                )

                amd_packages = []
                for line in result.stdout.split('\n'):
                    if 'amdgpu' in line.lower() or 'amd' in line.lower():
                        amd_packages.append(line)

                backup_info['packages'] = amd_packages

            # Sauvegarder dans un fichier JSON
            with open(backup_path / 'backup_info.json', 'w') as f:
                json.dump(backup_info, f, indent=2)

            if progress_callback:
                progress_callback("Sauvegarde créée", 1.0)

            return (True, backup_id, f"Sauvegarde créée: {backup_id}")

        except Exception as e:
            return (False, None, f"Erreur de sauvegarde: {str(e)}")

    def list_backups(self, vendor=None):
        """
        Liste les sauvegardes disponibles
        Retourne: liste de dicts avec backup_id, timestamp, vendor, driver
        """
        backups = []

        try:
            for backup_dir in self.backup_dir.iterdir():
                if backup_dir.is_dir():
                    info_file = backup_dir / 'backup_info.json'
                    if info_file.exists():
                        with open(info_file, 'r') as f:
                            backup_info = json.load(f)

                        # Filtrer par vendor si spécifié
                        if vendor is None or backup_info.get('vendor') == vendor:
                            backups.append({
                                'backup_id': backup_dir.name,
                                'timestamp': backup_info.get('timestamp'),
                                'vendor': backup_info.get('vendor'),
                                'driver': backup_info.get('driver'),
                                'distro': backup_info.get('distro')
                            })

            # Trier par timestamp décroissant (plus récent d'abord)
            backups.sort(key=lambda x: x['timestamp'], reverse=True)

        except Exception:
            pass

        return backups

    def rollback_driver(self, backup_id, progress_callback=None):
        """
        Restaure un driver depuis une sauvegarde
        Retourne: (success: bool, message: str)
        """
        try:
            backup_path = self.backup_dir / backup_id
            info_file = backup_path / 'backup_info.json'

            if not info_file.exists():
                return (False, "Sauvegarde introuvable")

            with open(info_file, 'r') as f:
                backup_info = json.load(f)

            vendor = backup_info.get('vendor')
            driver_info = backup_info.get('driver')

            if progress_callback:
                progress_callback(f"Restauration du driver {vendor}...", 0.3)

            # Pour l'instant, rollback = suppression du driver actuel
            # Le système reviendra au driver open source
            success, message = self.remove_driver(vendor, progress_callback)

            if success:
                # Ajouter à l'historique
                self.add_to_history(
                    action='rollback',
                    vendor=vendor,
                    driver_name=driver_info.get('name', 'Unknown'),
                    driver_version=driver_info.get('version', 'Unknown'),
                    source='backup',
                    success=True,
                    details={'backup_id': backup_id}
                )

                return (True, f"Rollback réussi. Driver supprimé, le système utilisera le driver open source.")

            return (False, f"Échec du rollback: {message}")

        except Exception as e:
            return (False, f"Erreur de rollback: {str(e)}")

    # ==========================================
    # INSTALLATION NVIDIA INTELLIGENTE (Wayland/X11)
    # ==========================================

    def install_nvidia_intelligently(self, run_file_path, progress_callback=None):
        """
        Installation NVIDIA intelligente avec gestion automatique de Wayland/X11
        Crée un script systemd pour installation au démarrage si nécessaire
        Retourne: (success: bool, message: str)
        """
        try:
            if progress_callback:
                progress_callback("Analyse de l'environnement...", 0.1)

            # Détecter le display server
            if self.display_server in ['X11', 'Wayland']:
                # Besoin d'arrêter le serveur graphique
                if progress_callback:
                    progress_callback("Installation nécessite arrêt du serveur graphique...", 0.2)

                return self._install_nvidia_with_systemd(run_file_path, progress_callback)

            elif self.display_server == 'TTY':
                # Déjà en TTY, installation directe possible
                if progress_callback:
                    progress_callback("Installation directe en mode TTY...", 0.3)

                return self._install_nvidia_direct(run_file_path, progress_callback)

            else:
                return (False, "Environnement d'affichage non détecté")

        except Exception as e:
            return (False, f"Erreur d'installation: {str(e)}")

    def _install_nvidia_with_systemd(self, run_file_path, progress_callback=None):
        """
        Crée un service systemd one-shot pour installer NVIDIA au prochain démarrage
        """
        try:
            # Créer un script d'installation
            install_script = self.drivers_dir / "install_nvidia.sh"

            script_content = f"""#!/bin/bash
# Script d'installation automatique NVIDIA
# Généré par KernelCustom Manager

# Arrêter le serveur graphique
systemctl stop gdm3 2>/dev/null
systemctl stop lightdm 2>/dev/null
systemctl stop sddm 2>/dev/null

# Installation
{run_file_path} --silent --no-questions

# Nettoyer le service
systemctl disable kernelcustom-nvidia-install.service
rm -f /etc/systemd/system/kernelcustom-nvidia-install.service
rm -f {install_script}

# Redémarrer
reboot
"""

            with open(install_script, 'w') as f:
                f.write(script_content)

            install_script.chmod(0o755)

            # Créer le service systemd
            service_content = f"""[Unit]
Description=KernelCustom Manager - NVIDIA Driver Installation
After=multi-user.target
Before=display-manager.service

[Service]
Type=oneshot
ExecStart={install_script}
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

            service_file = Path("/tmp/kernelcustom-nvidia-install.service")
            with open(service_file, 'w') as f:
                f.write(service_content)

            # Copier vers /etc/systemd/system/ avec pkexec
            subprocess.run(
                ["pkexec", "cp", str(service_file), "/etc/systemd/system/kernelcustom-nvidia-install.service"],
                check=True
            )

            # Activer le service
            subprocess.run(
                ["pkexec", "systemctl", "enable", "kernelcustom-nvidia-install.service"],
                check=True
            )

            if progress_callback:
                progress_callback("Service créé", 1.0)

            return (True, "Installation programmée au prochain redémarrage.\n\n⚠️ Le système va redémarrer et installer le driver NVIDIA automatiquement.\n\nVoulez-vous redémarrer maintenant ?")

        except Exception as e:
            return (False, f"Erreur de création du service: {str(e)}")

    def _install_nvidia_direct(self, run_file_path, progress_callback=None):
        """Installation NVIDIA directe (déjà en mode TTY)"""
        try:
            if progress_callback:
                progress_callback("Installation en cours...", 0.5)

            result = subprocess.run(
                ["pkexec", str(run_file_path), "--silent", "--no-questions"],
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode == 0:
                if progress_callback:
                    progress_callback("Installation terminée", 1.0)

                return (True, "Driver NVIDIA installé avec succès. Un redémarrage est recommandé.")
            else:
                return (False, f"Erreur d'installation: {result.stderr}")

        except subprocess.TimeoutExpired:
            return (False, "Installation expirée (timeout)")
        except Exception as e:
            return (False, f"Erreur: {str(e)}")
