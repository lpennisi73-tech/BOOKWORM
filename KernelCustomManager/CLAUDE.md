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
| Interface | **GTK4 + libadwaita** (`Adw.Application`), portage fait à l'étape 7 |

## Plan (un commit par étape)

- [x] **1. CLAUDE.md** : plan et conventions (ce fichier)
- [x] **2. Retrait d'Ubuntu** : `core/driver_manager.py`, `core/secureboot_manager.py`, `gui/build_tab_*.py`, `install.sh`, `scripts/secureboot/fix_mok_not_appearing.sh` (`EFI/debian`), doc et traductions
- [x] **3. Helper root en Python** : `kernelcustom-helper` réécrit en Python avec une **liste blanche d'actions** et la validation des chemins (uniquement dans `/usr/src`, le dossier de travail de l'utilisateur, `/boot`…). Supprimer `pkexec bash -c` (`gui/secureboot_tab.py`) et `shell=True` (`core/secureboot_manager.py`). Tous les `pkexec apt/dpkg/cp/systemctl` dispersés passent par le helper
- [x] **4. Portage du bash restant** : `manage_kernel_sources.sh` → `core/sources_manager.py` + actions `sources-*` du helper. `scripts/secureboot/*.sh` supprimés (doublons de l'app ; seul le contrôle shim/mmx64.efi était nouveau → intégré au diagnostic via `mokutil-diagnose`). Script de compilation `bash -c` → `core/build_runner.py` lancé via `utils/terminal.py`
- [x] **5. Chemins centralisés** : `utils/paths.py` (code, traductions, icônes, runner, helpers, données XDG, configuration) + migration automatique de `~/KernelCustomManager/build`
- [x] **6. Outil de nettoyage (logique)** : `core/cleanup_manager.py` (`scan()` / `clean()`, sans GTK) + traductions `cleanup.*`. **L'interface sera écrite en GTK4 à l'étape 7** (onglet ou dialogue « 🧹 Nettoyage »)
- [x] **7. Portage GTK4 + libadwaita** (branche `gtk4`) : `Adw.Application`, fenêtre `Adw.ApplicationWindow` + `Adw.ViewStack`, dialogues asynchrones, `Gtk.ColumnView`, `Gio.Notification`, nouvel onglet « Nettoyage ». Voir « Interface GTK4 »
- [x] **8. Paquet .deb** : `debian/` (debhelper 13, `dh-python`), `lintian` propre (y compris `--pedantic` et expérimental), installation, désinstallation et purge testées. `install.sh`, `uninstall-policykit.sh` et le dossier en double `KernelCustomManager/` sont supprimés. Voir « Paquet .deb »
- [ ] **9. Release v3.0** : mise à jour de la version, du changelog Debian et de la doc

> L'app s'installe avec le paquet .deb. Pour développer, on peut toujours la lancer depuis le dépôt (`python3 kernelcustom_manager.py`) : elle utilise alors les helpers et la policy **installés par le paquet**.

## Opérations privilégiées (étape 3)

- **Seul `utils/pkexec_helper.py` (`PkexecHelper`) appelle `pkexec`.** Interdit ailleurs : `pkexec` direct, `sudo`, `bash -c`, `shell=True`.
- Le code des helpers est dans `helpers/` et ils sont installés dans `/usr/libexec/kernelcustom-manager/` (`root:root 0755`) par le paquet :
  - `kernelcustom-helper` : liste blanche (`apt-install`, `install-debs`, `remove-packages`, `reboot`, `mokutil-*`, `sign-kernel`). Policy `com.kernelcustom.manager.helper` en `auth_admin_keep`.
  - `kernelcustom-nvidia-installer` : `run`, `schedule`, `boot-install`, `cancel`, `uninstall`. Policy `com.kernelcustom.manager.nvidia` en `auth_admin`, qui redemande **toujours** le mot de passe. Le `.run` est copié dans `/var/lib/kernelcustom-manager/nvidia/` avant exécution.
- Les helpers sont **autonomes** (`#!/usr/bin/python3 -I`, aucun import de l'app). Ils valident tout : noms de paquets, versions, fichiers **appartenant à l'utilisateur appelant** (`PKEXEC_UID`), `sign-file` appartenant à root avec ses dossiers parents non modifiables, vmlinuz dans `/boot`. Ils refusent de supprimer le kernel en cours d'exécution.
- **Après une modification de `helpers/*`, il faut les réinstaller** (reconstruire et réinstaller le paquet, ou `sudo install -m 0755 helpers/* /usr/libexec/kernelcustom-manager/` pour un test rapide). L'app utilise toujours la copie installée.
- Ajouter une opération root = une nouvelle action validée dans le helper + une méthode dans `PkexecHelper`. Documenter dans `docs/POLICYKIT_README.md`.
- `modinfo` **ne nécessite pas root** et lit directement les `.ko.xz`/`.ko.zst` : pas de helper pour vérifier une signature.
- Le `kmod` de Debian est compilé sans zlib : les modules `.ko.gz` ne sont pas lisibles par `modinfo` (Debian utilise xz/zstd).

## Chemins (étape 5)

- **Tous les chemins viennent de `utils/paths.py`** : `APP_DIR`, `APP_ID` (`kernelcustom-manager`), `APPLICATION_ID` (`com.kernelcustom.manager` : id GTK/D-Bus, nom de l'icône et du .desktop), `TRANSLATIONS_DIR`, `ICONS_DIR` (`data/icons/hicolor/…`), `BUILD_RUNNER`, `HELPER_DIR` (fixe : `/usr/libexec/kernelcustom-manager`, référencé par la policy), `data_dir()` et `config_dir()`. Ne pas utiliser `Path.home()` ni `__file__` ailleurs.
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

## Paquet .deb (étape 8)

```
/usr/bin/kernelcustom-manager                          → lanceur (script Python minimal)
/usr/lib/kernelcustom-manager/                         → paquet Python (core, gui, utils) + translations
/usr/libexec/kernelcustom-manager/kernelcustom-helper            → helper root (pkexec)
/usr/libexec/kernelcustom-manager/kernelcustom-nvidia-installer  → installeur NVIDIA (pkexec, auth_admin)
/usr/share/polkit-1/actions/com.kernelcustom.manager.policy
/usr/share/applications/com.kernelcustom.manager.desktop
/usr/share/icons/hicolor/256x256/apps/com.kernelcustom.manager.png
/usr/share/man/man1/kernelcustom-manager.1.gz
/usr/share/doc/kernelcustom-manager/
```

- Paquet `kernelcustom-manager`, architecture `all`, format `3.0 (native)`. `dh $@ --with python3`, avec `dh_python3 /usr/lib/kernelcustom-manager` (dossier privé, précompilé à l'installation).
- Fichiers du dépôt propres au paquet : `bin/kernelcustom-manager` (lanceur : ajoute `/usr/lib/kernelcustom-manager` à `sys.path` et appelle `main()`), `data/com.kernelcustom.manager.desktop`, `data/kernelcustom-manager.1`.
- **Ne jamais lancer `dh_python3` sur `/usr/libexec`** : il réécrit le shebang des helpers root et **supprime `-I`**.
- `kernelcustom_manager.py` est exécutable dans le dépôt, mais remis en 0644 dans le paquet (`override_dh_fixperms`), car il est importé par le lanceur.
- `Depends` : outils de compilation du kernel (`build-essential`, `bc`, `bison`, `flex`, `libssl-dev`, `libelf-dev`, `libdw-dev`, `libncurses-dev`, `fakeroot`, `dpkg-dev`, `rsync`, `cpio`, `kmod`, `pahole` car Debian active `CONFIG_DEBUG_INFO_BTF`, `xz-utils`), plus `debhelper`, `openssl`, `pciutils`, `pkexec`, `polkitd`, `ptyxis | x-terminal-emulator`, GTK4 et libadwaita. **`debhelper` est vraiment nécessaire** : le `debian/rules` généré par `make bindeb-pkg` appelle `dh_*` (override lintian `binary-package-depends-on-toolchain-package`).
- `Recommends` : dkms, mokutil, sbsigntool, shim-signed. `Suggests` : firmware-amd-graphics (non-free-firmware).
- `prerm` (remove) : annule une installation NVIDIA programmée (`kernelcustom-nvidia-installer cancel`), sinon le service appellerait au démarrage un helper supprimé. `postrm` (purge) : supprime `/var/lib/kernelcustom-manager`. **Les données utilisateur (`~/.local/share/kernelcustom-manager`) ne sont jamais touchées.**
- Aucun fichier écrit dans le `$HOME` à l'installation.
- Construction : `dpkg-buildpackage -us -uc -b` depuis `KernelCustomManager/`. Les `.deb`, `.buildinfo` et `.changes` sont écrits dans `/usr/src/BOOKWORM/`, et ignorés par le `.gitignore` racine.
- Un ancien `~/.local/share/applications/com.kernelcustom.manager.desktop`, créé par `install.sh`, est prioritaire sur celui du paquet et lance la version du dépôt. Il faut le supprimer.

## Interface GTK4 (étape 7)

- **GTK 4 + libadwaita uniquement** (`gi.require_version('Gtk', '4.0')`, `'Adw', '1'`). Aucun code GTK3 (`pack_start`, `show_all`, `dialog.run()`, `Gtk.TreeView`, `Notify`…).
- Point d'entrée : `kernelcustom_manager.py` → `KernelCustomApplication(Adw.Application)`, id `com.kernelcustom.manager`. Icône chargée par nom (`Gtk.Window.set_default_icon_name`) ; depuis le dépôt, `paths.ICONS_DIR` est ajouté au thème d'icônes.
- Fenêtre : `gui/main_window.py`. La table `PAGES` liste les onglets (nom, clé de traduction, icône symbolique, module, fonction `create_*_tab(main_window)`). `Adw.ViewSwitcher` dans la barre de titre, remplacé par `Adw.ViewSwitcherBar` en bas sous 1550 sp (9 onglets). Menu principal : langue, à propos, quitter.
- **Dialogues : `utils/dialogs.py` (`main_window.dialogs`), tous asynchrones**. Le code qui suit une réponse est passé en callback :
  - `show_info` / `show_warning` / `show_error(title, message, on_close=None)`, `toast(message)` pour les confirmations discrètes ;
  - `ask(title, message, on_yes, on_no=None, destructive=False, yes_label=, no_label=)`. **Il n'y a plus de `show_question()`** ;
  - `form(title, child, ok_label, on_ok)` (Adw.AlertDialog + formulaire) et `window(title, child, ok_label, on_ok)` (Adw.Dialog). Pour `window`, `on_ok()` renvoie True pour fermer ;
  - `progress(title, status, cancellable=False)` → `ProgressDialog` dont `set_status`, `set_fraction`, `pulse`, `close` et `.cancelled` sont **utilisables depuis un thread** ;
  - `open_file(title, on_selected, filters)`, `save_file(title, on_selected, initial_name)` (`Gtk.FileDialog`).
- **Threads : `run_task(work, on_done, on_error)`** (dans `utils/dialogs.py`) exécute `work()` dans un thread et rappelle `on_done(résultat)` dans le thread GTK. À utiliser pour tout `pkexec`, réseau, `apt-cache`, `make` ou scan de fichiers. Ne jamais toucher un widget depuis un thread (sinon passer par `GLib.idle_add`).
- Widgets communs : `gui/widgets.py`. On y trouve `SimpleList` (tableau `Gtk.ColumnView` : `set_rows`, `append`, `selected()` → `Row` avec `row[i]` et `row.data`), `section` (bloc titré en carte), `page_box`, `title_label`, `markup_label`, `button`, `button_row`, `labeled`, `entry`, `monospace_view`, `inner_tabs` (`Gtk.Stack` + `StackSwitcher`), `info_bar`, `clear_box` et `run_once_when_mapped`.
- **Chargement différé** : ce qui demande le mot de passe ou est lent se lance à la première ouverture de l'onglet (`run_once_when_mapped`). C'est le cas du diagnostic SecureBoot (une seule lecture `mokutil-diagnose`, réutilisée par la liste des clés, échec compris) et du scan de nettoyage. La version stable de kernel.org est lue en arrière-plan.
- Les onglets complexes sont des classes (`DriversPage`, `SecureBootPage`, `CleanupPage`) accessibles depuis la fenêtre (`main_window.drivers_page`…).
- Notifications : `KernelManager.notifier` est branché par la fenêtre sur `app.notify()` (`Gio.Notification`). `core/` reste sans GTK. GNOME n'affiche les `Gio.Notification` que si le `.desktop` `com.kernelcustom.manager.desktop` est installé. Sinon (lancement depuis le dépôt sans le paquet), `app.notify()` passe par `org.freedesktop.Notifications`.
- La signature SecureBoot à la compilation est réactivée. La case est cochée par défaut si SecureBoot est actif et qu'une clé MOK existe (`find_signing_key`).
- **Tester sans afficher de fenêtre sur la session de l'utilisateur** : `DISPLAY=:0` est la vraie session GNOME. Utiliser broadway, par exemple `gtk4-broadwayd :7 &`, puis `env -u DISPLAY GDK_BACKEND=broadway BROADWAY_DISPLAY=:7 KCM_DATA_DIR=/tmp/x python3 kernelcustom_manager.py`. Pour une capture : `win.snapshot_child(win.get_first_child(), snapshot)` puis `get_renderer().render_texture(...)`, avec `gtk-enable-animations=False`, sinon les dialogues restent invisibles car l'animation n'avance pas sans client broadway.

## Conventions du code

- **Langue** : code et commentaires en français (existant). **Tout texte affiché à l'utilisateur passe par `utils/i18n.py`**. Ajouter chaque clé dans `translations/fr.json` ET `translations/en.json`.
- **Privilèges** : uniquement via `PkexecHelper` (voir « Opérations privilégiées »).
- **Structure** : la logique va dans `core/` (sans GTK), l'interface dans `gui/`, les utilitaires transverses dans `utils/`.
- **Commits** : messages en français, préfixés `Fix:`, `Feat:`, `Refactor:`, `Release:`, `Docs:`.
- Nettoyages en cours de route : les `except:` nus restants (`core/`) sont à remplacer par `except Exception:` (fait pour `gui/`, `utils/` et `core/kernel_manager.py`).

## Dette repérée

- `core/driver_manager.py` et `core/secureboot_manager.py` renvoient encore des messages en dur (français ou anglais) affichés tels quels. Ils devraient renvoyer des clés i18n.
- `docs/ARCHITECTURE.md` décrit encore GTK3, Ubuntu et AMD. À réécrire à l'étape Release.
- `data/icons/hicolor/scalable/…svg` n'est qu'un PNG encapsulé (3 Mo) : le paquet n'installe que le PNG 256×256. Prévoir un vrai SVG.
- Corrigé à l'étape 7 :
  - le `pkexec` lancé au démarrage par l'onglet SecureBoot ;
  - `show_question()` qui renvoyait un booléen (supprimé) ;
  - les `print("[DEBUG GUI]")` ;
  - la signature SecureBoot désactivée à la compilation ;
  - `locale.getdefaultlocale()`.

## Commandes utiles

```bash
python3 kernelcustom_manager.py              # lancer depuis le dépôt
python3 -m py_compile $(git ls-files '*.py') # vérification de syntaxe rapide
dpkg-buildpackage -us -uc -b                 # construire le .deb (dans /usr/src/BOOKWORM/)
lintian -I --pedantic ../kernelcustom-manager_*.changes  # vérifier le paquet
sudo apt install ../kernelcustom-manager_*_all.deb       # installer
```

## Notes Debian 14

- Sur testing/sid, `/etc/os-release` **ne contient pas `VERSION_ID`**. Il faut lire `/etc/debian_version` (ex. `forky/sid`). Utiliser `platform.freedesktop_os_release()` plutôt que de parser le fichier à la main.
- Pilotes depuis les dépôts : NVIDIA = `nvidia-driver` (paquet unique, section **non-free**), `nvidia-open-kernel-dkms`, `nvidia-tesla-XXX-driver`. AMD/Intel = Mesa + `firmware-amd-graphics` / `firmware-intel-graphics`. Les versions sont lues via `apt-cache policy` avec `LC_ALL=C`.
- Pilotes depuis le site officiel : **NVIDIA uniquement** (le `.run`). Pas d'`amdgpu-install` ni d'AMDGPU-PRO.

- `mokutil` peut renvoyer un code de sortie non nul même quand sa sortie est valide (bug déjà observé sous Debian 13). D'où les `|| true` dans le helper actuel, à conserver dans la version Python.
- Debian recompresse les modules (`CONFIG_MODULE_COMPRESS_XZ`) : il faut signer **avant** la compression ou re-signer après (voir `core/secureboot_manager.py`).
- `modinfo` et `lsmod` sont dans `/usr/sbin`, **absent du PATH d'un utilisateur Debian** : `kernelcustom_manager.py` (`extend_path()`) l'ajoute au démarrage. Sans cela, tous les modules apparaissent « non signés ».
