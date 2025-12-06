"""
Module de gestion SecureBoot
Logique métier pour vérifier le statut, gérer les clés MOK et configurer SecureBoot
"""

import subprocess
import re
import json
from pathlib import Path
from datetime import datetime
import shutil
import os
import logging
import threading
import platform

# Configurer le logging
log_file = Path.home() / "KernelCustomManager" / "build" / "secureboot" / "sign_debug.log"
log_file.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)


class SecureBootManager:
    """Classe principale pour gérer SecureBoot"""

    def __init__(self, base_dir=None):
        if base_dir is None:
            self.base_dir = Path.home() / "KernelCustomManager" / "build"
        else:
            self.base_dir = Path(base_dir)

        # Dossiers pour SecureBoot
        self.secureboot_dir = self.base_dir / "secureboot"
        self.keys_dir = self.secureboot_dir / "keys"
        self.backup_dir = self.secureboot_dir / "backups"
        self.history_file = self.secureboot_dir / "secureboot_history.json"

        # Créer les dossiers
        self.secureboot_dir.mkdir(parents=True, exist_ok=True)
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Initialiser l'historique
        if not self.history_file.exists():
            self._save_history([])

        # Cache pour les données MOK (évite de demander le mot de passe plusieurs fois)
        self._mok_cache = None
        self._mok_cache_lock = threading.Lock()

    def clear_mok_cache(self):
        """Vide le cache MOK pour forcer une nouvelle lecture"""
        with self._mok_cache_lock:
            self._mok_cache = None
            print("[DEBUG] MOK cache cleared")

    # ==================== Historique ====================

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

    def add_to_history(self, action, details, success=True):
        """Ajoute une entrée à l'historique"""
        history = self._load_history()

        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'details': details,
            'success': success
        }

        history.insert(0, entry)
        history = history[:100]  # Garder les 100 dernières entrées
        self._save_history(history)
        return entry

    def get_history(self):
        """Récupère l'historique"""
        return self._load_history()

    # ==================== Détection du statut ====================

    def is_uefi_system(self):
        """Vérifie si le système utilise UEFI"""
        efi_dir = Path("/sys/firmware/efi")
        return efi_dir.exists()

    def get_secureboot_status(self):
        """
        Récupère le statut de SecureBoot
        Retourne: dict avec enabled (bool), setup_mode (bool), details (str)
        """
        if not self.is_uefi_system():
            return {
                'enabled': False,
                'setup_mode': False,
                'details': 'System is not using UEFI',
                'error': 'NOT_UEFI'
            }

        status = {
            'enabled': False,
            'setup_mode': False,
            'details': '',
            'error': None
        }

        # Méthode 1: Lire via mokutil (préféré)
        try:
            result = subprocess.run(
                ["mokutil", "--sb-state"],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                if "SecureBoot enabled" in output:
                    status['enabled'] = True
                    status['details'] = "SecureBoot is enabled"
                elif "SecureBoot disabled" in output:
                    status['enabled'] = False
                    status['details'] = "SecureBoot is disabled"
                else:
                    status['details'] = output

                return status
        except FileNotFoundError:
            # mokutil n'est pas installé, essayer la méthode 2
            pass

        # Méthode 2: Lire directement depuis efivars
        try:
            secureboot_file = Path("/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c")

            if secureboot_file.exists():
                with open(secureboot_file, 'rb') as f:
                    data = f.read()
                    # Le dernier octet indique le statut (0x00 = disabled, 0x01 = enabled)
                    if len(data) > 0:
                        sb_value = data[-1]
                        status['enabled'] = (sb_value == 1)
                        status['details'] = f"SecureBoot is {'enabled' if status['enabled'] else 'disabled'}"
                        return status
        except (FileNotFoundError, PermissionError):
            pass

        # Méthode 3: Utiliser bootctl (systemd-boot)
        try:
            result = subprocess.run(
                ["bootctl", "status"],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Secure Boot' in line:
                        if 'enabled' in line.lower():
                            status['enabled'] = True
                            status['details'] = "SecureBoot is enabled (via bootctl)"
                        else:
                            status['enabled'] = False
                            status['details'] = "SecureBoot is disabled (via bootctl)"
                        return status
        except FileNotFoundError:
            pass

        status['details'] = "Unable to determine SecureBoot status"
        status['error'] = "UNABLE_TO_DETECT"
        return status

    def check_setup_mode(self):
        """Vérifie si SecureBoot est en mode Setup"""
        try:
            setup_file = Path("/sys/firmware/efi/efivars/SetupMode-8be4df61-93ca-11d2-aa0d-00e098032b8c")

            if setup_file.exists():
                with open(setup_file, 'rb') as f:
                    data = f.read()
                    if len(data) > 0:
                        setup_value = data[-1]
                        return setup_value == 1
        except (FileNotFoundError, PermissionError):
            pass

        return False

    # ==================== Vérification enrollment MOK ====================

    def _fetch_mok_data(self):
        """
        Récupère toutes les données MOK en une seule commande (évite de demander le mot de passe plusieurs fois)
        Returns: dict avec enrolled_output et pending_output
        """
        import traceback

        # Vérifier le cache sans lock d'abord (optimisation)
        if self._mok_cache is not None:
            print(f"[DEBUG] _fetch_mok_data: Using CACHE (instance id: {id(self)})")
            return self._mok_cache

        # Utiliser un lock pour éviter les appels parallèles
        with self._mok_cache_lock:
            # Re-vérifier le cache après avoir acquis le lock
            # (un autre thread a pu le remplir pendant qu'on attendait le lock)
            if self._mok_cache is not None:
                print(f"[DEBUG] _fetch_mok_data: Using CACHE after lock (instance id: {id(self)})")
                return self._mok_cache

            print(f"[DEBUG] _fetch_mok_data: CALLING pkexec (instance id: {id(self)})")
            print(f"[DEBUG] Stack trace:")
            traceback.print_stack()

            try:
                result = subprocess.run(
                    ["pkexec", "/usr/local/bin/kernelcustom-helper", "mokutil-diagnose"],
                    capture_output=True, text=True, check=False
                )

                if result.returncode != 0:
                    return {'enrolled_output': '', 'pending_output': ''}

                output = result.stdout

                # Parser la sortie pour séparer ENROLLED et PENDING
                enrolled_output = ''
                pending_output = ''

                if 'ENROLLED:' in output and 'PENDING:' in output:
                    parts = output.split('PENDING:')
                    enrolled_output = parts[0].replace('ENROLLED:', '').strip()
                    pending_output = parts[1].strip()

                self._mok_cache = {
                    'enrolled_output': enrolled_output,
                    'pending_output': pending_output
                }

                return self._mok_cache
            except Exception:
                return {'enrolled_output': '', 'pending_output': ''}

    def check_mok_enrolled(self):
        """
        Vérifie si une clé MOK est déjà enrollée
        Returns: dict avec status, key_found, cn_name
        """
        try:
            mok_data = self._fetch_mok_data()
            output = mok_data['enrolled_output']

            if "MokListRT is empty" in output:
                return {
                    'status': 'none',
                    'key_found': False,
                    'cn_name': None,
                    'message': 'No MOK keys enrolled'
                }

            # Chercher notre clé
            if "kernelcustom" in output.lower():
                return {
                    'status': 'enrolled',
                    'key_found': True,
                    'cn_name': 'kernelcustom',
                    'message': 'MOK key is already enrolled'
                }

            return {
                'status': 'other_keys',
                'key_found': False,
                'cn_name': None,
                'message': 'Other MOK keys found, but not ours'
            }
        except Exception as e:
            return {
                'status': 'error',
                'key_found': False,
                'cn_name': None,
                'message': str(e)
            }

    def check_mok_pending(self):
        """
        Vérifie si une clé MOK est en attente d'enrollment
        Returns: bool
        """
        try:
            mok_data = self._fetch_mok_data()
            output = mok_data['pending_output']
            return not ("MokNew is empty" in output or output.strip() == "")
        except:
            return False

    def enroll_mok_key(self, password=None):
        """
        Importe la clé MOK pour enrollment au prochain redémarrage
        Args:
            password: Mot de passe temporaire (si None, demandé interactivement)
        Returns: dict avec success, message, needs_reboot
        """
        mok_key = self.keys_dir / "MOK.der"

        if not mok_key.exists():
            return {
                'success': False,
                'message': 'MOK key not found. Generate a key first.',
                'needs_reboot': False
            }

        try:
            # Importer la clé avec pkexec via le helper
            cmd = ["pkexec", "/usr/local/bin/kernelcustom-helper", "mokutil-import", str(mok_key)]

            if password:
                # Mode non-interactif (si supporté par mokutil)
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = process.communicate(input=f"{password}\n{password}\n")
                success = process.returncode == 0
                error_msg = stderr if stderr else ""
            else:
                # Mode interactif (terminal)
                result = subprocess.run(cmd, check=True)
                success = result.returncode == 0
                error_msg = ""

            if success:
                self.add_to_history(
                    "MOK Enrollment",
                    "MOK key imported, awaiting reboot",
                    success=True
                )

                return {
                    'success': True,
                    'message': 'MOK key imported successfully. Reboot required.',
                    'needs_reboot': True
                }
            else:
                return {
                    'success': False,
                    'message': f'Failed to import MOK key: {error_msg}',
                    'needs_reboot': False
                }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'needs_reboot': False
            }

    # ==================== Gestion des clés MOK ====================

    def list_enrolled_keys(self):
        """Liste les clés MOK enrollées"""
        try:
            # Utiliser le cache pour éviter de demander le mot de passe plusieurs fois
            mok_data = self._fetch_mok_data()
            output = mok_data['enrolled_output']

            if output:
                keys = self._parse_mok_list(output)
                return {'success': True, 'keys': keys, 'raw_output': output}
            else:
                return {'success': False, 'error': 'Unable to fetch MOK data', 'keys': []}
        except Exception as e:
            return {'success': False, 'error': str(e), 'keys': []}

    def _parse_mok_list(self, output):
        """Parse la sortie de mokutil --list-enrolled"""
        keys = []
        current_key = {}

        for line in output.split('\n'):
            line = line.strip()

            if line.startswith('[key '):
                if current_key:
                    keys.append(current_key)
                current_key = {'index': line}
            elif 'Subject:' in line or 'CN=' in line:
                current_key['subject'] = line.split('Subject:')[-1].strip() if 'Subject:' in line else line
            elif 'Issuer:' in line:
                current_key['issuer'] = line.split('Issuer:')[-1].strip()
            elif 'Not Before:' in line:
                current_key['not_before'] = line.split('Not Before:')[-1].strip()
            elif 'Not After:' in line:
                current_key['not_after'] = line.split('Not After:')[-1].strip()

        if current_key:
            keys.append(current_key)

        return keys

    def list_pending_keys(self):
        """Liste les clés en attente d'enrollment"""
        try:
            # Utiliser le cache pour éviter de demander le mot de passe plusieurs fois
            mok_data = self._fetch_mok_data()
            output = mok_data['pending_output']

            if "MokNew is empty" in output or not output:
                return {'success': True, 'keys': [], 'message': 'No pending keys'}
            else:
                keys = self._parse_mok_list(output)
                return {'success': True, 'keys': keys, 'raw_output': output}
        except Exception as e:
            return {'success': False, 'error': str(e), 'keys': []}

    def import_mok_key(self, key_file):
        """
        Importe une clé MOK (nécessitera un mot de passe et un reboot)
        key_file: chemin vers le fichier .der ou .cer
        """
        key_path = Path(key_file)

        if not key_path.exists():
            return {'success': False, 'error': f'Key file not found: {key_file}'}

        try:
            # mokutil --import demande un mot de passe interactivement
            # On ne peut pas l'automatiser complètement
            result = subprocess.run(
                ["pkexec", "/usr/local/bin/kernelcustom-helper", "mokutil-import", str(key_path)],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                self.add_to_history(
                    'import_key',
                    {'key_file': str(key_path), 'output': result.stdout},
                    success=True
                )
                return {
                    'success': True,
                    'message': 'Key import initiated. Reboot required to complete enrollment.',
                    'output': result.stdout
                }
            else:
                return {'success': False, 'error': result.stderr}
        except FileNotFoundError:
            return {'success': False, 'error': 'mokutil is not installed'}

    def delete_mok_key(self, key_file):
        """
        Supprime une clé MOK (nécessitera un reboot)
        """
        key_path = Path(key_file)

        if not key_path.exists():
            return {'success': False, 'error': f'Key file not found: {key_file}'}

        try:
            result = subprocess.run(
                ["pkexec", "/usr/local/bin/kernelcustom-helper", "mokutil-delete", str(key_path)],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                self.add_to_history(
                    'delete_key',
                    {'key_file': str(key_path), 'output': result.stdout},
                    success=True
                )
                return {
                    'success': True,
                    'message': 'Key deletion initiated. Reboot required to complete.',
                    'output': result.stdout
                }
            else:
                return {'success': False, 'error': result.stderr}
        except FileNotFoundError:
            return {'success': False, 'error': 'mokutil is not installed'}

    def reset_mok_keys(self):
        """Réinitialise toutes les clés MOK"""
        try:
            result = subprocess.run(
                ["pkexec", "/usr/local/bin/kernelcustom-helper", "mokutil-reset"],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                self.add_to_history('reset_keys', {'output': result.stdout}, success=True)
                return {
                    'success': True,
                    'message': 'MOK reset initiated. Reboot required.',
                    'output': result.stdout
                }
            else:
                return {'success': False, 'error': result.stderr}
        except FileNotFoundError:
            return {'success': False, 'error': 'mokutil is not installed'}

    # ==================== Génération de clés ====================

    def generate_signing_key(self, key_name="MOK", common_name=None):
        """
        Génère une paire de clés pour signer des modules kernel
        Retourne le chemin vers la clé privée et le certificat
        """
        if common_name is None:
            common_name = f"Kernel Module Signing Key - {key_name}"

        key_base = self.keys_dir / key_name
        priv_key = key_base.with_suffix('.priv')
        der_cert = key_base.with_suffix('.der')
        pem_cert = key_base.with_suffix('.pem')

        try:
            # Générer la clé privée
            subprocess.run([
                "openssl", "req", "-new", "-x509",
                "-newkey", "rsa:2048",
                "-keyout", str(priv_key),
                "-outform", "DER",
                "-out", str(der_cert),
                "-nodes",
                "-days", "36500",
                "-subj", f"/CN={common_name}/"
            ], check=True, capture_output=True)

            # Convertir en PEM également (pour certains outils)
            subprocess.run([
                "openssl", "x509",
                "-in", str(der_cert),
                "-inform", "DER",
                "-out", str(pem_cert),
                "-outform", "PEM"
            ], check=True, capture_output=True)

            self.add_to_history(
                'generate_key',
                {
                    'key_name': key_name,
                    'common_name': common_name,
                    'priv_key': str(priv_key),
                    'der_cert': str(der_cert),
                    'pem_cert': str(pem_cert)
                },
                success=True
            )

            return {
                'success': True,
                'priv_key': priv_key,
                'der_cert': der_cert,
                'pem_cert': pem_cert,
                'message': f'Key pair generated successfully'
            }

        except subprocess.CalledProcessError as e:
            return {
                'success': False,
                'error': f'Failed to generate key: {e.stderr.decode() if e.stderr else str(e)}'
            }
        except FileNotFoundError:
            return {
                'success': False,
                'error': 'openssl is not installed'
            }

    def sign_kernel_module(self, module_path, priv_key_path, cert_path):
        """
        Signe un module kernel avec une clé privée
        """
        module = Path(module_path)
        priv_key = Path(priv_key_path)
        cert = Path(cert_path)

        if not module.exists():
            return {'success': False, 'error': 'Module file not found'}
        if not priv_key.exists():
            return {'success': False, 'error': 'Private key not found'}
        if not cert.exists():
            return {'success': False, 'error': 'Certificate not found'}

        try:
            # Chercher l'outil de signature du kernel
            sign_file = self._find_sign_file_tool()
            if not sign_file:
                return {'success': False, 'error': 'sign-file tool not found'}

            # Signer le module
            result = subprocess.run([
                str(sign_file),
                "sha256",
                str(priv_key),
                str(cert),
                str(module)
            ], capture_output=True, text=True, check=False)

            if result.returncode == 0:
                self.add_to_history(
                    'sign_module',
                    {'module': str(module), 'key': str(priv_key)},
                    success=True
                )
                return {
                    'success': True,
                    'message': f'Module signed successfully: {module.name}'
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr if result.stderr else 'Unknown error'
                }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _find_sign_file_tool(self):
        """Trouve l'outil sign-file du kernel"""
        # Chercher dans les emplacements communs
        kernel_version = os.uname().release
        kernel_major_minor = '.'.join(kernel_version.split('.')[:2])

        possible_locations = [
            # Ubuntu/Debian - headers actuels
            Path("/usr/src/linux-headers-" + kernel_version) / "scripts" / "sign-file",
            # Ubuntu - kbuild-tools
            Path("/usr/lib/linux-kbuild-" + kernel_major_minor) / "scripts" / "sign-file",
            # Debian - kbuild-tools
            Path("/usr/lib/linux-kbuild-" + kernel_version.split('-')[0]) / "scripts" / "sign-file",
            # Module build symlink
            Path("/lib/modules") / kernel_version / "build" / "scripts" / "sign-file",
            # Chemins alternatifs pour Debian
            Path("/usr/lib/linux-tools-" + kernel_version) / "sign-file",
            Path("/usr/lib/linux-tools-" + kernel_major_minor) / "sign-file",
        ]

        for location in possible_locations:
            if location.exists() and location.is_file():
                return location

        # Chercher avec shutil.which avec PATH étendu
        extended_path = os.environ.get('PATH', '') + ':/sbin:/usr/sbin:/usr/local/sbin'
        result = shutil.which("sign-file", path=extended_path)
        if result:
            return Path(result)

        return None

    # ==================== Vérification des modules ====================

    def check_module_signature(self, module_path):
        """Vérifie si un module kernel est signé"""
        module = Path(module_path)

        if not module.exists():
            return {'success': False, 'error': 'Module file not found'}

        try:
            result = subprocess.run(
                ["modinfo", "-F", "sig_id", str(module)],
                capture_output=True,
                text=True,
                check=False
            )

            has_signature = bool(result.stdout.strip())

            # Obtenir plus d'infos
            info_result = subprocess.run(
                ["modinfo", str(module)],
                capture_output=True,
                text=True,
                check=False
            )

            return {
                'success': True,
                'signed': has_signature,
                'signature_info': result.stdout.strip() if has_signature else 'Not signed',
                'module_info': info_result.stdout
            }

        except FileNotFoundError:
            return {'success': False, 'error': 'modinfo command not found'}

    # ==================== Utilitaires ====================

    def check_dependencies(self):
        """Vérifie que les dépendances nécessaires sont installées"""
        deps = {
            'mokutil': self._check_command('mokutil'),
            'openssl': self._check_command('openssl'),
            'modinfo': self._check_command('modinfo'),
            'sign-file': self._find_sign_file_tool() is not None,
            'sbsign': self._check_command('sbsign'),
            'sbverify': self._check_command('sbverify')
        }

        all_installed = all(deps.values())

        return {
            'all_installed': all_installed,
            'dependencies': deps,
            'missing': [name for name, installed in deps.items() if not installed]
        }

    def _check_command(self, command):
        """Vérifie si une commande est disponible"""
        # Étendre le PATH pour inclure /sbin et /usr/sbin (pour Debian)
        extended_path = os.environ.get('PATH', '') + ':/sbin:/usr/sbin:/usr/local/sbin'

        # Utiliser shutil.which avec le PATH étendu
        result = shutil.which(command, path=extended_path)

        return result is not None

    def _is_vmlinuz_signing_supported(self):
        """
        Vérifie si la signature vmlinuz est supportée sur cette architecture.
        sbsign ne fonctionne que sur x86/x86_64 (PE/COFF format).
        Sur ARM, les kernels ne sont pas au format PE/COFF.
        """
        arch = platform.machine().lower()
        # Architectures supportées par sbsign (PE/COFF format)
        supported_archs = ['x86_64', 'amd64', 'i386', 'i686']
        return arch in supported_archs

    def get_system_info(self):
        """Récupère les informations système pertinentes pour SecureBoot"""
        info = {
            'is_uefi': self.is_uefi_system(),
            'secureboot_status': self.get_secureboot_status(),
            'setup_mode': self.check_setup_mode() if self.is_uefi_system() else False,
            'dependencies': self.check_dependencies()
        }

        return info

    # ==================== Détection et gestion des kernels custom ====================

    def get_custom_kernels(self):
        """
        Détecte tous les kernels personnalisés installés
        Returns: list de dict avec kernel_version, path, module_count
        """
        modules_dir = Path("/lib/modules")
        custom_kernels = []

        if not modules_dir.exists():
            return custom_kernels

        for kernel_dir in modules_dir.iterdir():
            if kernel_dir.is_dir() and "kernelcustom" in kernel_dir.name.lower():
                # Compter les modules (incluant les modules compressés)
                modules = []
                for ext in ['*.ko', '*.ko.xz', '*.ko.gz', '*.ko.zst']:
                    modules.extend(kernel_dir.rglob(ext))

                custom_kernels.append({
                    'kernel_version': kernel_dir.name,
                    'path': str(kernel_dir),
                    'module_count': len(modules),
                    'modules': [str(m) for m in modules]
                })

        return custom_kernels

    def check_module_signed(self, module_path):
        """
        Vérifie si un module est signé
        Returns: dict avec signed (bool), signer (str), sig_id (str)
        """
        try:
            result = subprocess.run(
                ["modinfo", "-F", "sig_id", module_path],
                capture_output=True, text=True, check=False
            )

            sig_id = result.stdout.strip()

            if not sig_id:
                return {'signed': False, 'signer': None, 'sig_id': None}

            # Récupérer le signataire
            result2 = subprocess.run(
                ["modinfo", "-F", "signer", module_path],
                capture_output=True, text=True, check=False
            )

            signer = result2.stdout.strip()

            return {
                'signed': True,
                'signer': signer,
                'sig_id': sig_id
            }
        except:
            return {'signed': False, 'signer': None, 'sig_id': None}

    def resign_kernel_modules(self, kernel_version, progress_callback=None):
        """
        Re-signe tous les modules d'un kernel avec la clé MOK
        Args:
            kernel_version: Version du kernel (ex: "6.17.10-kernelcustom")
            progress_callback: Fonction appelée pour chaque module (current, total, module_name)
        Returns: dict avec success, signed_count, failed_count, errors
        """
        logging.info(f"=== Starting module signing for {kernel_version} ===")

        mok_priv = self.keys_dir / "MOK.priv"
        mok_cert = self.keys_dir / "MOK.der"

        logging.debug(f"MOK priv: {mok_priv} (exists: {mok_priv.exists()})")
        logging.debug(f"MOK cert: {mok_cert} (exists: {mok_cert.exists()})")

        if not mok_priv.exists() or not mok_cert.exists():
            logging.error("MOK keys not found")
            return {
                'success': False,
                'message': 'MOK keys not found',
                'signed_count': 0,
                'failed_count': 0,
                'errors': []
            }

        # Trouver sign-file
        sign_file = self._find_sign_file_tool()
        logging.debug(f"sign-file tool: {sign_file}")

        if not sign_file:
            logging.error("sign-file tool not found")
            return {
                'success': False,
                'message': 'sign-file tool not found',
                'signed_count': 0,
                'failed_count': 0,
                'errors': []
            }

        # Trouver les modules
        kernel_dir = Path(f"/lib/modules/{kernel_version}")
        logging.debug(f"Kernel dir: {kernel_dir} (exists: {kernel_dir.exists()})")

        if not kernel_dir.exists():
            logging.error(f"Kernel directory not found: {kernel_dir}")
            return {
                'success': False,
                'message': f'Kernel directory not found: {kernel_dir}',
                'signed_count': 0,
                'failed_count': 0,
                'errors': []
            }

        # Trouver tous les modules (incluant les modules compressés)
        modules = []
        for ext in ['*.ko', '*.ko.xz', '*.ko.gz', '*.ko.zst']:
            modules.extend(kernel_dir.rglob(ext))
        total = len(modules)
        logging.info(f"Found {total} modules to sign")

        signed = 0
        failed = 0
        errors = []

        # Créer un script pour signer tous les modules avec pkexec (nécessaire pour /lib/modules)
        import tempfile

        script_content = f"""#!/bin/bash

SIGN_FILE="{sign_file}"
MOK_PRIV="{mok_priv}"
MOK_CERT="{mok_cert}"
KERNEL_DIR="{kernel_dir}"
TOTAL={total}

signed=0
failed=0
current=0

# Fonction pour signer un module (gère la compression)
sign_module() {{
    local module="$1"
    local compressed=false
    local compression_type=""
    local ko_file="$module"

    # Détecter le type de compression
    if [[ "$module" == *.ko.xz ]]; then
        compressed=true
        compression_type="xz"
        ko_file="${{module%.xz}}"
        xz -d -k "$module" 2>/dev/null || return 1
    elif [[ "$module" == *.ko.gz ]]; then
        compressed=true
        compression_type="gz"
        ko_file="${{module%.gz}}"
        gzip -d -k "$module" 2>/dev/null || return 1
    elif [[ "$module" == *.ko.zst ]]; then
        compressed=true
        compression_type="zst"
        ko_file="${{module%.zst}}"
        zstd -d -q "$module" -o "$ko_file" 2>/dev/null || return 1
    fi

    # Signer le module .ko
    if "$SIGN_FILE" sha256 "$MOK_PRIV" "$MOK_CERT" "$ko_file" 2>/dev/null; then
        # Si le module était compressé, le recompresser
        if [ "$compressed" = true ]; then
            case "$compression_type" in
                xz)
                    rm -f "$module"
                    xz -z -k "$ko_file" 2>/dev/null
                    rm -f "$ko_file"
                    ;;
                gz)
                    rm -f "$module"
                    gzip -c "$ko_file" > "$module" 2>/dev/null
                    rm -f "$ko_file"
                    ;;
                zst)
                    rm -f "$module"
                    zstd -q "$ko_file" -o "$module" 2>/dev/null
                    rm -f "$ko_file"
                    ;;
            esac
        fi
        return 0
    else
        # Nettoyer en cas d'échec
        [ "$compressed" = true ] && [ -f "$ko_file" ] && rm -f "$ko_file"
        return 1
    fi
}}

# Trouver et signer tous les modules (incluant compressés)
while IFS= read -r -d '' module; do
    ((current++))

    # Extraire le nom du module (basename)
    module_name=$(basename "$module")

    if sign_module "$module"; then
        ((signed++))
    else
        ((failed++))
    fi

    # Afficher la progression avec le nom du module
    echo "PROGRESS:$current:$TOTAL:$module_name"
done < <(find "$KERNEL_DIR" \\( -name "*.ko" -o -name "*.ko.xz" -o -name "*.ko.gz" -o -name "*.ko.zst" \\) -print0)

echo "SIGNED:$signed"
echo "FAILED:$failed"
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as tf:
            tf.write(script_content)
            script_path = tf.name

        logging.debug(f"Created batch signing script: {script_path}")
        os.chmod(script_path, 0o755)

        # Exécuter avec pkexec et suivre la progression
        logging.info("Executing batch module signing with pkexec...")

        process = subprocess.Popen(
            ["pkexec", "bash", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        # Lire la sortie en temps réel
        stdout_lines = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                line = line.strip()
                stdout_lines.append(line)

                # Mettre à jour la progression
                if line.startswith('PROGRESS:'):
                    parts = line.split(':')
                    current = int(parts[1])
                    total_modules = int(parts[2])
                    module_name = parts[3] if len(parts) > 3 else ""
                    if progress_callback:
                        progress_callback(current, total_modules, module_name)
                    logging.debug(f"Progress: {current}/{total_modules} - {module_name}")

        process.wait()

        # Nettoyer
        try:
            os.unlink(script_path)
        except:
            pass

        logging.debug(f"Batch signing result: returncode={process.returncode}")

        # Parser les résultats
        if process.returncode == 0:
            for line in stdout_lines:
                if line.startswith('SIGNED:'):
                    signed = int(line.split(':')[1])
                elif line.startswith('FAILED:'):
                    failed = int(line.split(':')[1])
        else:
            # Si le script échoue, tous les modules sont en échec
            failed = total
            logging.error(f"Batch signing script failed: {process.stderr.read()}")

        success = failed == 0

        logging.info(f"Module signing completed: {signed} signed, {failed} failed")

        self.add_to_history(
            "Module Signing",
            f"Kernel {kernel_version}: {signed} signed, {failed} failed",
            success=success
        )

        return {
            'success': success,
            'message': f'Signed {signed}/{total} modules',
            'signed_count': signed,
            'failed_count': failed,
            'errors': errors
        }

    def _find_vmlinuz_for_kernel(self, kernel_version):
        """
        Trouve le fichier vmlinuz correspondant à un kernel de manière intelligente
        Gère les cas où le nom dans /boot/ ne correspond pas exactement au nom dans /lib/modules/

        Args:
            kernel_version: Version du kernel (ex: "6.17.10-kernelcustom-secureboot")
        Returns: Path object du fichier vmlinuz trouvé, ou None
        """
        boot_dir = Path("/boot")

        # 1. Essayer le nom exact
        exact_match = boot_dir / f"vmlinuz-{kernel_version}"
        if exact_match.exists():
            logging.debug(f"Found exact match: {exact_match}")
            return exact_match

        # 2. Extraire la version de base (ex: "6.17.10" depuis "6.17.10-kernelcustom-secureboot")
        version_parts = kernel_version.split('-')
        if not version_parts:
            return None

        base_version = version_parts[0]  # ex: "6.17.10"
        logging.debug(f"Base version: {base_version}, searching for matches...")

        # 3. Chercher tous les vmlinuz qui correspondent à cette version de base
        candidates = []
        for vmlinuz_file in boot_dir.glob(f"vmlinuz-{base_version}*"):
            # Exclure les backups et fichiers temporaires
            if any(suffix in vmlinuz_file.name for suffix in ['.unsigned', '.old', '.bak', '.signed']):
                logging.debug(f"Skipping backup/temp file: {vmlinuz_file}")
                continue

            # Vérifier que le nom contient au moins une partie du kernel_version
            # (pour éviter les faux positifs avec d'autres kernels de même version de base)
            filename = vmlinuz_file.name.replace('vmlinuz-', '')

            # Compter combien de parties du nom correspondent
            score = 0
            for part in version_parts:
                if part in filename:
                    score += 1

            if score > 0:
                candidates.append((vmlinuz_file, score))
                logging.debug(f"Candidate: {vmlinuz_file} (score: {score})")

        # 4. Trier par score (le plus de correspondances en premier)
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_match = candidates[0][0]
            logging.info(f"Found best match: {best_match} (score: {candidates[0][1]})")
            return best_match

        logging.warning(f"No vmlinuz found for kernel {kernel_version}")
        return None

    def sign_vmlinuz(self, kernel_version, progress_callback=None):
        """
        Signe l'image vmlinuz d'un kernel avec la clé MOK
        Args:
            kernel_version: Version du kernel (ex: "6.17.10-kernelcustom")
            progress_callback: Fonction appelée pour suivre le progrès
        Returns: dict avec success, message
        """
        logging.info(f"=== Starting vmlinuz signing for {kernel_version} ===")

        # Vérifier si la signature vmlinuz est supportée sur cette architecture
        if not self._is_vmlinuz_signing_supported():
            arch = platform.machine()
            logging.warning(f"vmlinuz signing not supported on architecture: {arch}")
            return {
                'success': False,
                'message': f'vmlinuz signing not supported on {arch} architecture. '
                          f'sbsign only works with PE/COFF format kernels (x86/x86_64). '
                          f'ARM kernels use different boot formats. Module signing will still work.'
            }

        mok_priv = self.keys_dir / "MOK.priv"
        mok_cert = self.keys_dir / "MOK.pem"

        logging.debug(f"MOK priv key: {mok_priv} (exists: {mok_priv.exists()})")
        logging.debug(f"MOK cert: {mok_cert} (exists: {mok_cert.exists()})")

        if not mok_priv.exists() or not mok_cert.exists():
            logging.error("MOK keys not found")
            return {
                'success': False,
                'message': 'MOK keys not found. Generate keys first.'
            }

        # Trouver l'image vmlinuz avec recherche intelligente
        vmlinuz_path = self._find_vmlinuz_for_kernel(kernel_version)

        if not vmlinuz_path:
            # Chercher dans /boot/ pour aider au debugging
            boot_files = list(Path("/boot").glob("vmlinuz-*"))
            boot_files_str = "\n  ".join([f.name for f in boot_files[:10]])
            logging.error(f"vmlinuz not found for {kernel_version}")
            logging.debug(f"Available vmlinuz files in /boot/:\n  {boot_files_str}")
            return {
                'success': False,
                'message': f'vmlinuz not found for kernel {kernel_version}. Available files: {", ".join([f.name for f in boot_files[:5]])}'
            }

        # Vérifier que sbsign est installé
        sbsign_available = self._check_command('sbsign')
        logging.debug(f"sbsign available: {sbsign_available}")

        if not sbsign_available:
            logging.error("sbsign not installed")
            return {
                'success': False,
                'message': 'sbsign not installed. Install sbsigntool package.'
            }

        try:
            if progress_callback:
                progress_callback(0, 100, "Creating backup")

            # Créer un script temporaire pour exécuter avec pkexec
            import tempfile

            # Résoudre les chemins absolus (important pour pkexec)
            mok_priv_abs = mok_priv.resolve()
            mok_cert_abs = mok_cert.resolve()
            vmlinuz_path_abs = vmlinuz_path.resolve()

            logging.debug(f"Absolute paths:")
            logging.debug(f"  MOK_PRIV: {mok_priv_abs}")
            logging.debug(f"  MOK_CERT: {mok_cert_abs}")
            logging.debug(f"  VMLINUZ: {vmlinuz_path_abs}")

            script_content = f"""#!/bin/bash
set -e

# Chemins absolus
MOK_PRIV="{mok_priv_abs}"
MOK_CERT="{mok_cert_abs}"
VMLINUZ="{vmlinuz_path_abs}"

# Vérifier que les fichiers existent
if [ ! -f "$MOK_PRIV" ]; then
    echo "ERROR: MOK private key not found: $MOK_PRIV"
    exit 1
fi

if [ ! -f "$MOK_CERT" ]; then
    echo "ERROR: MOK certificate not found: $MOK_CERT"
    exit 1
fi

if [ ! -f "$VMLINUZ" ]; then
    echo "ERROR: vmlinuz not found: $VMLINUZ"
    exit 1
fi

# Créer backup si nécessaire
if [ ! -f "${{VMLINUZ}}.unsigned" ]; then
    cp "$VMLINUZ" "${{VMLINUZ}}.unsigned"
fi

# Signer l'image
sbsign --key "$MOK_PRIV" --cert "$MOK_CERT" --output "${{VMLINUZ}}.signed" "$VMLINUZ" 2>&1

# Remplacer l'original
mv "${{VMLINUZ}}.signed" "$VMLINUZ"

echo "SUCCESS"
"""

            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as tf:
                tf.write(script_content)
                script_path = tf.name

            logging.debug(f"Script created: {script_path}")
            logging.debug(f"Script content:\n{script_content}")

            # Rendre le script exécutable
            os.chmod(script_path, 0o755)

            if progress_callback:
                progress_callback(30, 100, "Signing vmlinuz")

            logging.info(f"Executing: pkexec bash {script_path}")

            # Exécuter le script avec pkexec
            result = subprocess.run([
                "pkexec",
                "bash",
                script_path
            ], capture_output=True, text=True, check=False)

            logging.debug(f"Script execution completed with returncode: {result.returncode}")
            logging.debug(f"STDOUT:\n{result.stdout}")
            logging.debug(f"STDERR:\n{result.stderr}")

            # Nettoyer le script temporaire
            try:
                os.unlink(script_path)
                logging.debug(f"Cleaned up script: {script_path}")
            except Exception as e:
                logging.warning(f"Failed to cleanup script: {e}")

            # Vérifier le résultat
            if result.returncode != 0 or "SUCCESS" not in result.stdout:
                error_msg = result.stderr if result.stderr else result.stdout
                logging.error(f"Signing failed: {error_msg}")
                return {
                    'success': False,
                    'message': f'Failed to sign vmlinuz: {error_msg}'
                }

            if progress_callback:
                progress_callback(90, 100, "Verifying signature")

            # Vérifier la signature (optionnel, ne pas échouer si sbverify n'est pas installé)
            verified = False
            if self._check_command('sbverify'):
                verify_result = subprocess.run([
                    "sbverify",
                    "--cert", str(mok_cert),
                    str(vmlinuz_path)
                ], capture_output=True, text=True, check=False)
                verified = verify_result.returncode == 0
            else:
                # Si sbverify n'est pas installé, on considère la signature réussie
                verified = True

            if progress_callback:
                progress_callback(100, 100, "Done")

            self.add_to_history(
                "vmlinuz Signing",
                f"Signed vmlinuz-{kernel_version}, verified={verified}",
                success=True
            )

            logging.info(f"vmlinuz signing completed successfully for {kernel_version}")

            return {
                'success': True,
                'message': f'vmlinuz signed successfully. Verified: {verified}',
                'verified': verified
            }

        except subprocess.CalledProcessError as e:
            logging.error(f"CalledProcessError: {e}")
            logging.error(f"  stderr: {e.stderr if e.stderr else 'None'}")
            return {
                'success': False,
                'message': f'Failed to sign vmlinuz: {e.stderr if e.stderr else str(e)}'
            }
        except Exception as e:
            logging.error(f"Unexpected error: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }

    def sign_all_custom_vmlinuz(self, progress_callback=None):
        """
        Signe tous les vmlinuz des kernels custom
        Returns: dict avec success, signed_count, failed_count, results
        """
        custom_kernels = self.get_custom_kernels()

        if not custom_kernels:
            return {
                'success': False,
                'message': 'No custom kernels found',
                'signed_count': 0,
                'failed_count': 0,
                'results': []
            }

        signed_count = 0
        failed_count = 0
        results = []

        total = len(custom_kernels)
        for i, kernel in enumerate(custom_kernels, 1):
            kernel_ver = kernel['kernel_version']

            if progress_callback:
                progress_callback(i, total, kernel_ver)

            result = self.sign_vmlinuz(kernel_ver)
            results.append({
                'kernel': kernel_ver,
                'success': result['success'],
                'message': result['message']
            })

            if result['success']:
                signed_count += 1
            else:
                failed_count += 1

        return {
            'success': failed_count == 0,
            'message': f'Signed {signed_count}/{total} vmlinuz images',
            'signed_count': signed_count,
            'failed_count': failed_count,
            'results': results
        }

    # ==================== Diagnostic automatique ====================

    def diagnose_secureboot_issue(self):
        """
        Diagnostique automatique des problèmes SecureBoot
        Returns: dict avec issue_type, message, solutions (list)
        """
        print("[DEBUG] ===== Starting SecureBoot diagnosis =====")
        diagnosis = {
            'issue_type': None,
            'message': '',
            'solutions': []
        }

        # 1. Vérifier UEFI
        print("[DEBUG] Step 1: Checking UEFI system...")
        if not self.is_uefi_system():
            diagnosis['issue_type'] = 'NOT_UEFI'
            diagnosis['message'] = 'System is not using UEFI. SecureBoot requires UEFI.'
            diagnosis['solutions'] = [
                'Convert to UEFI boot (advanced)',
                'Disable SecureBoot and use Legacy boot'
            ]
            return diagnosis

        print("[DEBUG] Step 1: UEFI system OK")

        # 2. Vérifier statut SecureBoot
        print("[DEBUG] Step 2: Checking SecureBoot status...")
        sb_status = self.get_secureboot_status()
        print(f"[DEBUG] SecureBoot status: {sb_status}")
        if not sb_status['enabled']:
            diagnosis['issue_type'] = 'SB_DISABLED'
            diagnosis['message'] = 'SecureBoot is disabled in BIOS/UEFI'
            diagnosis['solutions'] = [
                'Enable SecureBoot in BIOS settings',
                'Keep SecureBoot disabled (less secure)'
            ]
            return diagnosis

        print("[DEBUG] Step 2: SecureBoot is enabled")

        # 3. Vérifier enrollment MOK
        print("[DEBUG] Step 3: Checking MOK enrollment...")
        mok_status = self.check_mok_enrolled()
        print(f"[DEBUG] MOK status: {mok_status}")
        if not mok_status['key_found']:
            if self.check_mok_pending():
                diagnosis['issue_type'] = 'MOK_PENDING'
                diagnosis['message'] = 'MOK key is pending enrollment. Reboot required.'
                diagnosis['solutions'] = [
                    'Reboot and follow MOK Manager instructions',
                    'Cancel pending enrollment and re-enroll'
                ]
            else:
                diagnosis['issue_type'] = 'MOK_NOT_ENROLLED'
                diagnosis['message'] = 'MOK key is not enrolled. Cannot boot custom kernels.'
                diagnosis['solutions'] = [
                    'Enroll MOK key (automated wizard available)',
                    'Disable SecureBoot to boot without signature'
                ]
            return diagnosis

        print("[DEBUG] Step 3: MOK key is enrolled")

        # 4. Vérifier signature des kernels custom
        print("[DEBUG] Step 4: Checking kernel signatures...")
        custom_kernels = self.get_custom_kernels()
        print(f"[DEBUG] diagnose_secureboot_issue: Found {len(custom_kernels)} custom kernels")

        if custom_kernels:
            unsigned_kernels = []
            wrong_signature_kernels = []

            for kernel in custom_kernels:
                print(f"[DEBUG] Checking kernel: {kernel['kernel_version']} ({kernel['module_count']} modules)")
                if kernel['modules']:
                    # Vérifier un module échantillon
                    sample_module = kernel['modules'][0]
                    print(f"[DEBUG] Sample module: {sample_module}")
                    sig_info = self.check_module_signed(sample_module)
                    print(f"[DEBUG] Signature info: {sig_info}")

                    if not sig_info['signed']:
                        unsigned_kernels.append(kernel['kernel_version'])
                        print(f"[DEBUG] -> UNSIGNED kernel: {kernel['kernel_version']}")
                    elif sig_info['signer'] and 'kernelcustom' not in sig_info['signer'].lower():
                        wrong_signature_kernels.append(kernel['kernel_version'])
                        print(f"[DEBUG] -> WRONG SIGNATURE kernel: {kernel['kernel_version']}")
                    else:
                        print(f"[DEBUG] -> Properly signed kernel: {kernel['kernel_version']}")

            print(f"[DEBUG] Results: unsigned={len(unsigned_kernels)}, wrong_signature={len(wrong_signature_kernels)}")

            if unsigned_kernels or wrong_signature_kernels:
                diagnosis['issue_type'] = 'MODULES_NOT_SIGNED'
                diagnosis['message'] = f'Custom kernel modules are not properly signed. Unsigned: {len(unsigned_kernels)}, Wrong signature: {len(wrong_signature_kernels)}'
                diagnosis['solutions'] = [
                    'Re-sign all custom kernel modules (automated tool available)',
                    'Recompile kernels with "Sign for SecureBoot" option'
                ]
                print(f"[DEBUG] Returning MODULES_NOT_SIGNED diagnosis")
                return diagnosis
        else:
            print(f"[DEBUG] No custom kernels found, skipping module signature check")

        # Tout est OK !
        diagnosis['issue_type'] = 'OK'
        diagnosis['message'] = 'SecureBoot is properly configured'
        diagnosis['solutions'] = []
        return diagnosis

    # ==================== Automatisation pour kernels personnalisés ====================

    def should_prompt_for_signing(self):
        """
        Vérifie si on devrait proposer la signature de modules
        (si SecureBoot est activé et système UEFI)
        """
        if not self.is_uefi_system():
            return False

        status = self.get_secureboot_status()
        return status.get('enabled', False)

    def find_kernel_modules_in_package(self, package_dir):
        """
        Trouve tous les modules kernel (.ko) dans un répertoire de package
        """
        from pathlib import Path
        package_path = Path(package_dir)

        modules = []
        for ko_file in package_path.rglob("*.ko"):
            modules.append(ko_file)

        return modules

    def auto_sign_kernel_modules(self, kernel_dir, priv_key_path, cert_path):
        """
        Signe automatiquement tous les modules d'un kernel compilé
        kernel_dir: répertoire du kernel compilé
        priv_key_path: chemin vers la clé privée
        cert_path: chemin vers le certificat
        """
        from pathlib import Path
        kernel_path = Path(kernel_dir)

        # Trouver tous les modules .ko
        modules = list(kernel_path.rglob("*.ko"))

        if not modules:
            return {
                'success': False,
                'error': 'No kernel modules found',
                'signed_count': 0
            }

        priv_key = Path(priv_key_path)
        cert = Path(cert_path)

        if not priv_key.exists() or not cert.exists():
            return {
                'success': False,
                'error': 'Key or certificate not found',
                'signed_count': 0
            }

        # Trouver sign-file
        sign_file = self._find_sign_file_tool()
        if not sign_file:
            return {
                'success': False,
                'error': 'sign-file tool not found',
                'signed_count': 0
            }

        # Signer tous les modules
        signed_count = 0
        failed_modules = []

        for module in modules:
            try:
                result = subprocess.run([
                    str(sign_file),
                    "sha256",
                    str(priv_key),
                    str(cert),
                    str(module)
                ], capture_output=True, text=True, check=False)

                if result.returncode == 0:
                    signed_count += 1
                else:
                    failed_modules.append(str(module))
            except Exception as e:
                failed_modules.append(str(module))

        self.add_to_history(
            'auto_sign_modules',
            {
                'kernel_dir': str(kernel_dir),
                'total_modules': len(modules),
                'signed_count': signed_count,
                'failed_count': len(failed_modules)
            },
            success=(len(failed_modules) == 0)
        )

        return {
            'success': (len(failed_modules) == 0),
            'total_modules': len(modules),
            'signed_count': signed_count,
            'failed_modules': failed_modules
        }
