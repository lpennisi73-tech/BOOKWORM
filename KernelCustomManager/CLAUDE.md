# CLAUDE.md — KernelCustom Manager

Application Python de gestion de kernels Linux personnalisés : compilation, paquets, sources `/usr/src`, pilotes NVIDIA/AMD et SecureBoot (signature des modules et de vmlinuz, clés MOK).

## Cible

- **Debian 14 « forky » uniquement** (machine de dev : forky/sid, Python 3.14, GTK 4.24, libadwaita 1.10).
- **Le support Ubuntu, Mint, Fedora et Arch est abandonné.** Ne pas réintroduire de code spécifique à une autre distribution.
- Distribution de l'app : **paquet `.deb`** construit avec `debhelper` (`dpkg-buildpackage`).

## Décisions prises (2026-10-31)

| Sujet | Décision |
|---|---|
| Ubuntu | Retiré : correspondance des noms de version, motifs `-generic`, `-aws`, etc., `is_ubuntu`, `EFI/ubuntu`, `lsb_release` |
| Pilotes AMD | `amdgpu-install` (Ubuntu seulement) retiré. On n'utilise que les dépôts Debian : mesa et `firmware-amd-graphics` |
| Bash | **Tout est porté en Python**, y compris `manage_kernel_sources.sh`, `kernelcustom-helper` et `scripts/secureboot/*.sh`. Les commandes système (`make`, `dpkg`, `apt`, `mokutil`, `sign-file`, `pkexec`) restent appelées via `subprocess` avec des listes d'arguments |
| Paquet | Option A : répertoire `debian/` + debhelper, vérifié par `lintian` |
| Dossier de travail | Standard XDG `~/.local/share/kernelcustom-manager/` (au lieu de `~/KernelCustomManager/build`), **avec migration automatique** de l'ancien dossier |
| Interface | **Portage GTK3 → GTK4 + libadwaita** (`Adw.Application`) |

## Plan (un commit par étape)

