"""
Dialogues réutilisables (GTK4 + libadwaita)

Tous les dialogues sont ASYNCHRONES : rien ne bloque, il n'y a plus de
`dialog.run()`. Le code qui dépend de la réponse est passé en callback :

    dialogs.ask(titre, message, on_yes=lambda: faire_quelque_chose())

Toutes les méthodes doivent être appelées depuis le thread GTK. Depuis un
thread de travail, passer par GLib.idle_add (ou utiliser run_task()).
"""

import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio, GLib, Gtk

from utils.i18n import get_i18n


def _escape(text):
    return GLib.markup_escape_text(str(text)) if text is not None else ""


def run_task(work, on_done=None, on_error=None):
    """
    Exécute work() dans un thread puis appelle on_done(résultat) dans le thread GTK.
    Une exception dans work() est passée à on_error(exception) (ou journalisée).
    """
    def runner():
        try:
            result = work()
        except Exception as error:  # remonté à l'interface
            import logging
            logging.exception("Tâche en arrière-plan")
            if on_error:
                GLib.idle_add(_once, on_error, error)
            return
        if on_done:
            GLib.idle_add(_once, on_done, result)

    threading.Thread(target=runner, daemon=True).start()


def _once(callback, *args):
    callback(*args)
    return False  # ne pas répéter l'idle


class ProgressDialog:
    """
    Dialogue modal de progression. Ses méthodes sont utilisables DEPUIS N'IMPORTE
    QUEL THREAD (elles passent par GLib.idle_add).
    """

    def __init__(self, parent, title, status="", cancellable=False, on_cancel=None):
        self._pulse_id = None
        self.cancelled = False
        self._on_cancel = on_cancel

        self.dialog = Adw.Dialog(title=title, content_width=460, can_close=False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_top=12, margin_bottom=24, margin_start=24, margin_end=24)
        self.status = Gtk.Label(label=status, wrap=True, xalign=0)
        box.append(self.status)
        self.bar = Gtk.ProgressBar(show_text=True)
        box.append(self.bar)

        if cancellable:
            button = Gtk.Button(label=get_i18n()._("button.cancel"), halign=Gtk.Align.END)
            button.connect("clicked", self._cancel)
            box.append(button)

        header = Adw.HeaderBar(show_end_title_buttons=False, show_start_title_buttons=False)
        view = Adw.ToolbarView(content=box)
        view.add_top_bar(header)
        self.dialog.set_child(view)
        self.dialog.present(parent)

    def _cancel(self, button):
        self.cancelled = True
        button.set_sensitive(False)
        if self._on_cancel:
            self._on_cancel()

    # --- utilisables depuis un thread ---

    def set_status(self, text):
        GLib.idle_add(_once, self.status.set_text, text)

    def set_fraction(self, fraction, text=None):
        def update():
            self._stop_pulse()
            self.bar.set_fraction(max(0.0, min(1.0, fraction)))
            self.bar.set_text(text if text is not None else f"{int(fraction * 100)}%")
        GLib.idle_add(_once, update)

    def pulse(self):
        """Barre « indéterminée » jusqu'au prochain set_fraction() ou close()"""
        def start():
            if self._pulse_id is None:
                self.bar.set_show_text(False)
                self._pulse_id = GLib.timeout_add(100, lambda: (self.bar.pulse(), True)[1])
        GLib.idle_add(_once, start)

    def close(self):
        def do_close():
            self._stop_pulse()
            self.dialog.force_close()
        GLib.idle_add(_once, do_close)

    def _stop_pulse(self):
        if self._pulse_id is not None:
            GLib.source_remove(self._pulse_id)
            self._pulse_id = None
            self.bar.set_show_text(True)


