"""
Onglet de gestion des kernels installés
"""

import platform
import subprocess

from gui.widgets import SimpleList, button, button_row, markup_label, page_box
from utils.dialogs import run_task
from utils.i18n import get_i18n
from utils.pkexec_helper import PkexecHelper


def create_kernels_tab(main_window):
    """Crée l'onglet de gestion des kernels"""
    i18n = get_i18n()
    box = page_box()

    box.append(markup_label(
        f"<b>{i18n._('kernel.active')}</b> <span color='green'>{platform.release()}</span>"))

    kernels = SimpleList(["", i18n._("kernel.column_package"), i18n._("kernel.column_version")], expand=[1])
    box.append(kernels)

    box.append(button_row(
        button(i18n._("button.refresh"), lambda: refresh_kernels(main_window, kernels)),
        button(i18n._("button.remove"), lambda: remove_kernel(main_window, kernels), "destructive-action"),
        button(i18n._("button.reboot"), lambda: reboot_system(main_window)),
    ))

    refresh_kernels(main_window, kernels)
    return box


def refresh_kernels(main_window, kernels):
    """Actualise la liste des kernels"""
    current = platform.release()
    rows = []
    for kernel in main_window.kernel_manager.get_installed_kernels():
        mark = "✓" if current in kernel['package'] else ""
        rows.append([mark, kernel['package'], kernel['version']])
    kernels.set_rows(rows)


def _related_packages(package):
    """Paquets linux-image/linux-headers installés pour la même version"""
    kernel_version = package.replace("linux-image-", "")
    try:
        result = subprocess.run(["dpkg-query", "-W", "-f=${db:Status-Abbrev} ${Package}\n"],
                                capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return [package]
    related = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "ii":
            name = parts[1]
            if name in (f"linux-image-{kernel_version}", f"linux-headers-{kernel_version}",
                        f"linux-image-{kernel_version}-dbg"):
                related.append(name)
    return related or [package]


def remove_kernel(main_window, kernels):
    """Supprime un kernel sélectionné"""
    i18n = get_i18n()
    row = kernels.selected()
    if row is None:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.select_kernel"))
        return

    if row[0] == "✓":
        main_window.dialogs.show_error(i18n._("misc.impossible"),
                                       i18n._("message.error.active_kernel", kernel=platform.release()))
        return

    related = _related_packages(row[1])
    packages_list = "\n• ".join(related)

    def do_remove():
        progress = main_window.dialogs.progress(
            i18n._("dialog.remove_kernel.title"),
            i18n._("dialog.remove_kernel.status_count", count=len(related)))
        progress.pulse()

        def done(result):
            progress.close()
            success, _, error = result
            if success:
                main_window.dialogs.show_info(i18n._("message.success.title"),
                                              i18n._("message.success.kernel_deleted", packages=packages_list))
                refresh_kernels(main_window, kernels)
            else:
                main_window.dialogs.show_error(i18n._("message.error.title"),
                                               i18n._("message.error.remove_failed", error=error))

        def failed(error):
            progress.close()
            main_window.dialogs.show_error(i18n._("message.error.title"),
                                           i18n._("message.error.remove_failed", error=str(error)))

        # Helper privilégié (refuse de supprimer le kernel en cours d'exécution)
        run_task(lambda: PkexecHelper.remove_packages(*related, autoremove=True), done, failed)

    main_window.dialogs.ask(i18n._("message.confirm.title"),
                            i18n._("message.confirm.delete_kernel", packages=packages_list),
                            on_yes=do_remove, destructive=True)


def reboot_system(main_window):
    """Redémarre le système"""
    i18n = get_i18n()

    def do_reboot():
        def done(result):
            success, _, error = result
            if not success:
                main_window.dialogs.show_error(i18n._("message.error.title"),
                                               i18n._("message.error.reboot_failed", error=error))
        run_task(PkexecHelper.reboot, done)

    main_window.dialogs.ask(i18n._("message.confirm.title"), i18n._("message.confirm.reboot"),
                            on_yes=do_reboot, destructive=True)
