"""
Onglet de l'historique des compilations
"""

from datetime import datetime

from gui.widgets import SimpleList, button, button_row, page_box, title_label
from utils.i18n import get_i18n


def create_history_tab(main_window):
    """Crée l'onglet de l'historique"""
    i18n = get_i18n()
    box = page_box()
    box.append(title_label(i18n._("history.title")))

    history = SimpleList([
        i18n._("history.column_date"), i18n._("history.column_version"),
        i18n._("history.column_suffix"), i18n._("history.column_duration"),
        i18n._("history.column_status"),
    ], expand=[1])
    box.append(history)

    box.append(button_row(
        button(i18n._("button.refresh"), lambda: refresh_history(main_window, history)),
        button(i18n._("button.clear"), lambda: clear_history(main_window, history), "destructive-action"),
    ))

    refresh_history(main_window, history)
    return box


def refresh_history(main_window, history):
    """Actualise l'historique"""
    i18n = get_i18n()
    rows = []
    for entry in main_window.kernel_manager.get_compilation_history():
        date = datetime.fromisoformat(entry['timestamp']).strftime("%Y-%m-%d %H:%M")
        seconds = entry['duration_seconds']
        rows.append([
            date,
            entry['kernel_version'],
            entry.get('suffix', ''),
            f"{seconds // 60}m {seconds % 60}s",
            i18n._("history.status_success") if entry['success'] else i18n._("history.status_failed"),
        ])
    history.set_rows(rows)


def clear_history(main_window, history):
    """Efface l'historique"""
    i18n = get_i18n()

    def do_clear():
        main_window.kernel_manager._save_history([])
        refresh_history(main_window, history)
        main_window.dialogs.toast(i18n._("message.success.history_cleared"))

    main_window.dialogs.ask(i18n._("message.confirm.title"), i18n._("message.confirm.clear_history"),
                            on_yes=do_clear, destructive=True)
