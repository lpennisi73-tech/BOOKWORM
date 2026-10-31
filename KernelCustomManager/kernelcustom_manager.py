#!/usr/bin/env python3
"""
KernelCustom Manager - Version Python/GTK
Édition Professionnelle v2.3
Point d'entrée principal
"""

import logging

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, Notify, GLib

from utils import paths


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


def main():
    """Point d'entrée principal"""
    # Migration de ~/KernelCustomManager/build AVANT que les gestionnaires
    # ne créent leurs dossiers dans le nouveau dossier de travail
    migration_message = paths.migrate_legacy_data()
    setup_logging()
    if migration_message:
        logging.info(migration_message)

    # Import après la migration (les modules utilisent paths.data_dir())
    from gui.main_window import KernelManagerWindow

    # Définir le nom de l'application pour GNOME Shell
    # Cela permet à GNOME de lier l'application au fichier .desktop
    GLib.set_prgname("KernelCustom Manager")
    GLib.set_application_name("KernelCustom Manager")

    print("KernelCustom Manager - Version Python/GTK")
    print("Édition Professionnelle v2.3")
    print("=" * 50)
    print(f"📁 Dossier de travail : {paths.data_dir()}")

    # Initialiser les notifications
    try:
        Notify.init("KernelCustom Manager")
        print("✓ Notifications activées")
    except Exception:
        print("⚠️  Notifications désactivées (installez gir1.2-notify-0.7)")

    # Créer et afficher la fenêtre
    win = KernelManagerWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()

    if migration_message:
        def show_migration():
            win.dialogs.show_info("KernelCustom Manager", migration_message)
            return False
        GLib.idle_add(show_migration)

    Gtk.main()


if __name__ == "__main__":
    main()
