"""
Onglet de gestion des sources dans /usr/src/
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import subprocess
import threading
from pathlib import Path
from utils.i18n import get_i18n
from utils.pkexec_helper import PkexecHelper


def create_sources_tab(main_window):
    """Crée l'onglet de gestion des sources système"""
    i18n = get_i18n()

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

    # Info
    info = Gtk.Label()
    info.set_markup(f"<b>{i18n._('sources.title')}</b>\n{i18n._('sources.subtitle')}")
    info.set_halign(Gtk.Align.START)
    box.pack_start(info, False, False, 5)
    
    # Panneau divisé
    paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
    
    # === Sources disponibles (gauche) ===
    left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

    left_label = Gtk.Label()
    left_label.set_markup(f"<b>{i18n._('sources.available')}</b>\n{i18n._('sources.available_subtitle')}")
    left_box.pack_start(left_label, False, False, 0)

    scrolled_left = Gtk.ScrolledWindow()
    scrolled_left.set_vexpand(True)

    available_store = Gtk.ListStore(str)
    available_view = Gtk.TreeView(model=available_store)

    renderer = Gtk.CellRendererText()
    column = Gtk.TreeViewColumn(i18n._("sources.column_version"), renderer, text=0)
    available_view.append_column(column)
    
    scrolled_left.add(available_view)
    left_box.pack_start(scrolled_left, True, True, 0)
    
    # Boutons d'installation
    install_btn = Gtk.Button(label=i18n._("sources.button_copy"))
    install_btn.connect("clicked", lambda w: install_to_usr_src(main_window, available_view, available_store, installed_store))
    left_box.pack_start(install_btn, False, False, 0)

    link_btn = Gtk.Button(label=i18n._("sources.button_link_simple"))
    link_btn.connect("clicked", lambda w: link_to_usr_src(main_window, available_view, available_store, installed_store, False))
    left_box.pack_start(link_btn, False, False, 0)

    link_suffix_btn = Gtk.Button(label=i18n._("sources.button_link_suffix"))
    link_suffix_btn.connect("clicked", lambda w: link_to_usr_src(main_window, available_view, available_store, installed_store, True))
    left_box.pack_start(link_suffix_btn, False, False, 0)
    
    paned.add1(left_box)
    
    # === Sources installées (droite) ===
    right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

    right_label = Gtk.Label()
    right_label.set_markup(f"<b>{i18n._('sources.installed')}</b>\n{i18n._('sources.installed_subtitle')}")
    right_box.pack_start(right_label, False, False, 0)

    scrolled_right = Gtk.ScrolledWindow()
    scrolled_right.set_vexpand(True)

    installed_store = Gtk.ListStore(str, str)
    installed_view = Gtk.TreeView(model=installed_store)

    for i, title in enumerate([i18n._("sources.column_version"), i18n._("sources.column_active")]):
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(title, renderer, text=i)
        installed_view.append_column(column)
    
    scrolled_right.add(installed_view)
    right_box.pack_start(scrolled_right, True, True, 0)
    
    # Boutons
    btn_box = Gtk.Box(spacing=5)

    refresh_btn = Gtk.Button(label=i18n._("button.refresh"))
    refresh_btn.connect("clicked", lambda w: refresh_sources(main_window, available_store, installed_store))
    btn_box.pack_start(refresh_btn, False, False, 0)

    remove_btn = Gtk.Button(label=i18n._("button.remove"))
    remove_btn.connect("clicked", lambda w: remove_from_usr_src(main_window, installed_view, available_store, installed_store))
    btn_box.pack_start(remove_btn, False, False, 0)
    
    right_box.pack_start(btn_box, False, False, 0)
    
    paned.add2(right_box)
    
    box.pack_start(paned, True, True, 0)
    
    refresh_sources(main_window, available_store, installed_store)
    
    return box


def refresh_sources(main_window, available_store, installed_store):
    """Actualise la liste des sources"""
    
    available_store.clear()
    sources_dir = main_window.kernel_manager.sources_dir
    if sources_dir.exists():
        for src in sorted(sources_dir.glob("linux-*")):
            if src.is_dir():
                version = src.name.replace("linux-", "")
                available_store.append([version])
    
    installed_store.clear()
    usr_src = Path("/usr/src")
    
    active_link = ""
    linux_link = usr_src / "linux"
    if linux_link.is_symlink():
        target = linux_link.readlink()
        active_link = str(target).replace("linux-", "")
    
    if usr_src.exists():
        for src in sorted(usr_src.glob("linux-[0-9]*")):
            if src.is_dir() or src.is_symlink():
                version = src.name.replace("linux-", "")
                is_active = "✓" if version == active_link else ""
                installed_store.append([version, is_active])


