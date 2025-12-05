"""
Onglet de gestion SecureBoot
Interface pour vérifier le statut, gérer les clés MOK et configurer SecureBoot
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Pango
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from utils.i18n import get_i18n
from core.secureboot_manager import SecureBootManager


def create_secureboot_tab(main_window):
    """Crée l'onglet de gestion SecureBoot"""
    i18n = get_i18n()

    # Initialiser le SecureBoot manager
    sb_manager = SecureBootManager()

    # Container principal avec notebook (onglets internes)
    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

    # === Barre d'informations système en haut ===
    system_info_bar = create_system_info_bar(sb_manager, i18n)
    main_box.pack_start(system_info_bar, False, False, 0)

    # === Notebook pour les sections ===
    notebook = Gtk.Notebook()
    notebook.set_tab_pos(Gtk.PositionType.TOP)

    # Onglet 1: Statut SecureBoot
    status_tab = create_status_tab(main_window, sb_manager, i18n)
    notebook.append_page(status_tab, Gtk.Label(label=i18n._("secureboot.tab_status")))

    # Onglet 2: Gestion des clés
    keys_tab = create_keys_tab(main_window, sb_manager, i18n)
    notebook.append_page(keys_tab, Gtk.Label(label=i18n._("secureboot.tab_keys")))

    # Onglet 3: Signature de modules
    signing_tab = create_signing_tab(main_window, sb_manager, i18n)
    notebook.append_page(signing_tab, Gtk.Label(label=i18n._("secureboot.tab_signing")))

    # Onglet 4: Historique
    history_tab = create_history_tab(sb_manager, i18n)
    notebook.append_page(history_tab, Gtk.Label(label=i18n._("secureboot.tab_history")))

    main_box.pack_start(notebook, True, True, 0)

    return main_box


def create_system_info_bar(sb_manager, i18n):
    """Crée la barre d'informations système"""
    frame = Gtk.Frame()
    frame.set_shadow_type(Gtk.ShadowType.IN)

    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
    hbox.set_margin_start(10)
    hbox.set_margin_end(10)
    hbox.set_margin_top(5)
    hbox.set_margin_bottom(5)

    # Système UEFI
    is_uefi = sb_manager.is_uefi_system()
    uefi_label = Gtk.Label()
    if is_uefi:
        uefi_label.set_markup(f"<b>🔒 UEFI:</b> <span color='green'>{i18n._('secureboot.enabled')}</span>")
    else:
        uefi_label.set_markup(f"<b>🔒 UEFI:</b> <span color='red'>{i18n._('secureboot.disabled')}</span>")
    hbox.pack_start(uefi_label, False, False, 0)

    # Statut SecureBoot
    if is_uefi:
        sb_status = sb_manager.get_secureboot_status()
        sb_label = Gtk.Label()
        if sb_status['enabled']:
            sb_label.set_markup(f"<b>🛡️ SecureBoot:</b> <span color='green'>{i18n._('secureboot.enabled')}</span>")
        else:
            sb_label.set_markup(f"<b>🛡️ SecureBoot:</b> <span color='orange'>{i18n._('secureboot.disabled')}</span>")
        hbox.pack_start(sb_label, False, False, 0)

        # Mode Setup
        if sb_manager.check_setup_mode():
            setup_label = Gtk.Label()
            setup_label.set_markup(f"<b>⚙️ {i18n._('secureboot.setup_mode')}:</b> <span color='orange'>{i18n._('secureboot.active')}</span>")
            hbox.pack_start(setup_label, False, False, 0)

    frame.add(hbox)
    return frame


# ==================== Onglet 1: Statut SecureBoot ====================

