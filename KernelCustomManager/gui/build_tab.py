"""
Onglet de compilation et configuration
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import subprocess
import threading
import os
import shutil
from pathlib import Path
from datetime import datetime
from utils.i18n import get_i18n


def create_build_tab(main_window):
    """Crée l'onglet de compilation"""
    i18n = get_i18n()

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
    box.set_margin_start(20)
    box.set_margin_end(20)
    box.set_margin_top(20)

    # === TÉLÉCHARGEMENT ===
    download_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    download_box.pack_start(Gtk.Label(label=i18n._("build.version_label")), False, False, 0)

    main_window.version_entry = Gtk.Entry()
    stable_version = get_stable_kernel_version()
    main_window.version_entry.set_text(stable_version or "6.11.6")
    download_box.pack_start(main_window.version_entry, True, True, 0)

    download_btn = Gtk.Button(label=i18n._("button.download"))
    download_btn.connect("clicked", lambda w: download_kernel(main_window))
    download_box.pack_start(download_btn, False, False, 0)

    update_btn = Gtk.Button(label=i18n._("button.update"))
    update_btn.set_tooltip_text(i18n._("tooltip.update_stable"))
    update_btn.connect("clicked", lambda w: auto_update_kernel(main_window))
    download_box.pack_start(update_btn, False, False, 0)
    
    box.pack_start(download_box, False, False, 0)
    
    # === CONFIGURATION ===
    config_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

    config_btn = Gtk.Button(label=i18n._("button.configure"))
    config_btn.connect("clicked", lambda w: configure_kernel(main_window))
    config_box.pack_start(config_btn, True, True, 0)

    import_btn = Gtk.Button(label=i18n._("button.import"))
    import_btn.connect("clicked", lambda w: import_config_dialog(main_window))
    config_box.pack_start(import_btn, True, True, 0)

    export_btn = Gtk.Button(label=i18n._("button.export"))
    export_btn.connect("clicked", lambda w: export_config_dialog(main_window))
    config_box.pack_start(export_btn, True, True, 0)

    box.pack_start(config_box, False, False, 0)

    # === COMPILATION ===
    compile_btn = Gtk.Button(label=i18n._("button.compile"))
    compile_btn.connect("clicked", lambda w: compile_kernel_dialog(main_window))
    box.pack_start(compile_btn, False, False, 0)
    
    return box


def get_stable_kernel_version():
    """Récupère la version stable depuis kernel.org"""
    try:
        import urllib.request
        import json
        
        url = "https://www.kernel.org/releases.json"
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
            
            for release in data.get('releases', []):
                if release.get('moniker') == 'stable':
                    return release.get('version')
        return None
    except:
        return None


def download_kernel(main_window):
    """Télécharge les sources du kernel"""
    i18n = get_i18n()
    version = main_window.version_entry.get_text().strip()

    if not version:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.enter_version"))
        return

    dialog = Gtk.Dialog(
        title=i18n._("dialog.download.title"),
        transient_for=main_window,
        flags=0
    )
    dialog.set_default_size(500, 150)

    content = dialog.get_content_area()
    content.set_spacing(10)
    content.set_margin_start(20)
    content.set_margin_end(20)
    content.set_margin_top(10)
    content.set_margin_bottom(10)

    status_label = Gtk.Label()
    status_label.set_text(i18n._("dialog.download.status", version=version))
    content.pack_start(status_label, False, False, 0)
    
    progress = Gtk.ProgressBar()
    progress.set_show_text(True)
    content.pack_start(progress, False, False, 0)

    dialog.add_button(i18n._("button.cancel"), Gtk.ResponseType.CANCEL)
    dialog.show_all()
    
    cancelled = [False]
    
    def on_cancel(d, r):
        if r == Gtk.ResponseType.CANCEL:
            cancelled[0] = True
    
    dialog.connect("response", on_cancel)
    
    def update_progress(percent, message=None):
        GLib.idle_add(lambda: progress.set_fraction(percent / 100.0))
        GLib.idle_add(lambda: progress.set_text(f"{percent}%"))
        if message:
            GLib.idle_add(lambda: status_label.set_text(message))
    
    def download_thread():
        try:
            success = main_window.kernel_manager.download_kernel(
                version,
                lambda p, m=None: update_progress(p, m) if not cancelled[0] else None
            )
            
            GLib.idle_add(dialog.destroy)

            if cancelled[0]:
                GLib.idle_add(main_window.dialogs.show_info, i18n._("message.info.title"), i18n._("message.info.cancelled"))
            elif success:
                GLib.idle_add(main_window.dialogs.show_info, i18n._("message.success.title"),
                            i18n._("message.success.kernel_downloaded", version=version))
            else:
                GLib.idle_add(main_window.dialogs.show_error, i18n._("message.error.title"),
                            i18n._("message.error.download_failed"))
        except Exception as e:
            GLib.idle_add(dialog.destroy)
            GLib.idle_add(main_window.dialogs.show_error, i18n._("message.error.title"), str(e))
    
    thread = threading.Thread(target=download_thread, daemon=True)
    thread.start()


