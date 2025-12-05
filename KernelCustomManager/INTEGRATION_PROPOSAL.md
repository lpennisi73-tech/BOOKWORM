# 🔄 Proposition d'Intégration - Workflow MOK Automatisé

## 📊 État Actuel

### ✅ Ce qui existe déjà
- Interface SecureBoot avec 4 onglets (Statut, Clés, Signature, Historique)
- `SecureBootManager` class avec logique de base
- Détection UEFI et statut SecureBoot
- Génération de clés MOK
- Signature de modules kernel

### ❌ Ce qui manque (cause du problème actuel)
- **Enrollment automatisé de la clé MOK** (obligatoire au premier usage)
- **Workflow guidé** pour l'utilisateur débutant
- **Diagnostic automatique** des problèmes "bad shim signature"
- **Re-signature intelligente** des kernels déjà installés
- **Détection automatique** si MOK est enrollé ou non

---

## 🎯 Objectif

Rendre SecureBoot **100% transparent** pour l'utilisateur :
1. Clic sur "Activer SecureBoot"
2. Suivre les instructions à l'écran
3. Redémarrer
4. **ÇA MARCHE** ✅

---

## 🏗️ Architecture Proposée

### Phase 1 : Court Terme (Utilisation des scripts)
**Délai : Immédiat**

```
scripts/
└── secureboot/
    ├── README.md                      ✅ Créé
    ├── enroll_mok_key.sh              ✅ Créé
    ├── verify_mok_enrollment.sh       ✅ Créé
    ├── fix_mok_not_appearing.sh       ✅ Créé
    └── resign_all_custom_kernels.sh   ✅ Créé
```

**Avantages :**
- ✅ Disponible immédiatement
- ✅ Utilisateurs CLI peuvent les utiliser
- ✅ Facilite le debugging
- ✅ Documentation complète incluse

**Inconvénients :**
- ❌ Utilisateurs non-techniques seront perdus
- ❌ Pas intégré dans l'interface graphique

---

### Phase 2 : Moyen Terme (Intégration Python)
**Délai : 1-2 semaines**

#### 2.1. Amélioration du `SecureBootManager`

**Fichier : `core/secureboot_manager.py`**

Ajouter les méthodes suivantes :

