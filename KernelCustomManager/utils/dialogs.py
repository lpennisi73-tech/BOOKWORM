"""
Dialogues et utilitaires réutilisables
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


class DialogHelper:
    """Classe helper pour les dialogues"""
    
    def __init__(self, parent_window):
        self.parent = parent_window
    
    def show_info(self, title, message):
        """Affiche un dialogue d'information"""
        dialog = Gtk.MessageDialog(
            transient_for=self.parent,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
    
    def show_error(self, title, message):
        """Affiche un dialogue d'erreur"""
        dialog = Gtk.MessageDialog(
            transient_for=self.parent,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
    
    def show_question(self, title, message):
        """Affiche un dialogue de question (Oui/Non)"""
        dialog = Gtk.MessageDialog(
            transient_for=self.parent,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=title
        )
        dialog.format_secondary_text(message)
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.YES
    
    def show_warning(self, title, message):
        """Affiche un avertissement"""
        dialog = Gtk.MessageDialog(
            transient_for=self.parent,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