def create_status_tab(main_window, sb_manager, i18n):
    """Crée l'onglet de vérification du statut"""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_margin_start(10)
    box.set_margin_end(10)
    box.set_margin_top(10)
    box.set_margin_bottom(10)

    # === Section: Statut actuel ===
    status_frame = Gtk.Frame(label=i18n._("secureboot.current_status"))
    status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    status_box.set_margin_start(10)
    status_box.set_margin_end(10)
    status_box.set_margin_top(10)
    status_box.set_margin_bottom(10)

    # Label de statut
    status_label = Gtk.Label()
    status_label.set_line_wrap(True)
    status_label.set_xalign(0)
    update_status_display(sb_manager, status_label, i18n)
    status_box.pack_start(status_label, False, False, 0)

    # Bouton rafraîchir
    refresh_btn = Gtk.Button(label=i18n._("button.refresh"))
    refresh_btn.connect("clicked", lambda w: update_status_display(sb_manager, status_label, i18n))
    status_box.pack_start(refresh_btn, False, False, 0)

    status_frame.add(status_box)
    box.pack_start(status_frame, False, False, 0)

    # === Section: Dépendances ===
    deps_frame = Gtk.Frame(label=i18n._("secureboot.dependencies"))
    deps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    deps_box.set_margin_start(10)
    deps_box.set_margin_end(10)
    deps_box.set_margin_top(10)
    deps_box.set_margin_bottom(10)

    deps_label = Gtk.Label()
    deps_label.set_line_wrap(True)
    deps_label.set_xalign(0)
    update_dependencies_display(sb_manager, deps_label, i18n)
    deps_box.pack_start(deps_label, False, False, 0)

    # Bouton installer dépendances
    install_deps_btn = Gtk.Button(label=i18n._("secureboot.install_dependencies"))
    install_deps_btn.connect("clicked", lambda w: install_dependencies(main_window, sb_manager, deps_label, i18n))
    deps_box.pack_start(install_deps_btn, False, False, 0)

    deps_frame.add(deps_box)
    box.pack_start(deps_frame, False, False, 0)

    # === Section: Instructions ===
    info_frame = Gtk.Frame(label=i18n._("secureboot.instructions"))
    info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    info_box.set_margin_start(10)
    info_box.set_margin_end(10)
    info_box.set_margin_top(10)
    info_box.set_margin_bottom(10)

    instructions_text = i18n._("secureboot.instructions_text")
    instructions_label = Gtk.Label(label=instructions_text)
    instructions_label.set_line_wrap(True)
    instructions_label.set_xalign(0)
    info_box.pack_start(instructions_label, False, False, 0)

    info_frame.add(info_box)
    box.pack_start(info_frame, True, True, 0)

    return box


def update_status_display(sb_manager, label, i18n):
    """Met à jour l'affichage du statut"""
    info = sb_manager.get_system_info()

    text = []

    # UEFI
    if info['is_uefi']:
        text.append(f"✅ <b>{i18n._('secureboot.uefi_mode')}:</b> {i18n._('secureboot.enabled')}")
    else:
        text.append(f"❌ <b>{i18n._('secureboot.uefi_mode')}:</b> {i18n._('secureboot.disabled')} - {i18n._('secureboot.legacy_boot')}")
        label.set_markup('\n'.join(text))
        return

    # SecureBoot status
    sb_status = info['secureboot_status']
    if sb_status['enabled']:
        text.append(f"🛡️ <b>SecureBoot:</b> <span color='green'>{i18n._('secureboot.enabled')}</span>")
    else:
        text.append(f"🔓 <b>SecureBoot:</b> <span color='orange'>{i18n._('secureboot.disabled')}</span>")

    text.append(f"   <i>{sb_status['details']}</i>")

    # Setup mode
    if info['setup_mode']:
        text.append(f"⚙️ <b>{i18n._('secureboot.setup_mode')}:</b> <span color='orange'>{i18n._('secureboot.active')}</span>")

    label.set_markup('\n'.join(text))


def update_dependencies_display(sb_manager, label, i18n):
    """Met à jour l'affichage des dépendances"""
    deps = sb_manager.check_dependencies()

    text = []
    for name, installed in deps['dependencies'].items():
        if installed:
            text.append(f"✅ <b>{name}:</b> {i18n._('secureboot.installed')}")
        else:
            text.append(f"❌ <b>{name}:</b> <span color='red'>{i18n._('secureboot.not_installed')}</span>")

    label.set_markup('\n'.join(text))


