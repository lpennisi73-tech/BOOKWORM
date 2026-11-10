"""
Onglet de compilation et configuration
"""

from gi.repository import Gtk

from core import kernel_releases
from core.kernel_manager import DownloadCancelled
from gui.widgets import button, entry, markup_label, page_box, section, title_label
from utils.dialogs import run_task
from utils.i18n import get_i18n


class ReleasePicker:
    """
    Choix de la version à télécharger : liste des versions publiées sur kernel.org
    (stable, mainline, longterm) + champ libre pour une version précise.
    La liste remplit le champ ; c'est toujours le champ qui est téléchargé.
    """

    def __init__(self, on_activate):
        i18n = get_i18n()
        self.releases = []
        self._filling = False

        self.dropdown = Gtk.DropDown(model=Gtk.StringList.new([i18n._("build.releases_loading")]),
                                     hexpand=True, sensitive=False)
        self.dropdown.connect("notify::selected", self._on_selected)
        self.entry = entry(placeholder="7.3.3")
        self.entry.set_hexpand(True)
        self.entry.connect("activate", lambda _e: on_activate())
        self.entry.connect("changed", lambda _e: self._update_hint())
        self.hint = markup_label()
        self.hint.add_css_class("dim-label")
        self.hint.add_css_class("caption")
        self.hint.set_visible(False)

    def version(self):
        return self.entry.get_text().strip()

    def selected(self):
        """KernelRelease choisie dans la liste (None si la liste est vide)"""
        index = self.dropdown.get_selected()
        return self.releases[index] if index < len(self.releases) else None

    def set_releases(self, releases, select=None):
        """Remplit la liste. select : KernelRelease à sélectionner (défaut : la première)"""
        i18n = get_i18n()
        self._filling = True
        self.releases = list(releases)
        labels = [self._label(r) for r in self.releases] or [i18n._("build.releases_unavailable")]
        self.dropdown.set_model(Gtk.StringList.new(labels))
        self.dropdown.set_sensitive(bool(self.releases))
        if select in self.releases:
            self.dropdown.set_selected(self.releases.index(select))
        self._filling = False
        chosen = self.selected()
        if chosen and (select is not None or not self.version()):
            self.entry.set_text(chosen.version)
        self._update_hint()

    @staticmethod
    def _label(release):
        i18n = get_i18n()
        label = f"{i18n._('build.branch.' + release.branch)} — {release.version}"
        return f"{label} ({i18n._('build.eol')})" if release.eol else label

    def _on_selected(self, *_args):
        chosen = self.selected()
        if chosen and not self._filling:
            self.entry.set_text(chosen.version)

    def _update_hint(self):
        """Avertissement sous le champ : pré-version, fin de vie, ou branche et date"""
        i18n = get_i18n()
        version = self.version()
        release = kernel_releases.find_release(self.releases, version)
        if kernel_releases.is_prerelease(version) and kernel_releases.is_valid_version(version):
            text = f"⚠️ {i18n._('build.hint_prerelease')}"
        elif release and release.eol:
            text = f"⚠️ {i18n._('build.hint_eol')}"
        elif release:
            text = i18n._("build.hint_release", branch=i18n._("build.branch." + release.branch),
                          date=release.date)
        else:
            text = ""
        self.hint.set_text(text)
        self.hint.set_visible(bool(text))


