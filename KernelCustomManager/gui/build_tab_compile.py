"""
Module de compilation du kernel
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import subprocess
import threading
import os
from datetime import datetime
from utils.i18n import get_i18n
from core.secureboot_manager import SecureBootManager


def show_compile_dialog(main_window):
    """Dialogue de compilation"""
    i18n = get_i18n()
    linux_dir = main_window.kernel_manager.base_dir / "linux"

    if not linux_dir.exists():
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_kernel_source"))
        return

    if not (linux_dir / ".config").exists():
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_config"))
        return

    dialog = Gtk.Dialog(
        title=i18n._("dialog.compile.title"),
        transient_for=main_window,
        flags=0
    )
    dialog.set_default_size(450, 250)
    
    content = dialog.get_content_area()
    content.set_spacing(10)
    content.set_margin_start(20)
    content.set_margin_end(20)
    content.set_margin_top(10)
    content.set_margin_bottom(10)
    
    # Threads
    threads_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    threads_box.pack_start(Gtk.Label(label=i18n._("dialog.compile.threads")), False, False, 0)

    threads_spin = Gtk.SpinButton()
    threads_spin.set_range(1, os.cpu_count() * 2)
    threads_spin.set_value(os.cpu_count())
    threads_spin.set_increments(1, 4)
    threads_box.pack_start(threads_spin, True, True, 0)

    content.pack_start(threads_box, False, False, 0)

    # Suffixe
    suffix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    suffix_box.pack_start(Gtk.Label(label=i18n._("dialog.compile.suffix")), False, False, 0)

    suffix_entry = Gtk.Entry()
    suffix_entry.set_placeholder_text(i18n._("dialog.compile.suffix_placeholder"))
    suffix_box.pack_start(suffix_entry, True, True, 0)

    content.pack_start(suffix_box, False, False, 0)

    # Fakeroot
    fakeroot_check = Gtk.CheckButton(label=i18n._("dialog.compile.use_fakeroot"))
    fakeroot_check.set_active(True)
    content.pack_start(fakeroot_check, False, False, 0)

    # SecureBoot signing option
    sb_manager = main_window.secureboot_manager
    secureboot_check = None

    if sb_manager.should_prompt_for_signing():
        secureboot_check = Gtk.CheckButton(label=i18n._("dialog.compile.sign_for_secureboot"))
        secureboot_check.set_active(False)
        content.pack_start(secureboot_check, False, False, 0)

        sb_info_label = Gtk.Label()
        sb_info_label.set_markup(f"<small><i>{i18n._('dialog.compile.secureboot_info')}</i></small>")
        sb_info_label.set_line_wrap(True)
        content.pack_start(sb_info_label, False, False, 0)

    # Info
    info_label = Gtk.Label()
    info_label.set_markup(f"<i>{i18n._('dialog.compile.estimated_time')}</i>")
    content.pack_start(info_label, False, False, 0)

    dialog.add_button(i18n._("button.cancel"), Gtk.ResponseType.CANCEL)
    dialog.add_button(i18n._("dialog.compile.button_compile"), Gtk.ResponseType.OK)
    
    dialog.show_all()
    response = dialog.run()
    
    if response == Gtk.ResponseType.OK:
        jobs = int(threads_spin.get_value())
        suffix = suffix_entry.get_text().strip()
        use_fakeroot = fakeroot_check.get_active()
        sign_for_secureboot = secureboot_check and secureboot_check.get_active()

        dialog.destroy()
        compile_kernel(main_window, jobs, suffix, use_fakeroot, sign_for_secureboot)
    else:
        dialog.destroy()


def compile_kernel(main_window, jobs, suffix, use_fakeroot, sign_for_secureboot=False):
    """Lance la compilation dans un terminal"""
    i18n = get_i18n()
    linux_dir = main_window.kernel_manager.base_dir / "linux"

    try:
        kernel_version = linux_dir.resolve().name.replace("linux-", "")
    except:
        kernel_version = "unknown"

    # Sauvegarder la config
    main_window.kernel_manager.backup_config(kernel_version, suffix)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = main_window.kernel_manager.log_dir / f"compile-{timestamp}.log"

    fakeroot_cmd = "fakeroot " if use_fakeroot else ""
    suffix_cmd = f"LOCALVERSION={suffix}" if suffix else ""

    start_time = datetime.now()

    # Détecter la distribution pour adapter la configuration
    sb_manager = main_window.secureboot_manager
    distro_info = sb_manager.get_distribution_info()
    is_debian = distro_info['is_debian']

    # Sur Debian, désactiver la compression des modules dans le .config
    # Ubuntu ne compresse pas par défaut, Debian active CONFIG_MODULE_COMPRESS_XZ
    if is_debian:
        config_file = linux_dir / ".config"
        if config_file.exists():
            # Lire le fichier .config
            with open(config_file, 'r') as f:
                config_content = f.read()

            # Désactiver toutes les options de compression des modules
            config_modified = False

            # Désactiver CONFIG_MODULE_COMPRESS (option principale)
            if 'CONFIG_MODULE_COMPRESS=y' in config_content:
                config_content = config_content.replace('CONFIG_MODULE_COMPRESS=y', '# CONFIG_MODULE_COMPRESS is not set')
                config_modified = True

            # Désactiver CONFIG_MODULE_COMPRESS_ALL
            if 'CONFIG_MODULE_COMPRESS_ALL=y' in config_content:
                config_content = config_content.replace('CONFIG_MODULE_COMPRESS_ALL=y', '# CONFIG_MODULE_COMPRESS_ALL is not set')
                config_modified = True

            # Désactiver les algorithmes de compression spécifiques
            if 'CONFIG_MODULE_COMPRESS_XZ=y' in config_content:
                config_content = config_content.replace('CONFIG_MODULE_COMPRESS_XZ=y', '# CONFIG_MODULE_COMPRESS_XZ is not set')
                config_modified = True
            if 'CONFIG_MODULE_COMPRESS_GZIP=y' in config_content:
                config_content = config_content.replace('CONFIG_MODULE_COMPRESS_GZIP=y', '# CONFIG_MODULE_COMPRESS_GZIP is not set')
                config_modified = True
            if 'CONFIG_MODULE_COMPRESS_ZSTD=y' in config_content:
                config_content = config_content.replace('CONFIG_MODULE_COMPRESS_ZSTD=y', '# CONFIG_MODULE_COMPRESS_ZSTD is not set')
                config_modified = True

            # Ajouter CONFIG_MODULE_COMPRESS_NONE=y si pas présent
            if 'CONFIG_MODULE_COMPRESS_NONE' not in config_content:
                config_content += '\nCONFIG_MODULE_COMPRESS_NONE=y\n'
                config_modified = True
            elif 'CONFIG_MODULE_COMPRESS_NONE is not set' in config_content:
                config_content = config_content.replace('# CONFIG_MODULE_COMPRESS_NONE is not set', 'CONFIG_MODULE_COMPRESS_NONE=y')
                config_modified = True

            # Sauvegarder le .config modifié
            if config_modified:
                with open(config_file, 'w') as f:
                    f.write(config_content)

    # Préparer la signature SecureBoot (TOUJOURS avant bindeb-pkg, simple et fiable)
    signing_before_bindeb = ""

    if sign_for_secureboot:
        keys_dir = sb_manager.keys_dir
        available_keys = list(keys_dir.glob("*.priv"))

        if available_keys:
            # Utiliser la première clé disponible (ou MOK si elle existe)
            key_file = None
            for k in available_keys:
                if k.stem == "MOK":
                    key_file = k
                    break
            if not key_file:
                key_file = available_keys[0]

            priv_key = key_file
            cert = key_file.with_suffix('.der')

            if cert.exists():
                # Script de signature des modules AVANT bindeb-pkg
                # Simple et fiable : signe tous les modules .ko dans le répertoire de build
                # Sur Debian, CONFIG_MODULE_COMPRESS_NONE=y garantit que les modules restent en .ko
                signing_before_bindeb = f"""
