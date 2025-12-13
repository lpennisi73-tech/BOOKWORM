#!/bin/bash
# Script de gestion des sources kernel dans /usr/src/
# Usage: ./manage_kernel_sources.sh [install|remove] [version]

set -e

# Déterminer le répertoire build de KernelCustomManager
# 1. Chercher la racine du repo git
# 2. Sinon utiliser le chemin par défaut ~/KernelCustomManager/build
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Déterminer le vrai HOME de l'utilisateur (même avec pkexec/sudo)
if [ -n "$PKEXEC_UID" ]; then
    # Exécuté avec pkexec, récupérer le home de l'utilisateur original
    REAL_USER=$(getent passwd "$PKEXEC_UID" | cut -d: -f1)
    REAL_HOME=$(getent passwd "$PKEXEC_UID" | cut -d: -f6)
elif [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
    # Exécuté avec sudo
    REAL_USER="$SUDO_USER"
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    # Exécution normale
    REAL_USER="$USER"
    REAL_HOME="$HOME"
fi

# Essayer de trouver la racine du repo git
GIT_ROOT=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || echo "")

if [ -n "$GIT_ROOT" ] && [ -d "$GIT_ROOT/build/sources" ]; then
    # Utiliser le build/ à la racine du repo git
    BUILD_DIR="$GIT_ROOT/build"
elif [ -d "$REAL_HOME/KernelCustomManager/build/sources" ]; then
    # Utiliser le chemin par défaut (comme dans kernel_manager.py)
    BUILD_DIR="$REAL_HOME/KernelCustomManager/build"
else
    # Fallback sur l'ancien comportement
    BUILD_DIR="$SCRIPT_DIR/build"
fi

SOURCES_DIR="$BUILD_DIR/sources"
USR_SRC="/usr/src"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERREUR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[ATTENTION]${NC} $1"
}

# Fonction pour installer les sources
install_sources() {
    local version="$1"
    
    if [ -z "$version" ]; then
        print_error "Version non spécifiée"
        echo "Usage: $0 install <version>"
        echo "Exemple: $0 install 6.11.6"
        exit 1
    fi
    
    # Chercher les sources (avec ou sans suffixe)
    local src_path=""
    
    if [ -d "$SOURCES_DIR/linux-$version" ]; then
        src_path="$SOURCES_DIR/linux-$version"
    else
        src_path=$(find "$SOURCES_DIR" -maxdepth 1 -type d -name "linux-$version*" | head -n1)
    fi
    
    if [ -z "$src_path" ] || [ ! -d "$src_path" ]; then
        print_error "Sources introuvables: $src_path"
        echo "Téléchargez d'abord le kernel avec KernelCustom Manager"
        exit 1
    fi
    
    # Extraire le nom complet (avec suffixe)
    local full_name=$(basename "$src_path")
    local full_version="${full_name#linux-}"
    
    print_info "Installation des sources du kernel $full_version dans /usr/src/"
    
    # Vérifier les droits root
    if [ "$EUID" -ne 0 ]; then
        print_warning "Ce script nécessite les droits root"
        exec sudo "$0" install "$version"
        exit $?
    fi
    
    # Copier les sources
    print_info "Copie des sources..."
    if [ -d "$USR_SRC/$full_name" ]; then
        print_warning "Le répertoire $USR_SRC/$full_name existe déjà"
        read -p "Écraser? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Opération annulée"
            exit 0
        fi
        rm -rf "$USR_SRC/$full_name"
    fi
    
    cp -r "$src_path" "$USR_SRC/$full_name"
    print_success "Sources copiées vers $USR_SRC/$full_name"
    
    # Créer le lien symbolique linux
    print_info "Création du lien symbolique linux..."
    if [ -L "$USR_SRC/linux" ]; then
        rm "$USR_SRC/linux"
    fi
    ln -sf "$full_name" "$USR_SRC/linux"
    print_success "Lien créé: $USR_SRC/linux -> $full_name"
    
    # Chercher les headers avec la version complète
    local headers_src=""
    
    # 1. D'abord vérifier si déjà installé dans /usr/src/
    if [ -d "$USR_SRC/linux-headers-$full_version" ]; then
        print_success "Headers déjà présents dans /usr/src/linux-headers-$full_version"
        headers_src="$USR_SRC/linux-headers-$full_version"
    # 2. Chercher dans le même dossier que les sources
    elif [ -d "$(dirname "$src_path")/linux-headers-$full_version" ]; then
        headers_src="$(dirname "$src_path")/linux-headers-$full_version"
    # 3. Chercher dans SOURCES_DIR
    elif [ -d "$SOURCES_DIR/linux-headers-$full_version" ]; then
        headers_src="$SOURCES_DIR/linux-headers-$full_version"
    fi
    
    if [ -n "$headers_src" ] && [ -d "$headers_src" ]; then
        local headers_name=$(basename "$headers_src")
        
        # Si headers déjà dans /usr/src, ne rien faire
        if [ "$headers_src" = "$USR_SRC/$headers_name" ]; then
            print_info "Headers déjà en place, aucune copie nécessaire"
        else
            print_info "Copie des headers: $headers_name"
            
            if [ -d "$USR_SRC/$headers_name" ]; then
                rm -rf "$USR_SRC/$headers_name"
            fi
            
            cp -r "$headers_src" "$USR_SRC/$headers_name"
            print_success "Headers copiés vers $USR_SRC/$headers_name"
        fi
        
        # Créer le lien symbolique pour les headers
        if [ -L "$USR_SRC/linux-headers" ]; then
            rm "$USR_SRC/linux-headers"
        fi
        ln -sf "$headers_name" "$USR_SRC/linux-headers"
        print_success "Lien créé: $USR_SRC/linux-headers -> $headers_name"
    else
        print_warning "Headers non trouvés pour $full_version"
        print_info "Vous pouvez les générer avec: make headers_install"
    fi
    
    # Ajuster les permissions
    print_info "Ajustement des permissions..."
    chown -R root:root "$USR_SRC/$full_name"
    [ -d "$USR_SRC/linux-headers-$full_version" ] && chown -R root:root "$USR_SRC/linux-headers-$full_version"
    
    print_success "Installation terminée!"
    echo ""
    echo "Sources installées dans:"
    echo "  - $USR_SRC/$full_name"
    echo "  - $USR_SRC/linux -> $full_name"
    [ -d "$USR_SRC/linux-headers-$full_version" ] && echo "  - $USR_SRC/linux-headers-$full_version"
    [ -L "$USR_SRC/linux-headers" ] && echo "  - $USR_SRC/linux-headers -> linux-headers-$full_version"
}