def install_dependencies(main_window, sb_manager, deps_label, i18n):
    """Installe les dépendances manquantes"""
    deps = sb_manager.check_dependencies()

    if deps['all_installed']:
        show_info_dialog(main_window, i18n._("secureboot.all_dependencies_installed"), i18n)
        return

    # Préparer la commande d'installation
    packages = []
    if not deps['dependencies']['mokutil']:
        packages.append('mokutil')
    if not deps['dependencies']['openssl']:
        packages.append('openssl')

    if not packages:
        show_info_dialog(main_window, i18n._("secureboot.all_dependencies_installed"), i18n)
        return

    cmd = f"apt install -y {' '.join(packages)}"

    # Demander confirmation
    dialog = Gtk.MessageDialog(
        transient_for=main_window,
        flags=0,
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.YES_NO,
        text=i18n._("secureboot.install_dependencies_confirm")
    )
    dialog.format_secondary_text(f"{i18n._('secureboot.packages')}: {', '.join(packages)}")

    response = dialog.run()
    dialog.destroy()

    if response == Gtk.ResponseType.YES:
        run_pkexec_command(main_window, cmd, i18n._("secureboot.installing_dependencies"), i18n,
                          lambda success: update_dependencies_display(sb_manager, deps_label, i18n))


# ==================== Onglet 2: Gestion des clés ====================

def create_keys_tab(main_window, sb_manager, i18n):
    """Crée l'onglet de gestion des clés MOK"""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_margin_start(10)
    box.set_margin_end(10)
    box.set_margin_top(10)
    box.set_margin_bottom(10)

    # === Section: Clés enrollées ===
    enrolled_frame = Gtk.Frame(label=i18n._("secureboot.enrolled_keys"))
    enrolled_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    enrolled_box.set_margin_start(10)
    enrolled_box.set_margin_end(10)
    enrolled_box.set_margin_top(10)
    enrolled_box.set_margin_bottom(10)

    # ScrolledWindow pour la liste des clés
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_min_content_height(150)
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

    enrolled_textview = Gtk.TextView()
    enrolled_textview.set_editable(False)
    enrolled_textview.set_wrap_mode(Gtk.WrapMode.WORD)
    enrolled_textview.modify_font(Pango.FontDescription("monospace 9"))
    scrolled.add(enrolled_textview)
    enrolled_box.pack_start(scrolled, True, True, 0)

    # Boutons
    btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    refresh_enrolled_btn = Gtk.Button(label=i18n._("button.refresh"))
    refresh_enrolled_btn.connect("clicked", lambda w: update_enrolled_keys(sb_manager, enrolled_textview, i18n))
    btn_box.pack_start(refresh_enrolled_btn, True, True, 0)
    enrolled_box.pack_start(btn_box, False, False, 0)

    enrolled_frame.add(enrolled_box)
    box.pack_start(enrolled_frame, True, True, 0)

    # === Section: Gestion des clés ===
    manage_frame = Gtk.Frame(label=i18n._("secureboot.manage_keys"))
    manage_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    manage_box.set_margin_start(10)
    manage_box.set_margin_end(10)
    manage_box.set_margin_top(10)
    manage_box.set_margin_bottom(10)

    # Importer une clé
    import_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    import_label = Gtk.Label(label=i18n._("secureboot.import_key") + ":")
    import_box.pack_start(import_label, False, False, 0)

    import_entry = Gtk.Entry()
    import_entry.set_placeholder_text(i18n._("secureboot.key_file_path"))
    import_box.pack_start(import_entry, True, True, 0)

    browse_btn = Gtk.Button(label="📁")
    browse_btn.connect("clicked", lambda w: browse_file(main_window, import_entry, i18n))
    import_box.pack_start(browse_btn, False, False, 0)

    import_btn = Gtk.Button(label=i18n._("secureboot.import"))
    import_btn.connect("clicked", lambda w: import_mok_key(main_window, sb_manager, import_entry, i18n))
    import_box.pack_start(import_btn, False, False, 0)

    manage_box.pack_start(import_box, False, False, 0)

    # Réinitialiser les clés
    reset_btn = Gtk.Button(label=i18n._("secureboot.reset_keys"))
    reset_btn.connect("clicked", lambda w: reset_mok_keys(main_window, sb_manager, i18n))
    manage_box.pack_start(reset_btn, False, False, 0)

    # Avertissement
    warning_label = Gtk.Label()
    warning_label.set_markup(f"<span color='orange'>⚠️ {i18n._('secureboot.keys_warning')}</span>")
    warning_label.set_line_wrap(True)
    warning_label.set_xalign(0)
    manage_box.pack_start(warning_label, False, False, 0)

    manage_frame.add(manage_box)
    box.pack_start(manage_frame, False, False, 0)

    # Charger les clés au démarrage
    GLib.idle_add(lambda: update_enrolled_keys(sb_manager, enrolled_textview, i18n))

    return box


