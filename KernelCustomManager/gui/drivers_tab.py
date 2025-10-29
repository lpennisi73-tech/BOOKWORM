"""
Onglet de gestion des drivers GPU (NVIDIA, AMD et Intel)
Version Avancée avec historique, rollback, web scraping dynamique et support Wayland
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import threading
from pathlib import Path
from datetime import datetime
from utils.i18n import get_i18n
from core.driver_manager import DriverManager


def create_drivers_tab(main_window):
    """Crée l'onglet de gestion des drivers GPU avec interface avancée"""
    i18n = get_i18n()

    # Initialiser le driver manager
    driver_manager = DriverManager()

    # Container principal avec notebook (onglets internes)
    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

    # === Barre d'informations système en haut ===
    system_info_bar = create_system_info_bar(driver_manager, i18n)
    main_box.pack_start(system_info_bar, False, False, 0)

    # === Notebook pour les sections ===
    notebook = Gtk.Notebook()
    notebook.set_tab_pos(Gtk.PositionType.TOP)

    # Onglet 1: Installation
    install_tab = create_installation_tab(main_window, driver_manager, i18n)
    notebook.append_page(install_tab, Gtk.Label(label=i18n._("drivers.tab_installation")))

    # Onglet 2: Historique
    history_tab = create_history_tab(driver_manager, i18n)
    notebook.append_page(history_tab, Gtk.Label(label=i18n._("drivers.tab_history")))

    # Onglet 3: Rollback
    rollback_tab = create_rollback_tab(main_window, driver_manager, i18n)
    notebook.append_page(rollback_tab, Gtk.Label(label=i18n._("drivers.tab_rollback")))

    main_box.pack_start(notebook, True, True, 0)

    return main_box


def create_system_info_bar(driver_manager, i18n):
    """Crée la barre d'informations système"""
    frame = Gtk.Frame()
    frame.set_shadow_type(Gtk.ShadowType.IN)

    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
    hbox.set_margin_start(10)
    hbox.set_margin_end(10)
    hbox.set_margin_top(5)
    hbox.set_margin_bottom(5)

    # GPU détecté
    gpu_info = driver_manager.detect_gpu()
    if gpu_info:
        gpu_label = Gtk.Label()
        gpu_label.set_markup(f"<b>🖥️ GPU:</b> {gpu_info['vendor']} {gpu_info['model']}")
        hbox.pack_start(gpu_label, False, False, 0)
    else:
        gpu_label = Gtk.Label()
        gpu_label.set_markup(f"<b>🖥️ GPU:</b> <span color='red'>{i18n._('drivers.no_gpu_detected')}</span>")
        hbox.pack_start(gpu_label, False, False, 0)

    # Distribution
    distro_label = Gtk.Label()
    distro_label.set_markup(
        f"<b>💿 {i18n._('drivers.distribution')}:</b> "
        f"{driver_manager.distro_info['name']} {driver_manager.distro_info['version']}"
    )
    hbox.pack_start(distro_label, False, False, 0)

    # Display Server
    display_label = Gtk.Label()
    display_icon = "🪟" if driver_manager.display_server == "Wayland" else "🖼️"
    display_label.set_markup(
        f"<b>{display_icon} {i18n._('drivers.display_server')}:</b> {driver_manager.display_server}"
    )
    hbox.pack_start(display_label, False, False, 0)

    frame.add(hbox)
    return frame