class DialogHelper:
    """Dialogues de l'application (Adw.AlertDialog, Gtk.FileDialog)"""

    def __init__(self, parent_window):
        self.parent = parent_window
        self.toast_overlay = None  # défini par la fenêtre principale

    # ==================== Messages ====================

    def message(self, title, message, on_close=None, markup=False):
        dialog = Adw.AlertDialog(heading=title, body=message if markup else _escape(message),
                                 body_use_markup=True)
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        if on_close:
            dialog.connect("response", lambda d, r: on_close())
        dialog.present(self.parent)
        return dialog

    def show_info(self, title, message, on_close=None):
        return self.message(title, message, on_close)

    def show_warning(self, title, message, on_close=None):
        return self.message(f"⚠️ {title}", message, on_close)

    def show_error(self, title, message, on_close=None):
        return self.message(f"❌ {title}", message, on_close)

    def toast(self, message, timeout=4):
        """Message discret en bas de la fenêtre (repli sur un dialogue)"""
        if self.toast_overlay is None:
            self.show_info("", message)
            return
        self.toast_overlay.add_toast(Adw.Toast(title=_escape(message), timeout=timeout))

    # ==================== Questions ====================

    def ask(self, title, message, on_yes, on_no=None, yes_label=None, no_label=None,
            destructive=False, extra_child=None, markup=False):
        """
        Question Oui/Non. on_yes() est appelé seulement si l'utilisateur confirme.
        (Remplace show_question() qui renvoyait un booléen : rien ne bloque ici.)
        """
        i18n = get_i18n()
        dialog = Adw.AlertDialog(heading=title, body=message if markup else _escape(message),
                                 body_use_markup=True)
        dialog.add_response("no", no_label or i18n._("button.no"))
        dialog.add_response("yes", yes_label or i18n._("button.yes"))
        dialog.set_response_appearance(
            "yes", Adw.ResponseAppearance.DESTRUCTIVE if destructive else Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("no" if destructive else "yes")
        dialog.set_close_response("no")
        if extra_child is not None:
            dialog.set_extra_child(extra_child)

        def on_response(_dialog, response):
            if response == "yes":
                on_yes()
            elif on_no:
                on_no()

        dialog.connect("response", on_response)
        dialog.present(self.parent)
        return dialog

    def choose(self, title, message, choices, on_choice):
        """
        Question à plusieurs réponses. choices = [(id, libellé, style), …] avec
        style None, "suggested" ou "destructive". Un bouton Annuler est ajouté :
        on_choice(id) n'est appelé que si une réponse est choisie.
        """
        appearances = {"suggested": Adw.ResponseAppearance.SUGGESTED,
                       "destructive": Adw.ResponseAppearance.DESTRUCTIVE}
        dialog = Adw.AlertDialog(heading=title, body=_escape(message), body_use_markup=True)
        dialog.add_response("cancel", get_i18n()._("button.cancel"))
        for response, label, style in choices:
            dialog.add_response(response, label)
            if style in appearances:
                dialog.set_response_appearance(response, appearances[style])
                if style == "suggested":
                    dialog.set_default_response(response)
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda _d, response: response != "cancel" and on_choice(response))
        dialog.present(self.parent)
        return dialog

    def form(self, title, child, ok_label, on_ok, message="", destructive=False):
        """
        Dialogue avec un formulaire (child). on_ok() est appelé à la validation.
        """
        i18n = get_i18n()
        dialog = Adw.AlertDialog(heading=title, body=_escape(message), extra_child=child)
        dialog.add_response("cancel", i18n._("button.cancel"))
        dialog.add_response("ok", ok_label)
        dialog.set_response_appearance(
            "ok", Adw.ResponseAppearance.DESTRUCTIVE if destructive else Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("ok")
        dialog.set_close_response("cancel")

        def on_response(_dialog, response):
            if response == "ok":
                on_ok()

        dialog.connect("response", on_response)
        dialog.present(self.parent)
        return dialog

    def window(self, title, child, ok_label, on_ok, width=600, height=-1, destructive=False):
        """
        Dialogue libre (Adw.Dialog) avec Annuler / ok_label dans la barre de titre.
        on_ok() renvoie True pour fermer le dialogue, False pour le garder ouvert
        (erreur de saisie, opération lancée qui fermera elle-même le dialogue…).
        Retourne (dialog, bouton_ok).
        """
        i18n = get_i18n()
        dialog = Adw.Dialog(title=title, content_width=width, content_height=height)

        cancel = Gtk.Button(label=i18n._("button.cancel"))
        cancel.connect("clicked", lambda _b: dialog.close())
        ok = Gtk.Button(label=ok_label)
        ok.add_css_class("destructive-action" if destructive else "suggested-action")
        ok.connect("clicked", lambda _b: on_ok() and dialog.close())

        header = Adw.HeaderBar(show_end_title_buttons=False, show_start_title_buttons=False)
        header.pack_start(cancel)
        header.pack_end(ok)

        scrolled = Gtk.ScrolledWindow(child=child, propagate_natural_height=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER)
        view = Adw.ToolbarView(content=scrolled)
        view.add_top_bar(header)
        dialog.set_child(view)
        dialog.set_default_widget(ok)
        dialog.present(self.parent)
        return dialog, ok

    # ==================== Progression ====================

    def progress(self, title, status="", cancellable=False, on_cancel=None):
        return ProgressDialog(self.parent, title, status, cancellable, on_cancel)

    # ==================== Fichiers ====================

    @staticmethod
    def _filters(filters):
        """filters: liste de (nom, [motifs])"""
        store = Gio.ListStore(item_type=Gtk.FileFilter)
        for name, patterns in filters or []:
            file_filter = Gtk.FileFilter(name=name)
            for pattern in patterns:
                file_filter.add_pattern(pattern)
            store.append(file_filter)
        return store

    def open_file(self, title, on_selected, filters=None, initial_folder=None):
        """on_selected(chemin: str) n'est appelé que si un fichier est choisi"""
        dialog = Gtk.FileDialog(title=title, modal=True)
        if filters:
            dialog.set_filters(self._filters(filters))
        if initial_folder:
            dialog.set_initial_folder(Gio.File.new_for_path(str(initial_folder)))

        def done(dlg, result):
            try:
                gfile = dlg.open_finish(result)
            except GLib.Error:
                return  # annulé
            if gfile and gfile.get_path():
                on_selected(gfile.get_path())

        dialog.open(self.parent, None, done)

    def save_file(self, title, on_selected, initial_name=None):
        dialog = Gtk.FileDialog(title=title, modal=True)
        if initial_name:
            dialog.set_initial_name(initial_name)

        def done(dlg, result):
            try:
                gfile = dlg.save_finish(result)
            except GLib.Error:
                return
            if gfile and gfile.get_path():
                on_selected(gfile.get_path())

        dialog.save(self.parent, None, done)
