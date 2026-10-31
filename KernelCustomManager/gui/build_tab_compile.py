"""
Module de compilation du kernel
"""

import json
import os
import re
import threading
import time
from datetime import datetime

from gi.repository import GLib, Gtk

from gui.widgets import entry, labeled, markup_label
from utils.i18n import get_i18n
from utils.terminal import launch_in_terminal, build_runner_command


LOCALVERSION_RE = re.compile(r'^[A-Za-z0-9._+~-]+$')


def find_signing_key(sb_manager):
    """Clé MOK utilisée pour signer à la compilation : (clé .priv, certificat .der) ou None"""
    keys = sorted(sb_manager.keys_dir.glob("*.priv"))
    key_file = next((k for k in keys if k.stem == "MOK"), keys[0] if keys else None)
    if key_file and key_file.with_suffix('.der').exists():
        return key_file, key_file.with_suffix('.der')
    return None


def show_compile_dialog(main_window):
    """Dialogue de compilation"""
    i18n = get_i18n()
    linux_dir = main_window.kernel_manager.base_dir / "linux"

    if not linux_dir.exists():
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_kernel_source"))
        return

    if not (linux_dir / ".config").exists():
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_config"))
        return

    form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

    cpus = os.cpu_count() or 1
    threads_spin = Gtk.SpinButton.new_with_range(1, cpus * 2, 1)
    threads_spin.set_value(cpus)
    form.append(labeled(i18n._("dialog.compile.threads"), threads_spin))

    suffix_entry = entry(placeholder=i18n._("dialog.compile.suffix_placeholder"))
    form.append(labeled(i18n._("dialog.compile.suffix"), suffix_entry))

    fakeroot_check = Gtk.CheckButton(label=i18n._("dialog.compile.use_fakeroot"), active=True)
    form.append(fakeroot_check)

    # Signature SecureBoot des modules avant la création des paquets
    sb_manager = main_window.secureboot_manager
    signing_key = find_signing_key(sb_manager)
    secureboot_check = Gtk.CheckButton(label=i18n._("dialog.compile.sign_for_secureboot"))
    form.append(secureboot_check)
    if signing_key:
        secureboot_check.set_active(sb_manager.should_prompt_for_signing())
        hint = i18n._("dialog.compile.secureboot_info") + f"\n🔑 {signing_key[0].name}"
    else:
        secureboot_check.set_sensitive(False)
        hint = i18n._("dialog.compile.no_signing_key")
    form.append(markup_label(f"<small><i>{GLib.markup_escape_text(hint)}</i></small>"))

    form.append(markup_label(f"<i>{i18n._('dialog.compile.estimated_time')}</i>"))

    def on_compile():
        compile_kernel(main_window, int(threads_spin.get_value()), suffix_entry.get_text().strip(),
                       fakeroot_check.get_active(), signing_key if secureboot_check.get_active() else None)

    main_window.dialogs.form(i18n._("dialog.compile.title"), form,
                             i18n._("dialog.compile.button_compile"), on_compile)