def create_installation_tab(main_window, driver_manager, i18n):
    """Crée l'onglet d'installation des drivers"""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_margin_start(10)
    box.set_margin_end(10)
    box.set_margin_top(10)
    box.set_margin_bottom(10)

    # === Section 1: État actuel ===
    current_frame = Gtk.Frame(label=i18n._("drivers.current_state"))
    current_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    current_box.set_margin_start(10)
    current_box.set_margin_end(10)
    current_box.set_margin_top(10)
    current_box.set_margin_bottom(10)

    gpu_label = Gtk.Label()
    gpu_label.set_halign(Gtk.Align.START)
    current_box.pack_start(gpu_label, False, False, 0)

    current_driver_label = Gtk.Label()
    current_driver_label.set_halign(Gtk.Align.START)
    current_box.pack_start(current_driver_label, False, False, 0)

    # Boutons d'action pour état actuel
    current_btn_box = Gtk.Box(spacing=5)

    refresh_btn = Gtk.Button(label=i18n._("button.refresh"))
    refresh_btn.connect("clicked", lambda w: refresh_gpu_info(
        driver_manager, gpu_label, current_driver_label, None, None, i18n
    ))
    current_btn_box.pack_start(refresh_btn, False, False, 0)

    backup_btn = Gtk.Button(label=i18n._("drivers.create_backup"))
    backup_btn.connect("clicked", lambda w: create_backup(
        main_window, driver_manager, gpu_label, i18n
    ))
    current_btn_box.pack_start(backup_btn, False, False, 0)

    remove_btn = Gtk.Button(label=i18n._("drivers.remove_driver"))
    remove_btn.connect("clicked", lambda w: remove_current_driver(
        main_window, driver_manager, gpu_label, current_driver_label, i18n
    ))
    current_btn_box.pack_start(remove_btn, False, False, 0)

    current_box.pack_start(current_btn_box, False, False, 0)

    current_frame.add(current_box)
    box.pack_start(current_frame, False, False, 0)

    # === Section 2: Installation depuis dépôts ===
    repos_frame = Gtk.Frame(label=i18n._("drivers.from_repos"))
    repos_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    repos_vbox.set_margin_start(10)
    repos_vbox.set_margin_end(10)
    repos_vbox.set_margin_top(10)
    repos_vbox.set_margin_bottom(10)

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_vexpand(True)
    scrolled.set_min_content_height(120)

    repos_store = Gtk.ListStore(str, str, str, bool)
    repos_view = Gtk.TreeView(model=repos_store)

    for i, title in enumerate([i18n._("drivers.column_name"), i18n._("drivers.column_version"), i18n._("drivers.column_description")]):
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(title, renderer, text=i)
        column.set_resizable(True)
        if i == 2:
            column.set_expand(True)
        repos_view.append_column(column)

    scrolled.add(repos_view)
    repos_vbox.pack_start(scrolled, True, True, 0)

    repos_btn_box = Gtk.Box(spacing=5)

    install_repos_btn = Gtk.Button(label=i18n._("drivers.install_from_repos"))
    install_repos_btn.connect("clicked", lambda w: install_from_repos(
        main_window, driver_manager, repos_view, repos_store, gpu_label, current_driver_label, i18n
    ))
    repos_btn_box.pack_start(install_repos_btn, False, False, 0)

    repos_vbox.pack_start(repos_btn_box, False, False, 0)
    repos_frame.add(repos_vbox)
    box.pack_start(repos_frame, True, True, 0)

    # === Section 3: Installation depuis site officiel (avec scraping) ===
    official_frame = Gtk.Frame(label=i18n._("drivers.from_official_dynamic"))
    official_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    official_box.set_margin_start(10)
    official_box.set_margin_end(10)
    official_box.set_margin_top(10)
    official_box.set_margin_bottom(10)

    warning_label = Gtk.Label()
    warning_label.set_markup(f"<span color='orange'><b>⚠ {i18n._('drivers.warning_advanced')}</b></span>")
    warning_label.set_halign(Gtk.Align.START)
    official_box.pack_start(warning_label, False, False, 0)

    official_info_label = Gtk.Label()
    official_info_label.set_halign(Gtk.Align.START)
    official_info_label.set_line_wrap(True)
    official_box.pack_start(official_info_label, False, False, 0)

    official_btn_box = Gtk.Box(spacing=5)

    scrape_btn = Gtk.Button(label=i18n._("drivers.scrape_latest"))
    scrape_btn.connect("clicked", lambda w: scrape_and_display_official(
        main_window, driver_manager, official_info_label, gpu_label, i18n
    ))
    official_btn_box.pack_start(scrape_btn, False, False, 0)

    download_install_btn = Gtk.Button(label=i18n._("drivers.download_and_install"))
    download_install_btn.connect("clicked", lambda w: download_and_install_official(
        main_window, driver_manager, official_info_label, gpu_label, current_driver_label, i18n
    ))
    official_btn_box.pack_start(download_install_btn, False, False, 0)

    official_box.pack_start(official_btn_box, False, False, 0)
    official_frame.add(official_box)
    box.pack_start(official_frame, False, False, 0)

    # Rafraîchir au démarrage
    refresh_gpu_info(driver_manager, gpu_label, current_driver_label, repos_store, repos_view, i18n)

    return box