def auto_update_kernel(main_window):
    """Mise à jour auto vers version stable"""
    i18n = get_i18n()
    stable = get_stable_kernel_version()

    if not stable:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.stable_version_failed"))
        return

    linux_dir = main_window.kernel_manager.base_dir / "linux"
    if linux_dir.exists():
        try:
            current = linux_dir.resolve().name.replace("linux-", "")
            if current == stable:
                main_window.dialogs.show_info(i18n._("message.info.already_uptodate"),
                    i18n._("message.success.already_updated", version=stable))
                return
        except:
            pass

    if main_window.dialogs.show_question(i18n._("message.confirm.title"),
        i18n._("message.confirm.update_available", version=stable)):
        main_window.version_entry.set_text(stable)
        download_kernel(main_window)


def configure_kernel(main_window):
    """Configure le kernel"""
    i18n = get_i18n()
    linux_dir = main_window.kernel_manager.base_dir / "linux"

    if not linux_dir.exists():
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_kernel_source"))
        return

    # Suite du code dans le prochain fichier...
    from gui.build_tab_config import show_config_dialog
    show_config_dialog(main_window)


def compile_kernel_dialog(main_window):
    """Dialogue de compilation"""
    from gui.build_tab_compile import show_compile_dialog
    show_compile_dialog(main_window)


def import_config_dialog(main_window):
    """Importe une configuration"""
    i18n = get_i18n()
    dialog = Gtk.FileChooserDialog(
        title=i18n._("dialog.import_config.title"),
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
        source = dialog.get_filename()
        if main_window.kernel_manager.import_config(source):
            main_window.dialogs.show_info(i18n._("message.success.title"), i18n._("message.success.config_imported"))
        else:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.import_failed"))

    dialog.destroy()


def export_config_dialog(main_window):
    """Exporte la configuration"""
    i18n = get_i18n()
    linux_dir = main_window.kernel_manager.base_dir / "linux"

    if not (linux_dir / ".config").exists():
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_config_export"))
        return

    dialog = Gtk.FileChooserDialog(
        title=i18n._("dialog.export_config.title"),
        parent=main_window,
        action=Gtk.FileChooserAction.SAVE
    )
    dialog.add_buttons(
        Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
        Gtk.STOCK_SAVE, Gtk.ResponseType.OK
    )

    try:
        kernel_version = linux_dir.resolve().name.replace("linux-", "")
        default_name = f"kernel-config-{kernel_version}.config"
    except:
        default_name = "kernel-config.config"

    dialog.set_current_name(default_name)

    response = dialog.run()

    if response == Gtk.ResponseType.OK:
        destination = dialog.get_filename()
        if main_window.kernel_manager.export_config(destination):
            main_window.dialogs.show_info(i18n._("message.success.title"), i18n._("message.success.config_exported"))
        else:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.export_failed"))

    dialog.destroy()