def compile_kernel(main_window, jobs, suffix, use_fakeroot, signing_key=None):
    """Lance la compilation dans un terminal"""
    i18n = get_i18n()
    linux_dir = main_window.kernel_manager.base_dir / "linux"

    # LOCALVERSION : caractères autorisés dans une version de kernel uniquement
    if suffix and not LOCALVERSION_RE.match(suffix):
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.invalid_suffix"))
        return

    try:
        kernel_version = linux_dir.resolve().name.replace("linux-", "")
    except Exception:
        kernel_version = "unknown"

    # Sauvegarder la config
    main_window.kernel_manager.backup_config(kernel_version, suffix)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = main_window.kernel_manager.log_dir / f"compile-{timestamp}.log"


    start_time = datetime.now()

    # Debian active CONFIG_MODULE_COMPRESS_XZ : on désactive la compression des modules
    # dans le .config pour que les signatures SecureBoot posées avant bindeb-pkg restent valides
    config_file = linux_dir / ".config"
    if config_file.exists():
        # Lire le fichier .config
        with open(config_file, 'r') as f:
            config_content = f.read()

        # Désactiver toutes les options de compression des modules
        config_modified = False

        # Désactiver CONFIG_MODULE_COMPRESS (option principale)
        if 'CONFIG_MODULE_COMPRESS=y' in config_content:
            config_content = config_content.replace('CONFIG_MODULE_COMPRESS=y', '# CONFIG_MODULE_COMPRESS is not set')
            config_modified = True

        # Désactiver CONFIG_MODULE_COMPRESS_ALL
        if 'CONFIG_MODULE_COMPRESS_ALL=y' in config_content:
            config_content = config_content.replace('CONFIG_MODULE_COMPRESS_ALL=y', '# CONFIG_MODULE_COMPRESS_ALL is not set')
            config_modified = True

        # Désactiver les algorithmes de compression spécifiques
        if 'CONFIG_MODULE_COMPRESS_XZ=y' in config_content:
            config_content = config_content.replace('CONFIG_MODULE_COMPRESS_XZ=y', '# CONFIG_MODULE_COMPRESS_XZ is not set')
            config_modified = True
        if 'CONFIG_MODULE_COMPRESS_GZIP=y' in config_content:
            config_content = config_content.replace('CONFIG_MODULE_COMPRESS_GZIP=y', '# CONFIG_MODULE_COMPRESS_GZIP is not set')
            config_modified = True
        if 'CONFIG_MODULE_COMPRESS_ZSTD=y' in config_content:
            config_content = config_content.replace('CONFIG_MODULE_COMPRESS_ZSTD=y', '# CONFIG_MODULE_COMPRESS_ZSTD is not set')
            config_modified = True

        # Ajouter CONFIG_MODULE_COMPRESS_NONE=y si pas présent
        if 'CONFIG_MODULE_COMPRESS_NONE' not in config_content:
            config_content += '\nCONFIG_MODULE_COMPRESS_NONE=y\n'
            config_modified = True
        elif 'CONFIG_MODULE_COMPRESS_NONE is not set' in config_content:
            config_content = config_content.replace('# CONFIG_MODULE_COMPRESS_NONE is not set', 'CONFIG_MODULE_COMPRESS_NONE=y')
            config_modified = True

        # Sauvegarder le .config modifié
        if config_modified:
            with open(config_file, 'w') as f:
                f.write(config_content)

    # Signature SecureBoot des modules AVANT bindeb-pkg (CONFIG_MODULE_COMPRESS_NONE=y
    # garantit que les modules restent en .ko)
    sign_config = None
    if signing_key:
        sign_config = {"key": str(signing_key[0]), "cert": str(signing_key[1])}

    suffix_label = suffix or i18n._("compilation.suffix_none")
    header = [
        i18n._("compilation.header"),
        i18n._("compilation.threads", count=jobs),
        i18n._("compilation.suffix", suffix=suffix_label),
        i18n._("compilation.fakeroot", status=(i18n._("compilation.fakeroot_yes") if use_fakeroot else i18n._("compilation.fakeroot_no"))),
    ]
    if sign_config:
        header.append(i18n._("compilation.secureboot_signing", key=sign_config["key"]))
    header += ["", i18n._("compilation.starting")]

    status_file = log_file.with_suffix(".status.json")
    job = {
        "linux_dir": str(linux_dir),
        "jobs": jobs,
        "localversion": suffix,
        "use_fakeroot": use_fakeroot,
        "log_file": str(log_file),
        "repo_dir": str(main_window.kernel_manager.repo_dir),
        "status_file": str(status_file),
        "sign": sign_config,
        "messages": {
            "header": header,
            "compiling_modules": i18n._("compilation.compiling_modules"),
            "creating_package": i18n._("compilation.creating_package"),
            "success": i18n._("compilation.success"),
            "failed": i18n._("compilation.failed"),
            "moving_packages": i18n._("compilation.moving_packages"),
            "press_enter": i18n._("compilation.press_enter"),
            "signing_header": i18n._("secureboot.signing_modules_before_packaging"),
            "found_modules": i18n._("secureboot.found_modules"),
            "no_modules": i18n._("secureboot.no_modules_found"),
            "sign_failed": i18n._("secureboot.failed_to_sign"),
            "signed_with_errors": i18n._("secureboot.modules_signed_with_errors"),
            "all_signed": i18n._("secureboot.all_modules_signed"),
        },
    }
    main_window.kernel_manager.log_dir.mkdir(parents=True, exist_ok=True)
    job_file = log_file.with_suffix(".job.json")
    job_file.write_text(json.dumps(job, ensure_ascii=False, indent=2))

    # Lancement dans un terminal : liste d'arguments, aucun `bash -c`
    if launch_in_terminal(build_runner_command("compile", job_file)) is None:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_terminal"))
        return

    main_window.dialogs.show_info(
        i18n._("message.success.title"),
        i18n._("message.info.compilation_launched", threads=jobs, suffix=suffix_label, log=str(log_file))
    )

    def monitor_compilation():
        """
        Suit la compilation via le fichier d'état écrit par build_runner
        (le processus du terminal peut se terminer immédiatement, ex. gnome-terminal)
        """
        status = _wait_for_status(status_file)
        duration = int((datetime.now() - start_time).total_seconds())
        success = status.get("returncode") == 0
        packages = status.get("packages", [])

        main_window.kernel_manager.add_compilation_to_history(
            kernel_version, suffix, success, duration, packages
        )

        if success:
            main_window.kernel_manager.send_notification(
                i18n._("message.success.compilation_success"),
                i18n._("message.success.compilation_success_notification", version=kernel_version, suffix=suffix, time=f"{duration//60}m {duration%60}s"),
                "normal"
            )
        else:
            main_window.kernel_manager.send_notification(
                i18n._("compilation.failed"),
                i18n._("compilation.failed_notification", version=kernel_version, suffix=suffix),
                "critical"
            )

    threading.Thread(target=monitor_compilation, daemon=True).start()


def _wait_for_status(status_file, start_timeout=120, poll=2):
    """
    Attend la fin de la compilation (state == "done").
    Retourne {"returncode": 1} si le runner n'a jamais démarré ou si son
    processus a disparu (terminal fermé) sans écrire de résultat.
    """
    waited = 0
    while True:
        try:
            status = json.loads(status_file.read_text())
        except (OSError, ValueError):
            status = None

        if status is None:
            if waited >= start_timeout:
                return {"returncode": 1}
        elif status.get("state") == "done":
            return status
        elif status.get("state") == "running" and not _pid_alive(status.get("pid")):
            return {"returncode": 1}

        time.sleep(poll)
        waited += poll


def _pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False