def create_history_tab(driver_manager, i18n):
    """Crée l'onglet d'historique des opérations"""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_margin_start(10)
    box.set_margin_end(10)
    box.set_margin_top(10)
    box.set_margin_bottom(10)

    # Label explicatif
    info_label = Gtk.Label()
    info_label.set_markup(f"<b>{i18n._('drivers.history_title')}</b>\n{i18n._('drivers.history_subtitle')}")
    info_label.set_halign(Gtk.Align.START)
    box.pack_start(info_label, False, False, 0)

    # TreeView pour l'historique
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_vexpand(True)

    # timestamp, action, vendor, driver_name, version, source, success, distro
    history_store = Gtk.ListStore(str, str, str, str, str, str, str, str)
    history_view = Gtk.TreeView(model=history_store)

    columns = [
        i18n._("drivers.column_date"),
        i18n._("drivers.column_action"),
        i18n._("drivers.column_vendor"),
        i18n._("drivers.column_driver"),
        i18n._("drivers.column_version"),
        i18n._("drivers.column_source"),
        i18n._("drivers.column_status"),
        i18n._("drivers.column_distro")
    ]

    for i, title in enumerate(columns):
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(title, renderer, text=i)
        column.set_resizable(True)
        if i in [3, 7]:  # Driver name et distro
            column.set_expand(True)
        history_view.append_column(column)

    scrolled.add(history_view)
    box.pack_start(scrolled, True, True, 0)

    # Boutons
    btn_box = Gtk.Box(spacing=5)

    refresh_history_btn = Gtk.Button(label=i18n._("button.refresh"))
    refresh_history_btn.connect("clicked", lambda w: refresh_history(
        driver_manager, history_store, i18n
    ))
    btn_box.pack_start(refresh_history_btn, False, False, 0)

    box.pack_start(btn_box, False, False, 0)

    # Charger l'historique au démarrage
    refresh_history(driver_manager, history_store, i18n)

    return box


def create_rollback_tab(main_window, driver_manager, i18n):
    """Crée l'onglet de rollback/sauvegardes"""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_margin_start(10)
    box.set_margin_end(10)
    box.set_margin_top(10)
    box.set_margin_bottom(10)

    # Label explicatif
    info_label = Gtk.Label()
    info_label.set_markup(f"<b>{i18n._('drivers.rollback_title')}</b>\n{i18n._('drivers.rollback_subtitle')}")
    info_label.set_halign(Gtk.Align.START)
    box.pack_start(info_label, False, False, 0)

    # TreeView pour les sauvegardes
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_vexpand(True)

    # backup_id, timestamp, vendor, driver_name, driver_version, distro
    backup_store = Gtk.ListStore(str, str, str, str, str, str)
    backup_view = Gtk.TreeView(model=backup_store)

    columns = [
        i18n._("drivers.column_backup_id"),
        i18n._("drivers.column_date"),
        i18n._("drivers.column_vendor"),
        i18n._("drivers.column_driver"),
        i18n._("drivers.column_version"),
        i18n._("drivers.column_distro")
    ]

    for i, title in enumerate(columns):
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(title, renderer, text=i)
        column.set_resizable(True)
        if i in [0, 3]:  # Backup ID et driver name
            column.set_expand(True)
        backup_view.append_column(column)

    scrolled.add(backup_view)
    box.pack_start(scrolled, True, True, 0)

    # Boutons
    btn_box = Gtk.Box(spacing=5)

    refresh_backup_btn = Gtk.Button(label=i18n._("button.refresh"))
    refresh_backup_btn.connect("clicked", lambda w: refresh_backups(
        driver_manager, backup_store, i18n
    ))
    btn_box.pack_start(refresh_backup_btn, False, False, 0)

    restore_btn = Gtk.Button(label=i18n._("drivers.restore_backup"))
    restore_btn.connect("clicked", lambda w: restore_from_backup(
        main_window, driver_manager, backup_view, backup_store, i18n
    ))
    btn_box.pack_start(restore_btn, False, False, 0)

    box.pack_start(btn_box, False, False, 0)

    # Charger les sauvegardes au démarrage
    refresh_backups(driver_manager, backup_store, i18n)

    return box