def update_enrolled_keys(sb_manager, textview, i18n):
    """Met à jour la liste des clés enrollées"""
    result = sb_manager.list_enrolled_keys()

    buffer = textview.get_buffer()

    if result['success']:
        if result['keys']:
            text = f"{i18n._('secureboot.enrolled_keys_count')}: {len(result['keys'])}\n\n"
            text += result['raw_output']
        else:
            text = i18n._("secureboot.no_enrolled_keys")
    else:
        text = f"{i18n._('message.error.title')}: {result.get('error', 'Unknown error')}"

    buffer.set_text(text)


def browse_file(main_window, entry, i18n):
    """Ouvre un dialogue de sélection de fichier"""
    dialog = Gtk.FileChooserDialog(
        title=i18n._("secureboot.select_key_file"),
        parent=main_window,
        action=Gtk.FileChooserAction.OPEN
    )
    dialog.add_buttons(
        i18n._("button.cancel"), Gtk.ResponseType.CANCEL,
        i18n._("button.select"), Gtk.ResponseType.OK
    )

    # Filtre pour les fichiers de clés
    filter_keys = Gtk.FileFilter()
    filter_keys.set_name(i18n._("secureboot.key_files"))
    filter_keys.add_pattern("*.der")
    filter_keys.add_pattern("*.cer")
    filter_keys.add_pattern("*.crt")
    filter_keys.add_pattern("*.pem")
    dialog.add_filter(filter_keys)

    filter_all = Gtk.FileFilter()
    filter_all.set_name(i18n._("secureboot.all_files"))
    filter_all.add_pattern("*")
    dialog.add_filter(filter_all)

    response = dialog.run()
    if response == Gtk.ResponseType.OK:
        entry.set_text(dialog.get_filename())

    dialog.destroy()


def import_mok_key(main_window, sb_manager, entry, i18n):
    """Importe une clé MOK"""
    key_file = entry.get_text().strip()

    if not key_file:
        show_error_dialog(main_window, i18n._("secureboot.no_key_file"), i18n)
        return

    # Demander confirmation
    dialog = Gtk.MessageDialog(
        transient_for=main_window,
        flags=0,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.YES_NO,
        text=i18n._("secureboot.import_key_confirm")
    )
    dialog.format_secondary_text(i18n._("secureboot.import_key_details"))

    response = dialog.run()
    dialog.destroy()

    if response == Gtk.ResponseType.YES:
        # Exécuter l'import dans un terminal
        cmd = f"mokutil --import '{key_file}'"
        run_terminal_command(main_window, cmd, i18n._("secureboot.importing_key"), i18n)


def reset_mok_keys(main_window, sb_manager, i18n):
    """Réinitialise toutes les clés MOK"""
    dialog = Gtk.MessageDialog(
        transient_for=main_window,
        flags=0,
        message_type=Gtk.MessageType.WARNING,
        buttons=Gtk.ButtonsType.YES_NO,
        text=i18n._("secureboot.reset_keys_confirm")
    )
    dialog.format_secondary_text(i18n._("secureboot.reset_keys_warning"))

    response = dialog.run()
    dialog.destroy()

    if response == Gtk.ResponseType.YES:
        cmd = "mokutil --reset"
        run_terminal_command(main_window, cmd, i18n._("secureboot.resetting_keys"), i18n)


# ==================== Onglet 3: Signature de modules ====================