echo ''
echo '================================='
echo '{i18n._("secureboot.signing_modules_before_packaging")}'
echo '================================='

# Trouver l'outil sign-file
SIGN_FILE=""
for location in "/usr/src/linux-headers-$(uname -r)/scripts/sign-file" \\
                "/lib/modules/$(uname -r)/build/scripts/sign-file" \\
                "scripts/sign-file"; do
    if [ -f "$location" ]; then
        SIGN_FILE="$location"
        break
    fi
done

if [ -z "$SIGN_FILE" ]; then
    echo "❌ Error: sign-file tool not found"
    exit 1
fi

echo ""
echo "🔍 {i18n._("secureboot.counting_modules")}..."

# Compter les modules .ko (non compressés grâce à CONFIG_MODULE_COMPRESS_NONE)
MODULES=($(find . -name "*.ko"))
TOTAL_MODULES=${{#MODULES[@]}}

echo "📦 {i18n._("secureboot.found_modules")}: $TOTAL_MODULES"
echo ""

if [ "$TOTAL_MODULES" -eq 0 ]; then
    echo "⚠️  {i18n._("secureboot.no_modules_found")}"
else
    echo "🔐 {i18n._("secureboot.starting_signature")}..."
    echo ""

    # Signer tous les modules avec affichage de progression
    SIGNED_COUNT=0
    FAILED_COUNT=0
    CURRENT=0

    for module in "${{MODULES[@]}}"; do
        CURRENT=$((CURRENT + 1))
        MODULE_NAME=$(basename "$module")

        # Afficher la progression
        if [ "$TOTAL_MODULES" -le 50 ] || [ $((CURRENT % 10)) -eq 0 ] || [ "$CURRENT" -eq "$TOTAL_MODULES" ]; then
            printf "\\r🔏 [{i18n._("secureboot.progress")}: %3d/%3d] {i18n._("secureboot.signing")}: %-50s" "$CURRENT" "$TOTAL_MODULES" "$MODULE_NAME"
        fi

        # Signer le module
        if "$SIGN_FILE" sha256 '{priv_key}' '{cert}' "$module" >/dev/null 2>&1; then
            SIGNED_COUNT=$((SIGNED_COUNT + 1))
        else
            FAILED_COUNT=$((FAILED_COUNT + 1))
            echo ""
            echo "  ⚠️  {i18n._("secureboot.failed_to_sign")}: $MODULE_NAME"
        fi
    done

    echo ""
    echo ""

    if [ "$FAILED_COUNT" -eq 0 ]; then
        echo "✅ {i18n._("secureboot.all_modules_signed")}: $SIGNED_COUNT"
    else
        echo "⚠️  {i18n._("secureboot.modules_signed_with_errors")}: $SIGNED_COUNT/$TOTAL_MODULES ({i18n._("secureboot.signing_failed")}: $FAILED_COUNT)"
    fi
fi

echo '================================='
echo ''
"""

    cmd = f"""
cd '{linux_dir}' || exit 1
echo '{i18n._("compilation.header")}'
echo '{i18n._("compilation.threads", count=jobs)}'
echo '{i18n._("compilation.suffix", suffix=(suffix or i18n._("compilation.suffix_none")))}'
echo '{i18n._("compilation.fakeroot", status=(i18n._("compilation.fakeroot_yes") if use_fakeroot else i18n._("compilation.fakeroot_no")))}'
{"echo 'SecureBoot Signing: " + i18n._("compilation.fakeroot_yes") + " (AVANT bindeb-pkg)'" if sign_for_secureboot else ""}
{"echo 'Distribution: Debian (CONFIG_MODULE_COMPRESS_NONE activé)'" if is_debian and sign_for_secureboot else ""}
echo ''
echo '{i18n._("compilation.starting")}'
sleep 2

# Étape 1: Compilation des modules
echo ''
echo '{i18n._("compilation.compiling_modules")}'
make -j{jobs} {suffix_cmd} 2>&1 | tee '{log_file}'
RESULT=${{PIPESTATUS[0]}}

if [ $RESULT -ne 0 ]; then
    echo ''
    echo '================================='
    echo '{i18n._("compilation.failed")}'
    echo "Return code: $RESULT"
    echo '================================='
    echo ''
    echo '{i18n._("compilation.press_enter")}'
    read
    exit $RESULT
fi

{signing_before_bindeb}

# Étape 2: Création du package .deb
echo ''
echo '{i18n._("compilation.creating_package")}'
{fakeroot_cmd}make bindeb-pkg {suffix_cmd} 2>&1 | tee -a '{log_file}'
RESULT=${{PIPESTATUS[0]}}

if [ $RESULT -ne 0 ]; then
    echo ''
    echo '================================='
    echo '{i18n._("compilation.failed")}'
    echo "Return code: $RESULT"
    echo '================================='
    echo ''
    echo '{i18n._("compilation.press_enter")}'
    read
    exit $RESULT
fi

# Étape 3: Déplacement des packages
echo ''
echo '================================='
echo '{i18n._("compilation.success")}'
echo ''

echo '{i18n._("compilation.moving_packages")}'
for deb in ../*.deb; do
    if [ -f "$deb" ]; then
        mv "$deb" '{main_window.kernel_manager.repo_dir}/'
        echo "✓ $(basename "$deb") moved"
    fi
done

echo '================================='
echo ''
echo '{i18n._("compilation.press_enter")}'
read
"""
    
    terminals = [
        ["gnome-terminal", "--", "bash", "-c"],
        ["ptyxis", "--", "bash", "-c"],
        ["konsole", "-e", "bash", "-c"],
        ["xterm", "-e", "bash", "-c"]
    ]
    
    launched = False
    for terminal in terminals:
        try:
            process = subprocess.Popen(terminal + [cmd])
            launched = True
            
            main_window.dialogs.show_info(
                i18n._("message.success.title"),
                i18n._("message.info.compilation_launched", threads=jobs, suffix=(suffix or i18n._("compilation.suffix_none")), log=str(log_file))
            )
            
            # Thread pour surveiller la fin
            def monitor_compilation():
                process.wait()
                end_time = datetime.now()
                duration = int((end_time - start_time).total_seconds())

                success = process.returncode == 0
                packages = [p.name for p in main_window.kernel_manager.repo_dir.glob("linux-*.deb")]

                # Ajouter à l'historique
                main_window.kernel_manager.add_compilation_to_history(
                    kernel_version, suffix, success, duration, packages
                )

                # Notification
                if success:
                    main_window.kernel_manager.send_notification(
                        i18n._("message.success.compilation_success"),
                        i18n._("message.success.compilation_success_notification", version=kernel_version, suffix=suffix, time=f"{duration//60}m {duration%60}s"),
                        "low"
                    )
                else:
                    main_window.kernel_manager.send_notification(
                        i18n._("compilation.failed"),
                        i18n._("compilation.failed_notification", version=kernel_version, suffix=suffix),
                        "critical"
                    )

            threading.Thread(target=monitor_compilation, daemon=True).start()
            break
            
        except FileNotFoundError:
            continue
    
    if not launched:
        main_window.dialogs.show_error(i18n._("message.error.title"), i18n._("message.error.no_terminal"))