# ==========================================
# FONCTIONS DE RAFRAÎCHISSEMENT
# ==========================================

def refresh_gpu_info(driver_manager, gpu_label, current_driver_label, repos_store, repos_view, i18n):
    """Rafraîchit les informations GPU et driver actuel"""
    # Détecter le GPU
    gpu_info = driver_manager.detect_gpu()

    if gpu_info:
        vendor = gpu_info['vendor']
        model = gpu_info['model']
        pci_id = gpu_info['pci_id']

        gpu_label.set_markup(
            f"<b>{i18n._('drivers.detected_gpu')}</b> {vendor} {model} ({pci_id})"
        )

        # Récupérer driver actuel
        current_driver = driver_manager.get_current_driver(vendor)
        if current_driver:
            current_driver_label.set_markup(
                f"<b>{i18n._('drivers.current_driver')}</b> "
                f"{current_driver['name']} - {current_driver['version']} "
                f"({i18n._('drivers.source_' + current_driver['source'])})"
            )
        else:
            current_driver_label.set_markup(
                f"<b>{i18n._('drivers.current_driver')}</b> {i18n._('drivers.no_driver')}"
            )

        # Lister drivers disponibles si store fourni
        if repos_store is not None:
            repos_store.clear()
            if vendor in ['NVIDIA', 'AMD', 'Intel']:
                drivers = driver_manager.get_available_drivers_from_repos(vendor)
                for driver in drivers:
                    name = driver['name']
                    if driver['recommended']:
                        name += f" ⭐ ({i18n._('drivers.recommended')})"

                    repos_store.append([
                        driver['name'],
                        driver['version'],
                        driver['description'],
                        driver['recommended']
                    ])
    else:
        gpu_label.set_markup(
            f"<span color='red'>{i18n._('drivers.no_gpu_detected')}</span>"
        )
        current_driver_label.set_text("")


def refresh_history(driver_manager, history_store, i18n):
    """Rafraîchit l'historique des opérations"""
    history_store.clear()

    history = driver_manager.get_history()

    for entry in reversed(history):  # Plus récent en premier
        timestamp = datetime.fromisoformat(entry['timestamp']).strftime('%Y-%m-%d %H:%M')
        action = i18n._(f"drivers.action_{entry['action']}")
        vendor = entry['vendor']
        driver_name = entry['driver_name']
        version = entry['driver_version']
        source = i18n._(f"drivers.source_{entry['source']}")
        status = "✅" if entry['success'] else "❌"
        distro = entry.get('distro', 'Unknown')

        history_store.append([
            timestamp,
            action,
            vendor,
            driver_name,
            version,
            source,
            status,
            distro
        ])


def refresh_backups(driver_manager, backup_store, i18n):
    """Rafraîchit la liste des sauvegardes"""
    backup_store.clear()

    backups = driver_manager.list_backups()

    for backup in backups:
        timestamp = datetime.fromisoformat(backup['timestamp']).strftime('%Y-%m-%d %H:%M')
        vendor = backup['vendor']
        driver_info = backup['driver']
        driver_name = driver_info.get('name', 'Unknown')
        driver_version = driver_info.get('version', 'Unknown')
        distro = f"{backup['distro']['id']} {backup['distro']['version']}"

        backup_store.append([
            backup['backup_id'],
            timestamp,
            vendor,
            driver_name,
            driver_version,
            distro
        ])


# ==========================================
# FONCTIONS D'ACTION
# ==========================================