```python
class SecureBootManager:
    # ... code existant ...

    # ==================== Enrollment MOK ====================

    def check_mok_enrolled(self):
        """
        Vérifie si une clé MOK est déjà enrollée
        Returns: dict avec status, key_found, cn_name
        """
        try:
            result = subprocess.run(
                ["mokutil", "--list-enrolled"],
                capture_output=True, text=True, check=False
            )

            output = result.stdout

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
            result = subprocess.run(
                ["mokutil", "--list-new"],
                capture_output=True, text=True, check=False
            )

            output = result.stdout
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
            # Importer la clé
            cmd = ["mokutil", "--import", str(mok_key)]

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
            else:
                # Mode interactif (terminal)
                result = subprocess.run(cmd, check=True)
                success = result.returncode == 0

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
                    'message': f'Failed to import MOK key: {stderr}',
                    'needs_reboot': False
                }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'needs_reboot': False
            }

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
                # Compter les modules
                modules = list(kernel_dir.rglob("*.ko"))

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
        mok_priv = self.keys_dir / "MOK.priv"
        mok_cert = self.keys_dir / "MOK.der"

        if not mok_priv.exists() or not mok_cert.exists():
            return {
                'success': False,
                'message': 'MOK keys not found',
                'signed_count': 0,
                'failed_count': 0,
                'errors': []
            }

        # Trouver sign-file
        sign_file = self._find_sign_file()
        if not sign_file:
            return {
                'success': False,
                'message': 'sign-file tool not found',
                'signed_count': 0,
                'failed_count': 0,
                'errors': []
            }

        # Trouver les modules
        kernel_dir = Path(f"/lib/modules/{kernel_version}")
        if not kernel_dir.exists():
            return {
                'success': False,
                'message': f'Kernel directory not found: {kernel_dir}',
                'signed_count': 0,
                'failed_count': 0,
                'errors': []
            }

        modules = list(kernel_dir.rglob("*.ko"))
        total = len(modules)
        signed = 0
        failed = 0
        errors = []

        for i, module in enumerate(modules, 1):
            if progress_callback:
                progress_callback(i, total, module.name)

            try:
                result = subprocess.run(
                    [sign_file, "sha256", str(mok_priv), str(mok_cert), str(module)],
                    capture_output=True,
                    text=True,
                    check=True
                )
                signed += 1
            except subprocess.CalledProcessError as e:
                failed += 1
                errors.append(f"{module.name}: {e.stderr}")

        success = failed == 0

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

    def _find_sign_file(self):
        """Trouve l'outil sign-file"""
        import glob

        candidates = [
            "/usr/src/linux-headers-*/scripts/sign-file",
            "/usr/lib/linux-kbuild-*/scripts/sign-file"
        ]

        for pattern in candidates:
            matches = glob.glob(pattern)
            if matches:
                return matches[0]

        return None

    def diagnose_secureboot_issue(self):
        """
        Diagnostique automatique des problèmes SecureBoot
        Returns: dict avec issue_type, message, solutions (list)
        """
        diagnosis = {
            'issue_type': None,
            'message': '',
            'solutions': []
        }

        # 1. Vérifier UEFI
        if not self.is_uefi_system():
            diagnosis['issue_type'] = 'NOT_UEFI'
            diagnosis['message'] = 'System is not using UEFI. SecureBoot requires UEFI.'
            diagnosis['solutions'] = [
                'Convert to UEFI boot (advanced)',
                'Disable SecureBoot and use Legacy boot'
            ]
            return diagnosis

        # 2. Vérifier statut SecureBoot
        sb_status = self.get_secureboot_status()
        if not sb_status['enabled']:
            diagnosis['issue_type'] = 'SB_DISABLED'
            diagnosis['message'] = 'SecureBoot is disabled in BIOS/UEFI'
            diagnosis['solutions'] = [
                'Enable SecureBoot in BIOS settings',
                'Keep SecureBoot disabled (less secure)'
            ]
            return diagnosis

        # 3. Vérifier enrollment MOK
        mok_status = self.check_mok_enrolled()
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

        # 4. Vérifier signature des kernels custom
        custom_kernels = self.get_custom_kernels()
        if custom_kernels:
            unsigned_kernels = []
            wrong_signature_kernels = []

            for kernel in custom_kernels:
                if kernel['modules']:
                    # Vérifier un module échantillon
                    sample_module = kernel['modules'][0]
                    sig_info = self.check_module_signed(sample_module)

                    if not sig_info['signed']:
                        unsigned_kernels.append(kernel['kernel_version'])
                    elif sig_info['signer'] and 'kernelcustom' not in sig_info['signer'].lower():
                        wrong_signature_kernels.append(kernel['kernel_version'])

            if unsigned_kernels or wrong_signature_kernels:
                diagnosis['issue_type'] = 'MODULES_NOT_SIGNED'
                diagnosis['message'] = f'Custom kernel modules are not properly signed. Unsigned: {len(unsigned_kernels)}, Wrong signature: {len(wrong_signature_kernels)}'
                diagnosis['solutions'] = [
                    'Re-sign all custom kernel modules (automated tool available)',
                    'Recompile kernels with "Sign for SecureBoot" option'
                ]
                return diagnosis

        # Tout est OK !
        diagnosis['issue_type'] = 'OK'
        diagnosis['message'] = 'SecureBoot is properly configured'
        diagnosis['solutions'] = []
        return diagnosis
```

#### 2.2. Amélioration de l'interface `gui/secureboot_tab.py`

**Nouvel onglet : "🚀 Assistant" (Premier onglet)**

Ajouter un **wizard interactif** qui guide l'utilisateur :