# Fonction pour supprimer les sources
remove_sources() {
    local version="$1"
    
    if [ -z "$version" ]; then
        # Lister les versions disponibles
        print_info "Versions disponibles dans /usr/src/:"
        ls -d $USR_SRC/linux-[0-9]* 2>/dev/null | xargs -n1 basename || echo "Aucune"
        echo ""
        echo "Usage: $0 remove <version>"
        echo "Exemple: $0 remove 6.11.6"
        exit 1
    fi
    
    # Vérifier les droits root
    if [ "$EUID" -ne 0 ]; then
        print_warning "Ce script nécessite les droits root"
        exec sudo "$0" remove "$version"
        exit $?
    fi
    
    local src_path="$USR_SRC/linux-$version"
    local headers_path="$USR_SRC/linux-headers-$version"
    
    if [ ! -d "$src_path" ]; then
        print_error "Sources introuvables: $src_path"
        exit 1
    fi
    
    print_warning "Suppression des sources du kernel $version"
    echo "Cela supprimera:"
    echo "  - $src_path"
    [ -d "$headers_path" ] && echo "  - $headers_path"
    echo ""
    
    read -p "Confirmer la suppression? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Opération annulée"
        exit 0
    fi

    # Sauvegarder la cible du lien/répertoire avant de le supprimer
    local src_target=""
    if [ -L "$src_path" ]; then
        src_target=$(readlink "$src_path")
    fi

    # Supprimer les liens symboliques si ils pointent vers cette version
    if [ -L "$USR_SRC/linux" ]; then
        local target=$(readlink "$USR_SRC/linux")
        # Extraire le nom de base avec expansion de paramètre (plus robuste que basename)
        local target_basename="${target##*/}"

        # Supprimer si le nom correspond OU si le lien pointe vers le même endroit
        if [ "$target_basename" = "linux-$version" ] || [ "$target" = "$src_target" ]; then
            print_info "Suppression du lien $USR_SRC/linux -> $target"
            rm "$USR_SRC/linux"
        fi
    fi

    if [ -L "$USR_SRC/linux-headers" ]; then
        local target=$(readlink "$USR_SRC/linux-headers")
        # Extraire le nom de base avec expansion de paramètre
        local target_basename="${target##*/}"
        if [ "$target_basename" = "linux-headers-$version" ]; then
            print_info "Suppression du lien $USR_SRC/linux-headers -> $target"
            rm "$USR_SRC/linux-headers"
        fi
    fi
    
    # Supprimer les répertoires/liens
    if [ -L "$src_path" ]; then
        # C'est un lien symbolique (créé par 'link')
        print_info "Suppression du lien symbolique: $src_path"
        rm "$src_path"
        print_success "Lien supprimé"
    elif [ -d "$src_path" ]; then
        # C'est un répertoire réel (créé par 'install')
        print_info "Suppression du répertoire: $src_path"
        rm -rf "$src_path"
        print_success "Répertoire supprimé"
    fi

    # Pour les headers : NE supprimer QUE si c'est un lien symbolique
    # Ne JAMAIS supprimer les vrais headers système !
    if [ -e "$headers_path" ]; then
        if [ -L "$headers_path" ]; then
            # C'est un lien symbolique, on peut le supprimer
            print_info "Suppression du lien headers: $headers_path"
            rm "$headers_path"
            print_success "Lien headers supprimé"
        else
            # C'est un répertoire réel - probablement des headers système
            print_warning "ATTENTION: $headers_path n'est pas un lien symbolique"
            print_warning "Ce sont probablement des headers système installés."
            print_warning "Ils ne seront PAS supprimés automatiquement."
            echo ""
            read -p "Voulez-vous vraiment supprimer ce répertoire ? [y/N] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                print_info "Suppression du répertoire headers: $headers_path"
                rm -rf "$headers_path"
                print_success "Répertoire headers supprimé"
            else
                print_info "Headers conservés: $headers_path"
            fi
        fi
    fi

    print_success "Suppression terminée!"
}