def create_backup(main_window, driver_manager, gpu_label, i18n):
    """Crée une sauvegarde du driver actuel"""
    # Récupérer le vendor
    gpu_text = gpu_label.get_text()

    vendor = None
    if 'NVIDIA' in gpu_text:
        vendor = 'NVIDIA'
    elif 'AMD' in gpu_text:
        vendor = 'AMD'
    elif 'Intel' in gpu_text:
        vendor = 'Intel'

    if not vendor:
        main_window.dialogs.show_error(
            i18n._("message.error.title"),
            i18n._("drivers.detect_gpu_first")
        )
        return

    # Créer dialogue de progression
    dialog = Gtk.Dialog(
        title=i18n._("drivers.creating_backup"),
        transient_for=main_window,
        modal=True
    )
    dialog.set_default_size(400, 150)

    content = dialog.get_content_area()
    content.set_spacing(10)
    content.set_margin_start(10)
    content.set_margin_end(10)
    content.set_margin_top(10)
    content.set_margin_bottom(10)

    status_label = Gtk.Label(label=i18n._("drivers.preparing"))
    content.pack_start(status_label, False, False, 0)

    progress = Gtk.ProgressBar()
    progress.set_show_text(True)
    content.pack_start(progress, False, False, 0)

    dialog.show_all()

    def backup_thread():
        def update_progress(message, fraction):
            GLib.idle_add(lambda: status_label.set_text(message))
            GLib.idle_add(lambda: progress.set_fraction(fraction))

        success, backup_id, message = driver_manager.create_driver_backup(
            vendor,
            progress_callback=update_progress
        )

        GLib.idle_add(dialog.destroy)

        if success:
            GLib.idle_add(lambda: main_window.dialogs.show_info(
                i18n._("drivers.success_title"),
                f"{message}\n\n{i18n._('drivers.backup_saved')}"
            ))
        else:
            GLib.idle_add(lambda: main_window.dialogs.show_error(
                i18n._("message.error.title"),
                message
            ))

    thread = threading.Thread(target=backup_thread, daemon=True)
    thread.start()


def install_from_repos(main_window, driver_manager, view, store, gpu_label, current_driver_label, i18n):
    """Installe un driver depuis les dépôts"""
    selection = view.get_selection()
    model, treeiter = selection.get_selected()

    if not treeiter:
        main_window.dialogs.show_error(
            i18n._("message.error.title"),
            i18n._("drivers.error_select_driver")
        )
        return

    package_name = model[treeiter][0]

    # Récupérer vendor depuis le label GPU
    gpu_text = gpu_label.get_text()
    vendor = None
    if 'NVIDIA' in gpu_text:
        vendor = 'NVIDIA'
    elif 'AMD' in gpu_text:
        vendor = 'AMD'
    elif 'Intel' in gpu_text:
        vendor = 'Intel'

    # Demander si on veut créer un backup
    response = main_window.dialogs.show_question(
        i18n._("drivers.create_backup_before"),
        i18n._("drivers.backup_recommended")
    )

    if response == Gtk.ResponseType.YES:
        # Créer backup d'abord
        success, backup_id, msg = driver_manager.create_driver_backup(vendor)
        if not success:
            main_window.dialogs.show_warning(
                i18n._("drivers.backup_failed"),
                f"{msg}\n\n{i18n._('drivers.continue_anyway')}"
            )

    # Confirmation installation
    response = main_window.dialogs.show_question(
        i18n._("drivers.confirm_install_title"),
        i18n._("drivers.confirm_install_repos", driver=package_name) + "\n\n" +
        i18n._("drivers.reboot_required")
    )

    if response != Gtk.ResponseType.YES:
        return

    # Dialogue de progression
    dialog = Gtk.Dialog(
        title=i18n._("drivers.installing"),
        transient_for=main_window,
        modal=True
    )
    dialog.set_default_size(400, 150)

    content = dialog.get_content_area()
    content.set_spacing(10)
    content.set_margin_start(10)
    content.set_margin_end(10)
    content.set_margin_top(10)
    content.set_margin_bottom(10)

    status_label = Gtk.Label(label=i18n._("drivers.preparing"))
    content.pack_start(status_label, False, False, 0)

    progress = Gtk.ProgressBar()
    progress.set_show_text(True)
    content.pack_start(progress, False, False, 0)

    dialog.show_all()

    def install_thread():
        def update_progress(message, fraction):
            GLib.idle_add(lambda: status_label.set_text(message))
            GLib.idle_add(lambda: progress.set_fraction(fraction))

        success, message = driver_manager.install_from_repos(
            package_name,
            progress_callback=update_progress
        )

        GLib.idle_add(dialog.destroy)

        if success:
            # Ajouter à l'historique
            driver_manager.add_to_history(
                action='install',
                vendor=vendor,
                driver_name=package_name,
                driver_version='repository',
                source='repository',
                success=True
            )

            GLib.idle_add(lambda: main_window.dialogs.show_info(
                i18n._("drivers.success_title"),
                message + "\n\n" + i18n._("drivers.reboot_now")
            ))
            GLib.idle_add(lambda: refresh_gpu_info(
                driver_manager, gpu_label, current_driver_label, store, view, i18n
            ))
        else:
            driver_manager.add_to_history(
                action='install',
                vendor=vendor,
                driver_name=package_name,
                driver_version='repository',
                source='repository',
                success=False,
                details={'error': message}
            )

            GLib.idle_add(lambda: main_window.dialogs.show_error(
                i18n._("message.error.title"),
                message
            ))

    thread = threading.Thread(target=install_thread, daemon=True)
    thread.start()