def create_signing_tab(main_window, sb_manager, i18n):
    """Crée l'onglet de signature de modules"""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_margin_start(10)
    box.set_margin_end(10)
    box.set_margin_top(10)
    box.set_margin_bottom(10)

    # === Section: Générer une clé ===
    generate_frame = Gtk.Frame(label=i18n._("secureboot.generate_key"))
    generate_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    generate_box.set_margin_start(10)
    generate_box.set_margin_end(10)
    generate_box.set_margin_top(10)
    generate_box.set_margin_bottom(10)

    # Nom de la clé
    name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    name_label = Gtk.Label(label=i18n._("secureboot.key_name") + ":")
    name_box.pack_start(name_label, False, False, 0)

    key_name_entry = Gtk.Entry()
    key_name_entry.set_text("MOK")
    key_name_entry.set_placeholder_text("MOK")
    name_box.pack_start(key_name_entry, True, True, 0)
    generate_box.pack_start(name_box, False, False, 0)

    # Common Name
    cn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    cn_label = Gtk.Label(label=i18n._("secureboot.common_name") + ":")
    cn_box.pack_start(cn_label, False, False, 0)

    cn_entry = Gtk.Entry()
    cn_entry.set_placeholder_text("Kernel Module Signing Key")
    cn_box.pack_start(cn_entry, True, True, 0)
    generate_box.pack_start(cn_box, False, False, 0)

    # Bouton générer
    generate_btn = Gtk.Button(label=i18n._("secureboot.generate"))
    generate_btn.connect("clicked", lambda w: generate_key(main_window, sb_manager, key_name_entry, cn_entry, result_label, i18n))
    generate_box.pack_start(generate_btn, False, False, 0)

    # Label de résultat
    result_label = Gtk.Label()
    result_label.set_line_wrap(True)
    result_label.set_xalign(0)
    generate_box.pack_start(result_label, False, False, 0)

    generate_frame.add(generate_box)
    box.pack_start(generate_frame, False, False, 0)

    # === Section: Signer un module ===
    sign_frame = Gtk.Frame(label=i18n._("secureboot.sign_module"))
    sign_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    sign_box.set_margin_start(10)
    sign_box.set_margin_end(10)
    sign_box.set_margin_top(10)
    sign_box.set_margin_bottom(10)

    # Module à signer
    module_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    module_label = Gtk.Label(label=i18n._("secureboot.module_file") + ":")
    module_box.pack_start(module_label, False, False, 0)

    module_entry = Gtk.Entry()
    module_entry.set_placeholder_text("/path/to/module.ko")
    module_box.pack_start(module_entry, True, True, 0)

    browse_module_btn = Gtk.Button(label="📁")
    browse_module_btn.connect("clicked", lambda w: browse_module_file(main_window, module_entry, i18n))
    module_box.pack_start(browse_module_btn, False, False, 0)
    sign_box.pack_start(module_box, False, False, 0)

    # Clé privée
    priv_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    priv_label = Gtk.Label(label=i18n._("secureboot.private_key") + ":")
    priv_box.pack_start(priv_label, False, False, 0)

    priv_entry = Gtk.Entry()
    priv_entry.set_placeholder_text("/path/to/key.priv")
    priv_box.pack_start(priv_entry, True, True, 0)

    browse_priv_btn = Gtk.Button(label="📁")
    browse_priv_btn.connect("clicked", lambda w: browse_file(main_window, priv_entry, i18n))
    priv_box.pack_start(browse_priv_btn, False, False, 0)
    sign_box.pack_start(priv_box, False, False, 0)

    # Certificat
    cert_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    cert_label = Gtk.Label(label=i18n._("secureboot.certificate") + ":")
    cert_box.pack_start(cert_label, False, False, 0)

    cert_entry = Gtk.Entry()
    cert_entry.set_placeholder_text("/path/to/cert.der")
    cert_box.pack_start(cert_entry, True, True, 0)

    browse_cert_btn = Gtk.Button(label="📁")
    browse_cert_btn.connect("clicked", lambda w: browse_file(main_window, cert_entry, i18n))
    cert_box.pack_start(browse_cert_btn, False, False, 0)
    sign_box.pack_start(cert_box, False, False, 0)

    # Bouton signer
    sign_btn = Gtk.Button(label=i18n._("secureboot.sign"))
    sign_btn.connect("clicked", lambda w: sign_module(main_window, sb_manager, module_entry, priv_entry, cert_entry, sign_result_label, i18n))
    sign_box.pack_start(sign_btn, False, False, 0)

    # Label de résultat
    sign_result_label = Gtk.Label()
    sign_result_label.set_line_wrap(True)
    sign_result_label.set_xalign(0)
    sign_box.pack_start(sign_result_label, False, False, 0)

    sign_frame.add(sign_box)
    box.pack_start(sign_frame, True, True, 0)

    return box


