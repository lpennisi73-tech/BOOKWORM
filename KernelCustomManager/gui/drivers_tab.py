"""
Onglet de gestion des pilotes GPU (NVIDIA, AMD et Intel)
Dépôts Debian, pilote officiel NVIDIA (.run), historique et rollback
"""

from datetime import datetime

from gi.repository import GLib, Gtk

from core.driver_manager import DriverManager
from gui.widgets import (Row, SimpleList, button, button_row, info_bar, inner_tabs, markup_label,
                         page_box, section, title_label)
from utils.dialogs import run_task
from utils.i18n import get_i18n
from utils.pkexec_helper import PkexecHelper

VENDORS = ('NVIDIA', 'AMD', 'Intel')


class DriversPage:
    """État et widgets de l'onglet Pilotes"""

    def __init__(self, main_window):
        self.win = main_window
        self.dialogs = main_window.dialogs
        self.i18n = get_i18n()
        self.manager = DriverManager()
        self.gpu = None            # dict de detect_gpu() ou None
        self.official = None       # informations du dernier pilote NVIDIA trouvé

    @property
    def vendor(self):
        if self.gpu and self.gpu.get('vendor') in VENDORS:
            return self.gpu['vendor']
        return None

    # ==================== Construction ====================

    def build(self):
        i18n = self.i18n
        manager = self.manager

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.info = info_bar(
            f"<b>💿 {i18n._('drivers.distribution')}:</b> "
            f"{GLib.markup_escape_text(manager.distro_info['name'])} {manager.distro_info['version']}",
            f"<b>{'🪟' if manager.display_server == 'Wayland' else '🖼️'} "
            f"{i18n._('drivers.display_server')}:</b> {manager.display_server}",
        )
        root.append(self.info)

        tabs, _stack = inner_tabs([
            ("install", i18n._("drivers.tab_installation"), self._build_install()),
            ("history", i18n._("drivers.tab_history"), self._build_history()),
            ("rollback", i18n._("drivers.tab_rollback"), self._build_rollback()),
        ])
        root.append(tabs)

        self.refresh_gpu(with_repos=True)
        self.refresh_history()
        self.refresh_backups()
        return root

    def _build_install(self):
        i18n = self.i18n
        box = page_box()

        # --- État actuel ---
        current, inner = section(i18n._("drivers.current_state"))
        self.gpu_label = markup_label(f"<i>{i18n._('secureboot.analyzing')}…</i>")
        self.driver_label = markup_label()
        inner.append(self.gpu_label)
        inner.append(self.driver_label)
        inner.append(button_row(
            button(i18n._("button.refresh"), lambda: self.refresh_gpu(with_repos=True)),
            button(i18n._("drivers.create_backup"), self.create_backup),
            button(i18n._("drivers.remove_driver"), self.remove_driver, "destructive-action"),
        ))
        box.append(current)

        # --- Dépôts Debian ---
        repos, inner = section(i18n._("drivers.from_repos"))
        repos.set_vexpand(True)
        self.repos = SimpleList([i18n._("drivers.column_name"), i18n._("drivers.column_version"),
                                 i18n._("drivers.column_description")], expand=[2], min_height=140)
        inner.append(self.repos)
        inner.append(button_row(button(i18n._("drivers.install_from_repos"), self.install_from_repos,
                                       "suggested-action")))
        box.append(repos)

        # --- Site officiel (NVIDIA) ---
        official, inner = section(i18n._("drivers.from_official_dynamic"))
        inner.append(markup_label(f"<span color='orange'><b>{i18n._('drivers.warning_advanced')}</b></span>"))
        self.official_label = markup_label()
        inner.append(self.official_label)
        inner.append(button_row(
            button(i18n._("drivers.scrape_latest"), self.scrape_official),
            button(i18n._("drivers.download_and_install"), self.install_official),
        ))
        box.append(official)

        return Gtk.ScrolledWindow(child=box, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)

    def _build_history(self):
        i18n = self.i18n
        box = page_box()
        box.append(title_label(i18n._("drivers.history_title"), i18n._("drivers.history_subtitle")))
        self.history = SimpleList([
            i18n._("drivers.column_date"), i18n._("drivers.column_action"), i18n._("drivers.column_vendor"),
            i18n._("drivers.column_driver"), i18n._("drivers.column_version"), i18n._("drivers.column_source"),
            i18n._("drivers.column_status"), i18n._("drivers.column_distro"),
        ], expand=[3, 7])
        box.append(self.history)
        box.append(button_row(button(i18n._("button.refresh"), self.refresh_history)))
        return box

    def _build_rollback(self):
        i18n = self.i18n
        box = page_box()
        box.append(title_label(i18n._("drivers.rollback_title"), i18n._("drivers.rollback_subtitle")))
        self.backups = SimpleList([
            i18n._("drivers.column_backup_id"), i18n._("drivers.column_date"), i18n._("drivers.column_vendor"),
            i18n._("drivers.column_driver"), i18n._("drivers.column_version"), i18n._("drivers.column_distro"),
        ], expand=[0, 3])
        box.append(self.backups)
        box.append(button_row(
            button(i18n._("button.refresh"), self.refresh_backups),
            button(i18n._("drivers.restore_backup"), self.restore_backup, "destructive-action"),
        ))
        return box

    # ==================== Rafraîchissement ====================

    def refresh_gpu(self, with_repos=False):
        """Détection du GPU, du pilote actuel et (option) des pilotes des dépôts, dans un thread"""
        i18n = self.i18n
        manager = self.manager

        def work():
            gpu = manager.detect_gpu()
            vendor = gpu.get('vendor') if gpu else None
            data = {"gpu": gpu, "driver": None, "repos": None, "nonfree": True}
            if vendor:
                data["driver"] = manager.get_current_driver(vendor)
                if with_repos and vendor in VENDORS:
                    data["repos"] = manager.get_available_drivers_from_repos(vendor)
                    if vendor == 'NVIDIA':
                        data["nonfree"] = manager.is_nonfree_enabled()
            return data

        def apply(data):
            self.gpu = data["gpu"]
            if not self.gpu:
                self.gpu_label.set_markup(f"<span color='red'>{i18n._('drivers.no_gpu_detected')}</span>")
                self.driver_label.set_text("")
                return

            esc = GLib.markup_escape_text
            self.gpu_label.set_markup(
                f"<b>{i18n._('drivers.detected_gpu')}</b> {esc(self.gpu['vendor'])} "
                f"{esc(self.gpu['model'])} ({esc(self.gpu['pci_id'])})")

            driver = data["driver"]
            if driver:
                text = (f"<b>{i18n._('drivers.current_driver')}</b> {esc(driver['name'])} - "
                        f"{esc(driver['version'])} ({i18n._('drivers.source_' + driver['source'])})")
            else:
                text = f"<b>{i18n._('drivers.current_driver')}</b> {i18n._('drivers.no_driver')}"
            if not data["nonfree"]:
                text += f"\n<span color='orange'>⚠ {i18n._('drivers.nonfree_required')}</span>"
            self.driver_label.set_markup(text)

            if data["repos"] is not None:
                rows = []
                for drv in data["repos"]:
                    name = drv['name'] + (" ⭐" if drv['recommended'] else "")
                    rows.append(Row([name, drv['version'], drv['description']], data=drv['name']))
                self.repos.set_rows(rows)

        run_task(work, apply, lambda e: self.dialogs.show_error(i18n._("message.error.title"), str(e)))

    def refresh_history(self):
        i18n = self.i18n
        rows = []
        for entry in reversed(self.manager.get_history()):  # plus récent en premier
            rows.append([
                datetime.fromisoformat(entry['timestamp']).strftime('%Y-%m-%d %H:%M'),
                i18n._(f"drivers.action_{entry['action']}"),
                entry['vendor'],
                entry['driver_name'],
                entry['driver_version'],
                i18n._(f"drivers.source_{entry['source']}"),
                "✅" if entry['success'] else "❌",
                entry.get('distro', 'Unknown'),
            ])
        self.history.set_rows(rows)

    def refresh_backups(self):
        rows = []
        for backup in self.manager.list_backups():
            driver = backup['driver']
            rows.append([
                backup['backup_id'],
                datetime.fromisoformat(backup['timestamp']).strftime('%Y-%m-%d %H:%M'),
                backup['vendor'],
                driver.get('name', 'Unknown'),
                driver.get('version', 'Unknown'),
                f"{backup['distro']['id']} {backup['distro']['version']}",
            ])
        self.backups.set_rows(rows)

    # ==================== Utilitaires ====================

    def _require_vendor(self):
        if self.vendor is None:
            self.dialogs.show_error(self.i18n._("message.error.title"), self.i18n._("drivers.detect_gpu_first"))
            return False
        return True

    def _with_progress(self, title, work, on_done, pulse=False):
        """
        Lance work(update_progress) dans un thread avec un dialogue de progression.
        update_progress(message, fraction) est le callback attendu par DriverManager.
        """
        progress = self.dialogs.progress(title, self.i18n._("drivers.preparing"))
        if pulse:
            progress.pulse()

        def update_progress(message, fraction=None):
            progress.set_status(message)
            if fraction is not None and not pulse:
                progress.set_fraction(fraction)

        def done(result):
            progress.close()
            on_done(result)

        def failed(error):
            progress.close()
            self.dialogs.show_error(self.i18n._("message.error.title"), str(error))

        run_task(lambda: work(update_progress), done, failed)

    def _ask_backup_then(self, question_key, continuation):
        """Propose une sauvegarde du pilote actuel, puis appelle continuation()"""
        i18n = self.i18n
        vendor = self.vendor

        def backup():
            def done(result):
                success, _backup_id, message = result
                self.refresh_backups()
                if success:
                    continuation()
                else:
                    self.dialogs.ask(i18n._("drivers.backup_failed"),
                                     f"{message}\n\n{i18n._('drivers.continue_anyway')}",
                                     on_yes=continuation)

            self._with_progress(i18n._("drivers.creating_backup"),
                                lambda update: self.manager.create_driver_backup(vendor, progress_callback=update),
                                done)

        self.dialogs.ask(i18n._("drivers.create_backup_before"), i18n._(question_key),
                         on_yes=backup, on_no=continuation)

    def _ask_reboot(self, message):
        i18n = self.i18n

        def reboot():
            run_task(PkexecHelper.reboot, lambda r: r[0] or self.dialogs.show_error(
                i18n._("message.error.title"), r[2]))

        self.dialogs.ask(i18n._("drivers.success_title"), message, on_yes=reboot,
                         yes_label=i18n._("button.reboot_now"), no_label=i18n._("button.later"))

    # ==================== Actions ====================

    def create_backup(self):
        i18n = self.i18n
        if not self._require_vendor():
            return
        vendor = self.vendor

        def done(result):
            success, _backup_id, message = result
            self.refresh_backups()
            if success:
                self.dialogs.show_info(i18n._("drivers.success_title"),
                                       f"{message}\n\n{i18n._('drivers.backup_saved')}")
            else:
                self.dialogs.show_error(i18n._("message.error.title"), message)

        self._with_progress(i18n._("drivers.creating_backup"),
                            lambda update: self.manager.create_driver_backup(vendor, progress_callback=update),
                            done)

    def install_from_repos(self):
        i18n = self.i18n
        row = self.repos.selected()
        if row is None:
            self.dialogs.show_error(i18n._("message.error.title"), i18n._("drivers.error_select_driver"))
            return
        if not self._require_vendor():
            return
        package_name = row.data
        vendor = self.vendor

        def install():
            def done(result):
                success, message = result
                self.manager.add_to_history(
                    action='install', vendor=vendor, driver_name=package_name,
                    driver_version='repository', source='repository', success=success,
                    details=None if success else {'error': message})
                self.refresh_history()
                if success:
                    self.refresh_gpu(with_repos=True)
                    self._ask_reboot(message + "\n\n" + i18n._("drivers.reboot_now"))
                else:
                    self.dialogs.show_error(i18n._("message.error.title"), message)

            self._with_progress(i18n._("drivers.installing"),
                                lambda update: self.manager.install_from_repos(package_name,
                                                                               progress_callback=update),
                                done)

        def confirm():
            self.dialogs.ask(i18n._("drivers.confirm_install_title"),
                             i18n._("drivers.confirm_install_repos", driver=package_name) + "\n\n" +
                             i18n._("drivers.reboot_required"),
                             on_yes=install)

        self._ask_backup_then("drivers.backup_recommended", confirm)

    def scrape_official(self):
        i18n = self.i18n
        if self.vendor != 'NVIDIA':
            # AMD et Intel : pilotes libres fournis par les dépôts Debian uniquement
            self.official_label.set_markup(f"<span color='red'>{i18n._('drivers.scraping_not_supported')}</span>")
            return

        def done(info):
            self.official = info
            if not info:
                self.official_label.set_markup(f"<span color='red'>{i18n._('drivers.error_fetch_info')}</span>")
                return
            esc = GLib.markup_escape_text
            text = (f"<b>{i18n._('drivers.latest_official')}</b> {esc(info['version'])}\n"
                    f"{i18n._('drivers.size')}: {esc(str(info['size']))}\n"
                    f"{i18n._('drivers.date')}: {esc(str(info['date']))}")
            if 'note' in info:
                text += f"\n<i>{esc(info['note'])}</i>"
            self.official_label.set_markup(text)

        self._with_progress(i18n._("drivers.scraping_title"),
                            lambda update: self.manager.scrape_nvidia_latest_version(progress_callback=update),
                            done, pulse=True)

    def install_official(self):
        i18n = self.i18n
        if not self.official:
            self.dialogs.show_error(i18n._("message.error.title"), i18n._("drivers.scrape_first"))
            return
        if self.vendor != 'NVIDIA':
            self.dialogs.show_error(i18n._("message.error.title"), i18n._("drivers.detect_gpu_first"))
            return

        info = self.official
        manager = self.manager
        needs_reboot = manager.display_server in ('X11', 'Wayland')  # installation au démarrage

        warning = (i18n._("drivers.warning_official_install") + "\n\n" +
                   i18n._("drivers.warning_nvidia_intelligent") +
                   f"\n\n📊 {i18n._('drivers.display_server')}: {manager.display_server}")

        def work(update):
            # Sauvegarde automatique, téléchargement puis installation
            backup_ok, backup_id, _ = manager.create_driver_backup('NVIDIA')
            ok, filepath, message = manager.download_official_driver(info['url'], info['filename'],
                                                                     progress_callback=update)
            if not ok:
                return {"stage": "download", "success": False, "message": message,
                        "backup_id": backup_id if backup_ok else None}
            ok, message = manager.install_nvidia_intelligently(filepath, progress_callback=update)
            return {"stage": "install", "success": ok, "message": message,
                    "backup_id": backup_id if backup_ok else None}

        def done(result):
            details = {'backup_id': result["backup_id"], 'display_server': manager.display_server}
            if result["stage"] == "download":
                details = {'error': result["message"], 'stage': 'download'}
            manager.add_to_history(action='install', vendor='NVIDIA', driver_name=info['filename'],
                                   driver_version=info['version'], source='official',
                                   success=result["success"], details=details)
            self.refresh_history()
            self.refresh_backups()

            if not result["success"]:
                self.dialogs.show_error(i18n._("message.error.title"), result["message"])
                return
            self.refresh_gpu()
            if needs_reboot:
                self._ask_reboot(result["message"])
            else:
                self.dialogs.show_info(i18n._("drivers.success_title"), result["message"])

        self.dialogs.ask(i18n._("drivers.warning_title"), warning, destructive=True,
                         on_yes=lambda: self._with_progress(i18n._("drivers.downloading"), work, done))

    def remove_driver(self):
        i18n = self.i18n
        if self.vendor == 'AMD':
            self.dialogs.show_info(i18n._("message.info.title"), i18n._("drivers.amd_no_removal"))
            return
        if self.vendor == 'Intel':
            self.dialogs.show_info(i18n._("message.info.title"), i18n._("drivers.intel_no_removal"))
            return
        if not self._require_vendor():
            return

        def remove():
            def done(result):
                success, message = result
                self.manager.add_to_history(action='remove', vendor='NVIDIA', driver_name='proprietary',
                                            driver_version='unknown', source='system', success=success)
                self.refresh_history()
                if success:
                    self.refresh_gpu(with_repos=True)
                    self._ask_reboot(message)
                else:
                    self.dialogs.show_error(i18n._("message.error.title"), message)

            self._with_progress(i18n._("drivers.removing"),
                                lambda update: self.manager.remove_driver('NVIDIA', progress_callback=update),
                                done, pulse=True)

        def confirm():
            self.dialogs.ask(i18n._("drivers.confirm_remove_title"),
                             i18n._("drivers.confirm_remove_driver") + "\n\n" +
                             i18n._("drivers.opensource_fallback"),
                             on_yes=remove, destructive=True)

        self._ask_backup_then("drivers.backup_before_removal", confirm)

    def restore_backup(self):
        i18n = self.i18n
        row = self.backups.selected()
        if row is None:
            self.dialogs.show_error(i18n._("message.error.title"), i18n._("drivers.error_select_backup"))
            return
        backup_id = row[0]

        def done(result):
            success, message = result
            if success:
                self.refresh_backups()
                self.refresh_gpu(with_repos=True)
                self._ask_reboot(message + "\n\n" + i18n._("drivers.reboot_now"))
            else:
                self.dialogs.show_error(i18n._("message.error.title"), message)

        self.dialogs.ask(
            i18n._("drivers.confirm_rollback_title"), i18n._("drivers.confirm_rollback", backup_id=backup_id),
            destructive=True,
            on_yes=lambda: self._with_progress(
                i18n._("drivers.rolling_back"),
                lambda update: self.manager.rollback_driver(backup_id, progress_callback=update),
                done, pulse=True))


def create_drivers_tab(main_window):
    """Crée l'onglet de gestion des pilotes GPU"""
    page = DriversPage(main_window)
    main_window.drivers_page = page
    return page.build()
