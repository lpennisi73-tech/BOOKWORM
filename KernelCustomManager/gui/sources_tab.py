"""
Onglet de gestion des sources dans /usr/src/
"""

from pathlib import Path

from gi.repository import Gtk

from core.sources_manager import SourcesManager
from gui.widgets import (SimpleList, button, button_row, entry, markup_label, page_box,
                         section, title_label)
from utils.dialogs import run_task
from utils.i18n import get_i18n


def _manager(main_window):
    return SourcesManager(main_window.kernel_manager.sources_dir)


def create_sources_tab(main_window):
    """Crée l'onglet de gestion des sources système"""
    i18n = get_i18n()
    box = page_box()
    box.append(title_label(i18n._("sources.title"), i18n._("sources.subtitle")))

    lists = {}
    lists["available"] = SimpleList([i18n._("sources.column_version")], expand=[0])
    lists["installed"] = SimpleList([i18n._("sources.column_version"), i18n._("sources.column_active")],
                                    expand=[0])

    paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True,
                      shrink_start_child=False, shrink_end_child=False)

    # === Sources disponibles (gauche) ===
    left, left_inner = section(i18n._("sources.available"))
    left.set_margin_end(6)
    left_inner.append(markup_label(f"<small>{i18n._('sources.available_subtitle')}</small>"))
    left_inner.append(lists["available"])
    left_inner.append(button(i18n._("sources.button_copy"),
                             lambda: install_to_usr_src(main_window, lists)))
    left_inner.append(button(i18n._("sources.button_link_simple"),
                             lambda: link_to_usr_src(main_window, lists, False), "suggested-action"))
    left_inner.append(button(i18n._("sources.button_link_suffix"),
                             lambda: link_to_usr_src(main_window, lists, True)))
    paned.set_start_child(left)

    # === Sources installées (droite) ===
    right, right_inner = section(i18n._("sources.installed"))
    right.set_margin_start(6)
    right_inner.append(markup_label(f"<small>{i18n._('sources.installed_subtitle')}</small>"))
    right_inner.append(lists["installed"])
    right_inner.append(button_row(
        button(i18n._("button.refresh"), lambda: refresh_sources(main_window, lists)),
        button(i18n._("button.remove"), lambda: remove_from_usr_src(main_window, lists), "destructive-action"),
    ))
    paned.set_end_child(right)

    box.append(paned)
    refresh_sources(main_window, lists)
    return box


def refresh_sources(main_window, lists):
    """Actualise la liste des sources"""
    manager = _manager(main_window)
    lists["available"].set_rows([version] for version in manager.list_available())
    lists["installed"].set_rows([entry['version'], "✓" if entry['active'] else ""]
                                for entry in manager.list_installed())


def _selected_version(main_window, source_list):
    i18n = get_i18n()
    row = source_list.selected()
    if row is None:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.select_version"))
        return None
    return row[0]


def _run_privileged(main_window, lists, title, status, action, success_message):
    """Exécute une action du SourcesManager (success, message) avec un dialogue de progression"""
    i18n = get_i18n()
    progress = main_window.dialogs.progress(title, status)
    progress.pulse()

    def done(result):
        progress.close()
        success, message = result
        if success:
            text = success_message
            if message:  # avertissement (ex: headers absents)
                text += f"\n\n⚠️ {message}"
            main_window.dialogs.show_info(i18n._("message.success.title"), text)
            refresh_sources(main_window, lists)
        else:
            main_window.dialogs.show_error(i18n._("message.error.title"),
                                           message or i18n._("message.error.operation"))

    def failed(error):
        progress.close()
        main_window.dialogs.show_error(i18n._("message.error.title"), str(error))

    run_task(action, done, failed)


def link_to_usr_src(main_window, lists, with_suffix):
    """Crée un lien symbolique dans /usr/src/"""
    i18n = get_i18n()
    base_version = _selected_version(main_window, lists["available"])
    if base_version is None:
        return

    def confirm(full_version):
        if full_version:
            description = f"linux-{base_version} → linux-{full_version}"
            success_message = i18n._("message.success.link_created", version=full_version)
        else:
            description = f"linux-{base_version}"
            success_message = i18n._("message.success.link_created_simple")

        main_window.dialogs.ask(
            i18n._("message.confirm.title"),
            i18n._("message.confirm.create_link", description=description),
            on_yes=lambda: _run_privileged(
                main_window, lists, i18n._("dialog.link_sources.title"), i18n._("dialog.link_sources.status"),
                lambda: _manager(main_window).link(base_version, full_version), success_message))

    if not with_suffix:
        confirm(None)
        return

    # Demander la version complète (avec suffixe, ex: 6.16.9-custom)
    form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    form.append(markup_label(
        f"<b>{i18n._('dialog.suffix_dkms.base_version', version=base_version)}</b>\n\n"
        f"{i18n._('dialog.suffix_dkms.info')}"))
    form.append(Gtk.Label(label=i18n._("dialog.suffix_dkms.full_version"), xalign=0))
    version_entry = entry(text=base_version)
    form.append(version_entry)

    def on_create():
        full_version = version_entry.get_text().strip()
        if not full_version:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.invalid_version"))
            return
        confirm(full_version)

    main_window.dialogs.form(i18n._("dialog.suffix_dkms.title"), form,
                             i18n._("dialog.suffix_dkms.button_create"), on_create)


def install_to_usr_src(main_window, lists):
    """Copie les sources dans /usr/src/"""
    i18n = get_i18n()
    version = _selected_version(main_window, lists["available"])
    if version is None:
        return

    main_window.dialogs.ask(
        i18n._("message.confirm.title"),
        i18n._("message.confirm.copy_sources", version=version),
        on_yes=lambda: _run_privileged(
            main_window, lists, i18n._("dialog.copy_sources.title"), i18n._("dialog.copy_sources.status"),
            lambda: _manager(main_window).install(version),
            i18n._("message.success.sources_copied", version=version)))


def remove_from_usr_src(main_window, lists):
    """Supprime les sources (lien ou copie) de /usr/src/"""
    i18n = get_i18n()
    version = _selected_version(main_window, lists["installed"])
    if version is None:
        return

    if (Path("/usr/src") / f"linux-{version}").is_symlink():
        confirm_msg = i18n._("message.confirm.unlink_sources", version=version)
    else:
        confirm_msg = i18n._("message.confirm.delete_sources", version=version)

    # Le helper gère les deux cas (lien ou copie) et conserve les vrais headers système
    main_window.dialogs.ask(
        i18n._("message.confirm.title"), confirm_msg, destructive=True,
        on_yes=lambda: _run_privileged(
            main_window, lists, i18n._("dialog.delete_sources.title"), i18n._("dialog.delete_sources.status"),
            lambda: SourcesManager.remove(version),
            i18n._("message.success.sources_deleted", version=version)))