def scrape_and_display_official(main_window, driver_manager, info_label, gpu_label, i18n):
    """Scrape et affiche les informations officielles en temps réel"""
    gpu_text = gpu_label.get_text()

    vendor = None
    if 'NVIDIA' in gpu_text:
        vendor = 'NVIDIA'
    elif 'AMD' in gpu_text:
        vendor = 'AMD'
    else:
        info_label.set_markup(
            f"<span color='red'>{i18n._('drivers.scraping_not_supported')}</span>"
        )
        return

    # Dialogue de progression pour le scraping
    dialog = Gtk.Dialog(
        title=i18n._("drivers.scraping_title"),
        transient_for=main_window,
        modal=True
    )
    dialog.set_default_size(400, 150)

    content = dialog.get_content_area()
    content.set_spacing(10)
    content.set_margin_start(10)
    content.set_margin_end(10)
    content.set_margin_top(10)
    content.set_margin_bottom(10)

    status_label = Gtk.Label(label=i18n._("drivers.scraping_in_progress"))
    content.pack_start(status_label, False, False, 0)

    progress = Gtk.ProgressBar()
    progress.pulse()
    content.pack_start(progress, False, False, 0)

    dialog.show_all()

    def scrape_thread():
        def update_progress(message, fraction):
            GLib.idle_add(lambda: status_label.set_text(message))

        # Pulser la barre de progression
        def pulse():
            progress.pulse()
            return True

        pulse_id = GLib.timeout_add(100, pulse)

        if vendor == 'NVIDIA':
            official_info = driver_manager.scrape_nvidia_latest_version(progress_callback=update_progress)
        else:
            official_info = driver_manager.scrape_amd_latest_version(progress_callback=update_progress)

        GLib.source_remove(pulse_id)
        GLib.idle_add(dialog.destroy)

        if official_info:
            info_text = f"<b>{i18n._('drivers.latest_official')}</b> {official_info['version']}\n"
            info_text += f"{i18n._('drivers.size')}: {official_info['size']}\n"
            info_text += f"{i18n._('drivers.date')}: {official_info['date']}"

            if 'note' in official_info:
                info_text += f"\n<i>{official_info['note']}</i>"

            # Stocker les infos dans une propriété du label pour utilisation ultérieure
            info_label.official_data = official_info
            GLib.idle_add(lambda: info_label.set_markup(info_text))
        else:
            GLib.idle_add(lambda: info_label.set_markup(
                f"<span color='red'>{i18n._('drivers.error_fetch_info')}</span>"
            ))

    thread = threading.Thread(target=scrape_thread, daemon=True)
    thread.start()


