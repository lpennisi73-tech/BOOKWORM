"""
Module de configuration du kernel
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
import subprocess
import shutil
from pathlib import Path
from utils.i18n import get_i18n


def show_config_dialog(main_window):
    """Affiche le dialogue de configuration"""
    i18n = get_i18n()
    linux_dir = main_window.kernel_manager.base_dir / "linux"

    if not linux_dir.exists():
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_kernel_source_download"))
        return

    dialog = Gtk.Dialog(
        title=i18n._("dialog.configure.title"),
        transient_for=main_window,
        flags=0
    )
    dialog.set_default_size(500, 200)

    content = dialog.get_content_area()
    content.set_spacing(15)
    content.set_margin_start(20)
    content.set_margin_end(20)
    content.set_margin_top(10)
    content.set_margin_bottom(10)

    label = Gtk.Label()
    label.set_markup(f"<b>{i18n._('dialog.configure.choose_method')}</b>")
    content.pack_start(label, False, False, 0)

    system_radio = Gtk.RadioButton.new_with_label_from_widget(None, i18n._("dialog.configure.system_config"))
    content.pack_start(system_radio, False, False, 0)

    file_radio = Gtk.RadioButton.new_with_label_from_widget(system_radio, i18n._("dialog.configure.file_config"))
    content.pack_start(file_radio, False, False, 0)

    menuconfig_check = Gtk.CheckButton(label=i18n._("dialog.configure.run_menuconfig"))
    menuconfig_check.set_active(True)
    content.pack_start(menuconfig_check, False, False, 0)

    dialog.add_button(i18n._("button.cancel"), Gtk.ResponseType.CANCEL)
    dialog.add_button(i18n._("dialog.configure.button_configure"), Gtk.ResponseType.OK)
    
    dialog.show_all()
    response = dialog.run()
    
    if response == Gtk.ResponseType.OK:
        use_system = system_radio.get_active()
        run_menuconfig = menuconfig_check.get_active()
        
        if use_system:
            configure_from_system(main_window, run_menuconfig)
        else:
            configure_from_file(main_window, run_menuconfig)
    
    dialog.destroy()


def configure_from_system(main_window, run_menuconfig=True):
    """Configure depuis la config système"""
    i18n = get_i18n()
    import platform

    current_kernel = platform.release()
    config_file = Path(f"/boot/config-{current_kernel}")

    if not config_file.exists():
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.system_config_not_found", path=str(config_file)))
        return
    
    linux_dir = main_window.kernel_manager.base_dir / "linux"
    dest_config = linux_dir / ".config"
    
    try:
        shutil.copy(config_file, dest_config)
        
        # Adaptation pour Ubuntu/Debian
        subprocess.run(
            ["sed", "-i", 's/CONFIG_SYSTEM_TRUSTED_KEYS=.*/CONFIG_SYSTEM_TRUSTED_KEYS=""/', str(dest_config)],
            check=True
        )
        subprocess.run(
            ["sed", "-i", 's/CONFIG_SYSTEM_REVOCATION_KEYS=.*/CONFIG_SYSTEM_REVOCATION_KEYS=""/', str(dest_config)],
            check=True
        )
        
        subprocess.run(
            ["make", "olddefconfig"],
            cwd=str(linux_dir),
            check=True
        )
        
        if run_menuconfig:
            run_menuconfig_terminal(main_window)
        else:
            main_window.dialogs.show_info(i18n._("message.success.title"), i18n._("message.success.config_applied"))

    except Exception as e:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.config_failed", error=str(e)))


def configure_from_file(main_window, run_menuconfig=True):
    """Configure depuis un fichier"""
    i18n = get_i18n()
    dialog = Gtk.FileChooserDialog(
        title=i18n._("message.error.select_config_file"),
        parent=main_window,
        action=Gtk.FileChooserAction.OPEN
    )
    dialog.add_buttons(
        Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
        Gtk.STOCK_OPEN, Gtk.ResponseType.OK
    )

    filter_config = Gtk.FileFilter()
    filter_config.set_name(i18n._("dialog.import_config.filter_name"))
    filter_config.add_pattern("*.config")
    filter_config.add_pattern("*.conf")
    dialog.add_filter(filter_config)
    
    response = dialog.run()
    
    if response == Gtk.ResponseType.OK:
        config_file = Path(dialog.get_filename())
        linux_dir = main_window.kernel_manager.base_dir / "linux"
        dest_config = linux_dir / ".config"
        
        try:
            shutil.copy(config_file, dest_config)
            
            subprocess.run(
                ["make", "olddefconfig"],
                cwd=str(linux_dir),
                check=True
            )
            
            if run_menuconfig:
                run_menuconfig_terminal(main_window)
            else:
                main_window.dialogs.show_info(i18n._("message.success.title"), i18n._("message.success.config_loaded", path=str(config_file)))

        except Exception as e:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.load_failed", error=str(e)))

    dialog.destroy()


def run_menuconfig_terminal(main_window):
    """Lance menuconfig dans un terminal"""
    i18n = get_i18n()
    linux_dir = main_window.kernel_manager.base_dir / "linux"

    terminals = [
        ["gnome-terminal", "--", "bash", "-c"],
        ["ptyxis", "--", "bash", "-c"],
        ["konsole", "-e", "bash", "-c"],
        ["xterm", "-e", "bash", "-c"]
    ]

    cmd = f"cd '{linux_dir}' && make nconfig; read -p '{i18n._('misc.menuconfig_prompt')}'"

    for terminal in terminals:
        try:
            subprocess.Popen(terminal + [cmd])
            return
        except FileNotFoundError:
            continue

    main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_terminal"))