- [x] **1. CLAUDE.md** : plan et conventions (ce fichier)
- [x] **2. Retrait d'Ubuntu** : `core/driver_manager.py`, `core/secureboot_manager.py`, `gui/build_tab_*.py`, `install.sh`, `scripts/secureboot/fix_mok_not_appearing.sh` (`EFI/debian`), doc et traductions
- [ ] **3. Helper root en Python** : `kernelcustom-helper` réécrit en Python avec une **liste blanche d'actions** et la validation des chemins (uniquement dans `/usr/src`, le dossier de travail de l'utilisateur, `/boot`…). Supprimer `pkexec bash -c` (`gui/secureboot_tab.py`) et `shell=True` (`core/secureboot_manager.py`). Tous les `pkexec apt/dpkg/cp/systemctl` dispersés passent par le helper
- [ ] **4. Portage du bash restant** : `manage_kernel_sources.sh` devient `core/sources_manager.py` (actions install, remove, link, unlink, list, exécutées via le helper). `scripts/secureboot/*.sh` est intégré dans `core/secureboot_manager.py` ou supprimé s'il fait doublon. `install_nvidia.sh` généré par `driver_manager.py` est remplacé par une action du helper
- [ ] **5. Chemins centralisés** : nouveau module `utils/paths.py` (dossier de l'app, traductions, icônes, helper, dossier de travail XDG + migration). Plus de `Path(__file__).parent.parent` ni de `/usr/local/bin` codé en dur ailleurs. L'app doit fonctionner **installée ET lancée depuis le dépôt git**
- [ ] **6. Outil de nettoyage du dossier de travail** : `core/cleanup_manager.py` + une interface (onglet ou dialogue). Il liste avec leur taille les sources extraites, les arbres compilés, les archives `.tar.xz` téléchargées, les `.deb` générés, les logs et les fichiers pilotes. On peut les supprimer en sélection ou par catégorie, avec confirmation. **Il ne touche jamais** aux sources liées dans `/usr/src` ni au kernel en cours d'exécution (`uname -r`). Les clés MOK sont exclues par défaut
- [ ] **7. Portage GTK4 + libadwaita** : onglet par onglet (voir la section dédiée). L'interface de l'outil de nettoyage est écrite directement en GTK4 si l'étape 6 arrive après le début du portage
- [ ] **8. Paquet .deb (TOUT À LA FIN)** : création de `debian/`, construction, `lintian`, test d'installation et de désinstallation. Supprimer `install.sh`, `uninstall-policykit.sh` et le dossier en double `KernelCustomManager/` (il ne contient que des `__init__.py` vides)
- [ ] **9. Release v3.0** : mise à jour de la version, du changelog Debian et de la doc

> **Priorité : le portage de l'application (étapes 2 à 7).** Le paquet .deb vient tout à la fin, une fois l'app stabilisée en Python pur + GTK4. En attendant, l'app se lance depuis le dépôt git (`install.sh` reste utilisable jusqu'à l'étape 8, avec la policy polkit qui pointe vers le chemin du helper défini dans `utils/paths.py`).

## Disposition du paquet .deb

```
/usr/bin/kernelcustom-manager                          → lanceur (script Python minimal)
/usr/lib/kernelcustom-manager/                         → paquet Python (core, gui, utils) + translations
/usr/libexec/kernelcustom-manager/kernelcustom-helper  → helper root (pkexec)
/usr/share/polkit-1/actions/com.kernelcustom.manager.policy
/usr/share/applications/com.kernelcustom.manager.desktop
/usr/share/icons/hicolor/scalable/apps/com.kernelcustom.manager.svg
/usr/share/doc/kernelcustom-manager/
```

- Nom du paquet : `kernelcustom-manager`. Architecture `all`. Construction avec `dh $@ --with python3`.
- La policy polkit pointe vers `/usr/libexec/kernelcustom-manager/kernelcustom-helper` (et non plus `/usr/local/bin`).
- `Depends` : python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, policykit-1 (ou polkitd + pkexec), build-essential, bc, bison, flex, libssl-dev, libelf-dev, libncurses-dev, fakeroot, dpkg-dev, debhelper, rsync, kmod, curl, xz-utils, dkms
- `Recommends` : mokutil, sbsigntool, shim-signed, firmware-amd-graphics
- Aucun fichier écrit dans le `$HOME` à l'installation. Les données utilisateur sont créées au lancement.

## Portage GTK4 : points à traiter

État relevé au départ : environ 210 `pack_start`/`pack_end`, 131 `add()`, 22 `show_all`, 26 `.run()` de dialogues bloquants, 34 `Gtk.Dialog`/`MessageDialog`, 10 `FileChooser`, 30 `TreeView`/`ListStore`, 95 `GLib.idle_add` et des threads.

| GTK3 | GTK4 / libadwaita |
|---|---|
| `Gtk.main()` / `Gtk.main_quit` | `Adw.Application` + `app.run()` (id `com.kernelcustom.manager`) |
| `Gtk.Window` principal | `Adw.ApplicationWindow` (+ `Adw.ToolbarView`, `Adw.HeaderBar`, `Adw.ViewStack`/`ViewSwitcher` pour les onglets) |
| `box.pack_start(w, expand, fill, pad)` | `box.append(w)` + `set_hexpand`/`set_vexpand`/marges |
| `container.add(w)` | `set_child(w)` / `append(w)` selon le widget |
| `show_all()` | à supprimer (widgets visibles par défaut) |
| `dialog.run()` bloquant | **asynchrone** : `Adw.AlertDialog` + `choose()`/callback `response`. C'est la plus grosse refonte : il faut transformer le code appelant en callbacks |
| `Gtk.FileChooserDialog` | `Gtk.FileDialog` (asynchrone) |
| `Gtk.TreeView` + `ListStore` | `Gtk.ColumnView` + `Gio.ListStore` (TreeView reste utilisable mais est déprécié) |
| `Notify` (libnotify) | `Gio.Notification` + `app.send_notification()` |
| Signaux d'événements (`button-press-event`…) | `Gtk.GestureClick`, `Gtk.EventControllerKey` |
| `Gtk.Image.new_from_icon_name(name, size)` | `Gtk.Image.new_from_icon_name(name)` + `set_pixel_size` |

- Les mises à jour d'interface depuis les threads continuent de passer par `GLib.idle_add`.
- Ordre de portage conseillé : `utils/dialogs.py` (créer une API de dialogues async réutilisable) → `main_window.py` → onglets simples (history, profiles, packages, kernels) → sources → build (`build_tab*.py`) → drivers → secureboot (le plus gros).
- Lancer un terminal externe (`gnome-terminal`, `ptyxis`, `konsole`, `xterm`) : garder le principe, mais sans `bash -c` avec du texte interpolé non échappé (utiliser `shlex.quote`).

## Conventions du code

- **Langue** : code et commentaires en français (existant). **Tout texte affiché à l'utilisateur passe par `utils/i18n.py`**. Ajouter chaque clé dans `translations/fr.json` ET `translations/en.json`.
- **Privilèges** : jamais de `sudo`. Uniquement `pkexec` + le helper, avec des **listes d'arguments**, jamais `shell=True` ni `bash -c` avec des données utilisateur.
- **Structure** : la logique va dans `core/` (sans GTK), l'interface dans `gui/`, les utilitaires transverses dans `utils/`.
- **Commits** : messages en français, préfixés `Fix:`, `Feat:`, `Refactor:`, `Release:`, `Docs:`.
- Nettoyages en cours de route : `locale.getdefaultlocale()` (déprécié depuis Python 3.11+, à remplacer par `locale.getlocale()`) et les `except:` nus à remplacer par `except Exception:`.

## Dette repérée (à traiter pendant le portage)

- `core/secureboot_manager.py` `_fetch_mok_data` : `print("[DEBUG] …")` + `traceback.print_stack()` laissés dans le code. À remplacer par `logging.debug`.
- Un appel `pkexec` (mokutil-diagnose) est lancé **au démarrage** par l'onglet SecureBoot. Il faudrait le différer jusqu'à l'ouverture de l'onglet ou une action de l'utilisateur.
- `gui/drivers_tab.py` (fin de l'installation NVIDIA) : `response = GLib.idle_add(lambda: show_question(...))` renvoie un id de source GLib et non la réponse, donc le redémarrage proposé n'est jamais lancé. Ce sera corrigé naturellement avec les dialogues async GTK4.
- `docs/ARCHITECTURE.md` : décrit encore GTK3, Ubuntu et AMD. À réécrire à l'étape Release.
- `install.sh` : installe `debhelper-compat` (paquet virtuel). À revoir avec `debian/control` à l'étape 8.

## Commandes utiles

```bash
python3 kernelcustom_manager.py              # lancer depuis le dépôt
python3 -m py_compile $(git ls-files '*.py') # vérification de syntaxe rapide
dpkg-buildpackage -us -uc -b                 # construire le .deb (étape 6+)
lintian ../kernelcustom-manager_*.deb        # vérifier le paquet
```

## Notes Debian 14

- Sur testing/sid, `/etc/os-release` **ne contient pas `VERSION_ID`**. Il faut lire `/etc/debian_version` (ex. `forky/sid`). Utiliser `platform.freedesktop_os_release()` plutôt que de parser le fichier à la main.
- Pilotes depuis les dépôts : NVIDIA = `nvidia-driver` (paquet unique, section **non-free**), `nvidia-open-kernel-dkms`, `nvidia-tesla-XXX-driver`. AMD/Intel = Mesa + `firmware-amd-graphics` / `firmware-intel-graphics`. Les versions sont lues via `apt-cache policy` avec `LC_ALL=C`.
- Pilotes depuis le site officiel : **NVIDIA uniquement** (le `.run`). Pas d'`amdgpu-install` ni d'AMDGPU-PRO.

- `mokutil` peut renvoyer un code de sortie non nul même quand sa sortie est valide (bug déjà observé sous Debian 13). D'où les `|| true` dans le helper actuel, à conserver dans la version Python.
- Debian recompresse les modules (`CONFIG_MODULE_COMPRESS_XZ`) : il faut signer **avant** la compression ou re-signer après (voir `core/secureboot_manager.py`).
- `modinfo` sur les modules signés demande les droits root (action `modinfo-check` du helper).