def link_to_usr_src(main_window, view, available_store, installed_store, with_suffix):
    """Crée un lien symbolique dans /usr/src/"""
    i18n = get_i18n()
    selection = view.get_selection()
    model, treeiter = selection.get_selected()

    if not treeiter:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.select_version"))
        return

    base_version = model[treeiter][0]

    if with_suffix:
        # Demander le suffixe complet
        dialog = Gtk.Dialog(
            title=i18n._("dialog.suffix_dkms.title"),
            transient_for=main_window,
            flags=0
        )
        dialog.set_default_size(400, 150)

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_start(20)
        content.set_margin_end(20)
        content.set_margin_top(10)
        content.set_margin_bottom(10)

        info = Gtk.Label()
        info.set_markup(f"<b>{i18n._('dialog.suffix_dkms.base_version', version=base_version)}</b>\n\n{i18n._('dialog.suffix_dkms.info')}")
        info.set_halign(Gtk.Align.START)
        content.pack_start(info, False, False, 0)

        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        entry_box.pack_start(Gtk.Label(label=i18n._("dialog.suffix_dkms.full_version")), False, False, 0)

        suffix_entry = Gtk.Entry()
        suffix_entry.set_text(base_version)
        entry_box.pack_start(suffix_entry, True, True, 0)

        content.pack_start(entry_box, False, False, 0)

        dialog.add_button(i18n._("button.cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(i18n._("dialog.suffix_dkms.button_create"), Gtk.ResponseType.OK)
        
        dialog.show_all()
        response = dialog.run()
        
        if response != Gtk.ResponseType.OK:
            dialog.destroy()
            return
        
        full_version = suffix_entry.get_text().strip()
        dialog.destroy()

        if not full_version:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.invalid_version"))
            return
    else:
        full_version = None

    # Construire la commande
    script_path = Path(__file__).parent.parent / "manage_kernel_sources.sh"

    if full_version:
        cmd_desc = f"Lien: linux-{base_version} -> linux-{full_version}"
        cmd = ["pkexec", str(script_path), "link", base_version, full_version]
    else:
        cmd_desc = f"Lien: linux-{base_version}"
        cmd = ["pkexec", str(script_path), "link", base_version]

    if not main_window.dialogs.show_question(
        i18n._("message.confirm.title"),
        i18n._("message.confirm.create_link", description=cmd_desc)
    ):
        return

    # Dialogue de progression
    dialog = Gtk.Dialog(
        title=i18n._("dialog.link_sources.title"),
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
    status_label.set_text(i18n._("dialog.link_sources.status"))
    content.pack_start(status_label, False, False, 0)
    
    progress = Gtk.ProgressBar()
    progress.set_show_text(True)
    progress.set_pulse_step(0.1)
    content.pack_start(progress, False, False, 0)
    
    dialog.show_all()
    
    def link_thread():
        try:
            def pulse_progress():
                progress.pulse()
                return True
            
            pulse_id = GLib.timeout_add(100, pulse_progress)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            GLib.source_remove(pulse_id)
            GLib.idle_add(dialog.destroy)
            
            if result.returncode == 0:
                if full_version:
                    success_msg = i18n._("message.success.link_created", version=full_version)
                else:
                    success_msg = i18n._("message.success.link_created_simple")

                GLib.idle_add(main_window.dialogs.show_info, i18n._("message.success.title"), success_msg)
                GLib.idle_add(lambda: refresh_sources(main_window, available_store, installed_store))
            else:
                error_msg = result.stderr if result.stderr else "Erreur inconnue"
                GLib.idle_add(main_window.dialogs.show_error, i18n._("message.error.title"), f"Échec:\n\n{error_msg}")
        
        except Exception as e:
            GLib.idle_add(dialog.destroy)
            GLib.idle_add(main_window.dialogs.show_error, i18n._("message.error.title"), str(e))

    thread = threading.Thread(target=link_thread, daemon=True)
    thread.start()


def install_to_usr_src(main_window, view, available_store, installed_store):
    """Copie les sources dans /usr/src/"""
    i18n = get_i18n()
    selection = view.get_selection()
    model, treeiter = selection.get_selected()

    if not treeiter:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.select_version"))
        return

    version = model[treeiter][0]

    if not main_window.dialogs.show_question(
        i18n._("message.confirm.title"),
        i18n._("message.confirm.copy_sources", version=version)
    ):
        return

    dialog = Gtk.Dialog(
        title=i18n._("dialog.copy_sources.title"),
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
    status_label.set_text(i18n._("dialog.copy_sources.status"))
    content.pack_start(status_label, False, False, 0)
    
    progress = Gtk.ProgressBar()
    progress.set_show_text(True)
    progress.set_pulse_step(0.1)
    content.pack_start(progress, False, False, 0)
    
    dialog.show_all()
    
    def install_thread():
        try:
            def pulse_progress():
                progress.pulse()
                return True
            
            pulse_id = GLib.timeout_add(100, pulse_progress)
            
            script_path = Path(__file__).parent.parent / "manage_kernel_sources.sh"
            
            result = subprocess.run(
                ["pkexec", str(script_path), "install", version],
                capture_output=True,
                text=True
            )
            
            GLib.source_remove(pulse_id)
            GLib.idle_add(dialog.destroy)
            
            if result.returncode == 0:
                GLib.idle_add(
                    main_window.dialogs.show_info,
                    i18n._("message.success.title"),
                    i18n._("message.success.sources_copied", version=version)
                )
                GLib.idle_add(lambda: refresh_sources(main_window, available_store, installed_store))
            else:
                error_msg = result.stderr if result.stderr else "Erreur inconnue"
                GLib.idle_add(main_window.dialogs.show_error, i18n._("message.error.title"), f"Échec:\n\n{error_msg}")

        except Exception as e:
            GLib.idle_add(dialog.destroy)
            GLib.idle_add(main_window.dialogs.show_error, i18n._("message.error.title"), str(e))

    thread = threading.Thread(target=install_thread, daemon=True)
    thread.start()


def remove_from_usr_src(main_window, view, available_store, installed_store):
    """Supprime les sources de /usr/src/"""
    i18n = get_i18n()
    selection = view.get_selection()
    model, treeiter = selection.get_selected()

    if not treeiter:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.select_version"))
        return

    version = model[treeiter][0]

    # Détecter si c'est un lien symbolique ou un répertoire
    target_path = Path("/usr/src") / f"linux-{version}"
    is_symlink = target_path.is_symlink()

    # Utiliser le bon message de confirmation
    if is_symlink:
        confirm_msg = i18n._("message.confirm.unlink_sources", version=version)
    else:
        confirm_msg = i18n._("message.confirm.delete_sources", version=version)

    if not main_window.dialogs.show_question(
        i18n._("message.confirm.title"),
        confirm_msg
    ):
        return

    dialog = Gtk.Dialog(
        title=i18n._("dialog.delete_sources.title"),
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
    status_label.set_text(i18n._("dialog.delete_sources.status"))
    content.pack_start(status_label, False, False, 0)

    progress = Gtk.ProgressBar()
    progress.set_show_text(True)
    progress.set_pulse_step(0.1)
    content.pack_start(progress, False, False, 0)

    dialog.show_all()

    def remove_thread():
        try:
            def pulse_progress():
                progress.pulse()
                return True

            pulse_id = GLib.timeout_add(100, pulse_progress)

            script_path = Path(__file__).parent.parent / "manage_kernel_sources.sh"

            # Choisir la bonne commande selon le type
            command = "unlink" if is_symlink else "remove"

            process = subprocess.Popen(
                ["pkexec", str(script_path), command, version],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = process.communicate(input="y\n")
            
            GLib.source_remove(pulse_id)
            GLib.idle_add(dialog.destroy)
            
            if process.returncode == 0:
                GLib.idle_add(
                    main_window.dialogs.show_info,
                    i18n._("message.success.title"),
                    i18n._("message.success.sources_deleted", version=version)
                )
                GLib.idle_add(lambda: refresh_sources(main_window, available_store, installed_store))
            else:
                error_msg = stderr if stderr else "Erreur inconnue"
                GLib.idle_add(main_window.dialogs.show_error, i18n._("message.error.title"), f"Échec:\n\n{error_msg}")

        except Exception as e:
            GLib.idle_add(dialog.destroy)
            GLib.idle_add(main_window.dialogs.show_error, i18n._("message.error.title"), str(e))
    
    thread = threading.Thread(target=remove_thread, daemon=True)
    thread.start()