#!/bin/bash
# Script de gestion des sources kernel dans /usr/src/
# Usage: ./manage_kernel_sources.sh [install|remove] [version]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
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
    
    # Supprimer les liens symboliques si ils pointent vers cette version
    if [ -L "$USR_SRC/linux" ]; then
        local target=$(readlink "$USR_SRC/linux")
        if [ "$target" = "linux-$version" ]; then
            print_info "Suppression du lien $USR_SRC/linux"
            rm "$USR_SRC/linux"
        fi
    fi
    
    if [ -L "$USR_SRC/linux-headers" ]; then
        local target=$(readlink "$USR_SRC/linux-headers")
        if [ "$target" = "linux-headers-$version" ]; then
            print_info "Suppression du lien $USR_SRC/linux-headers"
            rm "$USR_SRC/linux-headers"
        fi
    fi
    
    # Supprimer les répertoires
    print_info "Suppression de $src_path"
    rm -rf "$src_path"
    
    if [ -d "$headers_path" ]; then
        print_info "Suppression de $headers_path"
        rm -rf "$headers_path"
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
    ln -sf "$target_name" "$USR_SRC/linux"
    print_success "Lien créé: $USR_SRC/linux -> $target_name"
    
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
        ln -sf "linux-headers-$full_version" "$USR_SRC/linux-headers"
        print_success "Lien créé: $USR_SRC/linux-headers -> linux-headers-$full_version"
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
  install <version>   Copier les sources dans /usr/src/
  link <version>      Créer des liens symboliques dans /usr/src/ (économise l'espace)
  remove <version>    Supprimer les sources/liens de /usr/src/
  list               Lister toutes les sources disponibles
  help               Afficher cette aide

Exemples:
  $0 install 6.11.6                  # Copie les sources
  $0 link 6.11.6                     # Crée juste des liens (recommandé)
  $0 link 6.16.9 6.16.9-kernelcustom # Crée des liens avec suffixe (recommandé)
  $0 remove 6.11.6
  $0 list

Différences:
  install : Copie complète des sources (prend de l'espace)
  link    : Lien symbolique (économise l'espace, recommandé)

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