# Fonction pour créer un lien symbolique
link_sources() {
    local base_version="$1"
    local full_version="$2"  # Version complète avec suffixe
    
    if [ -z "$base_version" ]; then
        print_error "Version non spécifiée"
        echo "Usage: $0 link <base-version> [full-version-with-suffix]"
        echo "Exemples:"
        echo "  $0 link 6.16.9                    # Sans suffixe"
        echo "  $0 link 6.16.9 6.16.9-kernelcustom # Avec suffixe"
        exit 1
    fi
    
    # Si pas de version complète fournie, utiliser la base
    if [ -z "$full_version" ]; then
        full_version="$base_version"
    fi
    
    # Chercher les sources (basées sur la version de base)
    local src_path=""
    
    if [ -d "$SOURCES_DIR/linux-$base_version" ]; then
        src_path="$SOURCES_DIR/linux-$base_version"
    else
        src_path=$(find "$SOURCES_DIR" -maxdepth 1 -type d -name "linux-$base_version*" | head -n1)
    fi
    
    if [ -z "$src_path" ] || [ ! -d "$src_path" ]; then
        print_error "Sources introuvables pour: $base_version"
        echo "Sources disponibles:"
        ls -d "$SOURCES_DIR"/linux-* 2>/dev/null | xargs -n1 basename || echo "Aucune"
        exit 1
    fi
    
    # Le nom cible dans /usr/src avec la version complète (incluant suffixe)
    local target_name="linux-$full_version"
    
    print_info "Création de liens symboliques:"
    print_info "  Source: $src_path"
    print_info "  Cible:  $USR_SRC/$target_name"
    
    # Vérifier les droits root
    if [ "$EUID" -ne 0 ]; then
        print_warning "Ce script nécessite les droits root"
        exec sudo "$0" link "$base_version" "$full_version"
        exit $?
    fi
    
    # Créer le lien pour les sources avec le nom complet
    print_info "Création du lien $target_name..."
    if [ -e "$USR_SRC/$target_name" ]; then
        if [ -L "$USR_SRC/$target_name" ]; then
            print_warning "Le lien existe déjà, remplacement..."
            rm "$USR_SRC/$target_name"
        else
            print_error "$USR_SRC/$target_name existe et n'est pas un lien"
            exit 1
        fi
    fi
    
    ln -sf "$src_path" "$USR_SRC/$target_name"
    print_success "Lien créé: $USR_SRC/$target_name -> $src_path"
    
    # Créer le lien symbolique linux principal
    print_info "Mise à jour du lien principal /usr/src/linux..."
    if [ -L "$USR_SRC/linux" ]; then
        rm "$USR_SRC/linux"
    fi
    ln -sf "$src_path" "$USR_SRC/linux"
    print_success "Lien créé: $USR_SRC/linux -> $src_path"
    
    # Chercher les headers avec la version complète
    local headers_src=""
    local headers_found=false
    
    # 1. D'abord vérifier si déjà présent dans /usr/src/ (répertoire ou lien)
    if [ -e "$USR_SRC/linux-headers-$full_version" ]; then
        if [ -L "$USR_SRC/linux-headers-$full_version" ]; then
            print_success "Lien headers déjà présent: $USR_SRC/linux-headers-$full_version -> $(readlink "$USR_SRC/linux-headers-$full_version")"
        else
            print_success "Headers déjà présents dans: $USR_SRC/linux-headers-$full_version"
        fi
        headers_found=true
        headers_src="$USR_SRC/linux-headers-$full_version"
    # 2. Chercher dans sources/
    elif [ -d "$SOURCES_DIR/linux-headers-$full_version" ]; then
        headers_src="$SOURCES_DIR/linux-headers-$full_version"
    # 3. Chercher dans le parent des sources
    else
        headers_src=$(find "$(dirname "$src_path")" -maxdepth 1 -type d -name "linux-headers-$full_version" | head -n1)
    fi
    
    # Créer le lien uniquement si headers trouvés ailleurs que dans /usr/src
    if [ "$headers_found" = false ] && [ -n "$headers_src" ] && [ -d "$headers_src" ]; then
        local headers_name="linux-headers-$full_version"
        print_info "Création du lien pour les headers: $headers_name"
        
        if [ -e "$USR_SRC/$headers_name" ]; then
            if [ -L "$USR_SRC/$headers_name" ]; then
                rm "$USR_SRC/$headers_name"
            fi
        fi
        
        ln -sf "$headers_src" "$USR_SRC/$headers_name"
        print_success "Lien créé: $USR_SRC/$headers_name -> $headers_src"
        headers_found=true
    fi
    
    # Créer/mettre à jour le lien principal linux-headers si headers trouvés
    if [ "$headers_found" = true ]; then
        if [ -L "$USR_SRC/linux-headers" ]; then
            rm "$USR_SRC/linux-headers"
        fi
        ln -sf "$headers_src" "$USR_SRC/linux-headers"
        print_success "Lien créé: $USR_SRC/linux-headers -> $headers_src"
    else
        print_warning "Headers non trouvés pour: linux-headers-$full_version"
        print_info "Cherché dans:"
        print_info "  - $USR_SRC/linux-headers-$full_version"
        print_info "  - $SOURCES_DIR/linux-headers-$full_version"
        print_info "  - $(dirname "$src_path")/linux-headers-$full_version"
    fi
    
    print_success "Liens symboliques créés avec succès !"
    echo ""
    echo "Résultat dans /usr/src/ :"
    ls -la "$USR_SRC/linux" "$USR_SRC/$target_name" 2>/dev/null || true
    [ -e "$USR_SRC/linux-headers-$full_version" ] && ls -la "$USR_SRC/linux-headers-$full_version"
    [ -L "$USR_SRC/linux-headers" ] && ls -la "$USR_SRC/linux-headers"
    echo ""
    echo "✓ DKMS pourra compiler les modules pour: $full_version"
}

