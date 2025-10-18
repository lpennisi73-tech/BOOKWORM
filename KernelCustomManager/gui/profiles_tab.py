"""
Onglet de gestion des profils de configuration
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from datetime import datetime
from pathlib import Path
from utils.i18n import get_i18n


def create_profiles_tab(main_window):
    """Crée l'onglet de gestion des profils"""
    i18n = get_i18n()

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

    # Info
    info = Gtk.Label()
    info.set_markup(f"<b>{i18n._('profiles.title')}</b>\n{i18n._('profiles.subtitle')}")
    info.set_halign(Gtk.Align.START)
    box.pack_start(info, False, False, 5)

    # Liste des profils
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_vexpand(True)

    profiles_store = Gtk.ListStore(str, str, str)  # name, description, date
    profiles_view = Gtk.TreeView(model=profiles_store)

    for i, title in enumerate([i18n._("profiles.column_name"), i18n._("profiles.column_description"), i18n._("profiles.column_date")]):
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(title, renderer, text=i)
        column.set_resizable(True)
        profiles_view.append_column(column)
    
    scrolled.add(profiles_view)
    box.pack_start(scrolled, True, True, 0)
    
    # Boutons
    btn_box = Gtk.Box(spacing=5)

    refresh_btn = Gtk.Button(label=i18n._("button.refresh"))
    refresh_btn.connect("clicked", lambda w: refresh_profiles(main_window, profiles_store))
    btn_box.pack_start(refresh_btn, False, False, 0)

    save_btn = Gtk.Button(label=i18n._("button.save"))
    save_btn.connect("clicked", lambda w: save_profile_dialog(main_window, profiles_store))
    btn_box.pack_start(save_btn, False, False, 0)

    load_btn = Gtk.Button(label=i18n._("button.load"))
    load_btn.connect("clicked", lambda w: load_profile_dialog(main_window, profiles_view))
    btn_box.pack_start(load_btn, False, False, 0)

    delete_btn = Gtk.Button(label=i18n._("button.delete"))
    delete_btn.connect("clicked", lambda w: delete_profile(main_window, profiles_view, profiles_store))
    btn_box.pack_start(delete_btn, False, False, 0)
    
    box.pack_start(btn_box, False, False, 0)
    
    refresh_profiles(main_window, profiles_store)
    
    return box


def refresh_profiles(main_window, store):
    """Actualise la liste des profils"""
    store.clear()
    for profile in main_window.kernel_manager.get_profiles():
        date = datetime.fromisoformat(profile['created']).strftime("%Y-%m-%d %H:%M")
        store.append([
            profile['name'],
            profile.get('description', ''),
            date
        ])


def save_profile_dialog(main_window, store):
    """Dialogue pour sauvegarder un profil"""
    i18n = get_i18n()
    dialog = Gtk.Dialog(
        title=i18n._("dialog.save_profile.title"),
        transient_for=main_window,
        flags=0
    )
    dialog.set_default_size(400, 200)

    content = dialog.get_content_area()
    content.set_spacing(10)
    content.set_margin_start(20)
    content.set_margin_end(20)
    content.set_margin_top(10)
    content.set_margin_bottom(10)

    # Nom
    name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    name_box.pack_start(Gtk.Label(label=i18n._("dialog.save_profile.name")), False, False, 0)
    name_entry = Gtk.Entry()
    name_entry.set_placeholder_text(i18n._("dialog.save_profile.name_placeholder"))
    name_box.pack_start(name_entry, True, True, 0)
    content.pack_start(name_box, False, False, 0)

    # Description
    desc_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    desc_box.pack_start(Gtk.Label(label=i18n._("dialog.save_profile.description")), False, False, 0)
    desc_entry = Gtk.Entry()
    desc_entry.set_placeholder_text(i18n._("dialog.save_profile.description_placeholder"))
    desc_box.pack_start(desc_entry, True, True, 0)
    content.pack_start(desc_box, False, False, 0)

    dialog.add_button(i18n._("button.cancel"), Gtk.ResponseType.CANCEL)
    dialog.add_button(i18n._("dialog.save_profile.button_save"), Gtk.ResponseType.OK)
    
    dialog.show_all()
    response = dialog.run()
    
    if response == Gtk.ResponseType.OK:
        name = name_entry.get_text().strip()
        desc = desc_entry.get_text().strip()
        
        if name:
            if main_window.kernel_manager.save_profile(name, desc):
                main_window.dialogs.show_info(i18n._("message.success.title"), i18n._("message.success.profile_saved", name=name))
                refresh_profiles(main_window, store)
            else:
                main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.profile_save_failed"))
        else:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.enter_name"))

    dialog.destroy()


def load_profile_dialog(main_window, view):
    """Charge un profil sélectionné"""
    i18n = get_i18n()
    selection = view.get_selection()
    model, treeiter = selection.get_selected()

    if not treeiter:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.select_profile"))
        return

    profile_name = model[treeiter][0]

    if main_window.dialogs.show_question(
        i18n._("message.confirm.title"),
        i18n._("message.confirm.load_profile", name=profile_name)
    ):
        if main_window.kernel_manager.load_profile(profile_name):
            main_window.dialogs.show_info(i18n._("message.success.title"), i18n._("message.success.profile_loaded", name=profile_name))
        else:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.profile_load_failed"))


def delete_profile(main_window, view, store):
    """Supprime un profil"""
    i18n = get_i18n()
    selection = view.get_selection()
    model, treeiter = selection.get_selected()

    if not treeiter:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.select_profile"))
        return

    profile_name = model[treeiter][0]

    if main_window.dialogs.show_question(
        i18n._("message.confirm.title"),
        i18n._("message.confirm.delete_profile", name=profile_name)
    ):
        config_path = main_window.kernel_manager.profiles_dir / f"{profile_name}.config"
        meta_path = main_window.kernel_manager.profiles_dir / f"{profile_name}.json"

        try:
            config_path.unlink(missing_ok=True)
            meta_path.unlink(missing_ok=True)
            main_window.dialogs.show_info(i18n._("message.success.title"), i18n._("message.success.profile_deleted", name=profile_name))
            refresh_profiles(main_window, store)
        except Exception as e:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.profile_delete_failed", error=str(e)))
