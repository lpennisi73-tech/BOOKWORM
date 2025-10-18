"""
Onglet de gestion des kernels installés
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import subprocess
import threading
from pathlib import Path
from utils.i18n import get_i18n
from utils.pkexec_helper import PkexecHelper


def create_kernels_tab(main_window):
    """Crée l'onglet de gestion des kernels"""
    i18n = get_i18n()

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

    # Info kernel actuel
    import platform
    current_kernel = platform.release()
    info_label = Gtk.Label()
    info_label.set_markup(f"<b>{i18n._('kernel.active')}</b> <span color='green'>{current_kernel}</span>")
    info_label.set_halign(Gtk.Align.START)
    box.pack_start(info_label, False, False, 5)
    
    # Liste des kernels
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_vexpand(True)
    
    kernels_store = Gtk.ListStore(str, str, str)  # mark, package, version
    kernels_view = Gtk.TreeView(model=kernels_store)
    
    # Colonnes
    renderer = Gtk.CellRendererText()
    column = Gtk.TreeViewColumn("", renderer, text=0)
    column.set_min_width(30)
    kernels_view.append_column(column)

    for i, title in enumerate([i18n._("kernel.column_package"), i18n._("kernel.column_version")], 1):
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(title, renderer, text=i)
        column.set_resizable(True)
        kernels_view.append_column(column)
    
    scrolled.add(kernels_view)
    box.pack_start(scrolled, True, True, 0)
    
    # Boutons
    btn_box = Gtk.Box(spacing=5)

    refresh_btn = Gtk.Button(label=i18n._("button.refresh"))
    refresh_btn.connect("clicked", lambda w: refresh_kernels(main_window, kernels_store))
    btn_box.pack_start(refresh_btn, False, False, 0)

    remove_btn = Gtk.Button(label=i18n._("button.remove"))
    remove_btn.connect("clicked", lambda w: remove_kernel(main_window, kernels_view, kernels_store))
    btn_box.pack_start(remove_btn, False, False, 0)

    reboot_btn = Gtk.Button(label=i18n._("button.reboot"))
    reboot_btn.connect("clicked", lambda w: reboot_system(main_window))
    btn_box.pack_start(reboot_btn, False, False, 0)
    
    box.pack_start(btn_box, False, False, 0)
    
    # Charger les données
    refresh_kernels(main_window, kernels_store)
    
    return box


def refresh_kernels(main_window, store):
    """Actualise la liste des kernels"""
    import platform
    current = platform.release()
    
    store.clear()
    for kernel in main_window.kernel_manager.get_installed_kernels():
        is_active = current in kernel['package']
        mark = "✓" if is_active else ""
        store.append([mark, kernel['package'], kernel['version']])


def remove_kernel(main_window, view, store):
    """Supprime un kernel sélectionné"""
    i18n = get_i18n()
    selection = view.get_selection()
    model, treeiter = selection.get_selected()

    if not treeiter:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.select_kernel"))
        return

    mark = model[treeiter][0]
    package = model[treeiter][1]

    if mark == "✓":
        import platform
        current = platform.release()
        main_window.dialogs.show_error(
            i18n._("misc.impossible"),
            i18n._("message.error.active_kernel", kernel=current)
        )
        return
    
    kernel_version = package.replace("linux-image-", "")
    
    # Trouver les paquets associés
    related_packages = []
    try:
        result = subprocess.run(
            ["dpkg", "-l"],
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.splitlines():
            if line.startswith("ii") and kernel_version in line:
                parts = line.split()
                if len(parts) >= 2:
                    pkg_name = parts[1]
                    if any(x in pkg_name for x in ["linux-image-", "linux-headers-"]):
                        related_packages.append(pkg_name)
    except:
        related_packages = [package]
    
    packages_list = "\n• ".join(related_packages)

    if not main_window.dialogs.show_question(
        i18n._("message.confirm.title"),
        i18n._("message.confirm.delete_kernel", packages=packages_list)
    ):
        return

    # Dialogue de progression
    dialog = Gtk.Dialog(
        title=i18n._("dialog.remove_kernel.title"),
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
    status_label.set_text(i18n._("dialog.remove_kernel.status"))
    content.pack_start(status_label, False, False, 0)
    
    progress = Gtk.ProgressBar()
    progress.set_show_text(True)
    content.pack_start(progress, False, False, 0)
    
    dialog.show_all()
    
    def remove_thread():
        try:
            GLib.idle_add(lambda: status_label.set_text(i18n._("dialog.remove_kernel.status_count", count=len(related_packages))))
            GLib.idle_add(lambda: progress.set_fraction(0.5))
            GLib.idle_add(lambda: progress.set_text("50%"))

            # Use PolicyKit helper - only asks for password once
            if PkexecHelper.is_helper_installed():
                success, stdout, stderr = PkexecHelper.remove_packages(*related_packages)
                if not success:
                    raise Exception(f"Removal failed: {stderr}")
            else:
                # Fallback to old method if helper not installed
                subprocess.run(
                    ["pkexec", "apt", "purge", "-y"] + related_packages,
                    capture_output=True,
                    text=True,
                    check=True
                )

                subprocess.run(
                    ["pkexec", "apt", "autoremove", "-y"],
                    capture_output=True,
                    text=True,
                    check=True
                )

            GLib.idle_add(lambda: progress.set_fraction(1.0))
            GLib.idle_add(lambda: progress.set_text("100%"))
            GLib.idle_add(dialog.destroy)

            GLib.idle_add(
                main_window.dialogs.show_info,
                i18n._("message.success.title"),
                i18n._("message.success.kernel_deleted", packages=packages_list)
            )

            GLib.idle_add(lambda: refresh_kernels(main_window, store))

        except Exception as e:
            GLib.idle_add(dialog.destroy)
            GLib.idle_add(main_window.dialogs.show_error, i18n._("message.error.title"), i18n._("message.error.remove_failed", error=str(e)))
    
    thread = threading.Thread(target=remove_thread, daemon=True)
    thread.start()


def reboot_system(main_window):
    """Redémarre le système"""
    i18n = get_i18n()
    if main_window.dialogs.show_question(
        i18n._("message.confirm.title"),
        i18n._("message.confirm.reboot")
    ):
        try:
            # Use PolicyKit helper - only asks for password once
            if PkexecHelper.is_helper_installed():
                success, stdout, stderr = PkexecHelper.reboot()
                if not success:
                    raise Exception(f"Reboot failed: {stderr}")
            else:
                # Fallback to old method if helper not installed
                subprocess.run(["pkexec", "systemctl", "reboot"], check=True)
        except Exception as e:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.reboot_failed", error=str(e)))
