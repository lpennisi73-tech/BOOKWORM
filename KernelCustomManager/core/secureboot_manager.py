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

from utils import paths
from utils.pkexec_helper import PkexecHelper
from utils.i18n import get_i18n

# Le logging est configuré par le point d'entrée (kernelcustom_manager.py)


class SecureBootManager:
    """Classe principale pour gérer SecureBoot"""

    def __init__(self, base_dir=None):
        if base_dir is None:
            self.base_dir = paths.data_dir()
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

        # Initialiser i18n
        self.i18n = get_i18n()

    def clear_mok_cache(self):
        """Vide le cache MOK pour forcer une nouvelle lecture"""
        with self._mok_cache_lock:
            self._mok_cache = None
            logging.debug("Cache MOK vidé")

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
        # Vérifier le cache sans lock d'abord (optimisation)
        if self._mok_cache is not None:
            return self._mok_cache

        # Utiliser un lock pour éviter les appels parallèles
        with self._mok_cache_lock:
            # Re-vérifier le cache après avoir acquis le lock
            # (un autre thread a pu le remplir pendant qu'on attendait le lock)
            if self._mok_cache is not None:
                return self._mok_cache

            logging.debug("_fetch_mok_data: appel du helper (mokutil-diagnose)")

            try:
                success, output, error = PkexecHelper.mokutil_diagnose()

                if not success:
                    # Échec (mot de passe refusé, helper absent…) mis en cache aussi : sinon
                    # chaque vérification du diagnostic redemanderait le mot de passe.
                    # Le bouton « Lancer le diagnostic » vide le cache pour réessayer.
                    logging.warning(f"mokutil-diagnose: {error}")
                    self._mok_cache = {'enrolled_output': '', 'pending_output': '',
                                       'efi_shim': None, 'efi_mok_manager': None,
                                       'error': error}
                    return self._mok_cache

                # Sortie du helper :
                #   EFI_SHIM:<chemin>  EFI_MOKMANAGER:<chemin>  ENROLLED: ...  PENDING: ...
                sections = {'ENROLLED': [], 'PENDING': []}
                efi = {}
                current = None
                for line in output.splitlines():
                    if line.startswith(('EFI_SHIM:', 'EFI_MOKMANAGER:')):
                        key, _, value = line.partition(':')
                        efi[key] = value.strip() or None
                    elif line.strip() in ('ENROLLED:', 'PENDING:'):
                        current = line.strip()[:-1]
                    elif current:
                        sections[current].append(line)

                self._mok_cache = {
                    'enrolled_output': '\n'.join(sections['ENROLLED']).strip(),
                    'pending_output': '\n'.join(sections['PENDING']).strip(),
                    'efi_shim': efi.get('EFI_SHIM'),
                    'efi_mok_manager': efi.get('EFI_MOKMANAGER'),
                }

                return self._mok_cache
            except Exception:
                return {'enrolled_output': '', 'pending_output': '',
                        'efi_shim': None, 'efi_mok_manager': None}

    def _get_local_cert_fingerprint(self):
        """
        Extrait le fingerprint SHA1 du certificat MOK local
        Returns: str (fingerprint format XX:XX:XX:...) ou None si erreur
        """
        mok_cert = self.keys_dir / "MOK.der"

        if not mok_cert.exists():
            return None

        try:
            result = subprocess.run(
                ["openssl", "x509", "-in", str(mok_cert), "-inform", "DER", "-noout", "-fingerprint", "-sha1"],
                capture_output=True, text=True, check=True
            )
            # Output format: "SHA1 Fingerprint=XX:XX:XX:..."
            fingerprint_line = result.stdout.strip()
            if "=" in fingerprint_line:
                fingerprint = fingerprint_line.split("=", 1)[1].strip()
                return fingerprint.lower()  # Normaliser en minuscules
            return None
        except:
            return None

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

            # Méthode 1 : Comparer les fingerprints (le plus fiable)
            local_fingerprint = self._get_local_cert_fingerprint()
            if local_fingerprint:
                # Parser la sortie pour trouver le certificat avec le bon fingerprint
                lines = output.split('\n')
                current_cert_cn = None
                current_cert_fingerprint = None

                for i, line in enumerate(lines):
                    # Détecter une nouvelle clé
                    if line.strip().startswith('[key '):
                        current_cert_cn = None
                        current_cert_fingerprint = None

                    # Capturer le fingerprint
                    if 'SHA1 Fingerprint:' in line:
                        fp = line.split('SHA1 Fingerprint:')[1].strip().lower()
                        current_cert_fingerprint = fp

                    # Capturer le CN
                    if 'Subject:' in line and 'CN=' in line:
                        cn_part = line.split('CN=')[1].split(',')[0].split('/')[0].strip()
                        current_cert_cn = cn_part

                    # Vérifier si c'est notre certificat
                    if current_cert_fingerprint and current_cert_fingerprint == local_fingerprint:
                        return {
                            'status': 'enrolled',
                            'key_found': True,
                            'cn_name': current_cert_cn,
                            'message': f'MOK key is already enrolled (CN={current_cert_cn})',
                            'fingerprint': local_fingerprint
                        }

            # Méthode 2 : Fallback sur la recherche par nom (rétrocompatibilité)
            # Utile si le certificat local n'existe pas encore
            output_lower = output.lower()
            if "kernelcustom" in output_lower or "keernelcustom" in output_lower or "kernel custom" in output_lower:
                return {
                    'status': 'enrolled',
                    'key_found': True,
                    'cn_name': 'kernelcustom',
                    'message': 'MOK key is already enrolled (detected by name)'
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

    def check_efi_boot_files(self):
        """
        Présence de shim et de MOK Manager (mmx64.efi) sur la partition EFI
        (lue par le helper : la partition EFI n'est lisible que par root sur Debian)
        Returns: dict avec checked (bool), shim (str|None), mok_manager (str|None)
        """
        mok_data = self._fetch_mok_data()
        checked = 'efi_shim' in mok_data and (mok_data['efi_shim'] or mok_data['efi_mok_manager']
                                               or mok_data['enrolled_output'] or mok_data['pending_output'])
        return {
            'checked': bool(checked),
            'shim': mok_data.get('efi_shim'),
            'mok_manager': mok_data.get('efi_mok_manager'),
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
            # Importer la clé via le helper (le mot de passe temporaire est transmis sur stdin)
            success, _, error_msg = PkexecHelper.mokutil_import(mok_key, password=password)

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
                return {'success': False, 'error': mok_data.get('error') or 'Unable to fetch MOK data', 'keys': []}
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
            success, stdout, error = PkexecHelper.mokutil_import(key_path)

            if success:
                self.add_to_history(
                    'import_key',
                    {'key_file': str(key_path), 'output': stdout},
                    success=True
                )
                return {
                    'success': True,
                    'message': 'Key import initiated. Reboot required to complete enrollment.',
                    'output': stdout
                }
            else:
                return {'success': False, 'error': error}
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
            success, stdout, error = PkexecHelper.mokutil_delete(key_path)

            if success:
                self.add_to_history(
                    'delete_key',
                    {'key_file': str(key_path), 'output': stdout},
                    success=True
                )
                return {
                    'success': True,
                    'message': 'Key deletion initiated. Reboot required to complete.',
                    'output': stdout
                }
            else:
                return {'success': False, 'error': error}
        except FileNotFoundError:
            return {'success': False, 'error': 'mokutil is not installed'}

    def reset_mok_keys(self):
        """Réinitialise toutes les clés MOK"""
        try:
            success, stdout, error = PkexecHelper.mokutil_reset()

            if success:
                self.add_to_history('reset_keys', {'output': stdout}, success=True)
                return {
                    'success': True,
                    'message': 'MOK reset initiated. Reboot required.',
                    'output': stdout
                }
            else:
                return {'success': False, 'error': error}
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
            # Headers du kernel courant
            Path("/usr/src/linux-headers-" + kernel_version) / "scripts" / "sign-file",
            # Debian - linux-kbuild-X.Y
            Path("/usr/lib/linux-kbuild-" + kernel_major_minor) / "scripts" / "sign-file",
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

    def get_distribution_info(self):
        """
        Informations sur la distribution (l'application cible uniquement Debian)
        Returns: dict avec 'id', 'version', 'is_debian'
        Note: sur testing/sid, VERSION_ID est absent de /etc/os-release,
        on utilise alors /etc/debian_version (ex: "forky/sid")
        """
        info = {'id': 'unknown', 'version': '', 'is_debian': False}
        try:
            os_release = platform.freedesktop_os_release()
            info['id'] = os_release.get('ID', 'unknown').lower()
            info['version'] = os_release.get('VERSION_ID', '')
        except OSError as e:
            logging.warning(f"Failed to read os-release: {e}")

        if not info['version']:
            try:
                info['version'] = Path('/etc/debian_version').read_text().strip()
            except OSError:
                pass

        info['is_debian'] = info['id'] == 'debian'
        return info

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

        # Patterns des kernels officiels Debian à exclure
        # Ces kernels sont déjà signés par les distributeurs
        stock_patterns = [
            r'-amd64$',           # Debian: 6.8.12-amd64
            r'-686$',             # Debian 32-bit: 6.8.12-686
            r'-686-pae$',         # Debian 32-bit PAE: 6.8.12-686-pae
            r'-cloud-amd64$',     # Debian cloud: 6.8.12-cloud-amd64
            r'-rt-amd64$',        # Debian realtime: 6.8.12-rt-amd64
        ]

        import re

        for kernel_dir in modules_dir.iterdir():
            if not kernel_dir.is_dir():
                continue

            kernel_name = kernel_dir.name

            # Vérifier si c'est un kernel stock (officiel)
            is_stock = False
            for pattern in stock_patterns:
                if re.search(pattern, kernel_name):
                    is_stock = True
                    break

            # Si c'est un kernel stock, on l'ignore
            if is_stock:
                continue

            # Sinon, c'est un kernel personnalisé
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
        Vérifie si un module est signé.
        modinfo (libkmod) lit directement les modules compressés (.xz/.gz/.zst)
        et ne nécessite pas les droits root.
        Returns: dict avec signed (bool), signer (str), sig_id (str)
        """
        not_signed = {'signed': False, 'signer': None, 'sig_id': None}
        try:
            fields = {}
            for field in ('sig_id', 'signer'):
                result = subprocess.run(
                    ['modinfo', '-F', field, str(module_path)],
                    capture_output=True, text=True, check=False
                )
                if result.returncode != 0:
                    return not_signed
                fields[field] = result.stdout.strip()
        except FileNotFoundError:
            return not_signed

        if not fields['sig_id']:
            return not_signed
        return {'signed': True, 'signer': fields['signer'] or None, 'sig_id': fields['sig_id']}

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
            if any(suffix in vmlinuz_file.name for suffix in ['.old', '.bak', '.signed']):
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

    def _check_kernel_modules_signature_stats(self, kernel_version, sample_size=20):
        """
        Vérifie un échantillon statistique de modules pour détecter s'ils sont signés
        Returns: dict avec signed_count, unsigned_count, total_checked, is_signed (bool)
        """
        import random

        kernel_dir = Path(f"/lib/modules/{kernel_version}")
        if not kernel_dir.exists():
            return {'signed_count': 0, 'unsigned_count': 0, 'total_checked': 0, 'is_signed': False}

        # Trouver tous les modules
        modules = []
        for ext in ['*.ko', '*.ko.xz', '*.ko.gz', '*.ko.zst']:
            modules.extend(kernel_dir.rglob(ext))

        if not modules:
            return {'signed_count': 0, 'unsigned_count': 0, 'total_checked': 0, 'is_signed': False}

        # Prendre un échantillon aléatoire
        sample = random.sample(modules, min(sample_size, len(modules)))

        signed_count = 0
        unsigned_count = 0

        for module in sample:
            sig_info = self.check_module_signed(str(module))
            if sig_info['signed']:
                signed_count += 1
            else:
                unsigned_count += 1

        total_checked = len(sample)
        # Considérer comme signé si au moins 95% des modules sont signés
        is_signed = (signed_count / total_checked) >= 0.95 if total_checked > 0 else False

        return {
            'signed_count': signed_count,
            'unsigned_count': unsigned_count,
            'total_checked': total_checked,
            'is_signed': is_signed,
            'total_modules': len(modules)
        }

    def _check_initrd_modules_signed(self, kernel_version):
        """
        Vérifie si l'initrd contient des modules signés
        Returns: dict avec success, initrd_ok, message
        """
        import tempfile
        import subprocess

        initrd_path = Path(f"/boot/initrd.img-{kernel_version}")
        if not initrd_path.exists():
            return {
                'success': False,
                'initrd_ok': None,
                'message': f'Initrd not found: {initrd_path}'
            }

        try:
            # Créer un répertoire temporaire
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)

                # Extraire l'initrd
                # unmkinitramfs extrait l'initrd dans un répertoire
                result = subprocess.run(
                    ['unmkinitramfs', str(initrd_path), str(tmpdir_path)],
                    capture_output=True,
                    text=True,
                    check=False
                )

                if result.returncode != 0:
                    # Si unmkinitramfs échoue, essayer avec cpio
                    zcat = subprocess.Popen(['zcat', str(initrd_path)], stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL)
                    cpio = subprocess.run(['cpio', '-id'], stdin=zcat.stdout, cwd=tmpdir_path,
                                          capture_output=True, check=False)
                    zcat.stdout.close()
                    zcat.wait()
                    if cpio.returncode != 0 or zcat.returncode != 0:
                        return {
                            'success': False,
                            'initrd_ok': None,
                            'message': 'Failed to extract initrd'
                        }

                # Chercher des modules dans l'initrd
                modules_in_initrd = []
                for ext in ['*.ko', '*.ko.xz', '*.ko.gz', '*.ko.zst']:
                    modules_in_initrd.extend(tmpdir_path.rglob(ext))

                if not modules_in_initrd:
                    # Pas de modules dans l'initrd - c'est OK (certains kernels n'en ont pas)
                    return {
                        'success': True,
                        'initrd_ok': True,
                        'message': 'No modules in initrd (OK)'
                    }

                # Vérifier un échantillon de modules dans l'initrd
                import random
                sample = random.sample(modules_in_initrd, min(10, len(modules_in_initrd)))

                signed_count = 0
                for module in sample:
                    # modinfo lit directement les modules compressés (.xz/.zst)
                    if self.check_module_signed(str(module))['signed']:
                        signed_count += 1

                # Si moins de 50% des modules sont signés, l'initrd a un problème
                initrd_ok = (signed_count / len(sample)) >= 0.5 if len(sample) > 0 else False

                return {
                    'success': True,
                    'initrd_ok': initrd_ok,
                    'message': f'Initrd modules checked: {signed_count}/{len(sample)} signed',
                    'modules_count': len(modules_in_initrd),
                    'signed_count': signed_count,
                    'checked_count': len(sample)
                }

        except Exception as e:
            return {
                'success': False,
                'initrd_ok': None,
                'message': f'Error checking initrd: {str(e)}'
            }

    def _check_vmlinuz_signed(self, kernel_version):
        """
        Vérifie si vmlinuz est signé
        Returns: dict avec success, is_signed, message
        """
        vmlinuz_path = self._find_vmlinuz_for_kernel(kernel_version)

        if not vmlinuz_path:
            return {
                'success': False,
                'is_signed': None,
                'message': f'vmlinuz not found for {kernel_version}'
            }

        # Vérifier si sbverify est disponible
        if not self._check_command('sbverify'):
            return {
                'success': False,
                'is_signed': None,
                'message': 'sbverify not installed, cannot verify vmlinuz signature'
            }

        # Vérifier avec la clé MOK
        mok_cert = self.keys_dir / "MOK.pem"
        if not mok_cert.exists():
            return {
                'success': False,
                'is_signed': None,
                'message': 'MOK certificate not found'
            }

        try:
            result = subprocess.run(
                ['sbverify', '--cert', str(mok_cert), str(vmlinuz_path)],
                capture_output=True,
                text=True,
                check=False
            )

            # sbverify peut retourner returncode=0 avec des warnings dans stderr
            # Il faut vérifier "Signature verification OK" dans stdout
            is_signed = (result.returncode == 0) and ("Signature verification OK" in result.stdout or "Signature verification OK" in result.stderr)

            return {
                'success': True,
                'is_signed': is_signed,
                'message': 'Signed' if is_signed else 'Not signed',
                'vmlinuz_path': str(vmlinuz_path)
            }
        except Exception as e:
            return {
                'success': False,
                'is_signed': None,
                'message': f'Error verifying vmlinuz: {str(e)}'
            }

    def diagnose_secureboot_issue(self):
        """
        Diagnostique automatique des problèmes SecureBoot (VERSION AMÉLIORÉE)
        Vérifie de manière fiable les modules, l'initrd et vmlinuz
        Returns: dict avec issue_type, message, solutions (list), details (dict)
        """
        logging.info("===== Starting SecureBoot diagnosis (improved) =====")
        diagnosis = {
            'issue_type': None,
            'message': '',
            'solutions': [],
            'details': {}
        }

        # 1. Vérifier UEFI
        logging.debug("Step 1: Checking UEFI system...")
        if not self.is_uefi_system():
            diagnosis['issue_type'] = 'NOT_UEFI'
            diagnosis['message'] = self.i18n._('secureboot.diag.not_uefi')
            diagnosis['solutions'] = [
                self.i18n._('secureboot.diag.sol_convert_uefi'),
                self.i18n._('secureboot.diag.sol_disable_sb_legacy')
            ]
            return diagnosis

        logging.debug("Step 1: UEFI system OK")

        # 2. Vérifier statut SecureBoot
        logging.debug("Step 2: Checking SecureBoot status...")
        sb_status = self.get_secureboot_status()
        logging.debug(f"SecureBoot status: {sb_status}")
        if not sb_status['enabled']:
            diagnosis['issue_type'] = 'SB_DISABLED'
            diagnosis['message'] = self.i18n._('secureboot.diag.sb_disabled')
            diagnosis['solutions'] = [
                self.i18n._('secureboot.diag.sol_enable_sb'),
                self.i18n._('secureboot.diag.sol_keep_sb_disabled')
            ]
            return diagnosis

        logging.debug("Step 2: SecureBoot is enabled")

        # 3. Vérifier enrollment MOK
        logging.debug("Step 3: Checking MOK enrollment...")
        mok_status = self.check_mok_enrolled()
        logging.debug(f"MOK status: {mok_status}")
        if not mok_status['key_found']:
            if self.check_mok_pending():
                diagnosis['issue_type'] = 'MOK_PENDING'
                diagnosis['message'] = self.i18n._('secureboot.diag.mok_pending')
                diagnosis['solutions'] = [
                    self.i18n._('secureboot.diag.sol_reboot_mok'),
                    self.i18n._('secureboot.diag.sol_cancel_reenroll')
                ]
                # Sans mmx64.efi, l'écran MOK Manager ne s'affichera jamais au démarrage
                efi = self.check_efi_boot_files()
                diagnosis['details']['efi'] = efi
                if efi['checked'] and not efi['mok_manager']:
                    diagnosis['message'] += '\n\n' + self.i18n._('secureboot.diag.mok_manager_missing')
                    diagnosis['solutions'].insert(0, self.i18n._('secureboot.diag.sol_reinstall_shim'))
            else:
                diagnosis['issue_type'] = 'MOK_NOT_ENROLLED'
                diagnosis['message'] = self.i18n._('secureboot.diag.mok_not_enrolled')
                diagnosis['solutions'] = [
                    self.i18n._('secureboot.diag.sol_enroll_mok'),
                    self.i18n._('secureboot.diag.sol_disable_sb')
                ]
            return diagnosis

        logging.debug("Step 3: MOK key is enrolled")

        # 4. Vérifier signature des kernels custom (VERSION AMÉLIORÉE)
        logging.debug("Step 4: Checking custom kernel signatures (improved method)...")
        custom_kernels = self.get_custom_kernels()

        if custom_kernels:
            kernels_with_issues = []

            for kernel in custom_kernels:
                kernel_ver = kernel['kernel_version']
                logging.debug(f"Checking kernel: {kernel_ver}")

                kernel_issues = []

                # 4a. Vérifier les modules dans /lib/modules/ (échantillon statistique)
                modules_stats = self._check_kernel_modules_signature_stats(kernel_ver)
                logging.debug(f"  Modules stats: {modules_stats}")

                if not modules_stats['is_signed'] and modules_stats['total_modules'] > 0:
                    kernel_issues.append({
                        'type': 'MODULES_UNSIGNED',
                        'message': self.i18n._('secureboot.diag.modules_not_signed').format(
                            signed=modules_stats['signed_count'],
                            total=modules_stats['total_checked']
                        ),
                        'details': modules_stats
                    })

                # 4b. Vérifier l'initrd (optionnel - ne bloque pas si échec d'extraction)
                initrd_check = self._check_initrd_modules_signed(kernel_ver)
                logging.debug(f"  Initrd check: {initrd_check}")

                # Seulement signaler un problème si l'extraction a réussi ET que les modules ne sont pas signés
                if initrd_check['success'] and not initrd_check['initrd_ok'] and initrd_check.get('modules_count', 0) > 0:
                    kernel_issues.append({
                        'type': 'INITRD_UNSIGNED_MODULES',
                        'message': self.i18n._('secureboot.diag.initrd_unsigned_modules').format(
                            signed=initrd_check.get('signed_count', 0),
                            total=initrd_check.get('checked_count', 0)
                        ),
                        'details': initrd_check
                    })
                elif not initrd_check['success']:
                    # L'extraction a échoué - juste logger, ne pas bloquer
                    logging.warning(f"  Initrd verification skipped: {initrd_check['message']}")

                # 4c. Vérifier vmlinuz (si architecture supportée)
                if self._is_vmlinuz_signing_supported():
                    vmlinuz_check = self._check_vmlinuz_signed(kernel_ver)
                    logging.debug(f"  vmlinuz check: {vmlinuz_check}")

                    if vmlinuz_check['success'] and not vmlinuz_check['is_signed']:
                        kernel_issues.append({
                            'type': 'VMLINUZ_UNSIGNED',
                            'message': self.i18n._('secureboot.diag.vmlinuz_not_signed'),
                            'details': vmlinuz_check
                        })

                if kernel_issues:
                    kernels_with_issues.append({
                        'kernel_version': kernel_ver,
                        'issues': kernel_issues
                    })

            # Si des problèmes ont été détectés
            if kernels_with_issues:
                diagnosis['issue_type'] = 'KERNEL_SIGNATURE_ISSUES'
                diagnosis['details'] = {'kernels': kernels_with_issues}

                # Message détaillé
                messages = []
                for k in kernels_with_issues:
                    messages.append(f"Kernel {k['kernel_version']}:")
                    for issue in k['issues']:
                        messages.append(f"  - {issue['message']}")

                diagnosis['message'] = '\n'.join(messages)

                # Solutions
                diagnosis['solutions'] = [
                    self.i18n._('secureboot.diag.sol_sign_modules'),
                    self.i18n._('secureboot.diag.sol_regenerate_initrd'),
                    self.i18n._('secureboot.diag.sol_verify_sb_config')
                ]

                return diagnosis

        # Tout est OK !
        logging.info("Step 4: All kernels properly signed")
        diagnosis['issue_type'] = 'OK'
        diagnosis['message'] = self.i18n._('secureboot.diag.all_ok')
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

    def sign_kernel_complete(self, kernel_version, sign_vmlinuz_flag=True, progress_callback=None):
        """
        Signe les modules ET vmlinuz d'un kernel en un seul appel au helper privilégié
        (évite de redemander le mot de passe entre les deux étapes)

        Args:
            kernel_version: Version du kernel
            sign_vmlinuz_flag: Si True, signe aussi vmlinuz
            progress_callback: Fonction appelée pour suivre le progrès (current, total, module_name)

        Returns: dict avec success, message, modules_signed, modules_failed, vmlinuz_signed
        """
        logging.info(f"=== Complete signing for kernel {kernel_version} (vmlinuz={sign_vmlinuz_flag}) ===")

        mok_priv = self.keys_dir / "MOK.priv"
        mok_cert_der = self.keys_dir / "MOK.der"
        mok_cert_pem = self.keys_dir / "MOK.pem"

        if not mok_priv.exists() or not mok_cert_der.exists():
            return {
                'success': False,
                'message': 'MOK keys not found',
                'modules_signed': 0,
                'modules_failed': 0,
                'vmlinuz_signed': False
            }

        # Trouver sign-file
        sign_file = self._find_sign_file_tool()
        if not sign_file:
            return {
                'success': False,
                'message': 'sign-file tool not found',
                'modules_signed': 0,
                'modules_failed': 0,
                'vmlinuz_signed': False
            }

        # Trouver les modules
        kernel_dir = Path(f"/lib/modules/{kernel_version}")
        if not kernel_dir.exists():
            return {
                'success': False,
                'message': f'Kernel directory not found: {kernel_dir}',
                'modules_signed': 0,
                'modules_failed': 0,
                'vmlinuz_signed': False
            }

        # Trouver vmlinuz si nécessaire
        vmlinuz_path = None
        if sign_vmlinuz_flag:
            # Vérifier si architecture supporte vmlinuz signing
            if not self._is_vmlinuz_signing_supported():
                logging.warning(f"vmlinuz signing not supported on {platform.machine()}")
                sign_vmlinuz_flag = False
            else:
                vmlinuz_path = self._find_vmlinuz_for_kernel(kernel_version)
                if not vmlinuz_path:
                    logging.warning(f"vmlinuz not found for {kernel_version}, skipping vmlinuz signing")
                    sign_vmlinuz_flag = False
                elif not self._check_command('sbsign'):
                    logging.warning("sbsign not installed, skipping vmlinuz signing")
                    sign_vmlinuz_flag = False

        # Compter les modules
        modules = []
        for ext in ['*.ko', '*.ko.xz', '*.ko.gz', '*.ko.zst']:
            modules.extend(kernel_dir.rglob(ext))
        total_modules = len(modules)
        logging.info(f"Found {total_modules} modules to sign")

        # Une seule action du helper : modules + vmlinuz + initrd (un seul mot de passe)
        args = [
            kernel_version,
            "--sign-file", sign_file,
            "--key", mok_priv.resolve(),
            "--cert-der", mok_cert_der.resolve(),
        ]
        if sign_vmlinuz_flag and vmlinuz_path:
            args += ["--cert-pem", mok_cert_pem.resolve(), "--vmlinuz", vmlinuz_path.resolve()]

        modules_signed = 0
        modules_failed = 0
        vmlinuz_signed = False
        initrd_updated = False

        def on_line(line):
            nonlocal modules_signed, modules_failed, vmlinuz_signed, initrd_updated
            if line.startswith('PROGRESS_MODULE:'):
                parts = line.split(':', 3)
                if progress_callback:
                    progress_callback(int(parts[1]), int(parts[2]), parts[3] if len(parts) > 3 else "")
            elif line.startswith('PROGRESS_VMLINUZ:'):
                if progress_callback:
                    progress_callback(total_modules, total_modules, "vmlinuz")
            elif line.startswith('PROGRESS_INITRD:'):
                if progress_callback:
                    progress_callback(total_modules, total_modules, "initrd")
            elif line.startswith('MODULES_SIGNED:'):
                modules_signed = int(line.split(':')[1])
            elif line.startswith('MODULES_FAILED:'):
                modules_failed = int(line.split(':')[1])
            elif line.startswith('VMLINUZ_SIGNED:'):
                vmlinuz_signed = line.split(':')[1] == '1'
            elif line.startswith('INITRD_UPDATED:'):
                initrd_updated = line.split(':')[1] == '1'
            else:
                logging.debug(f"helper: {line}")

        logging.info("Executing unified signing via helper (one password prompt only)...")
        helper_ok, _, helper_error = PkexecHelper.stream("sign-kernel", *args, on_line=on_line)
        if not helper_ok:
            logging.error(f"sign-kernel failed: {helper_error}")
            if modules_signed == 0 and modules_failed == 0:
                return {
                    'success': False,
                    'message': helper_error,
                    'modules_signed': 0,
                    'modules_failed': total_modules,
                    'vmlinuz_signed': False,
                    'initrd_updated': False
                }

        success = (modules_failed == 0) and (not sign_vmlinuz_flag or vmlinuz_signed) and initrd_updated

        logging.info(f"Complete signing finished: modules={modules_signed}/{total_modules}, vmlinuz={vmlinuz_signed}, initrd={initrd_updated}")

        self.add_to_history(
            "Complete Kernel Signing",
            f"Kernel {kernel_version}: {modules_signed} modules signed, vmlinuz={'✅' if vmlinuz_signed else '❌'}, initrd={'✅' if initrd_updated else '❌'}",
            success=success
        )

        message = f'Signed {modules_signed}/{total_modules} modules'
        if sign_vmlinuz_flag:
            message += f', vmlinuz: {"✅" if vmlinuz_signed else "❌"}'
        message += f', initrd: {"✅ regenerated" if initrd_updated else "❌ failed"}'

        return {
            'success': success,
            'message': message,
            'modules_signed': modules_signed,
            'modules_failed': modules_failed,
            'vmlinuz_signed': vmlinuz_signed,
            'initrd_updated': initrd_updated
        }