```python
def create_wizard_tab(main_window, sb_manager, i18n):
    """Crée l'onglet assistant SecureBoot (wizard)"""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
    box.set_margin_start(20)
    box.set_margin_end(20)
    box.set_margin_top(20)
    box.set_margin_bottom(20)

    # Titre
    title = Gtk.Label()
    title.set_markup("<big><b>🔒 Assistant Configuration SecureBoot</b></big>")
    box.pack_start(title, False, False, 0)

    # Zone de diagnostic
    diagnosis_frame = Gtk.Frame(label="📊 Diagnostic Automatique")
    diagnosis_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    diagnosis_box.set_margin_start(10)
    diagnosis_box.set_margin_end(10)
    diagnosis_box.set_margin_top(10)
    diagnosis_box.set_margin_bottom(10)

    diagnosis_label = Gtk.Label()
    diagnosis_label.set_line_wrap(True)
    diagnosis_label.set_xalign(0)
    diagnosis_box.pack_start(diagnosis_label, False, False, 0)

    diagnosis_frame.add(diagnosis_box)
    box.pack_start(diagnosis_frame, False, False, 0)

    # Zone d'actions
    actions_frame = Gtk.Frame(label="⚡ Actions Recommandées")
    actions_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    actions_box.set_margin_start(10)
    actions_box.set_margin_end(10)
    actions_box.set_margin_top(10)
    actions_box.set_margin_bottom(10)

    actions_frame.add(actions_box)
    box.pack_start(actions_frame, False, False, 0)

    # Bouton diagnostic
    diagnose_btn = Gtk.Button(label="🔍 Lancer le Diagnostic")
    diagnose_btn.connect("clicked",
        lambda w: run_diagnosis_wizard(
            sb_manager, diagnosis_label, actions_box, main_window, i18n
        )
    )
    box.pack_start(diagnose_btn, False, False, 0)

    # Lancer automatiquement au chargement
    GLib.idle_add(lambda: run_diagnosis_wizard(
        sb_manager, diagnosis_label, actions_box, main_window, i18n
    ))

    return box


def run_diagnosis_wizard(sb_manager, diagnosis_label, actions_box, main_window, i18n):
    """Execute le diagnostic et affiche les actions recommandées"""

    # Nettoyer les actions précédentes
    for child in actions_box.get_children():
        actions_box.remove(child)

    diagnosis_label.set_markup("<i>Analyse en cours...</i>")

    def do_diagnosis():
        diag = sb_manager.diagnose_secureboot_issue()

        GLib.idle_add(lambda: display_diagnosis_results(
            diag, diagnosis_label, actions_box, sb_manager, main_window, i18n
        ))

    # Lancer dans un thread
    threading.Thread(target=do_diagnosis, daemon=True).start()


def display_diagnosis_results(diag, diagnosis_label, actions_box, sb_manager, main_window, i18n):
    """Affiche les résultats du diagnostic"""

    # Afficher le message
    if diag['issue_type'] == 'OK':
        diagnosis_label.set_markup(f"<span color='green'><b>✅ {diag['message']}</b></span>")
    elif diag['issue_type'] in ['NOT_UEFI', 'SB_DISABLED']:
        diagnosis_label.set_markup(f"<span color='orange'><b>⚠️ {diag['message']}</b></span>")
    else:
        diagnosis_label.set_markup(f"<span color='red'><b>❌ {diag['message']}</b></span>")

    # Afficher les solutions avec boutons d'action
    for i, solution in enumerate(diag['solutions'], 1):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        label = Gtk.Label(label=f"{i}. {solution}")
        label.set_xalign(0)
        label.set_line_wrap(True)
        hbox.pack_start(label, True, True, 0)

        # Boutons d'action selon le type de problème
        if diag['issue_type'] == 'MOK_NOT_ENROLLED' and i == 1:
            btn = Gtk.Button(label="▶️ Démarrer l'Enrollment")
            btn.connect("clicked", lambda w: start_mok_enrollment_wizard(
                sb_manager, main_window, i18n
            ))
            hbox.pack_start(btn, False, False, 0)

        elif diag['issue_type'] == 'MODULES_NOT_SIGNED' and i == 1:
            btn = Gtk.Button(label="▶️ Re-signer les Modules")
            btn.connect("clicked", lambda w: start_module_signing_wizard(
                sb_manager, main_window, i18n
            ))
            hbox.pack_start(btn, False, False, 0)

        actions_box.pack_start(hbox, False, False, 0)

    actions_box.show_all()
```

**Wizards spécialisés :**

