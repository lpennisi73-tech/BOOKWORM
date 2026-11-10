# KernelCustom Manager - Architecture

Technical documentation for KernelCustom Manager **v3.0**: how the code is organized, how the
privileged operations are secured, and how the main workflows (compilation, SecureBoot, cleanup)
work.

## Table of Contents
- [Overview](#overview)
- [Repository Layout](#repository-layout)
- [Installed Layout](#installed-layout)
- [Layers](#layers)
- [Paths and User Data](#paths-and-user-data)
- [Privileged Operations](#privileged-operations)
- [User Interface (GTK4 + libadwaita)](#user-interface-gtk4--libadwaita)
- [Kernel Compilation](#kernel-compilation)
- [SecureBoot](#secureboot)
- [Cleanup](#cleanup)
- [Internationalization](#internationalization)
- [Logging and Notifications](#logging-and-notifications)
- [Debian Specifics](#debian-specifics)
- [Testing](#testing)

---

## Overview

| | |
|---|---|
| Target | **Debian 14 "forky" only** (other distributions are not supported) |
| Language | Python 3 (Debian's version), standard library only |
| Interface | GTK 4 + libadwaita (PyGObject) |
| Root access | PolicyKit (`pkexec`) + two standalone helpers with a whitelist of actions |
| Distribution | Debian package `kernelcustom-manager` (debhelper) |
| License | GPL-2.0 |

Design principles:
- **No shell**: every command is run with an argument list. No `bash -c`, no `shell=True`, no `sudo`.
- **No GTK in `core/`**: business logic can be used and tested without a display.
- **One source for paths** (`utils/paths.py`) and **one entry point for root** (`utils/pkexec_helper.py`).
- **Long work never blocks the GTK thread** (`run_task`).

---

## Repository Layout

```
KernelCustomManager/
├── kernelcustom_manager.py      # Entry point: KernelCustomApplication (Adw.Application), main()
├── bin/kernelcustom-manager     # Launcher installed in /usr/bin
├── core/                        # Business logic, no GTK
│   ├── kernel_manager.py        # Kernels, packages, profiles, configs, history, download
│   ├── kernel_releases.py       # Versions published on kernel.org (stable, mainline, longterm)
│   ├── distcc.py                # distcc: compiler name, host list, job count
│   ├── build_runner.py          # Standalone script run in a terminal (compile, nconfig)
│   ├── sources_manager.py       # /usr/src sources and headers
│   ├── driver_manager.py        # GPU detection and drivers (Debian repositories, NVIDIA .run)
│   ├── secureboot_manager.py    # SecureBoot state, MOK keys, signatures, diagnosis
│   └── cleanup_manager.py       # Working directory inventory and cleanup
├── gui/                         # GTK4 + libadwaita interface
│   ├── main_window.py           # KernelManagerWindow, PAGES table, main menu
│   ├── widgets.py               # Shared widgets
│   ├── kernels_tab.py, packages_tab.py, build_tab.py (+ build_tab_config.py, build_tab_compile.py),
│   ├── drivers_tab.py, secureboot_tab.py, sources_tab.py, profiles_tab.py,
│   └── history_tab.py, cleanup_tab.py
├── utils/
│   ├── paths.py                 # All paths, XDG data, legacy data migration
│   ├── dialogs.py               # DialogHelper, ProgressDialog, run_task
│   ├── i18n.py                  # Translations
│   ├── settings.py              # User preferences (settings.json)
│   ├── pkexec_helper.py         # PkexecHelper: the only caller of pkexec
│   └── terminal.py              # launch_in_terminal(), build_runner_command()
├── helpers/
│   ├── kernelcustom-helper            # Root helper (whitelisted actions)
│   └── kernelcustom-nvidia-installer  # Root NVIDIA .run installer
├── translations/                # fr.json, en.json
├── data/                        # .desktop file, icons, man page
├── com.kernelcustom.manager.policy   # PolicyKit actions
└── debian/                      # Debian packaging
```

---

## Installed Layout

```
/usr/bin/kernelcustom-manager                                    → launcher
/usr/lib/kernelcustom-manager/                                   → kernelcustom_manager.py, core, gui, utils, translations
/usr/libexec/kernelcustom-manager/kernelcustom-helper            → root helper (pkexec)
/usr/libexec/kernelcustom-manager/kernelcustom-nvidia-installer  → NVIDIA installer (pkexec)
/usr/share/polkit-1/actions/com.kernelcustom.manager.policy
/usr/share/applications/com.kernelcustom.manager.desktop
/usr/share/icons/hicolor/256x256/apps/com.kernelcustom.manager.png
/usr/share/man/man1/kernelcustom-manager.1.gz
```

The launcher adds `/usr/lib/kernelcustom-manager` to `sys.path` and calls `kernelcustom_manager.main()`.
The same code also runs from the git repository (`python3 kernelcustom_manager.py`): paths are
computed relative to `utils/paths.py`. The helpers, however, are always the installed copies.

Package details (`debian/`):
- `dh $@ --with python3`; `dh_python3 /usr/lib/kernelcustom-manager` byte-compiles the private directory.
- `dh_python3` is **not** run on `/usr/libexec`: it would rewrite the helpers' shebang and drop `-I`.
- `prerm` (remove) cancels a scheduled NVIDIA installation; `postrm` (purge) removes
  `/var/lib/kernelcustom-manager`. User data in `$HOME` is never touched.

---

## Layers

```
┌───────────────────────────────────────────────────────────────┐
│ gui/            GTK4 + libadwaita (main thread only)          │
│   main_window ── PAGES ──▶ *_tab.py ──▶ widgets.py            │
└──────────────┬──────────────────────────────┬─────────────────┘
               │ run_task (threads)           │ dialogs (async)
┌──────────────▼──────────────┐   ┌───────────▼─────────────────┐
│ core/  business logic       │   │ utils/  paths, i18n,        │
│ (no GTK, usable in threads) │──▶│ pkexec_helper, terminal     │
└──────────────┬──────────────┘   └───────────┬─────────────────┘
               │ subprocess (argument lists)  │ pkexec
               ▼                              ▼
     make, dpkg-query, apt-cache,    /usr/libexec/kernelcustom-manager/
     modinfo, sbverify, openssl…     kernelcustom-helper (root, whitelist)
```

Managers (`KernelManager`, `SecureBootManager`, `DriverManager`, `SourcesManager`,
`CleanupManager`) are created by the window and shared by the tabs through `main_window`.

---

## Paths and User Data

`utils/paths.py` is the only module that builds paths:

| Name | Value |
|---|---|
| `APP_ID` | `kernelcustom-manager` |
| `APPLICATION_ID` | `com.kernelcustom.manager` (GTK/D-Bus id, icon and .desktop name) |
| `APP_DIR` | directory containing the code (repository or `/usr/lib/kernelcustom-manager`) |
| `TRANSLATIONS_DIR`, `ICONS_DIR`, `BUILD_RUNNER` | inside `APP_DIR` |
| `HELPER_DIR` | `/usr/libexec/kernelcustom-manager` (fixed, referenced by the policy) |
| `data_dir()` | `$KCM_DATA_DIR`, else `$XDG_DATA_HOME/kernelcustom-manager`, else `~/.local/share/kernelcustom-manager` |
| `config_dir()` | `~/.config/kernelcustom-manager` (`language.conf`) |

Working directory content:
```
~/.local/share/kernelcustom-manager/
├── sources/linux-X.Y.Z/      # extracted sources
├── linux -> sources/linux-X.Y.Z   # active build tree
├── archive/                  # downloaded tarballs
├── kernels_repo/             # compiled .deb packages
├── configs/                  # .config backups (one per compilation)
├── profiles/                 # NAME.config + NAME.json
├── logs/                     # compile-*.log, *.job.json, *.status.json, kernelcustom-manager.log
├── drivers/, drivers_backup/ # NVIDIA downloads, driver backups
├── secureboot/keys/          # MOK.priv, MOK.der, MOK.pem
├── compilation_history.json, drivers_history.json
```

**Migration**: `paths.migrate_legacy_data()` runs in `main()` before the GUI is imported. It moves
the v2.x directory `~/KernelCustomManager/build`, rewrites internal absolute symlinks and keeps a
compatibility link if `/usr/src` links still point to the old location.

---

## Privileged Operations

`utils/pkexec_helper.py` (`PkexecHelper`) is the **only** code that calls `pkexec`. It runs one of
two helpers installed `root:root 0755` in `/usr/libexec/kernelcustom-manager/`:

| Program | PolicyKit action | Authentication |
|---|---|---|
| `kernelcustom-helper` | `com.kernelcustom.manager.helper` | `auth_admin_keep` (password remembered a few minutes) |
| `kernelcustom-nvidia-installer` | `com.kernelcustom.manager.nvidia` | `auth_admin` (asked **every time**: runs third-party code as root) |

The helpers are **standalone** (`#!/usr/bin/python3 -I`, no import from the application, whose
directory may be writable by the user) and **validate everything**:
- action name against a whitelist (`apt-install`, `install-debs`, `remove-packages`, `reboot`,
  `mokutil-*`, `sources-install`, `sources-link`, `sources-remove`, `sign-kernel`);
- package names and kernel versions with strict regular expressions;
- files must belong to the calling user (`PKEXEC_UID`); `sign-file` must belong to root, as well as
  its parent directories; vmlinuz must be in `/boot`;
- the running kernel cannot be removed; real Debian headers in `/usr/src` are never deleted.

`PkexecHelper.run()` returns `(ok, stdout, stderr)`; `stream()` forwards output line by line
(used for signing progress); `terminal_command()` builds the command for interactive `mokutil`
actions run in a terminal.

Adding a root operation = a new validated action in the helper + a method in `PkexecHelper` +
documentation in [POLICYKIT_README.md](POLICYKIT_README.md).

---

## User Interface (GTK4 + libadwaita)

**Application**: `KernelCustomApplication(Adw.Application)`, id `com.kernelcustom.manager`
(single instance). `do_startup` sets the icon and actions, `do_activate` creates the window.

**Window**: `gui/main_window.py` (`KernelManagerWindow`, `Adw.ApplicationWindow`). The `PAGES`
table lists the tabs: name, translation key, symbolic icon, module, `create_*_tab(main_window)`
function. The tabs live in an `Adw.ViewStack`; the `Adw.ViewSwitcher` in the header bar is
replaced by an `Adw.ViewSwitcherBar` at the bottom on narrow windows (breakpoint at 1550 sp).
Complex tabs are classes reachable from the window (`DriversPage`, `SecureBootPage`, `CleanupPage`).

**Dialogs** (`utils/dialogs.py`, `main_window.dialogs`) are all **asynchronous**: the code that
follows an answer is passed as a callback.
- `show_info` / `show_warning` / `show_error(title, message, on_close=None)`, `toast(message)`
- `ask(title, message, on_yes, on_no=None, destructive=False, yes_label=…)`
- `form(title, child, ok_label, on_ok)` (`Adw.AlertDialog`) and `window(…)` (`Adw.Dialog`)
- `progress(title, status, cancellable=False)` → `ProgressDialog`, usable from a thread
- `open_file(…)`, `save_file(…)` (`Gtk.FileDialog`)

**Threads**: `run_task(work, on_done, on_error)` runs `work()` in a thread and calls `on_done(result)`
in the GTK thread. It is used for every `pkexec`, network access, `apt-cache`, `make` and file scan.
Widgets are never touched from a thread (otherwise `GLib.idle_add`).

**Lazy loading**: slow work or work that asks for a password starts the first time a tab is shown
(`widgets.run_once_when_mapped`): SecureBoot diagnosis (a single `mokutil-diagnose` call, reused by
the key list) and the cleanup scan.

**Shared widgets** (`gui/widgets.py`): `SimpleList` (`Gtk.ColumnView`: `set_rows`, `append`,
`selected()` → `Row`), `section`, `page_box`, `title_label`, `markup_label`, `button`,
`button_row`, `labeled`, `entry`, `monospace_view`, `inner_tabs`, `info_bar`, `clear_box`.

---

## Kernel Compilation

```
Compile dialog (gui/build_tab_compile.py)
  │  validates LOCALVERSION (^[A-Za-z0-9._+~-]+$), backs up .config,
  │  disables module compression (signatures must stay valid),
  │  writes logs/compile-DATE.job.json (settings + already translated texts)
  ▼
utils/terminal.launch_in_terminal([python3, -I, core/build_runner.py, compile, job.json])
  │  first available terminal: ptyxis, gnome-terminal, kgx, konsole, xfce4-terminal, xterm
  ▼
core/build_runner.py (standalone, no application import)
  │  status.json = {"state": "running", "pid": …}
  │  make -jN [LOCALVERSION=…]            (output shown and written to the log)
  │  sign the .ko modules with the MOK key (optional, before packaging)
  │  make bindeb-pkg [LOCALVERSION=…] [CC=distcc …]
  │  move the .deb files to kernels_repo/
  │  status.json = {"state": "done", "returncode": …, "packages": […]}
  ▼
Monitoring thread in the application (_wait_for_status)
     reads status.json (the terminal's own exit code is useless: gnome-terminal returns at once),
     detects a closed terminal (pid gone), adds the history entry, sends a notification
```

Configuration (`gui/build_tab_config.py`): copy of the running system's config or of a file, then
`make olddefconfig`, then optionally `make nconfig` in a terminal (`build_runner.py nconfig`).

---

## SecureBoot

`core/secureboot_manager.py` (`SecureBootManager`):
- **State**: UEFI, SecureBoot (`mokutil --sb-state` and EFI variables), MOK key enrollment.
- **Keys**: `generate_signing_key()` creates `MOK.priv` / `MOK.der` / `MOK.pem` (RSA-2048,
  `openssl`) in `secureboot/keys/`; import, delete and reset through the helper (`mokutil-*`).
- **Diagnosis** (wizard): UEFI → SecureBoot → MOK key → for each custom kernel, a sample of the
  modules in `/lib/modules`, the modules in the initrd (`unmkinitramfs`) and vmlinuz (`sbverify`).
  Each problem comes with solutions and an action.
- **Signing**: `sign_kernel_complete()` signs the modules and vmlinuz of an installed kernel in a
  single helper call (`sign-kernel`); compressed modules are decompressed, signed and recompressed;
  the initramfs is regenerated.

`modinfo` (in `/usr/sbin`, added to `PATH` by `extend_path()` at startup) reads signatures without
root, including `.ko.xz` / `.ko.zst` modules.

---

## Cleanup

`core/cleanup_manager.py` (`CleanupManager`), also usable from the command line
(`python3 -m core.cleanup_manager [--keys]`, read only):
- `scan(include_keys=False)` → list of `CleanupItem` (category, path, size, action `delete` or
  `make_clean`, protected, reason, selected). Always called in a thread.
- Categories: `build_objects`, `archives`, `logs`, `driver_downloads` (selected by default),
  `sources`, `headers`, `packages`, `driver_backups`, `config_backups`, `secureboot_keys`.
- Protected (never removed): targets of `/usr/src` and `/lib/modules/*/build|source` links, sources
  and headers of the running kernel.
- `clean(items, progress_callback)` → `{freed, done, errors}`, **revalidates everything**
  (path inside the working directory, protection recomputed, keys only through their category).

---

## Internationalization

`utils/i18n.py`: `get_i18n()._("section.key", name=value)` reads `translations/<lang>.json`
(nested keys) and applies `str.format`. The key parameter is positional-only, so a variable can be
called `key`. Every user-visible text goes through it, and each key exists in both `fr.json` and
`en.json`. The language comes from `~/.config/kernelcustom-manager/language.conf`, else from the
system locale; it can be changed from the main menu (restart required).

---

## Logging and Notifications

- `setup_logging()` (in `kernelcustom_manager.py`) writes to the console and to
  `data_dir()/logs/kernelcustom-manager.log`. Modules only use `logging`.
- Uncaught exceptions (for example in a GTK callback) are written to the log by `sys.excepthook`.
- `KernelManager.notifier` is connected by the window to `app.notify()`. GNOME only shows a
  `Gio.Notification` when `com.kernelcustom.manager.desktop` is installed; otherwise (running from
  the repository) `org.freedesktop.Notifications` is used.

---

## Debian Specifics

- `/etc/os-release` has no `VERSION_ID` on testing/sid: use `platform.freedesktop_os_release()`
  and `/etc/debian_version`.
- Drivers from the repositories: NVIDIA = `nvidia-driver` (non-free), `nvidia-open-kernel-dkms`;
  AMD/Intel = Mesa + `firmware-amd-graphics` / `firmware-intel-graphics`. Versions are read with
  `apt-cache policy` under `LC_ALL=C`.
- From the official site: NVIDIA `.run` only, copied to `/var/lib/kernelcustom-manager/nvidia/`
  before running it; it can be scheduled for the next boot with a systemd service.
- `mokutil` may exit with a non-zero code even when its output is valid.
- Debian compresses modules (`CONFIG_MODULE_COMPRESS_XZ`): modules must be signed before
  compression, or re-signed after.
- `make bindeb-pkg` runs a `debian/rules` that calls `dh_*`: `debhelper` is a runtime dependency.
- Debian's config enables `CONFIG_DEBUG_INFO_BTF`: `pahole` is required to compile.

---

## Testing

```bash
python3 -m py_compile $(git ls-files '*.py')          # syntax
KCM_DATA_DIR=/tmp/kcm-test python3 kernelcustom_manager.py   # without touching your data
python3 -m core.cleanup_manager                       # cleanup inventory (read only)
dpkg-buildpackage -us -uc -b && lintian -I --pedantic ../kernelcustom-manager_*.changes
```

To run the interface without showing a window on your desktop, use the GTK Broadway backend:
```bash
gtk4-broadwayd :7 &
env -u DISPLAY -u WAYLAND_DISPLAY GDK_BACKEND=broadway BROADWAY_DISPLAY=:7 \
    KCM_DATA_DIR=/tmp/kcm-test python3 kernelcustom_manager.py
```
The application is single-instance: if it is already running in your session, a second launch only
activates the existing window (use `dbus-run-session` to isolate a test).
