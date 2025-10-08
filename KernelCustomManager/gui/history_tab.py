"""
Onglet de l'historique des compilations
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from datetime import datetime


def create_history_tab(main_window):
    """Crée l'onglet de l'historique"""
    
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    
    # Info
    info = Gtk.Label()
    info.set_markup("<b>Historique des compilations</b>")
    info.set_halign(Gtk.Align.START)
    box.pack_start(info, False, False, 5)
    
    # Liste de l'historique
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_vexpand(True)
    
    history_store = Gtk.ListStore(str, str, str, str, str)  # date, version, suffix, durée, statut
    history_view = Gtk.TreeView(model=history_store)
    
    for i, title in enumerate(["Date", "Version", "Suffixe", "Durée", "Statut"]):
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(title, renderer, text=i)
        column.set_resizable(True)
        history_view.append_column(column)
    
    scrolled.add(history_view)
    box.pack_start(scrolled, True, True, 0)
    
    # Boutons
    btn_box = Gtk.Box(spacing=5)
    
    refresh_btn = Gtk.Button(label="🔄 Actualiser")
    refresh_btn.connect("clicked", lambda w: refresh_history(main_window, history_store))
    btn_box.pack_start(refresh_btn, False, False, 0)
    
    clear_btn = Gtk.Button(label="🗑️ Effacer")
    clear_btn.connect("clicked", lambda w: clear_history(main_window, history_store))
    btn_box.pack_start(clear_btn, False, False, 0)
    
    box.pack_start(btn_box, False, False, 0)
    
    refresh_history(main_window, history_store)
    
    return box


def refresh_history(main_window, store):
    """Actualise l'historique"""
    store.clear()
    for entry in main_window.kernel_manager.get_compilation_history():
        date = datetime.fromisoformat(entry['timestamp']).strftime("%Y-%m-%d %H:%M")
        duration = f"{entry['duration_seconds']//60}m {entry['duration_seconds']%60}s"
        status = "✅ Réussi" if entry['success'] else "❌ Échoué"
        
        store.append([
            date,
            entry['kernel_version'],
            entry.get('suffix', ''),
            duration,
            status
        ])


def clear_history(main_window, store):
    """Efface l'historique"""
    if main_window.dialogs.show_question(
        "Confirmer",
        "Effacer tout l'historique des compilations ?\n\nCette action est irréversible."
    ):
        main_window.kernel_manager._save_history([])
        refresh_history(main_window, store)
        main_window.dialogs.show_info("Succès", "Historique effacé")
