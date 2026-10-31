"""
Module de configuration du kernel
"""

import platform
import re
import shutil
import subprocess
from pathlib import Path

from gi.repository import Gtk

from gui.widgets import markup_label
from utils.dialogs import run_task
from utils.i18n import get_i18n
from utils.terminal import launch_in_terminal, build_runner_command


def show_config_dialog(main_window):
    """Affiche le dialogue de configuration"""
    i18n = get_i18n()
    if not (main_window.kernel_manager.base_dir / "linux").exists():
        main_window.dialogs.show_error(i18n._("message.error.title"),
                                       i18n._("message.error.no_kernel_source_download"))
        return

    form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    form.append(markup_label(f"<b>{i18n._('dialog.configure.choose_method')}</b>"))
    system_radio = Gtk.CheckButton(label=i18n._("dialog.configure.system_config"), active=True)
    file_radio = Gtk.CheckButton(label=i18n._("dialog.configure.file_config"), group=system_radio)
    menuconfig_check = Gtk.CheckButton(label=i18n._("dialog.configure.run_menuconfig"), active=True)
    for widget in (system_radio, file_radio, menuconfig_check):
        form.append(widget)

    def on_ok():
        run_menuconfig = menuconfig_check.get_active()
        if system_radio.get_active():
            configure_from_system(main_window, run_menuconfig)
        else:
            configure_from_file(main_window, run_menuconfig)

    main_window.dialogs.form(i18n._("dialog.configure.title"), form,
                             i18n._("dialog.configure.button_configure"), on_ok)


def _apply_config(main_window, source, run_menuconfig, success_message, error_key, clear_keys):
    """Copie source vers .config puis `make olddefconfig` (dans un thread)"""
    i18n = get_i18n()
    linux_dir = main_window.kernel_manager.base_dir / "linux"
    dest_config = linux_dir / ".config"

    def work():
        shutil.copy(source, dest_config)
        if clear_keys:
            # Adaptation Debian : pas de clés de confiance intégrées (sinon la compilation échoue)
            clear_system_keys(dest_config)
        subprocess.run(["make", "olddefconfig"], cwd=str(linux_dir), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def done(_result):
        _refresh_build_label(main_window)
        if run_menuconfig:
            run_menuconfig_terminal(main_window)
        else:
            main_window.dialogs.show_info(i18n._("message.success.title"), success_message)

    def failed(error):
        if isinstance(error, FileNotFoundError) and error.filename == "make":
            error = i18n._("message.error.make_missing")
        elif isinstance(error, subprocess.CalledProcessError) and error.stderr:
            error = error.stderr.decode(errors="replace").strip()
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._(error_key, error=str(error)))

    run_task(work, done, failed)


def _refresh_build_label(main_window):
    from gui.build_tab import update_source_label
    update_source_label(main_window)


def configure_from_system(main_window, run_menuconfig=True):
    """Configure depuis la config du kernel en cours (/boot/config-*)"""
    i18n = get_i18n()
    config_file = Path(f"/boot/config-{platform.release()}")

    if not config_file.exists():
        main_window.dialogs.show_error(i18n._("message.error.title"),
                                       i18n._("message.error.system_config_not_found", path=str(config_file)))
        return

    _apply_config(main_window, config_file, run_menuconfig, i18n._("message.success.config_applied"),
                  "message.error.config_failed", clear_keys=True)


def configure_from_file(main_window, run_menuconfig=True):
    """Configure depuis un fichier choisi par l'utilisateur"""
    i18n = get_i18n()
    from gui.build_tab import config_filters

    def on_selected(path):
        _apply_config(main_window, Path(path), run_menuconfig,
                      i18n._("message.success.config_loaded", path=path),
                      "message.error.load_failed", clear_keys=False)

    main_window.dialogs.open_file(i18n._("message.error.select_config_file"), on_selected, config_filters())


def clear_system_keys(config_path):
    """Vide CONFIG_SYSTEM_TRUSTED_KEYS et CONFIG_SYSTEM_REVOCATION_KEYS (clés Debian absentes)"""
    content = config_path.read_text()
    for option in ("CONFIG_SYSTEM_TRUSTED_KEYS", "CONFIG_SYSTEM_REVOCATION_KEYS"):
        content = re.sub(rf'^{option}=.*$', f'{option}=""', content, flags=re.MULTILINE)
    config_path.write_text(content)


def run_menuconfig_terminal(main_window):
    """Lance make nconfig dans un terminal (liste d'arguments, aucun `bash -c`)"""
    i18n = get_i18n()
    linux_dir = main_window.kernel_manager.base_dir / "linux"

    command = build_runner_command("nconfig", linux_dir, i18n._('misc.menuconfig_prompt'))
    if launch_in_terminal(command) is None:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_terminal"))
