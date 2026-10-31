#!/bin/bash
# Script d'installation KernelCustom Manager

set -e

echo "=========================================="
echo "  KernelCustom Manager - Installation"
echo "  Édition Professionnelle v2.3"
echo "=========================================="
echo ""

# Vérifier la distribution (Debian 13+ uniquement)
if [ -f /etc/os-release ]; then
    . /etc/os-release
else
    echo "❌ Distribution non reconnue (/etc/os-release absent)"
    exit 1
fi

if [ "$ID" != "debian" ]; then
    echo "❌ KernelCustom Manager supporte uniquement Debian (détecté: $ID)"
    exit 1
fi

echo "📦 Distribution: $PRETTY_NAME"
echo ""

# Installer les dépendances
echo "📥 Installation des dépendances..."

sudo apt update
sudo apt install -y \
    python3 \
    python3-gi \
    gir1.2-gtk-3.0 \
    gir1.2-gtk-4.0 \
    gir1.2-adw-1 \
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
    gawk dkms \
    mokutil sbsigntool

echo ""
echo "✅ Dépendances installées"
echo ""

# Rendre les scripts exécutables
chmod +x kernelcustom_manager.py 2>/dev/null || true
chmod +x manage_kernel_sources.sh 2>/dev/null || true

# Rendre les scripts SecureBoot exécutables
echo "🔐 Configuration des scripts SecureBoot..."
if [ -d "scripts/secureboot" ]; then
    chmod +x scripts/secureboot/*.sh 2>/dev/null || true
    echo "   ✓ Scripts SecureBoot configurés"
fi

# Installer les helpers privilégiés (root:root, non modifiables) et la policy PolicyKit
echo "🔐 Installation des helpers privilégiés..."
HELPER_DIR=/usr/libexec/kernelcustom-manager
sudo install -d -o root -g root -m 0755 "$HELPER_DIR"
sudo install -o root -g root -m 0755 helpers/kernelcustom-helper "$HELPER_DIR/kernelcustom-helper"
sudo install -o root -g root -m 0755 helpers/kernelcustom-nvidia-installer "$HELPER_DIR/kernelcustom-nvidia-installer"
echo "   ✓ Helpers installés dans $HELPER_DIR"

# Ancien emplacement (versions ≤ 2.3)
if [ -e /usr/local/bin/kernelcustom-helper ]; then
    sudo rm -f /usr/local/bin/kernelcustom-helper
    echo "   ✓ Ancien helper /usr/local/bin/kernelcustom-helper supprimé"
fi

sudo install -o root -g root -m 0644 com.kernelcustom.manager.policy /usr/share/polkit-1/actions/
echo "   ✓ Règles PolicyKit installées (mot de passe mémorisé quelques minutes)"

# Créer le lanceur d'application
echo "🚀 Installation du lanceur d'application..."
INSTALL_DIR="$(pwd)"
DESKTOP_FILE="$HOME/.local/share/applications/kernelcustom.desktop"

# Créer le répertoire s'il n'existe pas
mkdir -p "$HOME/.local/share/applications"

# Créer le fichier .desktop avec le chemin absolu vers l'icône
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=KernelCustom Manager
Comment=Gestionnaire de kernels personnalisés
Exec=python3 $INSTALL_DIR/kernelcustom_manager.py
Icon=$INSTALL_DIR/icon.png
Terminal=false
Categories=System;Settings;
Keywords=kernel;compile;linux;
StartupWMClass=KernelCustom Manager
StartupNotify=true
EOF

# Rendre le fichier .desktop exécutable
chmod +x "$DESKTOP_FILE"

# S'assurer que le script Python est exécutable
chmod +x "$INSTALL_DIR/kernelcustom_manager.py"

# Mettre à jour la base de données des applications
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

echo "   ✓ Lanceur créé avec l'icône: $INSTALL_DIR/icon.png"

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
