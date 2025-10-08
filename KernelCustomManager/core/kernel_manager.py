"""
Module de gestion des kernels
Logique métier pour télécharger, compiler, installer les kernels
"""

from gi.repository import Notify
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
import json


class KernelManager:
    """Classe principale pour gérer les kernels"""
    
    def __init__(self, base_dir=None):
        if base_dir is None:
            self.base_dir = Path.home() / "KernelCustomManager" / "build"
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
        except:
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
        """Sauvegarde un profil"""
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
    
    def load_profile(self, profile_name):
        """Charge un profil"""
        config_path = self.profiles_dir / f"{profile_name}.config"
        linux_dir = self.base_dir / "linux"
        
        if not config_path.exists():
            return False
        
        shutil.copy(config_path, linux_dir / ".config")
        
        subprocess.run(
            ["make", "olddefconfig"],
            cwd=str(linux_dir),
            capture_output=True
        )
        
        return True
    
    def get_profiles(self):
        """Liste tous les profils"""
        profiles = []
        
        for meta_file in self.profiles_dir.glob("*.json"):
            try:
                with open(meta_file, 'r') as f:
                    profile_data = json.load(f)
                    profiles.append(profile_data)
            except:
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
        linux_dir = self.base_dir / "linux"
        
        if not Path(source).exists():
            return False
        
        shutil.copy(source, linux_dir / ".config")
        
        subprocess.run(
            ["make", "olddefconfig"],
            cwd=str(linux_dir),
            capture_output=True
        )
        
        return True
    
    def send_notification(self, title, message, urgency="normal"):
        """Envoie une notification système"""
        try:
            notification = Notify.Notification.new(title, message, "dialog-information")
            
            if urgency == "critical":
                notification.set_urgency(Notify.Urgency.CRITICAL)
            elif urgency == "low":
                notification.set_urgency(Notify.Urgency.LOW)
            
            notification.show()
        except:
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
        except:
            return []
    
    def get_local_packages(self):
        """Liste les paquets .deb locaux"""
        packages = []
        for deb_file in self.repo_dir.glob("linux-image-*.deb"):
            size = deb_file.stat().st_size / (1024 * 1024)
            packages.append({
                'name': deb_file.name,
                'path': deb_file,
                'size': f"{size:.1f} Mo"
            })
        return packages
    
    def download_kernel(self, version, progress_callback=None):
        """Télécharge les sources d'un kernel"""
        major = version.split('.')[0]
        archive = f"linux-{version}.tar.xz"
        url = f"https://cdn.kernel.org/pub/linux/kernel/v{major}.x/{archive}"
        dest = self.sources_dir / archive
        
        try:
            import urllib.request
            
            def report_progress(block_num, block_size, total_size):
                if progress_callback and total_size > 0:
                    percent = min(int((block_num * block_size * 100) / total_size), 100)
                    progress_callback(percent)
            
            urllib.request.urlretrieve(url, dest, reporthook=report_progress)
            
            if progress_callback:
                progress_callback(90, "Extraction...")
            
            subprocess.run(
                ["tar", "-xf", str(dest), "-C", str(self.sources_dir)],
                check=True
            )
            
            dest.unlink()
            
            linux_link = self.base_dir / "linux"
            if linux_link.exists():
                linux_link.unlink()
            linux_link.symlink_to(self.sources_dir / f"linux-{version}")
            
            return True
            
        except Exception as e:
            print(f"Erreur téléchargement: {e}")
            return False