#!/usr/bin/env python3
"""
KernelCustom Manager - Version Python/GTK
Édition Professionnelle v2.2
Point d'entrée principal
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, Notify, GLib

from gui.main_window import KernelManagerWindow


def main():
    """Point d'entrée principal"""
    # Définir le nom de l'application pour GNOME Shell
    # Cela permet à GNOME de lier l'application au fichier .desktop
    GLib.set_prgname("KernelCustom Manager")
    GLib.set_application_name("KernelCustom Manager")

    print("KernelCustom Manager - Version Python/GTK")
    print("Édition Professionnelle v2.2")
    print("=" * 50)

    # Initialiser les notifications
    try:
        Notify.init("KernelCustom Manager")
        print("✓ Notifications activées")
    except:
        print("⚠️  Notifications désactivées (installez gir1.2-notify-0.7)")

    # Créer et afficher la fenêtre
    win = KernelManagerWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    
    print("\n✨ Application lancée avec succès !")
    print("📋 Fonctionnalités disponibles :")
    print("   • Gestion complète des kernels installés")
    print("   • Compilation avec options avancées")
    print("   • Sauvegarde automatique des configurations")
    print("   • Historique des compilations")
    print("   • Profils de configuration")
    print("   • Import/Export de configs")
    print("   • Notifications système")
    print("   • Mise à jour automatique")
    print("\n🚀 Bon développement !\n")
    
    Gtk.main()


if __name__ == "__main__":
    main()
