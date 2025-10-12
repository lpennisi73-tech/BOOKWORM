"""
Module de configuration du kernel
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
import subprocess
import shutil
from pathlib import Path


def show_config_dialog(main_window):
    """Affiche le dialogue de configuration"""
    linux_dir = main_window.kernel_manager.base_dir / "linux"
    
    if not linux_dir.exists():
        main_window.dialogs.show_error("Erreur", "Aucune source kernel trouvée\n\nTéléchargez d'abord un kernel")
        return
    
    dialog = Gtk.Dialog(
        title="Configuration du kernel",
        transient_for=main_window,
        flags=0
    )
    dialog.set_default_size(500, 200)
    
    content = dialog.get_content_area()
    content.set_spacing(15)
    content.set_margin_start(20)
    content.set_margin_end(20)
    content.set_margin_top(10)
    content.set_margin_bottom(10)
    
    label = Gtk.Label()
    label.set_markup("<b>Choisissez une méthode de configuration :</b>")
    content.pack_start(label, False, False, 0)
    
    system_radio = Gtk.RadioButton.new_with_label_from_widget(None, "Config système actuelle")
    content.pack_start(system_radio, False, False, 0)
    
    file_radio = Gtk.RadioButton.new_with_label_from_widget(system_radio, "Charger un fichier .config")
    content.pack_start(file_radio, False, False, 0)
    
    menuconfig_check = Gtk.CheckButton(label="Lancer menuconfig après")
    menuconfig_check.set_active(True)
    content.pack_start(menuconfig_check, False, False, 0)
    
    dialog.add_button("Annuler", Gtk.ResponseType.CANCEL)
    dialog.add_button("Configurer", Gtk.ResponseType.OK)
    
    dialog.show_all()
    response = dialog.run()
    
    if response == Gtk.ResponseType.OK:
        use_system = system_radio.get_active()
        run_menuconfig = menuconfig_check.get_active()
        
        if use_system:
            configure_from_system(main_window, run_menuconfig)
        else:
            configure_from_file(main_window, run_menuconfig)
    
    dialog.destroy()


def configure_from_system(main_window, run_menuconfig=True):
    """Configure depuis la config système"""
    import platform
    
    current_kernel = platform.release()
    config_file = Path(f"/boot/config-{current_kernel}")
    
    if not config_file.exists():
        main_window.dialogs.show_error("Erreur", f"Config système introuvable:\n{config_file}")
        return
    
    linux_dir = main_window.kernel_manager.base_dir / "linux"
    dest_config = linux_dir / ".config"
    
    try:
        shutil.copy(config_file, dest_config)
        
        # Adaptation pour Ubuntu/Debian
        subprocess.run(
            ["sed", "-i", 's/CONFIG_SYSTEM_TRUSTED_KEYS=.*/CONFIG_SYSTEM_TRUSTED_KEYS=""/', str(dest_config)],
            check=True
        )
        subprocess.run(
            ["sed", "-i", 's/CONFIG_SYSTEM_REVOCATION_KEYS=.*/CONFIG_SYSTEM_REVOCATION_KEYS=""/', str(dest_config)],
            check=True
        )
        
        subprocess.run(
            ["make", "olddefconfig"],
            cwd=str(linux_dir),
            check=True
        )
        
        if run_menuconfig:
            run_menuconfig_terminal(main_window)
        else:
            main_window.dialogs.show_info("Succès", "Configuration système appliquée !")
            
    except Exception as e:
        main_window.dialogs.show_error("Erreur", f"Échec de la configuration:\n{e}")


def configure_from_file(main_window, run_menuconfig=True):
    """Configure depuis un fichier"""
    dialog = Gtk.FileChooserDialog(
        title="Sélectionner un fichier .config",
        parent=main_window,
        action=Gtk.FileChooserAction.OPEN
    )
    dialog.add_buttons(
        Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
        Gtk.STOCK_OPEN, Gtk.ResponseType.OK
    )
    
    filter_config = Gtk.FileFilter()
    filter_config.set_name("Fichiers config")
    filter_config.add_pattern("*.config")
    filter_config.add_pattern("*.conf")
    dialog.add_filter(filter_config)
    
    response = dialog.run()
    
    if response == Gtk.ResponseType.OK:
        config_file = Path(dialog.get_filename())
        linux_dir = main_window.kernel_manager.base_dir / "linux"
        dest_config = linux_dir / ".config"
        
        try:
            shutil.copy(config_file, dest_config)
            
            subprocess.run(
                ["make", "olddefconfig"],
                cwd=str(linux_dir),
                check=True
            )
            
            if run_menuconfig:
                run_menuconfig_terminal(main_window)
            else:
                main_window.dialogs.show_info("Succès", f"Configuration chargée depuis:\n{config_file}")
                
        except Exception as e:
            main_window.dialogs.show_error("Erreur", f"Échec du chargement:\n{e}")
    
    dialog.destroy()


def run_menuconfig_terminal(main_window):
    """Lance menuconfig dans un terminal"""
    linux_dir = main_window.kernel_manager.base_dir / "linux"
    
    terminals = [
        ["gnome-terminal", "--", "bash", "-c"],
        ["ptyxis", "--", "bash", "-c"],
        ["konsole", "-e", "bash", "-c"],
        ["xterm", "-e", "bash", "-c"]
    ]
    
    cmd = f"cd '{linux_dir}' && make nconfig; read -p 'Appuyez sur Entrée...'"
    
    for terminal in terminals:
        try:
            subprocess.Popen(terminal + [cmd])
            return
        except FileNotFoundError:
            continue
    
    main_window.dialogs.show_error("Erreur", "Aucun terminal compatible trouvé")
