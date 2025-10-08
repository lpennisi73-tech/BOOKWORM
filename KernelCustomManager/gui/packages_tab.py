"""
Onglet de gestion des paquets locaux
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import subprocess
import threading
import re
from pathlib import Path


def create_packages_tab(main_window):
    """Crée l'onglet de gestion des paquets"""
    
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    
    # Liste des paquets
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_vexpand(True)
    
    packages_store = Gtk.ListStore(str, str)  # name, size
    packages_view = Gtk.TreeView(model=packages_store)
    
    for i, title in enumerate(["Paquet", "Taille"]):
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(title, renderer, text=i)
        column.set_resizable(True)
        packages_view.append_column(column)
    
    scrolled.add(packages_view)
    box.pack_start(scrolled, True, True, 0)
    
    # Boutons
    btn_box = Gtk.Box(spacing=5)
    
    refresh_btn = Gtk.Button(label="🔄 Actualiser")
    refresh_btn.connect("clicked", lambda w: refresh_packages(main_window, packages_store))
    btn_box.pack_start(refresh_btn, False, False, 0)
    
    install_btn = Gtk.Button(label="📥 Installer")
    install_btn.connect("clicked", lambda w: install_package(main_window, packages_view, packages_store))
    btn_box.pack_start(install_btn, False, False, 0)
    
    box.pack_start(btn_box, False, False, 0)
    
    refresh_packages(main_window, packages_store)
    
    return box


def refresh_packages(main_window, store):
    """Actualise la liste des paquets"""
    store.clear()
    for pkg in main_window.kernel_manager.get_local_packages():
        store.append([pkg['name'], pkg['size']])


def install_package(main_window, view, store):
    """Installe un paquet sélectionné"""
    selection = view.get_selection()
    model, treeiter = selection.get_selected()
    
    if not treeiter:
        main_window.dialogs.show_error("Erreur", "Veuillez sélectionner un paquet à installer")
        return
    
    package_name = model[treeiter][0]
    package_path = main_window.kernel_manager.repo_dir / package_name
    
    # Chercher les headers correspondants
    match = re.search(r'linux-image-([^_]+)', package_name)
    if match:
        kernel_version = match.group(1)
        headers_pkg = f"linux-headers-{kernel_version}"
        
        headers_file = None
        for deb in main_window.kernel_manager.repo_dir.glob(f"{headers_pkg}*.deb"):
            headers_file = deb
            break
    else:
        headers_file = None
    
    # Dialogue d'options
    dialog = Gtk.Dialog(
        title="Options d'installation",
        transient_for=main_window,
        flags=0
    )
    dialog.set_default_size(450, 200)
    
    content = dialog.get_content_area()
    content.set_spacing(15)
    content.set_margin_start(20)
    content.set_margin_end(20)
    content.set_margin_top(10)
    content.set_margin_bottom(10)
    
    info = Gtk.Label()
    info.set_markup(f"<b>Installation de :</b>\n{package_name}")
    info.set_halign(Gtk.Align.START)
    content.pack_start(info, False, False, 0)
    
    headers_check = Gtk.CheckButton(label="Installer aussi les headers")
    if headers_file:
        headers_check.set_active(True)
        headers_check.set_sensitive(True)
        headers_label = Gtk.Label()
        headers_label.set_markup(f"<small>{headers_file.name}</small>")
        headers_label.set_halign(Gtk.Align.START)
        headers_label.set_margin_start(30)
        content.pack_start(headers_check, False, False, 0)
        content.pack_start(headers_label, False, False, 0)
    else:
        headers_check.set_active(False)
        headers_check.set_sensitive(False)
        headers_check.set_label("Installer aussi les headers (non disponibles)")
        content.pack_start(headers_check, False, False, 0)
    
    dialog.add_button("Annuler", Gtk.ResponseType.CANCEL)
    dialog.add_button("📥 Installer", Gtk.ResponseType.OK)
    
    dialog.show_all()
    response = dialog.run()
    
    if response != Gtk.ResponseType.OK:
        dialog.destroy()
        return
    
    install_headers = headers_check.get_active() and headers_file is not None
    dialog.destroy()
    
    # Installation avec progression
    progress_dialog = Gtk.Dialog(
        title="Installation du kernel",
        transient_for=main_window,
        flags=0
    )
    progress_dialog.set_default_size(500, 150)
    
    content = progress_dialog.get_content_area()
    content.set_spacing(10)
    content.set_margin_start(20)
    content.set_margin_end(20)
    content.set_margin_top(10)
    content.set_margin_bottom(10)
    
    status_label = Gtk.Label()
    status_label.set_text("Préparation de l'installation...")
    content.pack_start(status_label, False, False, 0)
    
    progress = Gtk.ProgressBar()
    progress.set_show_text(True)
    content.pack_start(progress, False, False, 0)
    
    progress_dialog.show_all()
    
    def install_thread():
        try:
            packages_to_install = [str(package_path)]
            if install_headers:
                packages_to_install.append(str(headers_file))
            
            total_steps = len(packages_to_install) + 1
            current_step = 0
            
            for pkg in packages_to_install:
                current_step += 1
                pkg_name = Path(pkg).name
                pct = int((current_step / total_steps) * 70)
                
                GLib.idle_add(lambda n=pkg_name, p=pct: status_label.set_text(f"Installation de {n}..."))
                GLib.idle_add(lambda p=pct: progress.set_fraction(p / 100.0))
                GLib.idle_add(lambda p=pct: progress.set_text(f"{p}%"))
                
                result = subprocess.run(
                    ["pkexec", "dpkg", "-i", pkg],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    raise Exception(f"dpkg error: {result.stderr}")
            
            GLib.idle_add(lambda: status_label.set_text("Résolution des dépendances..."))
            GLib.idle_add(lambda: progress.set_fraction(0.85))
            GLib.idle_add(lambda: progress.set_text("85%"))
            
            subprocess.run(
                ["pkexec", "apt", "-f", "install", "-y"],
                capture_output=True,
                text=True,
                check=True
            )
            
            GLib.idle_add(lambda: progress.set_fraction(1.0))
            GLib.idle_add(lambda: progress.set_text("100%"))
            GLib.idle_add(progress_dialog.destroy)
            
            installed_list = "\n• ".join([Path(p).name for p in packages_to_install])
            GLib.idle_add(
                main_window.dialogs.show_info,
                "✅ Installation réussie !",
                f"Paquets installés :\n\n• {installed_list}\n\n"
                f"🔄 Redémarrez votre système pour utiliser le nouveau kernel."
            )
            
        except Exception as e:
            GLib.idle_add(progress_dialog.destroy)
            GLib.idle_add(main_window.dialogs.show_error, "❌ Erreur d'installation", str(e))
    
    thread = threading.Thread(target=install_thread, daemon=True)
    thread.start()