def download_and_install_official(main_window, driver_manager, info_label, gpu_label, current_driver_label, i18n):
    """Télécharge et installe depuis le site officiel"""
    # Vérifier qu'on a les infos scrapées
    if not hasattr(info_label, 'official_data'):
        main_window.dialogs.show_error(
            i18n._("message.error.title"),
            i18n._("drivers.scrape_first")
        )
        return

    official_info = info_label.official_data
    gpu_text = gpu_label.get_text()

    vendor = None
    if 'NVIDIA' in gpu_text:
        vendor = 'NVIDIA'
    elif 'AMD' in gpu_text:
        vendor = 'AMD'

    if not vendor:
        main_window.dialogs.show_error(
            i18n._("message.error.title"),
            i18n._("drivers.detect_gpu_first")
        )
        return

    # Avertissement avancé
    warning_msg = i18n._("drivers.warning_official_install")
    if vendor == 'NVIDIA':
        warning_msg += "\n\n" + i18n._("drivers.warning_nvidia_intelligent")
        warning_msg += f"\n\n📊 {i18n._('drivers.display_server')}: {driver_manager.display_server}"

    response = main_window.dialogs.show_question(
        i18n._("drivers.warning_title"),
        warning_msg
    )

    if response != Gtk.ResponseType.YES:
        return

    # Créer backup automatique
    backup_success, backup_id, _ = driver_manager.create_driver_backup(vendor)

    # Téléchargement + Installation
    dialog = Gtk.Dialog(
        title=i18n._("drivers.downloading"),
        transient_for=main_window,
        modal=True
    )
    dialog.set_default_size(450, 150)

    content = dialog.get_content_area()
    content.set_spacing(10)
    content.set_margin_start(10)
    content.set_margin_end(10)
    content.set_margin_top(10)
    content.set_margin_bottom(10)

    status_label = Gtk.Label(label=i18n._("drivers.preparing"))
    content.pack_start(status_label, False, False, 0)

    progress = Gtk.ProgressBar()
    progress.set_show_text(True)
    content.pack_start(progress, False, False, 0)

    dialog.show_all()

    def download_install_thread():
        def update_progress(message, fraction):
            GLib.idle_add(lambda: status_label.set_text(message))
            GLib.idle_add(lambda: progress.set_fraction(fraction))

        # Télécharger
        success, filepath, message = driver_manager.download_official_driver(
            official_info['url'],
            official_info['filename'],
            progress_callback=update_progress
        )

        if not success:
            GLib.idle_add(dialog.destroy)
            driver_manager.add_to_history(
                action='install',
                vendor=vendor,
                driver_name=official_info['filename'],
                driver_version=official_info['version'],
                source='official',
                success=False,
                details={'error': message, 'stage': 'download'}
            )
            GLib.idle_add(lambda: main_window.dialogs.show_error(
                i18n._("message.error.title"),
                message
            ))
            return

        # Installer intelligemment (NVIDIA uniquement pour l'instant)
        if vendor == 'NVIDIA':
            success, install_msg = driver_manager.install_nvidia_intelligently(
                filepath,
                progress_callback=update_progress
            )
        else:  # AMD
            success, install_msg = driver_manager.install_amd_deb_file(
                filepath,
                progress_callback=update_progress
            )

        GLib.idle_add(dialog.destroy)

        # Ajouter à l'historique
        driver_manager.add_to_history(
            action='install',
            vendor=vendor,
            driver_name=official_info['filename'],
            driver_version=official_info['version'],
            source='official',
            success=success,
            details={
                'backup_id': backup_id if backup_success else None,
                'display_server': driver_manager.display_server
            }
        )

        if success:
            # Si NVIDIA + systemd, demander redémarrage
            if vendor == 'NVIDIA' and "redémarrage" in install_msg.lower():
                response = GLib.idle_add(lambda: main_window.dialogs.show_question(
                    i18n._("drivers.success_title"),
                    install_msg
                ))

                if response == Gtk.ResponseType.YES:
                    import subprocess
                    subprocess.run(["pkexec", "reboot"])
            else:
                GLib.idle_add(lambda: main_window.dialogs.show_info(
                    i18n._("drivers.success_title"),
                    install_msg
                ))

            GLib.idle_add(lambda: refresh_gpu_info(
                driver_manager, gpu_label, current_driver_label, None, None, i18n
            ))
        else:
            GLib.idle_add(lambda: main_window.dialogs.show_error(
                i18n._("message.error.title"),
                install_msg
            ))

    thread = threading.Thread(target=download_install_thread, daemon=True)
    thread.start()