def browse_module_file(main_window, entry, i18n):
    """Ouvre un dialogue de sélection de module kernel"""
    dialog = Gtk.FileChooserDialog(
        title=i18n._("secureboot.select_module_file"),
        parent=main_window,
        action=Gtk.FileChooserAction.OPEN
    )
    dialog.add_buttons(
        i18n._("button.cancel"), Gtk.ResponseType.CANCEL,
        i18n._("button.select"), Gtk.ResponseType.OK
    )

    # Filtre pour les modules
    filter_modules = Gtk.FileFilter()
    filter_modules.set_name(i18n._("secureboot.kernel_modules"))
    filter_modules.add_pattern("*.ko")
    dialog.add_filter(filter_modules)

    filter_all = Gtk.FileFilter()
    filter_all.set_name(i18n._("secureboot.all_files"))
    filter_all.add_pattern("*")
    dialog.add_filter(filter_all)

    response = dialog.run()
    if response == Gtk.ResponseType.OK:
        entry.set_text(dialog.get_filename())

    dialog.destroy()


def generate_key(main_window, sb_manager, name_entry, cn_entry, result_label, i18n):
    """Génère une paire de clés"""
    key_name = name_entry.get_text().strip()
    common_name = cn_entry.get_text().strip()

    if not key_name:
        key_name = "MOK"

    def do_generate():
        result = sb_manager.generate_signing_key(key_name, common_name if common_name else None)

        def update_ui():
            if result['success']:
                text = f"✅ {i18n._('secureboot.key_generated')}\n\n"
                text += f"🔑 {i18n._('secureboot.private_key')}: {result['priv_key']}\n"
                text += f"📜 {i18n._('secureboot.certificate')}: {result['der_cert']}\n"
                text += f"📄 PEM: {result['pem_cert']}"
                result_label.set_markup(text)
            else:
                result_label.set_markup(f"❌ {i18n._('message.error.title')}: {result['error']}")

        GLib.idle_add(update_ui)

    thread = threading.Thread(target=do_generate)
    thread.daemon = True
    thread.start()


def sign_module(main_window, sb_manager, module_entry, priv_entry, cert_entry, result_label, i18n):
    """Signe un module kernel"""
    module_path = module_entry.get_text().strip()
    priv_path = priv_entry.get_text().strip()
    cert_path = cert_entry.get_text().strip()

    if not all([module_path, priv_path, cert_path]):
        result_label.set_markup(f"❌ {i18n._('secureboot.fill_all_fields')}")
        return

    def do_sign():
        result = sb_manager.sign_kernel_module(module_path, priv_path, cert_path)

        def update_ui():
            if result['success']:
                result_label.set_markup(f"✅ {result['message']}")
            else:
                result_label.set_markup(f"❌ {i18n._('message.error.title')}: {result['error']}")

        GLib.idle_add(update_ui)

    thread = threading.Thread(target=do_sign)
    thread.daemon = True
    thread.start()


# ==================== Onglet 4: Historique ====================

