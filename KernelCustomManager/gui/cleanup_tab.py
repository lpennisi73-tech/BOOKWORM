"""
Onglet de nettoyage du dossier de travail (sources compilées, paquets, logs…)
La logique est dans core/cleanup_manager.py ; cet onglet ne fait qu'afficher et confirmer.
"""

from gi.repository import Adw, GLib, Gtk

from core.cleanup_manager import CATEGORIES, CleanupManager, human_size
from gui.widgets import button, page_box, run_once_when_mapped, title_label
from utils.dialogs import run_task
from utils.i18n import get_i18n


class CleanupPage:

    def __init__(self, main_window):
        self.win = main_window
        self.dialogs = main_window.dialogs
        self.i18n = get_i18n()
        self.manager = CleanupManager(main_window.kernel_manager.base_dir)
        self.items = []
        self.checks = {}   # id(item) -> Gtk.CheckButton

    # ==================== Construction ====================

    def build(self):
        i18n = self.i18n
        box = page_box(spacing=12)

        header = Gtk.Box(spacing=12)
        heading = title_label(i18n._("cleanup.title"), i18n._("cleanup.subtitle"))
        heading.set_hexpand(True)
        header.append(heading)

        self.scan_button = button(i18n._("cleanup.scan"), self.scan)
        self.scan_button.set_valign(Gtk.Align.CENTER)
        header.append(self.scan_button)
        box.append(header)

        options = Gtk.Box(spacing=12)
        self.keys_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.keys_switch.connect("notify::active", lambda *a: self.scan())
        keys_label = Gtk.Label(label=i18n._("cleanup.include_keys"), xalign=0)
        options.append(self.keys_switch)
        options.append(keys_label)
        spacer = Gtk.Box(hexpand=True)
        options.append(spacer)
        self.total_label = Gtk.Label(xalign=1)
        self.total_label.add_css_class("heading")
        options.append(self.total_label)
        self.clean_button = button(i18n._("cleanup.clean_selected"), self.confirm_clean, "destructive-action")
        options.append(self.clean_button)
        box.append(options)

        # Liste reconstruite à chaque analyse
        self.list_holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.spinner = Adw.Spinner(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
                                   width_request=32, height_request=32, vexpand=True)
        self.list_holder.append(self.spinner)
        box.append(self.list_holder)

        self.update_total()
        # L'analyse parcourt de gros arbres : à la première ouverture de l'onglet, dans un thread
        run_once_when_mapped(box, self.scan)
        return box

    # ==================== Analyse ====================

    def scan(self):
        include_keys = self.keys_switch.get_active()
        self.scan_button.set_sensitive(False)
        self.clean_button.set_sensitive(False)
        self._set_list(self.spinner)

        def done(items):
            self.scan_button.set_sensitive(True)
            self.items = items
            self._show_items()

        def failed(error):
            self.scan_button.set_sensitive(True)
            self.dialogs.show_error(self.i18n._("message.error.title"), str(error))

        run_task(lambda: self.manager.scan(include_keys=include_keys), done, failed)

    def _set_list(self, widget):
        child = self.list_holder.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self.list_holder.remove(child)
            child = following
        self.list_holder.append(widget)

    def _show_items(self):
        i18n = self.i18n
        self.checks = {}

        if not self.items:
            status = Adw.StatusPage(icon_name="user-trash-symbolic", title=i18n._("cleanup.empty"),
                                    vexpand=True)
            self._set_list(status)
            self.update_total()
            return

        page = Adw.PreferencesPage(vexpand=True)
        summary = CleanupManager.summary(self.items)
        for category in CATEGORIES:
            items = [item for item in self.items if item.category == category]
            if not items:
                continue
            count, size = summary.get(category, (0, 0))
            group = Adw.PreferencesGroup(
                title=i18n._(f"cleanup.category.{category}"),
                description=f"{count} · {human_size(size)}" if count else None)
            for item in items:
                group.add(self._item_row(item))
            page.add(group)

        self._set_list(page)
        self.update_total()

    def _item_row(self, item):
        i18n = self.i18n
        subtitle = human_size(item.size)
        if item.reason:
            subtitle += f" · {i18n._(f'cleanup.reason.{item.reason}')}"
        row = Adw.ActionRow(title=GLib.markup_escape_text(item.name),
                            subtitle=GLib.markup_escape_text(subtitle))
        row.set_tooltip_text(str(item.path))

        if item.protected:
            lock = Gtk.Image.new_from_icon_name("changes-prevent-symbolic")
            lock.set_tooltip_text(i18n._(f"cleanup.reason.{item.reason}"))
            row.add_prefix(lock)
            row.add_css_class("dim-label")
            return row

        check = Gtk.CheckButton(active=item.selected, valign=Gtk.Align.CENTER)

        def toggled(button):
            item.selected = button.get_active()
            self.update_total()

        check.connect("toggled", toggled)
        row.add_prefix(check)
        row.set_activatable_widget(check)
        if item.category == 'secureboot_keys':
            row.add_suffix(Gtk.Image.new_from_icon_name("dialog-warning-symbolic"))
        self.checks[id(item)] = check
        return row

    # ==================== Sélection ====================

    def selection(self):
        """
        Éléments à traiter. Un `make clean` est inutile si l'arbre entier est supprimé
        (et sa taille est déjà comptée dans celle de l'arbre).
        """
        selected = [item for item in self.items if item.selected and not item.protected]
        deleted_trees = {item.path for item in selected if item.category == 'sources'}
        return [item for item in selected
                if not (item.action == 'make_clean' and item.path in deleted_trees)]

    def update_total(self):
        selected = self.selection()
        size = sum(item.size for item in selected)
        self.total_label.set_text(self.i18n._("cleanup.total_selected", size=human_size(size)))
        self.clean_button.set_sensitive(bool(selected))

    # ==================== Nettoyage ====================

    def confirm_clean(self):
        i18n = self.i18n
        selected = self.selection()
        if not selected:
            self.dialogs.show_info(i18n._("cleanup.title"), i18n._("cleanup.nothing_selected"))
            return

        size = human_size(sum(item.size for item in selected))
        message = i18n._("cleanup.confirm", count=len(selected), size=size)
        if any(item.category == 'secureboot_keys' for item in selected):
            message += "\n\n" + i18n._("cleanup.confirm_keys")

        self.dialogs.ask(i18n._("cleanup.title"), message, destructive=True,
                         yes_label=i18n._("cleanup.clean_selected"),
                         on_yes=lambda: self.clean(selected))

    def clean(self, selected):
        i18n = self.i18n
        progress = self.dialogs.progress(i18n._("cleanup.title"))

        def on_progress(index, total, item):
            progress.set_fraction((index - 1) / total, f"{index}/{total}")
            progress.set_status(f"{i18n._(f'cleanup.category.{item.category}')}\n{item.name}")

        def done(result):
            progress.close()
            self.dialogs.toast(i18n._("cleanup.freed", size=human_size(result['freed'])))
            if result['errors']:
                details = "\n".join(f"• {item.name} : {error}" for item, error in result['errors'])
                self.dialogs.show_error(i18n._("cleanup.title"), f"{i18n._('cleanup.errors')}\n\n{details}")
            self._after_clean()

        def failed(error):
            progress.close()
            self.dialogs.show_error(i18n._("message.error.title"), str(error))
            self._after_clean()

        run_task(lambda: self.manager.clean(selected, on_progress), done, failed)

    def _after_clean(self):
        self.scan()
        # Le lien de l'arbre actif a pu disparaître
        if hasattr(self.win, "build_source_label"):
            from gui.build_tab import update_source_label
            update_source_label(self.win)


def create_cleanup_tab(main_window):
    """Crée l'onglet de nettoyage du dossier de travail"""
    page = CleanupPage(main_window)
    main_window.cleanup_page = page
    return page.build()
