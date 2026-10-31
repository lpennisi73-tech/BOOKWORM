"""
Onglet de gestion des profils de configuration
"""

from datetime import datetime

from gi.repository import Gtk

from core.kernel_manager import is_valid_profile_name
from gui.widgets import SimpleList, button, button_row, entry, page_box, title_label
from utils.i18n import get_i18n


def create_profiles_tab(main_window):
    """Crée l'onglet de gestion des profils"""
    i18n = get_i18n()
    box = page_box()
    box.append(title_label(i18n._("profiles.title"), i18n._("profiles.subtitle")))

    profiles = SimpleList([
        i18n._("profiles.column_name"), i18n._("profiles.column_description"), i18n._("profiles.column_date"),
    ], expand=[1])
    box.append(profiles)

    box.append(button_row(
        button(i18n._("button.refresh"), lambda: refresh_profiles(main_window, profiles)),
        button(i18n._("button.save"), lambda: save_profile_dialog(main_window, profiles), "suggested-action"),
        button(i18n._("button.load"), lambda: load_profile(main_window, profiles)),
        button(i18n._("button.delete"), lambda: delete_profile(main_window, profiles), "destructive-action"),
    ))

    refresh_profiles(main_window, profiles)
    return box


def refresh_profiles(main_window, profiles):
    """Actualise la liste des profils"""
    rows = []
    for profile in main_window.kernel_manager.get_profiles():
        date = datetime.fromisoformat(profile['created']).strftime("%Y-%m-%d %H:%M")
        rows.append([profile['name'], profile.get('description', ''), date])
    profiles.set_rows(rows)


def _selected_profile(main_window, profiles):
    i18n = get_i18n()
    row = profiles.selected()
    if row is None:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.select_profile"))
        return None
    return row[0]


def save_profile_dialog(main_window, profiles):
    """Dialogue pour sauvegarder un profil"""
    i18n = get_i18n()

    form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    name_entry = entry(placeholder=i18n._("dialog.save_profile.name_placeholder"))
    desc_entry = entry(placeholder=i18n._("dialog.save_profile.description_placeholder"))
    for label, widget in ((i18n._("dialog.save_profile.name"), name_entry),
                          (i18n._("dialog.save_profile.description"), desc_entry)):
        form.append(Gtk.Label(label=label, xalign=0))
        form.append(widget)
        if widget is name_entry:
            hint = Gtk.Label(label=i18n._("dialog.save_profile.name_hint"), xalign=0, wrap=True)
            hint.add_css_class("dim-label")
            hint.add_css_class("caption")
            form.append(hint)

    def on_save():
        name = name_entry.get_text().strip()
        desc = desc_entry.get_text().strip()
        if not name:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.enter_name"))
        elif not is_valid_profile_name(name):
            main_window.dialogs.show_error(i18n._("message.error.title"),
                                           i18n._("message.error.invalid_profile_name", name=name))
        elif main_window.kernel_manager.profile_exists(name):
            main_window.dialogs.ask(i18n._("message.confirm.title"),
                                    i18n._("message.confirm.overwrite_profile", name=name),
                                    on_yes=lambda: do_save(name, desc), destructive=True,
                                    yes_label=i18n._("button.replace"))
        else:
            do_save(name, desc)

    def do_save(name, desc):
        if main_window.kernel_manager.save_profile(name, desc):
            main_window.dialogs.toast(i18n._("message.success.profile_saved", name=name))
            refresh_profiles(main_window, profiles)
        else:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.profile_save_failed"))

    main_window.dialogs.form(i18n._("dialog.save_profile.title"), form,
                             i18n._("dialog.save_profile.button_save"), on_save)
    name_entry.grab_focus()


def load_profile(main_window, profiles):
    """Charge un profil sélectionné"""
    i18n = get_i18n()
    profile_name = _selected_profile(main_window, profiles)
    if profile_name is None:
        return

    def do_load():
        if main_window.kernel_manager.load_profile(profile_name):
            main_window.dialogs.toast(i18n._("message.success.profile_loaded", name=profile_name))
        else:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.profile_load_failed"))

    main_window.dialogs.ask(i18n._("message.confirm.title"),
                            i18n._("message.confirm.load_profile", name=profile_name), on_yes=do_load)


def delete_profile(main_window, profiles):
    """Supprime un profil"""
    i18n = get_i18n()
    profile_name = _selected_profile(main_window, profiles)
    if profile_name is None:
        return

    def do_delete():
        profiles_dir = main_window.kernel_manager.profiles_dir
        try:
            (profiles_dir / f"{profile_name}.config").unlink(missing_ok=True)
            (profiles_dir / f"{profile_name}.json").unlink(missing_ok=True)
        except OSError as e:
            main_window.dialogs.show_error(i18n._("message.error.title"),
                                           i18n._("message.error.profile_delete_failed", error=str(e)))
            return
        main_window.dialogs.toast(i18n._("message.success.profile_deleted", name=profile_name))
        refresh_profiles(main_window, profiles)

    main_window.dialogs.ask(i18n._("message.confirm.title"),
                            i18n._("message.confirm.delete_profile", name=profile_name),
                            on_yes=do_delete, destructive=True)
