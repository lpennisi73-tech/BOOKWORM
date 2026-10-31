"""
Onglet de compilation et configuration
"""

import json
import re
import urllib.request

from gi.repository import Gtk

from gui.widgets import button, entry, markup_label, page_box, section, title_label
from utils.dialogs import run_task
from utils.i18n import get_i18n

# Version publiée sur kernel.org : 6.17, 6.16.9 (pas de -rc : autre dossier sur le CDN)
KERNEL_VERSION_RE = re.compile(r'^\d+\.\d+(\.\d+)?$')


class DownloadCancelled(Exception):
    pass


def create_build_tab(main_window):
    """Crée l'onglet de compilation"""
    i18n = get_i18n()
    box = page_box(spacing=18, margin=18)

    # === TÉLÉCHARGEMENT ===
    download, download_inner = section(i18n._("button.download"))
    row = Gtk.Box(spacing=8)
    row.append(Gtk.Label(label=i18n._("build.version_label")))
    main_window.version_entry = entry(placeholder="6.17.5")
    main_window.version_entry.set_hexpand(True)
    main_window.version_entry.connect("activate", lambda _e: download_kernel(main_window))
    row.append(main_window.version_entry)
    row.append(button(i18n._("button.download"), lambda: download_kernel(main_window), "suggested-action"))
    row.append(button(i18n._("button.update"), lambda: auto_update_kernel(main_window),
                      tooltip=i18n._("tooltip.update_stable")))
    download_inner.append(row)
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

    # Version stable de kernel.org en arrière-plan (réseau : ne pas bloquer le démarrage)
    def set_stable(version):
        if version and not main_window.version_entry.get_text():
            main_window.version_entry.set_text(version)
    run_task(get_stable_kernel_version, set_stable)

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


def get_stable_kernel_version():
    """Récupère la version stable depuis kernel.org (None en cas d'échec)"""
    try:
        with urllib.request.urlopen("https://www.kernel.org/releases.json", timeout=5) as response:
            data = json.loads(response.read().decode())
        for release in data.get('releases', []):
            if release.get('moniker') == 'stable':
                return release.get('version')
    except Exception:
        pass
    return None


def download_kernel(main_window):
    """Télécharge et extrait les sources du kernel"""
    i18n = get_i18n()
    version = main_window.version_entry.get_text().strip()

    if not version:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.enter_version"))
        return
    if not KERNEL_VERSION_RE.match(version):
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.invalid_version"))
        return

    progress = main_window.dialogs.progress(i18n._("dialog.download.title"),
                                            i18n._("dialog.download.status", version=version),
                                            cancellable=True)

    def on_progress(percent, message=None):
        if progress.cancelled:
            raise DownloadCancelled()  # interrompt urlretrieve
        progress.set_fraction(percent / 100.0)
        if message:
            progress.set_status(message)

    def done(success):
        progress.close()
        update_source_label(main_window)
        if progress.cancelled:
            main_window.dialogs.toast(i18n._("message.info.cancelled"))
        elif success:
            main_window.dialogs.show_info(i18n._("message.success.title"),
                                          i18n._("message.success.kernel_downloaded", version=version))
        else:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.download_failed"))

    def failed(error):
        progress.close()
        main_window.dialogs.show_error(i18n._("message.error.title"), str(error))

    run_task(lambda: main_window.kernel_manager.download_kernel(version, on_progress), done, failed)


def auto_update_kernel(main_window):
    """Mise à jour vers la version stable de kernel.org"""
    i18n = get_i18n()

    def check(stable):
        if not stable:
            main_window.dialogs.show_error(i18n._("message.error.title"),
                                           i18n._("message.error.stable_version_failed"))
            return

        linux_dir = main_window.kernel_manager.base_dir / "linux"
        if linux_dir.exists() and linux_dir.resolve().name == f"linux-{stable}":
            main_window.dialogs.show_info(i18n._("message.info.already_uptodate"),
                                          i18n._("message.success.already_updated", version=stable))
            return

        def update():
            main_window.version_entry.set_text(stable)
            download_kernel(main_window)

        main_window.dialogs.ask(i18n._("message.confirm.title"),
                                i18n._("message.confirm.update_available", version=stable), on_yes=update)

    run_task(get_stable_kernel_version, check)


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

    def on_selected(source):
        if main_window.kernel_manager.import_config(source):
            update_source_label(main_window)
            main_window.dialogs.toast(i18n._("message.success.config_imported"))
        else:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.import_failed"))

    main_window.dialogs.open_file(i18n._("dialog.import_config.title"), on_selected, config_filters())


def export_config_dialog(main_window):
    """Exporte la configuration"""
    i18n = get_i18n()
    linux_dir = main_window.kernel_manager.base_dir / "linux"

    if not (linux_dir / ".config").exists():
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_config_export"))
        return

    version = linux_dir.resolve().name.replace("linux-", "")
    default_name = f"kernel-config-{version}.config"

    def on_selected(destination):
        if main_window.kernel_manager.export_config(destination):
            main_window.dialogs.toast(i18n._("message.success.config_exported"))
        else:
            main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.export_failed"))

    main_window.dialogs.save_file(i18n._("dialog.export_config.title"), on_selected, default_name)
