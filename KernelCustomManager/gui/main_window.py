"""
Fenêtre principale de l'application
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from pathlib import Path

from core.kernel_manager import KernelManager
from utils.dialogs import DialogHelper
from utils.i18n import get_i18n


class KernelManagerWindow(Gtk.Window):
    """Fenêtre principale de l'application"""
    
    def __init__(self):
        self.i18n = get_i18n()
        super().__init__(title=self.i18n._("window.title"))
        self.set_default_size(900, 600)
        self.set_border_width(10)

        self.kernel_manager = KernelManager()
        self.dialogs = DialogHelper(self)
        
        # Icône
        try:
            icon_path = Path(__file__).parent.parent / "icon.svg"
            if icon_path.exists():
                self.set_icon_from_file(str(icon_path))
            else:
                self.set_icon_name("system-software-update")
        except:
            pass
        
        # Header Bar
        headerbar = Gtk.HeaderBar()
        headerbar.set_show_close_button(True)
        headerbar.props.title = self.i18n._("window.title")
        headerbar.props.subtitle = self.i18n._("window.subtitle")

        # Language selector
        lang_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        lang_label = Gtk.Label(label="🌐")
        lang_box.pack_start(lang_label, False, False, 0)

        self.lang_combo = Gtk.ComboBoxText()
        self.lang_combo.append("en", "English")
        self.lang_combo.append("fr", "Français")
        self.lang_combo.set_active_id(self.i18n.get_language())
        self.lang_combo.connect("changed", self.on_language_changed)
        lang_box.pack_start(self.lang_combo, False, False, 0)

        headerbar.pack_end(lang_box)

        self.set_titlebar(headerbar)

        self.create_ui()
    
    def create_ui(self):
        """Crée l'interface utilisateur"""
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        
        # Import des onglets
        from gui.kernels_tab import create_kernels_tab
        from gui.packages_tab import create_packages_tab
        from gui.build_tab import create_build_tab
        from gui.drivers_tab import create_drivers_tab
        from gui.profiles_tab import create_profiles_tab
        from gui.history_tab import create_history_tab
        from gui.sources_tab import create_sources_tab
        
        # Ajouter les onglets
        self.stack.add_titled(
            create_kernels_tab(self),
            "kernels",
            self.i18n._("tab.kernels")
        )

        self.stack.add_titled(
            create_packages_tab(self),
            "packages",
            self.i18n._("tab.packages")
        )

        self.stack.add_titled(
            create_build_tab(self),
            "build",
            self.i18n._("tab.build")
        )

        self.stack.add_titled(
            create_drivers_tab(self),
            "drivers",
            self.i18n._("tab.drivers")
        )

        self.stack.add_titled(
            create_sources_tab(self),
            "sources",
            self.i18n._("tab.sources")
        )

        self.stack.add_titled(
            create_profiles_tab(self),
            "profiles",
            self.i18n._("tab.profiles")
        )

        self.stack.add_titled(
            create_history_tab(self),
            "history",
            self.i18n._("tab.history")
        )
        
        # Stack Switcher
        stack_switcher = Gtk.StackSwitcher()
        stack_switcher.set_stack(self.stack)
        
        # Layout principal
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.pack_start(stack_switcher, False, False, 0)
        vbox.pack_start(self.stack, True, True, 0)

        self.add(vbox)

    def on_language_changed(self, combo):
        """Handle language change"""
        new_lang = combo.get_active_id()
        if new_lang and new_lang != self.i18n.get_language():
            self.i18n.set_language(new_lang)
            # Show restart message
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Language Changed" if new_lang == "en" else "Langue modifiée"
            )
            message = "Please restart the application for the language change to take effect." if new_lang == "en" else "Veuillez redémarrer l'application pour que le changement de langue prenne effet."
            dialog.format_secondary_text(message)
            dialog.run()
            dialog.destroy()