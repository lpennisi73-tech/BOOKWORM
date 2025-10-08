"""
Onglet de gestion des profils de configuration
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from datetime import datetime
from pathlib import Path


def create_profiles_tab(main_window):
    """Crée l'onglet de gestion des profils"""
    
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    
    # Info
    info = Gtk.Label()
    info.set_markup("<b>Profils de configuration</b>\nSauvegardez et réutilisez vos configurations")
    info.set_halign(Gtk.Align.START)
    box.pack_start(info, False, False, 5)
    
    # Liste des profils
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_vexpand(True)
    
    profiles_store = Gtk.ListStore(str, str, str)  # name, description, date
    profiles_view = Gtk.TreeView(model=profiles_store)
    
    for i, title in enumerate(["Nom", "Description", "Date"]):
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(title, renderer, text=i)
        column.set_resizable(True)
        profiles_view.append_column(column)
    
    scrolled.add(profiles_view)
    box.pack_start(scrolled, True, True, 0)
    
    # Boutons
    btn_box = Gtk.Box(spacing=5)
    
    refresh_btn = Gtk.Button(label="🔄 Actualiser")
    refresh_btn.connect("clicked", lambda w: refresh_profiles(main_window, profiles_store))
    btn_box.pack_start(refresh_btn, False, False, 0)
    
    save_btn = Gtk.Button(label="💾 Sauvegarder")
    save_btn.connect("clicked", lambda w: save_profile_dialog(main_window, profiles_store))
    btn_box.pack_start(save_btn, False, False, 0)
    
    load_btn = Gtk.Button(label="📂 Charger")
    load_btn.connect("clicked", lambda w: load_profile_dialog(main_window, profiles_view))
    btn_box.pack_start(load_btn, False, False, 0)
    
    delete_btn = Gtk.Button(label="🗑️ Supprimer")
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
    dialog = Gtk.Dialog(
        title="Sauvegarder un profil",
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
    name_box.pack_start(Gtk.Label(label="Nom du profil:"), False, False, 0)
    name_entry = Gtk.Entry()
    name_entry.set_placeholder_text("ex: gaming, serveur, desktop")
    name_box.pack_start(name_entry, True, True, 0)
    content.pack_start(name_box, False, False, 0)
    
    # Description
    desc_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    desc_box.pack_start(Gtk.Label(label="Description:"), False, False, 0)
    desc_entry = Gtk.Entry()
    desc_entry.set_placeholder_text("Optionnel")
    desc_box.pack_start(desc_entry, True, True, 0)
    content.pack_start(desc_box, False, False, 0)
    
    dialog.add_button("Annuler", Gtk.ResponseType.CANCEL)
    dialog.add_button("💾 Sauvegarder", Gtk.ResponseType.OK)
    
    dialog.show_all()
    response = dialog.run()
    
    if response == Gtk.ResponseType.OK:
        name = name_entry.get_text().strip()
        desc = desc_entry.get_text().strip()
        
        if name:
            if main_window.kernel_manager.save_profile(name, desc):
                main_window.dialogs.show_info("Succès", f"Profil '{name}' sauvegardé !")
                refresh_profiles(main_window, store)
            else:
                main_window.dialogs.show_error("Erreur", "Impossible de sauvegarder le profil")
        else:
            main_window.dialogs.show_error("Erreur", "Veuillez entrer un nom")
    
    dialog.destroy()


def load_profile_dialog(main_window, view):
    """Charge un profil sélectionné"""
    selection = view.get_selection()
    model, treeiter = selection.get_selected()
    
    if not treeiter:
        main_window.dialogs.show_error("Erreur", "Veuillez sélectionner un profil")
        return
    
    profile_name = model[treeiter][0]
    
    if main_window.dialogs.show_question(
        "Confirmer le chargement",
        f"Charger le profil '{profile_name}' ?\n\nLa configuration actuelle sera remplacée."
    ):
        if main_window.kernel_manager.load_profile(profile_name):
            main_window.dialogs.show_info("Succès", f"Profil '{profile_name}' chargé !")
        else:
            main_window.dialogs.show_error("Erreur", "Impossible de charger le profil")


def delete_profile(main_window, view, store):
    """Supprime un profil"""
    selection = view.get_selection()
    model, treeiter = selection.get_selected()
    
    if not treeiter:
        main_window.dialogs.show_error("Erreur", "Veuillez sélectionner un profil")
        return
    
    profile_name = model[treeiter][0]
    
    if main_window.dialogs.show_question(
        "Confirmer la suppression",
        f"Supprimer le profil '{profile_name}' ?\n\nCette action est irréversible."
    ):
        config_path = main_window.kernel_manager.profiles_dir / f"{profile_name}.config"
        meta_path = main_window.kernel_manager.profiles_dir / f"{profile_name}.json"
        
        try:
            config_path.unlink(missing_ok=True)
            meta_path.unlink(missing_ok=True)
            main_window.dialogs.show_info("Succès", f"Profil '{profile_name}' supprimé")
            refresh_profiles(main_window, store)
        except Exception as e:
            main_window.dialogs.show_error("Erreur", f"Impossible de supprimer:\n{e}")
