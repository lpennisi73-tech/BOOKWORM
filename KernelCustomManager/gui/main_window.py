"""
Fenêtre principale de l'application
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from core.kernel_manager import KernelManager
from utils.dialogs import DialogHelper


class KernelManagerWindow(Gtk.Window):
    """Fenêtre principale de l'application"""
    
    def __init__(self):
        super().__init__(title="KernelCustom Manager")
        self.set_default_size(900, 600)
        self.set_border_width(10)
        
        self.kernel_manager = KernelManager()
        self.dialogs = DialogHelper(self)
        
        # Header Bar
        headerbar = Gtk.HeaderBar()
        headerbar.set_show_close_button(True)
        headerbar.props.title = "KernelCustom Manager"
        headerbar.props.subtitle = "Édition Professionnelle v2.0"
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
        from gui.profiles_tab import create_profiles_tab
        from gui.history_tab import create_history_tab
        
        # Ajouter les onglets
        self.stack.add_titled(
            create_kernels_tab(self),
            "kernels",
            "Kernels installés"
        )
        
        self.stack.add_titled(
            create_packages_tab(self),
            "packages",
            "Paquets locaux"
        )
        
        self.stack.add_titled(
            create_build_tab(self),
            "build",
            "Compiler"
        )
        
        self.stack.add_titled(
            create_profiles_tab(self),
            "profiles",
            "Profils"
        )
        
        self.stack.add_titled(
            create_history_tab(self),
            "history",
            "Historique"
        )
        
        # Stack Switcher
        stack_switcher = Gtk.StackSwitcher()
        stack_switcher.set_stack(self.stack)
        
        # Layout principal
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.pack_start(stack_switcher, False, False, 0)
        vbox.pack_start(self.stack, True, True, 0)
        
        self.add(vbox)
