#!/bin/bash
# Script d'installation KernelCustom Manager

set -e

echo "=========================================="
echo "  KernelCustom Manager - Installation"
echo "  Édition Professionnelle v2.2"
echo "=========================================="
echo ""

# Détecter la distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    echo "❌ Distribution non reconnue"
    exit 1
fi

echo "📦 Détection de la distribution: $DISTRO"
echo ""

# Installer les dépendances
echo "📥 Installation des dépendances..."

case "$DISTRO" in
    ubuntu|debian|linuxmint)
        sudo apt update
        sudo apt install -y \
            python3 \
            python3-gi \
            gir1.2-gtk-3.0 \
            gir1.2-gtk-4.0 \
            gir1.2-notify-0.7 \
            libnotify-bin \
            build-essential \
            bc bison flex \
            libssl-dev libelf-dev \
            libncurses-dev \
            fakeroot dpkg-dev \
            curl tar xz-utils \
            debhelper-compat \
            libdw-dev rsync \
            gawk dkms

        # ImageMagick (optionnel - pour générer les icônes en différentes tailles)
        sudo apt install -y imagemagick 2>/dev/null || echo "   ⚠️  ImageMagick non installé (optionnel)"
        ;;
    
    fedora)
        sudo dnf install -y \
            python3 \
            python3-gobject \
            gtk3 \
            libnotify \
            @development-tools \
            bc bison flex \
            openssl-devel elfutils-libelf-devel \
            ncurses-devel \
            fakeroot rpm-build \
            curl tar xz

        # ImageMagick (optionnel - pour générer les icônes en différentes tailles)
        sudo dnf install -y ImageMagick 2>/dev/null || echo "   ⚠️  ImageMagick non installé (optionnel)"
        ;;
    
    arch|manjaro)
        sudo pacman -S --noconfirm \
            python \
            python-gobject \
            gtk3 \
            libnotify \
            base-devel \
            bc bison flex \
            openssl elfutils \
            ncurses \
            fakeroot \
            curl tar xz

        # ImageMagick (optionnel - pour générer les icônes en différentes tailles)
        sudo pacman -S --noconfirm imagemagick 2>/dev/null || echo "   ⚠️  ImageMagick non installé (optionnel)"
        ;;
    
    *)
        echo "⚠️  Distribution $DISTRO non supportée automatiquement"
        echo "Installez manuellement les dépendances:"
        echo "  - Python 3 + GTK 3 + libnotify"
        echo "  - Outils de compilation (gcc, make, etc.)"
        echo "  - ImageMagick (optionnel - pour icônes multiples tailles)"
        ;;
esac

echo ""
echo "✅ Dépendances installées"
echo ""

# Rendre les scripts exécutables
chmod +x kernelcustom_manager.py 2>/dev/null || true
chmod +x manage_kernel_sources.sh 2>/dev/null || true
chmod +x kernelcustom-helper 2>/dev/null || true

# Rendre les scripts SecureBoot exécutables
echo "🔐 Configuration des scripts SecureBoot..."
if [ -d "scripts/secureboot" ]; then
    chmod +x scripts/secureboot/*.sh 2>/dev/null || true
    echo "   ✓ Scripts SecureBoot configurés"
fi

# Installer PolicyKit et le helper
echo "🔐 Installation du helper PolicyKit..."
if sudo cp kernelcustom-helper /usr/local/bin/kernelcustom-helper 2>/dev/null; then
    sudo chmod +x /usr/local/bin/kernelcustom-helper
    echo "   ✓ Helper installé dans /usr/local/bin/"
fi

if sudo cp com.kernelcustom.manager.policy /usr/share/polkit-1/actions/ 2>/dev/null; then
    echo "   ✓ Règles PolicyKit installées"
    echo "   ✓ Le mot de passe ne sera demandé qu'une fois toutes les 5 minutes !"
else
    echo "   ⚠️  Impossible d'installer les règles PolicyKit (sudo requis)"
    echo "      L'application fonctionnera mais demandera le mot de passe plus souvent"
fi

# Installer l'icône dans les répertoires standards
echo "🖼️  Installation de l'icône..."
INSTALL_DIR="$(pwd)"

# Créer les répertoires pour les icônes
mkdir -p "$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$HOME/.local/share/icons/hicolor/128x128/apps"
mkdir -p "$HOME/.local/share/icons/hicolor/48x48/apps"

# Copier l'icône PNG principale (256x256)
cp "$INSTALL_DIR/icon.png" "$HOME/.local/share/icons/hicolor/256x256/apps/kernelcustom-manager.png"
echo "   ✓ Icône 256x256 installée"

# Générer les autres tailles si ImageMagick est disponible
if command -v convert >/dev/null 2>&1; then
    convert "$INSTALL_DIR/icon.png" -resize 128x128 "$HOME/.local/share/icons/hicolor/128x128/apps/kernelcustom-manager.png" 2>/dev/null || true
    convert "$INSTALL_DIR/icon.png" -resize 48x48 "$HOME/.local/share/icons/hicolor/48x48/apps/kernelcustom-manager.png" 2>/dev/null || true
    echo "   ✓ Icônes 128x128 et 48x48 générées"
elif command -v magick >/dev/null 2>&1; then
    magick "$INSTALL_DIR/icon.png" -resize 128x128 "$HOME/.local/share/icons/hicolor/128x128/apps/kernelcustom-manager.png" 2>/dev/null || true
    magick "$INSTALL_DIR/icon.png" -resize 48x48 "$HOME/.local/share/icons/hicolor/48x48/apps/kernelcustom-manager.png" 2>/dev/null || true
    echo "   ✓ Icônes 128x128 et 48x48 générées"
else
    echo "   ⚠️  ImageMagick non disponible - seule l'icône 256x256 sera installée"
fi

# Créer le lanceur d'application
echo "🚀 Installation du lanceur d'application..."
DESKTOP_FILE="$HOME/.local/share/applications/kernelcustom.desktop"

# Créer le répertoire s'il n'existe pas
mkdir -p "$HOME/.local/share/applications"

# Créer le fichier .desktop
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=KernelCustom Manager
Comment=Gestionnaire de kernels personnalisés
Exec=python3 $INSTALL_DIR/kernelcustom_manager.py
Icon=kernelcustom-manager
Terminal=false
Categories=System;Settings;
Keywords=kernel;compile;linux;
EOF

# Rendre le fichier .desktop exécutable
chmod +x "$DESKTOP_FILE"

# S'assurer que le script Python est exécutable
chmod +x "$INSTALL_DIR/kernelcustom_manager.py"

# Mettre à jour le cache des icônes
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
    echo "   ✓ Cache des icônes mis à jour"
fi

# Mettre à jour la base de données des applications
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    echo "   ✓ Base de données des applications mise à jour"
fi

echo "✅ Lanceur installé dans : $DESKTOP_FILE"
echo "   Redémarrez votre session si le lanceur n'apparaît pas immédiatement"
echo ""

echo "=========================================="
echo "  ✨ Installation terminée !"
echo "=========================================="
echo ""
echo "📝 L'application est maintenant disponible :"
echo ""
echo "1. Dans votre menu d'applications (cherchez 'KernelCustom')"
echo "2. Ou en ligne de commande:"
echo "   cd $INSTALL_DIR"
echo "   ./kernelcustom_manager.py"
echo ""
echo "🚀 Bon développement !"
