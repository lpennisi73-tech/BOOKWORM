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


def show_compile_dialog(main_window):
    """Dialogue de compilation"""
    linux_dir = main_window.kernel_manager.base_dir / "linux"
    
    if not linux_dir.exists():
        main_window.dialogs.show_error("Erreur", "Aucune source kernel trouvée")
        return
    
    if not (linux_dir / ".config").exists():
        main_window.dialogs.show_error("Erreur", "Aucune configuration trouvée\n\nConfigurez d'abord le kernel")
        return
    
    dialog = Gtk.Dialog(
        title="Options de compilation",
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
    threads_box.pack_start(Gtk.Label(label="Nombre de threads:"), False, False, 0)
    
    threads_spin = Gtk.SpinButton()
    threads_spin.set_range(1, os.cpu_count() * 2)
    threads_spin.set_value(os.cpu_count())
    threads_spin.set_increments(1, 4)
    threads_box.pack_start(threads_spin, True, True, 0)
    
    content.pack_start(threads_box, False, False, 0)
    
    # Suffixe
    suffix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    suffix_box.pack_start(Gtk.Label(label="Suffixe (optionnel):"), False, False, 0)
    
    suffix_entry = Gtk.Entry()
    suffix_entry.set_placeholder_text("-custom")
    suffix_box.pack_start(suffix_entry, True, True, 0)
    
    content.pack_start(suffix_box, False, False, 0)
    
    # Fakeroot
    fakeroot_check = Gtk.CheckButton(label="Utiliser fakeroot (recommandé)")
    fakeroot_check.set_active(True)
    content.pack_start(fakeroot_check, False, False, 0)
    
    # Info
    info_label = Gtk.Label()
    info_label.set_markup("<i>Durée estimée: 30-90 minutes</i>")
    content.pack_start(info_label, False, False, 0)
    
    dialog.add_button("Annuler", Gtk.ResponseType.CANCEL)
    dialog.add_button("🔨 Compiler", Gtk.ResponseType.OK)
    
    dialog.show_all()
    response = dialog.run()
    
    if response == Gtk.ResponseType.OK:
        jobs = int(threads_spin.get_value())
        suffix = suffix_entry.get_text().strip()
        use_fakeroot = fakeroot_check.get_active()
        
        dialog.destroy()
        compile_kernel(main_window, jobs, suffix, use_fakeroot)
    else:
        dialog.destroy()


def compile_kernel(main_window, jobs, suffix, use_fakeroot):
    """Lance la compilation dans un terminal"""
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
    
    cmd = f"""
cd '{linux_dir}' || exit 1
echo '=== COMPILATION DU KERNEL ==='
echo 'Threads: {jobs}'
echo 'Suffixe: {suffix or "aucun"}'
echo 'Fakeroot: {"oui" if use_fakeroot else "non"}'
echo ''
echo 'La compilation va démarrer...'
sleep 2

{fakeroot_cmd}make -j{jobs} bindeb-pkg {suffix_cmd} 2>&1 | tee '{log_file}'
RESULT=${{PIPESTATUS[0]}}

echo ''
echo '================================='
if [ $RESULT -eq 0 ]; then
    echo '✅ COMPILATION RÉUSSIE !'
    
    echo 'Déplacement des paquets...'
    for deb in ../*.deb; do
        if [ -f "$deb" ]; then
            mv "$deb" '{main_window.kernel_manager.repo_dir}/'
            echo "✓ $(basename "$deb") déplacé"
        fi
    done
else
    echo '❌ COMPILATION ÉCHOUÉE !'
    echo 'Code retour: '$RESULT
fi
echo '================================='
echo ''
echo 'Appuyez sur Entrée pour fermer...'
read
exit $RESULT
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
                "Compilation lancée",
                f"La compilation s'exécute dans le terminal\n\n"
                f"Threads: {jobs}\n"
                f"Suffixe: {suffix or 'aucun'}\n"
                f"Log: {log_file}"
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
                        "✅ Compilation réussie !",
                        f"Kernel {kernel_version}{suffix} compilé en {duration//60}m {duration%60}s",
                        "low"
                    )
                else:
                    main_window.kernel_manager.send_notification(
                        "❌ Compilation échouée",
                        f"Erreur lors de la compilation du kernel {kernel_version}{suffix}",
                        "critical"
                    )
            
            threading.Thread(target=monitor_compilation, daemon=True).start()
            break
            
        except FileNotFoundError:
            continue
    
    if not launched:
        main_window.dialogs.show_error("Erreur", "Aucun terminal compatible trouvé")