# Fonction pour supprimer les liens symboliques (créés par link_sources)
unlink_sources() {
    local version="$1"

    if [ -z "$version" ]; then
        print_error "Version non spécifiée"
        echo "Usage: $0 unlink <version>"
        echo "Exemple: $0 unlink 6.16.9-kernelcustom"
        exit 1
    fi

    # Vérifier les droits root
    if [ "$EUID" -ne 0 ]; then
        print_warning "Ce script nécessite les droits root"
        exec sudo "$0" unlink "$version"
        exit $?
    fi

    local src_link="$USR_SRC/linux-$version"
    local headers_link="$USR_SRC/linux-headers-$version"
    local found_something=false

    print_info "Suppression des liens symboliques pour: $version"
    echo ""

    # Sauvegarder la cible du lien versionné avant de le supprimer
    local src_link_target=""
    if [ -L "$src_link" ]; then
        src_link_target=$(readlink "$src_link")
    fi

    # Vérifier et supprimer le lien des sources
    if [ -e "$src_link" ]; then
        if [ -L "$src_link" ]; then
            print_info "Suppression du lien: $src_link -> $src_link_target"
            rm "$src_link"
            print_success "Lien supprimé: $src_link"
            found_something=true
        else
            print_error "$src_link existe mais n'est PAS un lien symbolique !"
            print_error "C'est un répertoire réel. Utilisez 'remove' pour le supprimer."
            exit 1
        fi
    fi

    # Vérifier et supprimer le lien des headers SEULEMENT si c'est un lien
    if [ -e "$headers_link" ]; then
        if [ -L "$headers_link" ]; then
            print_info "Suppression du lien headers: $headers_link -> $(readlink "$headers_link")"
            rm "$headers_link"
            print_success "Lien supprimé: $headers_link"
            found_something=true
        else
            print_warning "$headers_link existe mais n'est PAS un lien symbolique"
            print_warning "Ce sont probablement des headers système. Ils ne seront PAS supprimés."
        fi
    fi

    # Supprimer les liens principaux s'ils pointent vers cette version
    if [ -L "$USR_SRC/linux" ]; then
        local target=$(readlink "$USR_SRC/linux")
        # Extraire le nom de base avec expansion de paramètre (plus robuste que basename)
        local target_basename="${target##*/}"

        # Supprimer si le nom correspond OU si le lien pointe vers le même endroit
        if [ "$target_basename" = "linux-$version" ] || [ "$target" = "$src_link_target" ]; then
            print_info "Suppression du lien principal: $USR_SRC/linux -> $target"
            rm "$USR_SRC/linux"
            print_success "Lien principal supprimé"
            found_something=true
        fi
    fi

    if [ -L "$USR_SRC/linux-headers" ]; then
        local target=$(readlink "$USR_SRC/linux-headers")
        # Extraire le nom de base avec expansion de paramètre
        local target_basename="${target##*/}"

        if [ "$target_basename" = "linux-headers-$version" ]; then
            print_info "Suppression du lien principal: $USR_SRC/linux-headers -> $target"
            rm "$USR_SRC/linux-headers"
            print_success "Lien principal headers supprimé"
        fi
    fi

    if [ "$found_something" = true ]; then
        print_success "Suppression des liens terminée !"
    else
        print_warning "Aucun lien trouvé pour la version: $version"
    fi
}

