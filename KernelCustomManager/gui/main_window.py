"""
Fenêtre principale de l'application (GTK4 + libadwaita)
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio, GLib, Gtk

from core.kernel_manager import KernelManager
from core.secureboot_manager import SecureBootManager
from utils.dialogs import DialogHelper
from utils.i18n import get_i18n
from utils import paths

# (nom de page, clé de traduction, icône, module, fonction de création)
PAGES = [
    ("kernels", "tab.kernels", "computer-symbolic", "gui.kernels_tab", "create_kernels_tab"),
    ("packages", "tab.packages", "package-x-generic-symbolic", "gui.packages_tab", "create_packages_tab"),
    ("build", "tab.build", "applications-engineering-symbolic", "gui.build_tab", "create_build_tab"),
    ("drivers", "tab.drivers", "video-display-symbolic", "gui.drivers_tab", "create_drivers_tab"),
    ("secureboot", "tab.secureboot", "security-high-symbolic", "gui.secureboot_tab", "create_secureboot_tab"),
    ("sources", "tab.sources", "folder-symbolic", "gui.sources_tab", "create_sources_tab"),
    ("profiles", "tab.profiles", "document-properties-symbolic", "gui.profiles_tab", "create_profiles_tab"),
    ("history", "tab.history", "document-open-recent-symbolic", "gui.history_tab", "create_history_tab"),
    ("cleanup", "tab.cleanup", "user-trash-symbolic", "gui.cleanup_tab", "create_cleanup_tab"),
]

LANGUAGES = [("en", "English"), ("fr", "Français")]


class KernelManagerWindow(Adw.ApplicationWindow):
    """Fenêtre principale de l'application"""

    def __init__(self, application, version=""):
        super().__init__(application=application)
        self.i18n = get_i18n()
        self.version = version
        self.set_title(self.i18n._("window.title"))
        self.set_default_size(1180, 760)
        self.set_size_request(760, 520)

        self.kernel_manager = KernelManager()
        self.kernel_manager.notifier = application.notify
        self.secureboot_manager = SecureBootManager()
        self.dialogs = DialogHelper(self)

        self._install_actions()
        self.create_ui()

    # ==================== Interface ====================

    def create_ui(self):
        """Crée l'interface utilisateur"""
        import importlib

        self.stack = Adw.ViewStack(vexpand=True)
        for name, title_key, icon, module_name, factory in PAGES:
            module = importlib.import_module(module_name)
            page = getattr(module, factory)(self)
            self.stack.add_titled_with_icon(page, name, self.i18n._(title_key), icon)

        header = Adw.HeaderBar()
        switcher = Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(switcher)

        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=self._build_menu(),
                                     tooltip_text=self.i18n._("menu.main"), primary=True)
        header.pack_end(menu_button)

        # Fenêtre étroite (9 onglets : ~1600 px en largeur naturelle) : le sélecteur passe en bas
        switcher_bar = Adw.ViewSwitcherBar(stack=self.stack)
        breakpoint = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 1550sp"))
        breakpoint.add_setter(header, "title-widget", Adw.WindowTitle(
            title=self.i18n._("window.title"), subtitle=self.version))
        breakpoint.add_setter(switcher_bar, "reveal", True)
        self.add_breakpoint(breakpoint)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(self.stack)
        toolbar_view.add_bottom_bar(switcher_bar)

        self.toast_overlay = Adw.ToastOverlay(child=toolbar_view)
        self.dialogs.toast_overlay = self.toast_overlay
        self.set_content(self.toast_overlay)

    def _build_menu(self):
        menu = Gio.Menu()
        languages = Gio.Menu()
        for code, name in LANGUAGES:
            languages.append(name, f"win.language::{code}")
        menu.append_submenu(f"🌐 {self.i18n._('menu.language')}", languages)
        section = Gio.Menu()
        section.append(self.i18n._("menu.about"), "win.about")
        section.append(self.i18n._("menu.quit"), "app.quit")
        menu.append_section(None, section)
        return menu

    def _install_actions(self):
        language = Gio.SimpleAction.new_stateful(
            "language", GLib.VariantType.new("s"), GLib.Variant.new_string(self.i18n.get_language()))
        language.connect("activate", self.on_language_changed)
        self.add_action(language)

        about = Gio.SimpleAction.new("about", None)
        about.connect("activate", lambda *a: self.show_about())
        self.add_action(about)

    # ==================== Actions ====================

    def on_language_changed(self, action, value):
        new_lang = value.get_string()
        if new_lang == self.i18n.get_language():
            return
        action.set_state(value)
        self.i18n.set_language(new_lang)
        # Message dans la NOUVELLE langue
        self.dialogs.show_info(self.i18n._("language.changed_title"), self.i18n._("language.restart"))

    def show_about(self):
        about = Adw.AboutDialog(
            application_name=self.i18n._("window.title"),
            application_icon=paths.APPLICATION_ID,
            version=self.version,
            comments=self.i18n._("about.comments"),
            license_type=Gtk.License.GPL_2_0_ONLY,
            developer_name="KernelCustom Manager",
        )
        about.present(self)
