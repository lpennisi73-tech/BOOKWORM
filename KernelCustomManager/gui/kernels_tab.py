"""
Onglet de gestion des kernels installés
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import subprocess
import threading
from pathlib import Path


def create_kernels_tab(main_window):
    """Crée l'onglet de gestion des kernels"""
    
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    
    # Info kernel actuel
    import platform
    current_kernel = platform.release()
    info_label = Gtk.Label()
    info_label.set_markup(f"<b>Kernel actif :</b> <span color='green'>{current_kernel}</span>")
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
    
    for i, title in enumerate(["Paquet", "Version"], 1):
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(title, renderer, text=i)
        column.set_resizable(True)
        kernels_view.append_column(column)
    
    scrolled.add(kernels_view)
    box.pack_start(scrolled, True, True, 0)
    
    # Boutons
    btn_box = Gtk.Box(spacing=5)
    
    refresh_btn = Gtk.Button(label="🔄 Actualiser")
    refresh_btn.connect("clicked", lambda w: refresh_kernels(main_window, kernels_store))
    btn_box.pack_start(refresh_btn, False, False, 0)
    
    remove_btn = Gtk.Button(label="🗑️ Supprimer")
    remove_btn.connect("clicked", lambda w: remove_kernel(main_window, kernels_view, kernels_store))
    btn_box.pack_start(remove_btn, False, False, 0)
    
    reboot_btn = Gtk.Button(label="🔄 Redémarrer")
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
    selection = view.get_selection()
    model, treeiter = selection.get_selected()
    
    if not treeiter:
        main_window.dialogs.show_error("Erreur", "Veuillez sélectionner un kernel à supprimer")
        return
    
    mark = model[treeiter][0]
    package = model[treeiter][1]
    
    if mark == "✓":
        import platform
        current = platform.release()
        main_window.dialogs.show_error(
            "Impossible",
            f"Impossible de supprimer le kernel actif !\n\n"
            f"Kernel actif: {current}\n\n"
            f"Redémarrez sur un autre kernel avant."
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
        "Confirmer la suppression",
        f"Les paquets suivants seront supprimés :\n\n• {packages_list}\n\nCette action est irréversible !"
    ):
        return
    
    # Dialogue de progression
    dialog = Gtk.Dialog(
        title="Suppression du kernel",
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
    status_label.set_text("Suppression des paquets...")
    content.pack_start(status_label, False, False, 0)
    
    progress = Gtk.ProgressBar()
    progress.set_show_text(True)
    content.pack_start(progress, False, False, 0)
    
    dialog.show_all()
    
    def remove_thread():
        try:
            GLib.idle_add(lambda: status_label.set_text(f"Suppression de {len(related_packages)} paquet(s)..."))
            GLib.idle_add(lambda: progress.set_fraction(0.5))
            GLib.idle_add(lambda: progress.set_text("50%"))
            
            subprocess.run(
                ["pkexec", "apt", "purge", "-y"] + related_packages,
                capture_output=True,
                text=True,
                check=True
            )
            
            GLib.idle_add(lambda: status_label.set_text("Nettoyage..."))
            GLib.idle_add(lambda: progress.set_fraction(0.9))
            GLib.idle_add(lambda: progress.set_text("90%"))
            
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
                "✅ Suppression réussie",
                f"Kernel et paquets associés supprimés :\n\n• {packages_list}"
            )
            
            GLib.idle_add(lambda: refresh_kernels(main_window, store))
            
        except Exception as e:
            GLib.idle_add(dialog.destroy)
            GLib.idle_add(main_window.dialogs.show_error, "❌ Erreur", f"Échec de la suppression:\n{e}")
    
    thread = threading.Thread(target=remove_thread, daemon=True)
    thread.start()


def reboot_system(main_window):
    """Redémarre le système"""
    if main_window.dialogs.show_question(
        "Confirmer le redémarrage",
        "Voulez-vous vraiment redémarrer le système maintenant ?\n\n"
        "Assurez-vous d'avoir sauvegardé votre travail."
    ):
        try:
            subprocess.run(["pkexec", "systemctl", "reboot"], check=True)
        except Exception as e:
            main_window.dialogs.show_error("Erreur", f"Impossible de redémarrer:\n{e}")
