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
- [x] **3. Helper root en Python** : `kernelcustom-helper` réécrit en Python avec une **liste blanche d'actions** et la validation des chemins (uniquement dans `/usr/src`, le dossier de travail de l'utilisateur, `/boot`…). Supprimer `pkexec bash -c` (`gui/secureboot_tab.py`) et `shell=True` (`core/secureboot_manager.py`). Tous les `pkexec apt/dpkg/cp/systemctl` dispersés passent par le helper
- [x] **4. Portage du bash restant** : `manage_kernel_sources.sh` → `core/sources_manager.py` + actions `sources-*` du helper. `scripts/secureboot/*.sh` supprimés (doublons de l'app ; seul le contrôle shim/mmx64.efi était nouveau → intégré au diagnostic via `mokutil-diagnose`). Script de compilation `bash -c` → `core/build_runner.py` lancé via `utils/terminal.py`
- [x] **5. Chemins centralisés** : `utils/paths.py` (code, traductions, icônes, runner, helpers, données XDG, configuration) + migration automatique de `~/KernelCustomManager/build`
- [x] **6. Outil de nettoyage (logique)** : `core/cleanup_manager.py` (`scan()` / `clean()`, sans GTK) + traductions `cleanup.*`. **L'interface sera écrite en GTK4 à l'étape 7** (onglet ou dialogue « 🧹 Nettoyage »)
- [ ] **7. Portage GTK4 + libadwaita** : onglet par onglet (voir la section dédiée). L'interface de l'outil de nettoyage est écrite directement en GTK4 si l'étape 6 arrive après le début du portage
- [ ] **8. Paquet .deb (TOUT À LA FIN)** : création de `debian/`, construction, `lintian`, test d'installation et de désinstallation. Supprimer `install.sh`, `uninstall-policykit.sh` et le dossier en double `KernelCustomManager/` (il ne contient que des `__init__.py` vides)
- [ ] **9. Release v3.0** : mise à jour de la version, du changelog Debian et de la doc

> **Priorité : le portage de l'application (étapes 2 à 7).** Le paquet .deb vient tout à la fin, une fois l'app stabilisée en Python pur + GTK4. En attendant, l'app se lance depuis le dépôt git (`install.sh` reste utilisable jusqu'à l'étape 8, avec la policy polkit qui pointe vers le chemin du helper défini dans `utils/paths.py`).

## Opérations privilégiées (étape 3)

- **Seul `utils/pkexec_helper.py` (`PkexecHelper`) appelle `pkexec`.** Interdit ailleurs : `pkexec` direct, `sudo`, `bash -c`, `shell=True`.
- Le code des helpers est dans `helpers/` et ils sont installés dans `/usr/libexec/kernelcustom-manager/` (`root:root 0755`) par `install.sh` :
  - `kernelcustom-helper` : liste blanche (`apt-install`, `install-debs`, `remove-packages`, `reboot`, `mokutil-*`, `sign-kernel`). Policy `com.kernelcustom.manager.helper` en `auth_admin_keep`.
  - `kernelcustom-nvidia-installer` : `run`, `schedule`, `boot-install`, `cancel`, `uninstall`. Policy `com.kernelcustom.manager.nvidia` en `auth_admin`, qui redemande **toujours** le mot de passe. Le `.run` est copié dans `/var/lib/kernelcustom-manager/nvidia/` avant exécution.
- Les helpers sont **autonomes** (`#!/usr/bin/python3 -I`, aucun import de l'app). Ils valident tout : noms de paquets, versions, fichiers **appartenant à l'utilisateur appelant** (`PKEXEC_UID`), `sign-file` appartenant à root avec ses dossiers parents non modifiables, vmlinuz dans `/boot`. Ils refusent de supprimer le kernel en cours d'exécution.
- **Après une modification de `helpers/*`, il faut les réinstaller** (`./install.sh` ou `sudo install -m 0755 helpers/* /usr/libexec/kernelcustom-manager/`). L'app utilise toujours la copie installée.
- Ajouter une opération root = une nouvelle action validée dans le helper + une méthode dans `PkexecHelper`. Documenter dans `docs/POLICYKIT_README.md`.
- `modinfo` **ne nécessite pas root** et lit directement les `.ko.xz`/`.ko.zst` : pas de helper pour vérifier une signature.
- Le `kmod` de Debian est compilé sans zlib : les modules `.ko.gz` ne sont pas lisibles par `modinfo` (Debian utilise xz/zstd).

## Chemins (étape 5)

- **Tous les chemins viennent de `utils/paths.py`** : `APP_DIR`, `TRANSLATIONS_DIR`, `ICON_PNG`/`ICON_SVG`, `BUILD_RUNNER`, `HELPER_DIR` (fixe : `/usr/libexec/kernelcustom-manager`, référencé par la policy), `data_dir()` et `config_dir()`. Ne pas utiliser `Path.home()` ni `__file__` ailleurs.
- `data_dir()` = `$KCM_DATA_DIR`, sinon `$XDG_DATA_HOME/kernelcustom-manager`, sinon `~/.local/share/kernelcustom-manager`. `config_dir()` = `~/.config/kernelcustom-manager` (fichier `language.conf`).
- Journal : `data_dir()/logs/kernelcustom-manager.log`, configuré dans `kernelcustom_manager.py` (`setup_logging`, `force=True`). Les modules utilisent `logging` sans le configurer. Dans `utils/paths.py`, utiliser `log = logging.getLogger(__name__)`, car un `logging.info()` avant la configuration crée une configuration implicite.
- **Migration** (`paths.migrate_legacy_data()`) : appelée dans `main()` **avant** l'import de `gui.main_window`. Elle déplace l'ancien dossier, réécrit les liens absolus internes (profondeur 2) et laisse un lien de compatibilité si des liens de `/usr/src` pointent vers l'ancien emplacement. Elle ne fait rien si le nouveau dossier est déjà rempli. Un message est affiché une fois.
- Pour tester sans toucher à ses données : `KCM_DATA_DIR=/tmp/x python3 kernelcustom_manager.py` ou `HOME=/tmp/fakehome …`.

## Compilation et terminaux (étape 4)

- `utils/terminal.py` `launch_in_terminal(argv)` est le **seul** moyen d'ouvrir un terminal. La commande est une liste d'arguments (ptyxis, gnome-terminal, kgx, konsole, xfce4-terminal, xterm).
- `core/build_runner.py` est un script **autonome** (aucun import de l'app, lancé avec `python3 -I`). Il prend en entrée un `compile <job.json>` (configuration + textes déjà traduits) ou un `nconfig <linux_dir> <message>`.
- Suivi de fin : le runner écrit `<log>.status.json` (`running` + pid, puis `done` + returncode + paquets) et l'app le surveille (`_wait_for_status`). Le code de retour du terminal ne sert pas, car gnome-terminal rend la main immédiatement.
- Le suffixe `LOCALVERSION` est validé (`^[A-Za-z0-9._+~-]+$`) et passé comme argument de `make`, jamais interprété par un shell.
- `tar` (extraction des sources) et `make` restent des outils système appelés avec des listes d'arguments.

## Nettoyage (étape 6)

- `CleanupManager.scan(include_keys=False)` renvoie des `CleanupItem` (category, path, size, action `delete`/`make_clean`, protected, reason, selected). `clean(items, progress_callback)` renvoie `{freed, done, errors}`. Le scan parcourt de gros arbres : **toujours l'appeler dans un thread**.
- Catégories, dans l'ordre et avec leur sélection par défaut : `build_objects`✅ (`make clean` : garde `.config` et de quoi compiler des modules externes, donc OK même pour un arbre utilisé par DKMS), `archives`✅, `logs`✅, `driver_downloads`✅, `sources`, `headers`, `packages`, `driver_backups`, `config_backups`, `secureboot_keys` (uniquement si `include_keys`).
- Protégés (`protected=True`, jamais supprimés) : les cibles des liens de `/usr/src` et `/lib/modules/*/build|source` (`linked_usr_src`), les sources et headers du kernel `uname -r` (`running_kernel`). Raisons informatives : `active_build`, `installed_kernel`, `secureboot_keys`.
- `clean()` **revalide tout** : chemin dans le dossier de travail, protection recalculée, clés uniquement via leur catégorie. Il supprime aussi le lien `build/linux` s'il pointait vers l'arbre supprimé.
- Jamais listés : profils, historiques, journal en cours.
- Inventaire en ligne de commande (lecture seule) : `python3 -m core.cleanup_manager [--keys]`.

## Disposition du paquet .deb

```
/usr/bin/kernelcustom-manager                          → lanceur (script Python minimal)
/usr/lib/kernelcustom-manager/                         → paquet Python (core, gui, utils) + translations
/usr/libexec/kernelcustom-manager/kernelcustom-helper            → helper root (pkexec)
/usr/libexec/kernelcustom-manager/kernelcustom-nvidia-installer  → installeur NVIDIA (pkexec, auth_admin)
/usr/share/polkit-1/actions/com.kernelcustom.manager.policy
/usr/share/applications/com.kernelcustom.manager.desktop
/usr/share/icons/hicolor/scalable/apps/com.kernelcustom.manager.svg
/usr/share/doc/kernelcustom-manager/
```

- Nom du paquet : `kernelcustom-manager`. Architecture `all`. Construction avec `dh $@ --with python3`.
- La policy polkit pointe déjà vers `/usr/libexec/kernelcustom-manager/` (fait à l'étape 3).
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
- **Privilèges** : uniquement via `PkexecHelper` (voir « Opérations privilégiées »).
- **Structure** : la logique va dans `core/` (sans GTK), l'interface dans `gui/`, les utilitaires transverses dans `utils/`.
- **Commits** : messages en français, préfixés `Fix:`, `Feat:`, `Refactor:`, `Release:`, `Docs:`.
- Nettoyages en cours de route : `locale.getdefaultlocale()` (déprécié depuis Python 3.11+, à remplacer par `locale.getlocale()`) et les `except:` nus à remplacer par `except Exception:`.

## Dette repérée (à traiter pendant le portage)

- Un appel `pkexec` (mokutil-diagnose) est lancé **au démarrage** par l'onglet SecureBoot. Il faudrait le différer jusqu'à l'ouverture de l'onglet ou une action de l'utilisateur.
- `utils/dialogs.py` `show_question()` renvoie un **booléen** : ne jamais le comparer à `Gtk.ResponseType` (bug corrigé à l'étape 3 dans `drivers_tab.py`, où l'installation, la suppression et le rollback ne pouvaient jamais aboutir). À garder en tête pour l'API async GTK4.
- `gui/secureboot_tab.py` contient encore de nombreux `print("[DEBUG GUI] …")` : à passer en `logging`.
- La signature SecureBoot à la compilation (`sign_for_secureboot`) est désactivée dans l'interface (case commentée dans `show_compile_dialog`). Le runner la gère : il suffira de la réactiver lors du portage GTK4.
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
