"""
Onglet de l'historique des compilations
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from datetime import datetime
from utils.i18n import get_i18n


def create_history_tab(main_window):
    """Crée l'onglet de l'historique"""
    i18n = get_i18n()

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

    # Info
    info = Gtk.Label()
    info.set_markup(f"<b>{i18n._('history.title')}</b>")
    info.set_halign(Gtk.Align.START)
    box.pack_start(info, False, False, 5)

    # Liste de l'historique
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_vexpand(True)

    history_store = Gtk.ListStore(str, str, str, str, str)  # date, version, suffix, durée, statut
    history_view = Gtk.TreeView(model=history_store)

    for i, title in enumerate([i18n._("history.column_date"), i18n._("history.column_version"), i18n._("history.column_suffix"), i18n._("history.column_duration"), i18n._("history.column_status")]):
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(title, renderer, text=i)
        column.set_resizable(True)
        history_view.append_column(column)
    
    scrolled.add(history_view)
    box.pack_start(scrolled, True, True, 0)
    
    # Boutons
    btn_box = Gtk.Box(spacing=5)

    refresh_btn = Gtk.Button(label=i18n._("button.refresh"))
    refresh_btn.connect("clicked", lambda w: refresh_history(main_window, history_store))
    btn_box.pack_start(refresh_btn, False, False, 0)

    clear_btn = Gtk.Button(label=i18n._("button.clear"))
    clear_btn.connect("clicked", lambda w: clear_history(main_window, history_store))
    btn_box.pack_start(clear_btn, False, False, 0)
    
    box.pack_start(btn_box, False, False, 0)
    
    refresh_history(main_window, history_store)
    
    return box


def refresh_history(main_window, store):
    """Actualise l'historique"""
    i18n = get_i18n()
    store.clear()
    for entry in main_window.kernel_manager.get_compilation_history():
        date = datetime.fromisoformat(entry['timestamp']).strftime("%Y-%m-%d %H:%M")
        duration = f"{entry['duration_seconds']//60}m {entry['duration_seconds']%60}s"
        status = i18n._("history.status_success") if entry['success'] else i18n._("history.status_failed")

        store.append([
            date,
            entry['kernel_version'],
            entry.get('suffix', ''),
            duration,
            status
        ])


def clear_history(main_window, store):
    """Efface l'historique"""
    i18n = get_i18n()
    if main_window.dialogs.show_question(
        i18n._("message.confirm.title"),
        i18n._("message.confirm.clear_history")
    ):
        main_window.kernel_manager._save_history([])
        refresh_history(main_window, store)
        main_window.dialogs.show_info(i18n._("message.success.title"), i18n._("message.success.history_cleared"))