# Fonction pour lister les sources
list_sources() {
    echo "=== Sources dans KernelCustom Manager ==="
    if [ -d "$SOURCES_DIR" ]; then
        ls -d $SOURCES_DIR/linux-[0-9]* 2>/dev/null | xargs -n1 basename || echo "Aucune"
    else
        echo "Aucune"
    fi
    
    echo ""
    echo "=== Sources dans /usr/src/ ==="
    ls -d $USR_SRC/linux-[0-9]* 2>/dev/null | xargs -n1 basename || echo "Aucune"
    
    echo ""
    echo "=== Liens symboliques ==="
    if [ -L "$USR_SRC/linux" ]; then
        echo "linux -> $(readlink $USR_SRC/linux)"
    else
        echo "linux -> (non défini)"
    fi
    
    if [ -L "$USR_SRC/linux-headers" ]; then
        echo "linux-headers -> $(readlink $USR_SRC/linux-headers)"
    else
        echo "linux-headers -> (non défini)"
    fi
}

# Fonction d'aide
show_help() {
    cat << EOF
Usage: $0 [COMMANDE] [OPTIONS]

Commandes:
  install <version>             Copier les sources dans /usr/src/
  link <version> [full-version] Créer des liens symboliques dans /usr/src/ (recommandé)
  unlink <version>              Supprimer uniquement les liens symboliques
  remove <version>              Supprimer les sources/liens de /usr/src/
  list                          Lister toutes les sources disponibles
  help                          Afficher cette aide

Exemples:
  $0 link 6.16.9 6.16.9-kernelcustom # Crée des liens avec suffixe (RECOMMANDÉ)
  $0 link 6.11.6                     # Crée des liens sans suffixe
  $0 unlink 6.16.9-kernelcustom      # Supprime les liens UNIQUEMENT
  $0 install 6.11.6                  # Copie complète des sources
  $0 remove 6.11.6                   # Supprime sources ET headers (prudent)
  $0 list                            # Liste toutes les versions

Différences importantes:
  link    : Crée des liens symboliques (économise l'espace, RECOMMANDÉ)
            → /usr/src/linux -> ~/KernelCustomManager/build/sources/VERSION
  unlink  : Supprime UNIQUEMENT les liens symboliques créés par 'link'
            → Ne touche JAMAIS aux vrais headers système
  install : Copie complète des sources (prend de l'espace)
  remove  : Supprime les sources. Protège les vrais headers système.

EOF
}

# Programme principal
case "${1:-}" in
    install)
        install_sources "$2"
        ;;
    link)
        link_sources "$2" "$3"
        ;;
    unlink)
        unlink_sources "$2"
        ;;
    remove)
        remove_sources "$2"
        ;;
    list)
        list_sources
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Commande invalide ou manquante"
        echo ""
        show_help
        exit 1
        ;;
esac