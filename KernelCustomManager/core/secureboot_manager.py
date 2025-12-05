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

    # ==================== Gestion des clés MOK ====================

    def list_enrolled_keys(self):
        """Liste les clés MOK enrollées"""
        try:
            result = subprocess.run(
                ["mokutil", "--list-enrolled"],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                keys = self._parse_mok_list(result.stdout)
                return {'success': True, 'keys': keys, 'raw_output': result.stdout}
            else:
                return {'success': False, 'error': result.stderr, 'keys': []}
        except FileNotFoundError:
            return {'success': False, 'error': 'mokutil is not installed', 'keys': []}

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
            result = subprocess.run(
                ["mokutil", "--list-new"],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                if "MokNew is empty" in result.stdout:
                    return {'success': True, 'keys': [], 'message': 'No pending keys'}
                else:
                    keys = self._parse_mok_list(result.stdout)
                    return {'success': True, 'keys': keys, 'raw_output': result.stdout}
            else:
                return {'success': False, 'error': result.stderr, 'keys': []}
        except FileNotFoundError:
            return {'success': False, 'error': 'mokutil is not installed', 'keys': []}

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
                ["mokutil", "--import", str(key_path)],
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
                ["mokutil", "--delete", str(key_path)],
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
                ["mokutil", "--reset"],
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
        possible_locations = [
            Path("/usr/src/linux-headers-" + os.uname().release) / "scripts" / "sign-file",
            Path("/usr/lib/linux-kbuild-" + os.uname().release.split('-')[0]) / "scripts" / "sign-file",
            Path("/lib/modules") / os.uname().release / "build" / "scripts" / "sign-file"
        ]

        for location in possible_locations:
            if location.exists():
                return location

        # Chercher avec which
        try:
            result = subprocess.run(
                ["which", "sign-file"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                return Path(result.stdout.strip())
        except:
            pass

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
            'sign-file': self._find_sign_file_tool() is not None
        }

        all_installed = all(deps.values())

        return {
            'all_installed': all_installed,
            'dependencies': deps,
            'missing': [name for name, installed in deps.items() if not installed]
        }

    def _check_command(self, command):
        """Vérifie si une commande est disponible"""
        try:
            subprocess.run(
                ["which", command],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_system_info(self):
        """Récupère les informations système pertinentes pour SecureBoot"""
        info = {
            'is_uefi': self.is_uefi_system(),
            'secureboot_status': self.get_secureboot_status(),
            'setup_mode': self.check_setup_mode() if self.is_uefi_system() else False,
            'dependencies': self.check_dependencies()
        }

        return info

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