def create_build_tab(main_window):
    """Crée l'onglet de compilation"""
    i18n = get_i18n()
    box = page_box(spacing=18, margin=18)

    # === TÉLÉCHARGEMENT ===
    download, download_inner = section(i18n._("button.download"))
    picker = ReleasePicker(lambda: download_kernel(main_window))
    main_window.release_picker = picker
    main_window.version_entry = picker.entry

    branch_row = Gtk.Box(spacing=8)
    branch_row.append(Gtk.Label(label=i18n._("build.branch_label")))
    branch_row.append(picker.dropdown)
    branch_row.append(button(i18n._("button.update"), lambda: auto_update_kernel(main_window),
                             tooltip=i18n._("tooltip.update_branch")))
    download_inner.append(branch_row)

    row = Gtk.Box(spacing=8)
    row.append(Gtk.Label(label=i18n._("build.version_label")))
    row.append(picker.entry)
    row.append(button(i18n._("button.download"), lambda: download_kernel(main_window), "suggested-action"))
    download_inner.append(row)
    download_inner.append(picker.hint)
    box.append(download)

    # === CONFIGURATION ===
    config, config_inner = section(i18n._("button.configure"))
    config_row = Gtk.Box(spacing=8, homogeneous=True)
    config_row.append(button(i18n._("button.configure"), lambda: configure_kernel(main_window)))
    config_row.append(button(i18n._("button.import"), lambda: import_config_dialog(main_window)))
    config_row.append(button(i18n._("button.export"), lambda: export_config_dialog(main_window)))
    config_inner.append(config_row)
    box.append(config)

    # === COMPILATION ===
    compile_section, compile_inner = section(i18n._("button.compile"))
    main_window.build_source_label = markup_label()
    compile_inner.append(main_window.build_source_label)
    compile_btn = button(i18n._("button.compile"), lambda: compile_kernel_dialog(main_window), "suggested-action")
    compile_btn.add_css_class("pill")
    compile_btn.set_halign(Gtk.Align.CENTER)
    compile_inner.append(compile_btn)
    box.append(compile_section)

    update_source_label(main_window)

    # Versions de kernel.org en arrière-plan (réseau : ne pas bloquer le démarrage)
    run_task(kernel_releases.get_releases, picker.set_releases)

    scrolled = Gtk.ScrolledWindow(child=box, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
    return scrolled


def update_source_label(main_window):
    """Affiche l'arbre de sources actif (dossier de travail / linux)"""
    i18n = get_i18n()
    linux_dir = main_window.kernel_manager.base_dir / "linux"
    if linux_dir.exists():
        name = linux_dir.resolve().name
        has_config = (linux_dir / ".config").exists()
        state = "✅ .config" if has_config else f"⚠️ {i18n._('message.error.no_config')}"
        main_window.build_source_label.set_markup(f"<b>{name}</b>  ·  {state}")
    else:
        main_window.build_source_label.set_markup(f"<i>{i18n._('message.error.no_kernel_source')}</i>")


def download_kernel(main_window, replace=False):
    """Télécharge et extrait les sources de la version saisie"""
    i18n = get_i18n()
    manager = main_window.kernel_manager
    picker = main_window.release_picker
    version = picker.version()

    if not version:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.enter_version"))
        return
    if not kernel_releases.is_valid_version(version):
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.invalid_version"))
        return

    # Sources déjà présentes : les réutiliser, ou les remplacer explicitement
    if not replace and manager.source_tree(version):
        _ask_existing_sources(main_window, version)
        return

    # Version de la liste : URL donnée par kernel.org. Sinon elle est déduite de la version
    release = kernel_releases.find_release(picker.releases, version)
    progress = main_window.dialogs.progress(i18n._("dialog.download.title"),
                                            i18n._("dialog.download.status", version=version),
                                            cancellable=True)

    def on_progress(fraction, message=None):
        if message:
            progress.set_status(message)
        if fraction is None:
            progress.pulse()
        else:
            progress.set_fraction(fraction)

    def done(_result):
        progress.close()
        update_source_label(main_window)
        main_window.dialogs.show_info(i18n._("message.success.title"),
                                      i18n._("message.success.kernel_downloaded", version=version))

    def failed(error):
        progress.close()
        update_source_label(main_window)
        if isinstance(error, DownloadCancelled):
            main_window.dialogs.toast(i18n._("message.info.cancelled"))
        else:
            main_window.dialogs.show_error(i18n._("message.error.download_failed"), str(error))

    run_task(lambda: manager.download_kernel(version, release.source if release else None, on_progress,
                                             lambda: progress.cancelled, replace),
             done, failed)


def _ask_existing_sources(main_window, version):
    """Les sources linux-<version> existent déjà : activer l'arbre ou le re-télécharger"""
    i18n = get_i18n()
    manager = main_window.kernel_manager
    active = manager.active_version() == version

    def on_choice(choice):
        if choice == "redownload":
            download_kernel(main_window, replace=True)
            return
        try:
            manager.activate_sources(version)
        except Exception as e:
            main_window.dialogs.show_error(i18n._("message.error.title"), str(e))
            return
        update_source_label(main_window)
        main_window.dialogs.toast(i18n._("message.success.sources_activated", version=version))

    choices = [("redownload", i18n._("button.redownload"), "destructive")]
    if not active:
        choices.append(("activate", i18n._("button.use_existing"), "suggested"))
    main_window.dialogs.choose(
        i18n._("message.confirm.title"),
        i18n._("message.confirm.sources_exist_active" if active else "message.confirm.sources_exist",
               version=version),
        choices, on_choice)


def auto_update_kernel(main_window):
    """Recherche la dernière version de la branche choisie dans la liste"""
    i18n = get_i18n()
    picker = main_window.release_picker
    current = picker.selected()

    def check(releases):
        if not releases:
            main_window.dialogs.show_error(i18n._("message.error.title"),
                                           i18n._("message.error.releases_failed"))
            return

        latest = (kernel_releases.latest_for(releases, current) if current else None) or releases[0]
        picker.set_releases(releases, select=latest)

        if main_window.kernel_manager.active_version() == latest.version:
            main_window.dialogs.show_info(i18n._("message.info.already_uptodate"),
                                          i18n._("message.success.already_updated", version=latest.version))
            return

        branch = i18n._("build.branch." + latest.branch)
        main_window.dialogs.ask(i18n._("message.confirm.title"),
                                i18n._("message.confirm.update_available", version=latest.version, branch=branch),
                                on_yes=lambda: download_kernel(main_window))

    run_task(lambda: kernel_releases.get_releases(refresh=True), check)


def configure_kernel(main_window):
    """Configure le kernel"""
    i18n = get_i18n()
    if not (main_window.kernel_manager.base_dir / "linux").exists():
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_kernel_source"))
        return

    from gui.build_tab_config import show_config_dialog
    show_config_dialog(main_window)


def compile_kernel_dialog(main_window):
    """Dialogue de compilation"""
    from gui.build_tab_compile import show_compile_dialog
    show_compile_dialog(main_window)


def config_filters():
    i18n = get_i18n()
    return [(i18n._("dialog.import_config.filter_name"), ["*.config", "*.conf", "config-*"]),
            (i18n._("secureboot.all_files"), ["*"])]


def import_config_dialog(main_window):
    """Importe une configuration"""
    i18n = get_i18n()

    if not (main_window.kernel_manager.base_dir / "linux").is_dir():
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_kernel_source"))
        return

    def on_selected(source):
        def done(success):
            update_source_label(main_window)
            if success:
                main_window.dialogs.toast(i18n._("message.success.config_imported"))
            else:
                main_window.dialogs.show_error(i18n._("message.error.title"),
                                               i18n._("message.error.import_failed"))

        # make olddefconfig : dans un thread
        run_task(lambda: main_window.kernel_manager.import_config(source), done, lambda _e: done(False))

    main_window.dialogs.open_file(i18n._("dialog.import_config.title"), on_selected, config_filters())


def export_config_dialog(main_window):
    """Exporte la configuration"""
    i18n = get_i18n()
    linux_dir = main_window.kernel_manager.base_dir / "linux"

    if not (linux_dir / ".config").exists():
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_config_export"))
        return

    version = main_window.kernel_manager.tree_version()
    default_name = f"kernel-config-{version}.config"

    def on_selected(destination):
        if main_window.kernel_manager.export_config(destination):
            main_window.dialogs.toast(i18n._("message.success.config_exported"))
        else:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.export_failed"))

    main_window.dialogs.save_file(i18n._("dialog.export_config.title"), on_selected, default_name)