```python
def start_mok_enrollment_wizard(sb_manager, main_window, i18n):
    """Lance le wizard d'enrollment MOK"""

    dialog = Gtk.Dialog(
        title="🔐 Enrollment de la Clé MOK",
        parent=main_window,
        flags=Gtk.DialogFlags.MODAL
    )
    dialog.set_default_size(600, 400)

    content = dialog.get_content_area()
    content.set_spacing(10)
    content.set_margin_start(20)
    content.set_margin_end(20)
    content.set_margin_top(20)
    content.set_margin_bottom(20)

    # Instructions
    instructions = Gtk.Label()
    instructions.set_markup("""
<b>📋 Instructions pour l'Enrollment MOK</b>

Cette opération va importer votre clé MOK. Voici ce qui va se passer :

1️⃣ Vous allez créer un <b>mot de passe temporaire</b> (8-16 caractères)
   ⚠️ <i>IMPORTANT : Notez-le bien !</i>

2️⃣ Votre système va redémarrer

3️⃣ Au redémarrage, un écran bleu "MOK Manager" apparaîtra :
   • Sélectionnez <b>Enroll MOK</b>
   • Sélectionnez <b>Continue</b>
   • Sélectionnez <b>Yes</b>
   • Entrez le <b>mot de passe</b> que vous allez créer
   • Sélectionnez <b>Reboot</b>

4️⃣ Votre clé sera enrollée et vos kernels custom pourront booter !
    """)
    instructions.set_line_wrap(True)
    instructions.set_xalign(0)
    content.pack_start(instructions, False, False, 0)

    # Champ mot de passe
    pw_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    pw_label = Gtk.Label(label="Mot de passe temporaire :")
    pw_entry = Gtk.Entry()
    pw_entry.set_visibility(False)
    pw_entry.set_placeholder_text("8-16 caractères")
    pw_box.pack_start(pw_label, False, False, 0)
    pw_box.pack_start(pw_entry, True, True, 0)
    content.pack_start(pw_box, False, False, 0)

    # Confirmation
    pw_confirm_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    pw_confirm_label = Gtk.Label(label="Confirmer :")
    pw_confirm_entry = Gtk.Entry()
    pw_confirm_entry.set_visibility(False)
    pw_confirm_box.pack_start(pw_confirm_label, False, False, 0)
    pw_confirm_box.pack_start(pw_confirm_entry, True, True, 0)
    content.pack_start(pw_confirm_box, False, False, 0)

    # Boutons
    dialog.add_button("❌ Annuler", Gtk.ResponseType.CANCEL)
    enroll_btn = dialog.add_button("✅ Importer la Clé MOK", Gtk.ResponseType.OK)

    content.show_all()

    response = dialog.run()

    if response == Gtk.ResponseType.OK:
        password = pw_entry.get_text()
        confirm = pw_confirm_entry.get_text()

        if password != confirm:
            show_error_dialog(main_window, "Les mots de passe ne correspondent pas")
            dialog.destroy()
            return

        if len(password) < 8 or len(password) > 16:
            show_error_dialog(main_window, "Le mot de passe doit faire 8-16 caractères")
            dialog.destroy()
            return

        # Lancer l'enrollment
        result = sb_manager.enroll_mok_key(password)

        if result['success']:
            # Afficher dialogue de succès avec instructions pour le reboot
            show_reboot_instructions_dialog(main_window)
        else:
            show_error_dialog(main_window, result['message'])

    dialog.destroy()


def start_module_signing_wizard(sb_manager, main_window, i18n):
    """Lance le wizard de re-signature des modules"""

    dialog = Gtk.Dialog(
        title="✍️ Re-signature des Modules Kernel",
        parent=main_window,
        flags=Gtk.DialogFlags.MODAL
    )
    dialog.set_default_size(600, 500)

    content = dialog.get_content_area()
    content.set_spacing(10)
    content.set_margin_start(20)
    content.set_margin_end(20)
    content.set_margin_top(20)
    content.set_margin_bottom(20)

    # Instructions
    title_label = Gtk.Label()
    title_label.set_markup("<big><b>✍️ Re-signature des Kernels Custom</b></big>")
    content.pack_start(title_label, False, False, 0)

    # Détecter les kernels
    custom_kernels = sb_manager.get_custom_kernels()

    if not custom_kernels:
        no_kernel_label = Gtk.Label()
        no_kernel_label.set_markup("<span color='orange'>⚠️ Aucun kernel custom détecté</span>")
        content.pack_start(no_kernel_label, False, False, 0)
        dialog.add_button("OK", Gtk.ResponseType.OK)
        content.show_all()
        dialog.run()
        dialog.destroy()
        return

    # Liste des kernels avec checkboxes
    info_label = Gtk.Label()
    info_label.set_markup(f"<b>{len(custom_kernels)} kernel(s) custom détecté(s):</b>")
    info_label.set_xalign(0)
    content.pack_start(info_label, False, False, 0)

    # ScrolledWindow pour la liste
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_min_content_height(200)

    kernel_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    kernel_checkboxes = []

    for kernel in custom_kernels:
        checkbox = Gtk.CheckButton(
            label=f"{kernel['kernel_version']} ({kernel['module_count']} modules)"
        )
        checkbox.set_active(True)
        checkbox.kernel_version = kernel['kernel_version']
        kernel_checkboxes.append(checkbox)
        kernel_list_box.pack_start(checkbox, False, False, 0)

    scrolled.add(kernel_list_box)
    content.pack_start(scrolled, True, True, 0)

    # Barre de progression
    progress = Gtk.ProgressBar()
    progress.set_show_text(True)
    content.pack_start(progress, False, False, 0)

    # Boutons
    dialog.add_button("❌ Annuler", Gtk.ResponseType.CANCEL)
    sign_btn = dialog.add_button("✍️ Signer les Modules", Gtk.ResponseType.OK)

    content.show_all()
    progress.hide()

    response = dialog.run()

    if response == Gtk.ResponseType.OK:
        # Récupérer les kernels sélectionnés
        selected_kernels = [
            cb.kernel_version for cb in kernel_checkboxes if cb.get_active()
        ]

        if not selected_kernels:
            show_error_dialog(main_window, "Aucun kernel sélectionné")
            dialog.destroy()
            return

        # Désactiver le bouton et afficher la barre de progression
        sign_btn.set_sensitive(False)
        progress.show()

        # Signer dans un thread
        def do_signing():
            total_signed = 0
            total_failed = 0

            for i, kernel_ver in enumerate(selected_kernels, 1):
                def update_progress(current, total, module_name):
                    fraction = current / total
                    text = f"[{i}/{len(selected_kernels)}] {kernel_ver}: {current}/{total} modules"
                    GLib.idle_add(progress.set_fraction, fraction)
                    GLib.idle_add(progress.set_text, text)

                result = sb_manager.resign_kernel_modules(
                    kernel_ver,
                    progress_callback=update_progress
                )

                total_signed += result['signed_count']
                total_failed += result['failed_count']

            # Afficher résultat final
            GLib.idle_add(lambda: show_signing_results(
                main_window, total_signed, total_failed
            ))
            GLib.idle_add(dialog.destroy)

        threading.Thread(target=do_signing, daemon=True).start()
    else:
        dialog.destroy()
```