def create_history_tab(sb_manager, i18n):
    """Crée l'onglet d'historique"""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_margin_start(10)
    box.set_margin_end(10)
    box.set_margin_top(10)
    box.set_margin_bottom(10)

    # Barre de boutons
    btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

    refresh_btn = Gtk.Button(label=i18n._("button.refresh"))
    clear_btn = Gtk.Button(label=i18n._("button.clear"))

    btn_box.pack_start(refresh_btn, False, False, 0)
    btn_box.pack_start(clear_btn, False, False, 0)
    box.pack_start(btn_box, False, False, 0)

    # ScrolledWindow pour l'historique
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

    history_textview = Gtk.TextView()
    history_textview.set_editable(False)
    history_textview.set_wrap_mode(Gtk.WrapMode.WORD)
    history_textview.modify_font(Pango.FontDescription("monospace 9"))
    scrolled.add(history_textview)
    box.pack_start(scrolled, True, True, 0)

    # Connexions
    refresh_btn.connect("clicked", lambda w: update_history_display(sb_manager, history_textview, i18n))
    clear_btn.connect("clicked", lambda w: clear_history(sb_manager, history_textview, i18n))

    # Charger l'historique au démarrage
    GLib.idle_add(lambda: update_history_display(sb_manager, history_textview, i18n))

    return box


def update_history_display(sb_manager, textview, i18n):
    """Met à jour l'affichage de l'historique"""
    history = sb_manager.get_history()

    buffer = textview.get_buffer()

    if not history:
        buffer.set_text(i18n._("secureboot.no_history"))
        return

    text = f"{i18n._('secureboot.history_count')}: {len(history)}\n\n"

    for entry in history:
        timestamp = datetime.fromisoformat(entry['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
        success_icon = "✅" if entry['success'] else "❌"

        text += f"{success_icon} [{timestamp}] {entry['action']}\n"

        if isinstance(entry['details'], dict):
            for key, value in entry['details'].items():
                text += f"   {key}: {value}\n"
        else:
            text += f"   {entry['details']}\n"

        text += "\n"

    buffer.set_text(text)


def clear_history(sb_manager, textview, i18n):
    """Efface l'historique"""
    sb_manager._save_history([])
    update_history_display(sb_manager, textview, i18n)


# ==================== Utilitaires ====================

def show_error_dialog(parent, message, i18n):
    """Affiche un dialogue d'erreur"""
    dialog = Gtk.MessageDialog(
        transient_for=parent,
        flags=0,
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        text=i18n._("message.error.title")
    )
    dialog.format_secondary_text(message)
    dialog.run()
    dialog.destroy()


def show_info_dialog(parent, message, i18n):
    """Affiche un dialogue d'information"""
    dialog = Gtk.MessageDialog(
        transient_for=parent,
        flags=0,
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK,
        text=i18n._("message.success.title") if hasattr(i18n._("message.success"), 'title') else "Information"
    )
    dialog.format_secondary_text(message)
    dialog.run()
    dialog.destroy()


def run_pkexec_command(parent, command, title, i18n, callback=None):
    """Exécute une commande avec pkexec"""
    def do_run():
        try:
            result = subprocess.run(
                ["pkexec", "bash", "-c", command],
                capture_output=True,
                text=True,
                check=False
            )

            def update_ui():
                if result.returncode == 0:
                    if callback:
                        callback(True)
                    show_info_dialog(parent, i18n._("message.success.operation"), i18n)
                else:
                    if callback:
                        callback(False)
                    show_error_dialog(parent, result.stderr or i18n._("message.error.operation"), i18n)

            GLib.idle_add(update_ui)
        except Exception as e:
            def show_error():
                show_error_dialog(parent, str(e), i18n)
            GLib.idle_add(show_error)

    thread = threading.Thread(target=do_run)
    thread.daemon = True
    thread.start()


def run_terminal_command(parent, command, title, i18n):
    """Exécute une commande dans un terminal"""
    try:
        # Essayer différents émulateurs de terminal
        terminals = [
            ["x-terminal-emulator", "-e"],
            ["gnome-terminal", "--"],
            ["konsole", "-e"],
            ["xterm", "-e"]
        ]

        for terminal_cmd in terminals:
            try:
                subprocess.Popen(terminal_cmd + ["bash", "-c", f"pkexec {command}; read -p 'Press Enter to close...'"])
                return
            except FileNotFoundError:
                continue

        show_error_dialog(parent, i18n._("secureboot.no_terminal"), i18n)
    except Exception as e:
        show_error_dialog(parent, str(e), i18n)
