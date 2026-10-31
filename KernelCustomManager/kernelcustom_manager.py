#!/usr/bin/env python3
"""
KernelCustom Manager - Python / GTK4 + libadwaita
Point d'entrée principal
"""

import logging
import os
import sys

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from utils import paths

VERSION = "3.0-dev"


def setup_logging():
    """Journal de l'application : console + fichier dans le dossier de travail"""
    log_file = paths.debug_log_file()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG,
        force=True,  # remplace une éventuelle configuration implicite
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    # Une exception dans un callback GTK n'arrête pas l'application et n'apparaît
    # que sur stderr : on l'enregistre aussi dans le journal
    def log_uncaught(exc_type, exc_value, exc_tb):
        logging.critical("Exception non interceptée", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = log_uncaught


class KernelCustomApplication(Adw.Application):
    """Application unique (une seule instance, id D-Bus com.kernelcustom.manager)"""

    def __init__(self, migration_message=None):
        super().__init__(application_id=paths.APPLICATION_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.migration_message = migration_message
        self.window = None
        GLib.set_application_name("KernelCustom Manager")

    def do_startup(self):
        Adw.Application.do_startup(self)

        # Icône de l'application depuis le dépôt (installée : thème hicolor du système)
        display = Gdk.Display.get_default()
        if display is not None and paths.ICONS_DIR.is_dir():
            Gtk.IconTheme.get_for_display(display).add_search_path(str(paths.ICONS_DIR))
        Gtk.Window.set_default_icon_name(paths.APPLICATION_ID)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *a: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])

    def do_activate(self):
        if self.window is None:
            # Import après la migration (les modules utilisent paths.data_dir())
            from gui.main_window import KernelManagerWindow
            self.window = KernelManagerWindow(application=self, version=VERSION)
            if self.migration_message:
                message = self.migration_message
                GLib.idle_add(lambda: self.window.dialogs.show_info("KernelCustom Manager", message) and False)
        self.window.present()

    def notify(self, title, message, urgency="normal"):
        """
        Notification de bureau, utilisable depuis un thread.

        GNOME Shell ignore les Gio.Notification d'une application sans fichier
        com.kernelcustom.manager.desktop (lancement depuis le dépôt, ou install.sh
        lancé avec sudo) : dans ce cas on passe par org.freedesktop.Notifications.
        """
        def send():
            if not self._has_desktop_file():
                self._notify_freedesktop(title, message, urgency)
                return False
            notification = Gio.Notification.new(title)
            notification.set_body(message)
            notification.set_priority({
                "low": Gio.NotificationPriority.LOW,
                "critical": Gio.NotificationPriority.URGENT,
            }.get(urgency, Gio.NotificationPriority.NORMAL))
            self.send_notification(None, notification)
            return False
        GLib.idle_add(send)

    @staticmethod
    def _has_desktop_file():
        """Le .desktop de l'application est-il installé (dossiers XDG) ?"""
        name = f"{paths.APPLICATION_ID}.desktop"
        dirs = [GLib.get_user_data_dir()] + list(GLib.get_system_data_dirs())
        return any(os.path.isfile(os.path.join(d, "applications", name)) for d in dirs)

    def _notify_freedesktop(self, title, message, urgency):
        """Notification via org.freedesktop.Notifications (ne demande pas de .desktop)"""
        hints = {"urgency": GLib.Variant("y", {"low": 0, "critical": 2}.get(urgency, 1))}
        params = GLib.Variant("(susssasa{sv}i)", (
            "KernelCustom Manager", 0, paths.APPLICATION_ID,
            title, message, [], hints, -1))

        def on_done(bus, result):
            try:
                bus.call_finish(result)
            except GLib.Error as e:
                logging.warning("Notification impossible : %s", e.message)

        Gio.bus_get_sync(Gio.BusType.SESSION, None).call(
            "org.freedesktop.Notifications", "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications", "Notify", params,
            GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, -1, None, on_done)


def main():
    """Point d'entrée principal"""
    # Migration de ~/KernelCustomManager/build AVANT que les gestionnaires
    # ne créent leurs dossiers dans le nouveau dossier de travail
    migration_message = paths.migrate_legacy_data()
    setup_logging()
    if migration_message:
        logging.info(migration_message)

    logging.info(f"KernelCustom Manager {VERSION} - dossier de travail : {paths.data_dir()}")

    app = KernelCustomApplication(migration_message)
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