---

### Phase 3 : Long Terme (Automatisation Complète)
**Délai : 1-2 mois**

#### Fonctionnalités avancées :

1. **Auto-détection au lancement**
   - Si SecureBoot activé + MOK non enrollé → Afficher popup "Configuration requise"
   - Bouton "Configuration automatique" qui lance tout le workflow

2. **Hook de compilation**
   - Quand un kernel est compilé, vérifier automatiquement si MOK est enrollé
   - Si oui, signer automatiquement pendant la compilation
   - Si non, proposer l'enrollment avant de continuer

3. **Monitoring post-reboot**
   - Détecter si l'utilisateur revient d'un reboot après enrollment
   - Vérifier automatiquement si l'enrollment a réussi
   - Afficher notification de succès ou d'échec

4. **Documentation interactive**
   - Vidéos/GIFs montrant les étapes dans MOK Manager
   - Tooltips contextuels sur chaque bouton
   - FAQ intégrée

---

## 📝 Plan d'Action Recommandé

### Semaine 1-2 : Phase 1 (Scripts) ✅ **TERMINÉ**
- [x] Organiser scripts dans `scripts/secureboot/`
- [x] Documentation complète des scripts
- [x] Tester tous les scripts

### Semaine 3-4 : Phase 2.1 (Backend)
- [ ] Implémenter les nouvelles méthodes dans `SecureBootManager`
- [ ] Tests unitaires
- [ ] Documentation des méthodes

### Semaine 5-6 : Phase 2.2 (Interface)
- [ ] Créer l'onglet "Assistant"
- [ ] Implémenter les wizards
- [ ] Tests d'intégration
- [ ] Documentation utilisateur

### Mois 2-3 : Phase 3 (Automatisation)
- [ ] Auto-détection au lancement
- [ ] Hooks de compilation
- [ ] Monitoring post-reboot
- [ ] Documentation interactive

---

## 🎯 Résultat Final Attendu

### Pour l'utilisateur débutant :
1. Lance KernelCustom Manager
2. Voit un message "SecureBoot détecté mais non configuré"
3. Clique sur "Configuration automatique"
4. Suit les 3 étapes guidées
5. **ÇA MARCHE** ✅

### Pour l'utilisateur avancé :
- Accès direct aux scripts CLI dans `scripts/secureboot/`
- Interface graphique avec options avancées
- Logs détaillés et historique

---

## 🔧 Avant de Commencer Phase 2

### Questions à résoudre :

1. **Mot de passe MOK** : Mode interactif ou non-interactif ?
   - Interactif = Plus sécurisé, mais nécessite terminal
   - Non-interactif = Plus user-friendly, mais mot de passe en clair temporaire

2. **Sudo/pkexec** : Comment gérer l'élévation de privilèges ?
   - PolicyKit (`.policy` file)
   - Sudo avec mot de passe
   - Pkexec wrapper

3. **Tests** : Environnement de test ?
   - VM avec SecureBoot activé
   - Tests sur système réel
   - CI/CD possible ?

4. **Traductions** : i18n pour toutes les nouvelles strings ?
   - FR ✅
   - EN ✅
   - Autres langues ?

---

**Qu'en penses-tu ?** On commence par quoi ? 🚀
