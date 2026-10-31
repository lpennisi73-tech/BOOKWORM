"""
Onglet de gestion des paquets locaux (.deb compilés)
"""

import re
from pathlib import Path

from gi.repository import Gtk

from gui.widgets import SimpleList, button, button_row, markup_label, page_box
from utils.dialogs import run_task
from utils.i18n import get_i18n
from utils.pkexec_helper import PkexecHelper


def create_packages_tab(main_window):
    """Crée l'onglet de gestion des paquets"""
    i18n = get_i18n()
    box = page_box()

    packages = SimpleList([i18n._("kernel.column_package"), i18n._("kernel.column_size")], expand=[0],
                          on_activate=lambda row: install_package(main_window, packages))
    box.append(packages)

    box.append(button_row(
        button(i18n._("button.refresh"), lambda: refresh_packages(main_window, packages)),
        button(i18n._("button.install"), lambda: install_package(main_window, packages), "suggested-action"),
    ))

    refresh_packages(main_window, packages)
    return box


def refresh_packages(main_window, packages):
    """Actualise la liste des paquets"""
    packages.set_rows([pkg['name'], pkg['size']] for pkg in main_window.kernel_manager.get_local_packages())


def _find_headers(repo_dir, package_name):
    """Paquet linux-headers correspondant à un linux-image, ou None"""
    match = re.search(r'linux-image-([^_]+)', package_name)
    if not match:
        return None
    return next(iter(sorted(repo_dir.glob(f"linux-headers-{match.group(1)}_*.deb"))), None)


def install_package(main_window, packages):
    """Installe un paquet sélectionné (avec ses headers si disponibles)"""
    i18n = get_i18n()
    row = packages.selected()
    if row is None:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.select_package"))
        return

    repo_dir = main_window.kernel_manager.repo_dir
    package_name = row[0]
    package_path = repo_dir / package_name
    headers_file = _find_headers(repo_dir, package_name)

    # Options d'installation
    form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    form.append(markup_label(f"<b>{i18n._('message.info.title')}</b>\n{package_name}"))
    if headers_file:
        headers_check = Gtk.CheckButton(label=i18n._("dialog.install_options.install_headers"), active=True)
        form.append(headers_check)
        form.append(markup_label(f"<small>{headers_file.name}</small>"))
    else:
        headers_check = Gtk.CheckButton(label=i18n._("dialog.install_options.install_headers_unavailable"),
                                        active=False, sensitive=False)
        form.append(headers_check)

    def on_install():
        to_install = [str(package_path)]
        if headers_file and headers_check.get_active():
            to_install.append(str(headers_file))
        _run_install(main_window, to_install)

    main_window.dialogs.form(i18n._("dialog.install_options.title"), form, i18n._("button.install"), on_install)


def _run_install(main_window, to_install):
    i18n = get_i18n()
    names = [Path(p).name for p in to_install]
    progress = main_window.dialogs.progress(
        i18n._("dialog.install_kernel.title"),
        i18n._("dialog.install_kernel.installing", package=", ".join(names)))
    progress.pulse()

    def done(result):
        progress.close()
        success, _, error = result
        if success:
            main_window.dialogs.show_info(i18n._("message.success.title"), i18n._(
                "message.success.packages_installed", packages="\n• ".join(names)))
        else:
            main_window.dialogs.show_error(i18n._("message.error.install_failed"), error)

    def failed(error):
        progress.close()
        main_window.dialogs.show_error(i18n._("message.error.install_failed"), str(error))

    # Helper privilégié : apt-get install des .deb (dépendances résolues)
    run_task(lambda: PkexecHelper.install_packages(*to_install), done, failed)