def remove_current_driver(main_window, driver_manager, gpu_label, current_driver_label, i18n):
    """Supprime le driver propriétaire actuel"""
    gpu_text = gpu_label.get_text()

    vendor = None
    if 'NVIDIA' in gpu_text:
        vendor = 'NVIDIA'
    elif 'AMD' in gpu_text:
        vendor = 'AMD'
    elif 'Intel' in gpu_text:
        main_window.dialogs.show_info(
            i18n._("message.info.title"),
            i18n._("drivers.intel_no_removal")
        )
        return

    if not vendor:
        main_window.dialogs.show_error(
            i18n._("message.error.title"),
            i18n._("drivers.detect_gpu_first")
        )
        return

    # Créer backup avant suppression
    response = main_window.dialogs.show_question(
        i18n._("drivers.create_backup_before"),
        i18n._("drivers.backup_before_removal")
    )

    if response == Gtk.ResponseType.YES:
        driver_manager.create_driver_backup(vendor)

    # Confirmation
    response = main_window.dialogs.show_question(
        i18n._("drivers.confirm_remove_title"),
        i18n._("drivers.confirm_remove_driver") + "\n\n" +
        i18n._("drivers.opensource_fallback")
    )

    if response != Gtk.ResponseType.YES:
        return

    # Suppression
    dialog = Gtk.Dialog(
        title=i18n._("drivers.removing"),
        transient_for=main_window,
        modal=True
    )
    dialog.set_default_size(400, 150)

    content = dialog.get_content_area()
    content.set_spacing(10)
    content.set_margin_start(10)
    content.set_margin_end(10)
    content.set_margin_top(10)
    content.set_margin_bottom(10)

    status_label = Gtk.Label(label=i18n._("drivers.removing_driver"))
    content.pack_start(status_label, False, False, 0)

    progress = Gtk.ProgressBar()
    progress.pulse()
    content.pack_start(progress, False, False, 0)

    dialog.show_all()

    def remove_thread():
        def update_progress(message, fraction):
            GLib.idle_add(lambda: status_label.set_text(message))

        success, message = driver_manager.remove_driver(vendor, progress_callback=update_progress)

        GLib.idle_add(dialog.destroy)

        # Ajouter à l'historique
        driver_manager.add_to_history(
            action='remove',
            vendor=vendor,
            driver_name='proprietary',
            driver_version='unknown',
            source='system',
            success=success
        )

        if success:
            GLib.idle_add(lambda: main_window.dialogs.show_info(
                i18n._("drivers.success_title"),
                message
            ))
            GLib.idle_add(lambda: refresh_gpu_info(
                driver_manager, gpu_label, current_driver_label, None, None, i18n
            ))
        else:
            GLib.idle_add(lambda: main_window.dialogs.show_error(
                i18n._("message.error.title"),
                message
            ))

    thread = threading.Thread(target=remove_thread, daemon=True)
    thread.start()


def restore_from_backup(main_window, driver_manager, view, store, i18n):
    """Restaure un driver depuis une sauvegarde"""
    selection = view.get_selection()
    model, treeiter = selection.get_selected()

    if not treeiter:
        main_window.dialogs.show_error(
            i18n._("message.error.title"),
            i18n._("drivers.error_select_backup")
        )
        return

    backup_id = model[treeiter][0]

    # Confirmation
    response = main_window.dialogs.show_question(
        i18n._("drivers.confirm_rollback_title"),
        i18n._("drivers.confirm_rollback", backup_id=backup_id)
    )

    if response != Gtk.ResponseType.YES:
        return

    # Dialogue de progression
    dialog = Gtk.Dialog(
        title=i18n._("drivers.rolling_back"),
        transient_for=main_window,
        modal=True
    )
    dialog.set_default_size(400, 150)

    content = dialog.get_content_area()
    content.set_spacing(10)
    content.set_margin_start(10)
    content.set_margin_end(10)
    content.set_margin_top(10)
    content.set_margin_bottom(10)

    status_label = Gtk.Label(label=i18n._("drivers.preparing"))
    content.pack_start(status_label, False, False, 0)

    progress = Gtk.ProgressBar()
    progress.pulse()
    content.pack_start(progress, False, False, 0)

    dialog.show_all()

    def rollback_thread():
        def update_progress(message, fraction):
            GLib.idle_add(lambda: status_label.set_text(message))

        success, message = driver_manager.rollback_driver(
            backup_id,
            progress_callback=update_progress
        )

        GLib.idle_add(dialog.destroy)

        if success:
            GLib.idle_add(lambda: main_window.dialogs.show_info(
                i18n._("drivers.success_title"),
                message + "\n\n" + i18n._("drivers.reboot_now")
            ))
            GLib.idle_add(lambda: refresh_backups(driver_manager, store, i18n))
        else:
            GLib.idle_add(lambda: main_window.dialogs.show_error(
                i18n._("message.error.title"),
                message
            ))

    thread = threading.Thread(target=rollback_thread, daemon=True)
    thread.start()
