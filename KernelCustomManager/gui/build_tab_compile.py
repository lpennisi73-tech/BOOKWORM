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

    # Détecter si on doit signer APRÈS bindeb-pkg (Debian 13+)
    sb_manager = main_window.secureboot_manager
    needs_post_bindeb_signing = sb_manager.needs_post_bindeb_signing()

    # Détecter la distribution pour adapter la commande bindeb-pkg
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

    # Préparer les variables pour la signature SecureBoot (initialisées vides par défaut)
    signing_before_bindeb = ""
    signing_after_bindeb = ""

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
                # Script de signature des modules (réutilisable)
                base_signing_script = f"""
echo ''
echo '================================='
echo '{{timing_message}}'
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
echo "🔍 {{count_message}}..."

# Compter d'abord tous les modules (incluant .ko.xz sur Debian)
MODULES=($(find {{{{search_path}}}} -name "*.ko" -o -name "*.ko.xz" -o -name "*.ko.gz" -o -name "*.ko.zst"))
TOTAL_MODULES=$${{{{#MODULES[@]}}}}

echo "📦 {{found_message}}: $TOTAL_MODULES"
echo ""

if [ "$TOTAL_MODULES" -eq 0 ]; then
    echo "⚠️  {{no_modules_message}}"
else
    echo "🔐 {{starting_message}}..."
    echo ""

    # Signer tous les modules avec affichage de progression
    SIGNED_COUNT=0
    FAILED_COUNT=0
    CURRENT=0

    for module in "$${{{{MODULES[@]}}}}"; do
        CURRENT=$((CURRENT + 1))
        MODULE_NAME=$(basename "$module")

        # Variables pour gérer la compression
        COMPRESSED=false
        COMPRESSION_TYPE=""
        MODULE_TO_SIGN="$module"

        # Détecter si le module est compressé et le décompresser temporairement
        if [[ "$module" == *.ko.xz ]]; then
            COMPRESSED=true
            COMPRESSION_TYPE="xz"
            MODULE_TO_SIGN="$${{{{module%.xz}}}}"
            xz -d -k "$module" 2>/dev/null || continue
        elif [[ "$module" == *.ko.gz ]]; then
            COMPRESSED=true
            COMPRESSION_TYPE="gz"
            MODULE_TO_SIGN="$${{{{module%.gz}}}}"
            gzip -d -k "$module" 2>/dev/null || continue
        elif [[ "$module" == *.ko.zst ]]; then
            COMPRESSED=true
            COMPRESSION_TYPE="zst"
            MODULE_TO_SIGN="$${{{{module%.zst}}}}"
            zstd -d -q "$module" -o "$MODULE_TO_SIGN" 2>/dev/null || continue
        fi

        # Afficher la progression
        if [ "$TOTAL_MODULES" -le 50 ] || [ $((CURRENT % 10)) -eq 0 ] || [ "$CURRENT" -eq "$TOTAL_MODULES" ]; then
            printf "\\r🔏 [{{progress_message}}: %3d/%3d] {{signing_message}}: %-50s" "$CURRENT" "$TOTAL_MODULES" "$MODULE_NAME"
        fi

        # Signer le module .ko décompressé
        if "$SIGN_FILE" sha256 '{priv_key}' '{cert}' "$MODULE_TO_SIGN" >/dev/null 2>&1; then
            SIGNED_COUNT=$((SIGNED_COUNT + 1))

            # Recompresser si nécessaire
            if [ "$COMPRESSED" = true ]; then
                case "$COMPRESSION_TYPE" in
                    xz)
                        rm -f "$module"
                        xz -z -k "$MODULE_TO_SIGN" 2>/dev/null
                        rm -f "$MODULE_TO_SIGN"
                        ;;
                    gz)
                        rm -f "$module"
                        gzip -c "$MODULE_TO_SIGN" > "$module" 2>/dev/null
                        rm -f "$MODULE_TO_SIGN"
                        ;;
                    zst)
                        rm -f "$module"
                        zstd -q "$MODULE_TO_SIGN" -o "$module" 2>/dev/null
                        rm -f "$MODULE_TO_SIGN"
                        ;;
                esac
            fi
        else
            FAILED_COUNT=$((FAILED_COUNT + 1))
            # Nettoyer en cas d'échec
            [ "$COMPRESSED" = true ] && [ -f "$MODULE_TO_SIGN" ] && rm -f "$MODULE_TO_SIGN"
            echo ""
            echo "  ⚠️  {{failed_message}}: $MODULE_NAME"
        fi
    done

    echo ""
    echo ""

    if [ "$FAILED_COUNT" -eq 0 ]; then
        echo "✅ {{all_signed_message}}: $SIGNED_COUNT"
    else
        echo "⚠️  {{signed_with_errors_message}}: $SIGNED_COUNT/$TOTAL_MODULES ({{signing_failed_message}}: $FAILED_COUNT)"
    fi
fi

echo '================================='
echo ''
"""

                # Pour Ubuntu : signer AVANT bindeb-pkg (modules .ko non compressés)
                signing_before_bindeb_content = base_signing_script.format(
                    timing_message=i18n._("secureboot.signing_modules_before_packaging"),
                    count_message=i18n._("secureboot.counting_modules"),
                    found_message=i18n._("secureboot.found_modules"),
                    no_modules_message=i18n._("secureboot.no_modules_found"),
                    starting_message=i18n._("secureboot.starting_signature"),
                    progress_message=i18n._("secureboot.progress"),
                    signing_message=i18n._("secureboot.signing"),
                    failed_message=i18n._("secureboot.failed_to_sign"),
                    all_signed_message=i18n._("secureboot.all_modules_signed"),
                    signed_with_errors_message=i18n._("secureboot.modules_signed_with_errors"),
                    signing_failed_message=i18n._("secureboot.signing_failed"),
                    search_path="."
                )

                # Pour Debian : signer APRÈS bindeb-pkg (modules .ko NON compressés grâce à CONFIG_MODULE_COMPRESS_NONE)
                # On détermine le nom du kernel avec le suffixe
                kernel_name = f"{kernel_version}{suffix}" if suffix else kernel_version

                signing_after_bindeb_content = f"""
# DEBIAN POST-BINDEB SIGNING
# Sur Debian, avec CONFIG_MODULE_COMPRESS_NONE=y, les modules restent en .ko
# Il faut signer APRÈS bindeb-pkg + régénérer l'initrd

echo ''
echo '================================='
echo '{i18n._("secureboot.signing_modules_after_packaging_debian")}'
echo '================================='
echo ''
echo '⚠️  Debian détecté : CONFIG_MODULE_COMPRESS_NONE utilisé'
echo '🔧 Signature des modules dans /lib/modules/ nécessaire...'
echo ''

# Extraire le .deb et signer les modules
KERNEL_VERSION="{kernel_name}"
DEB_FILE="../linux-image-$${{{{KERNEL_VERSION}}}}_*.deb"

# Vérifier que le .deb existe
if ! ls $DEB_FILE 1> /dev/null 2>&1; then
    echo "❌ Erreur: Package .deb non trouvé"
    exit 1
fi

# Installer temporairement le package pour accéder aux modules
echo "📦 Installation temporaire du package pour accéder aux modules..."
sudo dpkg -i $DEB_FILE 2>&1 | grep -v "^dpkg:"

# Maintenant signer les modules installés dans /lib/modules/
""" + base_signing_script.format(
                    timing_message="Signature des modules dans /lib/modules/",
                    count_message="Comptage des modules installés",
                    found_message="Modules trouvés",
                    no_modules_message="Aucun module trouvé",
                    starting_message="Démarrage de la signature",
                    progress_message="Progression",
                    signing_message="Signature",
                    failed_message="Échec signature",
                    all_signed_message="Tous les modules signés",
                    signed_with_errors_message="Modules signés avec erreurs",
                    signing_failed_message="Signature échouée",
                    search_path=f"/lib/modules/{kernel_name}"
                ) + f"""
# Régénérer l'initrd avec les modules signés
echo ''
echo '🔄 Régénération de l'initrd avec les modules signés...'
sudo update-initramfs -u -k "{kernel_name}"

if [ $? -eq 0 ]; then
    echo "✅ Initrd régénéré avec succès"
else
    echo "❌ Erreur lors de la régénération de l'initrd"
    exit 1
fi

echo ''
echo '================================='
echo '✅ Signature post-bindeb terminée (Debian)'
echo '================================='
echo ''
"""
                # Choisir le bon script de signature selon la distribution
                if needs_post_bindeb_signing:
                    # Debian : on ne signe PAS avant bindeb-pkg
                    signing_before_bindeb = ""
                    signing_after_bindeb = signing_after_bindeb_content
                else:
                    # Ubuntu : on signe AVANT bindeb-pkg
                    signing_before_bindeb = signing_before_bindeb_content
                    signing_after_bindeb = ""

    cmd = f"""
cd '{linux_dir}' || exit 1
echo '{i18n._("compilation.header")}'
echo '{i18n._("compilation.threads", count=jobs)}'
echo '{i18n._("compilation.suffix", suffix=(suffix or i18n._("compilation.suffix_none")))}'
echo '{i18n._("compilation.fakeroot", status=(i18n._("compilation.fakeroot_yes") if use_fakeroot else i18n._("compilation.fakeroot_no")))}'
{"echo 'SecureBoot Signing: " + i18n._("compilation.fakeroot_yes") + "'" if sign_for_secureboot else ""}
{"echo 'Distribution: Debian (CONFIG_MODULE_COMPRESS_NONE activé)'" if is_debian else "echo 'Distribution: Ubuntu (modules non compressés par défaut)'"}
echo ''
echo '{i18n._("compilation.starting")}'
sleep 2

# Étape 1: Compilation des modules
echo ''
echo '{i18n._("compilation.compiling_modules")}'
make -j{jobs} {suffix_cmd} 2>&1 | tee '{log_file}'
RESULT=$${{{{PIPESTATUS[0]}}}}

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
RESULT=$${{{{PIPESTATUS[0]}}}}

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

{signing_after_bindeb}

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
