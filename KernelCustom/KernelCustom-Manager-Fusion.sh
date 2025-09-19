#!/usr/bin/env bash
set -Eeuo pipefail

# --- Couleurs ---
RED="\e[31m"; GREEN="\e[32m"; YELLOW="\e[33m"; BLUE="\e[34m"; BOLD="\e[1m"; RESET="\e[0m"

# Définition du répertoire de base - toujours relatif à l'emplacement du script
SCRIPT_PATH=$(readlink -f "${BASH_SOURCE[0]}")
BASE_DIR="$(dirname "$SCRIPT_PATH")"

# Tous les dossiers sont relatifs au répertoire où se trouve le script
REPO_DIR="${BASE_DIR}/kernels_repo"
LOG_DIR="${BASE_DIR}/logs"
ARCHIVE_DIR="${BASE_DIR}/archive"
SRC_BASE="${BASE_DIR}/sources"
TEMPLATE_DIR="${BASE_DIR}/templates"

# Répertoire des sources du noyau (utilisé par les fonctions build)
SRC_DIR="${SRC_BASE}/linux"

# Création des répertoires si absents
mkdir -p "${REPO_DIR}" "${LOG_DIR}" "${ARCHIVE_DIR}" "${SRC_BASE}" "${TEMPLATE_DIR}" "${SRC_DIR}" || {
    echo "Erreur : impossible de créer un ou plusieurs répertoires."
    exit 1
}

echo "Répertoire de travail : ${BASE_DIR}"

TS="$(date +"%Y%m%d-%H%M%S")"
LOG_FILE="${LOG_DIR}/kernelcustom-${TS}.log"

# Mode DRYRUN par défaut désactivé
DRYRUN=${DRYRUN:-0}

# --- Fonctions utilitaires ---
log()   { echo -e "[$(date +'%F %T')] $*"        | tee -a "${LOG_FILE}"; }
info()  { echo -e "${BLUE}${BOLD}[*]${RESET} $*" | tee -a "${LOG_FILE}"; }
ok()    { echo -e "${GREEN}${BOLD}[OK]${RESET} $*"| tee -a "${LOG_FILE}"; }
warn()  { echo -e "${YELLOW}${BOLD}[!]${RESET} $*"| tee -a "${LOG_FILE}"; }
err()   { echo -e "${RED}${BOLD}[X]${RESET} $*"   | tee -a "${LOG_FILE}" >&2; }

# --- Gestion des erreurs avec trap personnalisé ---
error_occurred=0
error_function=""

custom_error_handler() {
  error_occurred=1
  error_function="$1"
  err "Erreur dans la fonction: $error_function"
  err "Voir le log: ${LOG_FILE}"
}

# Trap ERR désactivé par défaut - activation sélective
# trap 'custom_error_handler "${FUNCNAME[0]:-main}"' ERR

# --- Mode DRYRUN ---
run_cmd() {
  if [[ "${DRYRUN:-0}" -eq 1 ]]; then
    printf '[DRYRUN] %q ' "$@"; echo
  else
    "$@"
  fi
}

# --- Effets visuels ---
box() {
  local msg="$1"
  local len=${#msg}
  printf "%b" "${BLUE}${BOLD}"
  printf '=%.0s' $(seq 1 $((len+4))); echo
  echo "= ${msg} ="
  printf '=%.0s' $(seq 1 $((len+4))); echo
  printf "%b\n" "${RESET}"
}

# --- Pré-check dépendances ---
pre_checks() {
  # Activer trap pour cette fonction critique
  trap 'custom_error_handler "pre_checks"' ERR

  info "Vérification des dépendances..."
  local hard=(gcc make fakeroot bc flex bison curl tar xz)
  local soft=(libncurses-dev libssl-dev libelf-dev dpkg-dev build-essential)
  local missing=()

  for c in "${hard[@]}"; do
    command -v "$c" >/dev/null 2>&1 || missing+=("$c")
  done

  if command -v apt >/dev/null 2>&1; then
    for p in "${soft[@]}"; do
      dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p")
    done
  fi

  if (( ${#missing[@]} > 0 )); then
    err "Dépendances manquantes: ${missing[*]}"
    warn "Installe-les puis relance."
    read -rp "Entrée pour revenir..." _
    trap - ERR  # Désactiver trap
    return 1
  fi

  # jq est conseillé mais pas bloquant
  if ! command -v jq >/dev/null 2>&1; then
    warn "jq non installé: fallback grep/cut utilisé pour releases.json"
  fi

  trap - ERR  # Désactiver trap avant de sortir
  ok "Dépendances OK"
}

detect_jobs() {
  local default_jobs
  default_jobs="$(nproc)"
  echo
  info "Détection : ${default_jobs} cœurs logiques disponibles."
  read -rp "Nombre de jobs pour make [Entrée = ${default_jobs}] : " user_jobs

  if [[ -n "$user_jobs" && "$user_jobs" =~ ^[0-9]+$ && "$user_jobs" -gt 0 ]]; then
    JOBS="$user_jobs"
  else
    JOBS="$default_jobs"
  fi

  ok "Compilation configurée avec : make -j${JOBS}"
}

# --- Hook sécurité ---
pre_kernel_action() {
  local action="$1"
  info "Préparation sécurité avant ${action}..."

  if command -v vzdump >/dev/null 2>&1; then
    run_cmd vzdump "<VMID>" --dumpdir /backup --mode snapshot
  elif command -v zfs >/dev/null 2>&1; then
    run_cmd zfs snapshot rpool/ROOT@pre-kernel-$(date +%F-%H%M)
  elif command -v btrfs >/dev/null 2>&1; then
    run_cmd btrfs subvolume snapshot / /.snapshots/pre-kernel-$(date +%F-%H%M)
  else
    local backup_file="${ARCHIVE_DIR}/pre-kernel-backup-$(date +%F-%H%M).tar.gz"
    info "Création d'une sauvegarde tar dans ${backup_file}"

    # Créer le répertoire archive s'il n'existe pas
    mkdir -p "${ARCHIVE_DIR}"

    # Utiliser des chemins relatifs et exclure les liens symboliques problématiques
    run_cmd tar --exclude='lost+found' --exclude='*.tmp' --exclude='*.temp' \
        -czf "${backup_file}" \
        -C / \
        --exclude='boot/lost+found' \
        boot/config-* boot/System.map-* boot/vmlinuz-* boot/initrd.img-* boot/grub/grub.cfg \
        lib/modules 2>/dev/null || {
      warn "Sauvegarde tar partielle - certains fichiers ignorés"
      # Essayer une sauvegarde minimale des configs seulement
      run_cmd tar -czf "${backup_file}" -C / boot/config-* boot/System.map-* 2>/dev/null || {
        warn "Impossible de créer la sauvegarde - continuons sans backup"
        return 0
      }
    }

    if [[ -f "${backup_file}" ]]; then
      local backup_size=$(du -h "${backup_file}" | cut -f1)
      ok "Sauvegarde créée : ${backup_file} (${backup_size})"
    else
      warn "Fichier de sauvegarde non créé - continuons sans backup"
    fi
  fi

  ok "Préparation sécurité terminée"
}

# =========================
# 1. Gestion des kernels installés
# =========================
list_installed_kernels() {
  info "Kernels installés"
  local current; current="$(uname -r)"
  dpkg -l | awk '/linux-image-[0-9]/{print $2"\t"$3}' | while IFS=$'\t' read -r pkg ver; do
    local mark=" "
    [[ "${current}" == *"${pkg#linux-image-}"* ]] && mark="*"
    printf "%s  %-45s %-20s\n" "${mark}" "${pkg}" "${ver}" | tee -a "${LOG_FILE}"
  done
}

remove_installed_kernel() {
  list_installed_kernels
  echo -ne "${BOLD}Nom exact du paquet: ${RESET}"; read -r pkg
  local current; current="$(uname -r)"

  if [[ "${current}" == *"${pkg#linux-image-}"* ]]; then
    warn "Impossible: kernel actif"
    read -rp "Entrée pour revenir..." _
    return 0
  fi

  # Extraire la version du kernel pour chercher les headers correspondants
  local kernel_version="${pkg#linux-image-}"
  local headers_pkg="linux-headers-${kernel_version}"

  # Vérifier si les headers correspondants sont installés
  local packages_to_remove=("$pkg")
  if dpkg -l | grep -q "^ii.*${headers_pkg}[[:space:]]"; then
    ok "Headers correspondants trouvés: ${headers_pkg}"
    echo -ne "${YELLOW}Supprimer aussi les headers correspondants ? (O/n): ${RESET}"
    read -r remove_headers
    case "${remove_headers,,}" in
      n|non|no)
        warn "Suppression du kernel seul (headers conservés)"
        ;;
      *)
        packages_to_remove+=("$headers_pkg")
        ok "Suppression du kernel + headers"
        ;;
    esac
  else
    info "Aucun headers correspondant installé"
  fi

  # Affichage récapitulatif
  echo
  info "Paquets à supprimer :"
  for pkg_remove in "${packages_to_remove[@]}"; do
    echo "  - $pkg_remove"
  done
  echo

  pre_kernel_action "suppression"
  echo -ne "${YELLOW}Confirmer suppression (oui/non): ${RESET}"; read -r ans
  [[ "$ans" == "oui" ]] || { warn "Annulé"; read -rp "Entrée..." _; return; }

  # Suppression des paquets
  for pkg_remove in "${packages_to_remove[@]}"; do
    info "Suppression de ${pkg_remove}..."
    run_cmd sudo apt remove -y "${pkg_remove}"
  done

  run_cmd sudo apt autoremove -y
  ok "Suppression effectuée"
  if [[ ${#packages_to_remove[@]} -gt 1 ]]; then
    info "Paquets supprimés: ${#packages_to_remove[@]} (image + headers)"
  else
    info "Paquet supprimé: kernel image uniquement"
  fi

  read -rp "Entrée pour revenir..." _
}

kernels_menu() {
  while true; do
    clear
    box "Gestion des kernels installés"
    echo "1) Lister"
    echo "2) Supprimer"
    echo "0) Retour"
    read -r ch
    case "$ch" in
      1) list_installed_kernels; read -rp "Entrée..." _ ;;
      2) remove_installed_kernel ;;
      0) break ;;
      *) warn "Choix invalide"; read -rp "Entrée..." _ ;;
    esac
  done
}

# =========================
# 2. Gestion des paquets locaux
# =========================
list_local_packages() {
  info "Paquets locaux (${REPO_DIR})"
  shopt -s nullglob
  local files=( "${REPO_DIR}"/linux-image-*.deb )
  if (( ${#files[@]} == 0 )); then
    warn "Aucun paquet trouvé dans ${REPO_DIR}"
    return 0
  fi
  local i=1
  for f in "${files[@]}"; do
    printf "%2d) %s\n" "${i}" "$(basename "$f")" | tee -a "${LOG_FILE}"
    ((i++))
  done
}

install_kernel_package() {
  if ! list_local_packages; then
    read -rp "Entrée..." _
    return 0
  fi

  shopt -s nullglob
  local files=( "${REPO_DIR}"/linux-image-*.deb )
  if (( ${#files[@]} == 0 )); then
    warn "Aucun paquet disponible pour installation"
    read -rp "Entrée..." _
    return 0
  fi

  echo -ne "${BOLD}Sélection: ${RESET}"; read -r sel
  local idx=$((sel-1))
  [[ $idx -ge 0 && $idx -lt ${#files[@]} ]] || { warn "Sélection invalide"; read -rp "Entrée..." _; return 0; }

  local selected_image="${files[$idx]}"
  local image_name=$(basename "$selected_image" .deb)

  # Extraire la version du paquet image pour chercher le headers correspondant
  # Format attendu: linux-image-VERSION_BUILD_ARCH.deb
  if [[ "$image_name" =~ ^linux-image-(.+)_(.+)_(.+)$ ]]; then
    local version_part="${BASH_REMATCH[1]}"
    local build_part="${BASH_REMATCH[2]}"
    local arch_part="${BASH_REMATCH[3]}"

    # Chercher le paquet headers correspondant
    local headers_pattern="linux-headers-${version_part}_${build_part}_${arch_part}.deb"
    local headers_file="${REPO_DIR}/${headers_pattern}"

    info "Image sélectionnée: $(basename "$selected_image")"

    if [[ -f "$headers_file" ]]; then
      ok "Headers correspondants trouvés: $(basename "$headers_file")"
      echo -ne "${YELLOW}Installer aussi les headers correspondants ? (o/N): ${RESET}"
      read -r install_headers
      case "${install_headers,,}" in
        o|oui|y|yes)
          local packages_to_install=("$selected_image" "$headers_file")
          ;;
        *)
          local packages_to_install=("$selected_image")
          warn "Installation du kernel seul (headers ignorés)"
          ;;
      esac
    else
      warn "Aucun headers correspondant trouvé pour cette version"
      local packages_to_install=("$selected_image")
    fi
  else
    warn "Format de nom de paquet non reconnu, installation du kernel seul"
    local packages_to_install=("$selected_image")
  fi

  pre_kernel_action "installation"

  # Installation des paquets sélectionnés
  for package in "${packages_to_install[@]}"; do
    info "Installation de $(basename "$package")..."
    run_cmd sudo dpkg -i "$package"
  done

  info "Résolution des dépendances..."
  run_cmd sudo apt -f install -y

  ok "Installation terminée"
  if [[ ${#packages_to_install[@]} -gt 1 ]]; then
    info "Paquets installés: ${#packages_to_install[@]} (image + headers)"
  else
    info "Paquet installé: kernel image uniquement"
  fi

  read -rp "Entrée pour revenir..." _
}

packages_menu() {
  while true; do
    clear
    box "Gestion des paquets locaux"
    echo "1) Lister"
    echo "2) Installer"
    echo "0) Retour"
    read -r ch
    case "$ch" in
      1) list_local_packages; read -rp "Entrée..." _ ;;
      2) install_kernel_package ;;
      0) break ;;
      *) warn "Choix invalide"; read -rp "Entrée..." _ ;;
    esac
  done
}

# =========================
# 3. Compiler & packager
# =========================

choose_kernel_version() {
  pre_checks || return 1
  box "Téléchargement du kernel stable"
  info "Récupération de la version stable depuis kernel.org..."

  local latest=""
  if command -v jq >/dev/null 2>&1; then
    latest=$(curl -s https://www.kernel.org/releases.json \
      | jq -r '.releases[] | select(.moniker=="stable") | .version' \
      | head -n1)
  else
    latest=$(curl -s https://www.kernel.org/releases.json \
      | grep -Eo '"version"\s*:\s*"[0-9]+\.[0-9]+(\.[0-9]+)?"' \
      | head -n1 | cut -d'"' -f4)
  fi

  echo "[DEBUG] Version détectée: '${latest}'"
  if [[ -z "$latest" || "$latest" == "null" ]]; then
    warn "Impossible de détecter automatiquement la version stable."
    read -rp "Saisis une version (ex: 6.11.6) ou laisse vide pour annuler: " latest
    if [[ -z "$latest" ]]; then
      warn "Annulé."
      read -rp "Entrée pour revenir..." _
      return 1
    fi
  fi

  local major="${latest%%.*}"
  local archive="linux-${latest}.tar.xz"
  local url="https://cdn.kernel.org/pub/linux/kernel/v${major}.x/${archive}"
  local version_src_dir="${SRC_BASE}/linux-${latest}"

  if [[ ! -d "$version_src_dir" ]]; then
    info "Téléchargement: ${url}"
    run_cmd curl -fL -o "${SRC_BASE}/${archive}" "${url}"

    info "Extraction..."
    run_cmd tar -xf "${SRC_BASE}/${archive}" -C "${SRC_BASE}"

    info "Nettoyage..."
    run_cmd rm -f "${SRC_BASE}/${archive}"
  else
    warn "Sources déjà présentes: ${version_src_dir}"
  fi

  # Création/mise à jour du lien symbolique
  rm -f "${BASE_DIR}/linux"
  ln -sf "$version_src_dir" "${BASE_DIR}/linux"
  ok "Sources prêtes (${version_src_dir})"
  read -rp "Entrée pour revenir..." _
}

choose_config_template() {
  if [[ ! -d "${BASE_DIR}/linux" ]]; then
    warn "Pas de sources kernel. Lance d'abord 'Télécharger le kernel stable'."
    read -rp "Entrée pour revenir..." _
    return 1
  fi

  box "Choisir la configuration du noyau"

  echo "1) Sélectionner un template KernelCustom"
  echo "2) Partir de la configuration système actuelle"
  echo "3) Charger une configuration sauvegardée"
  echo "4) Annuler"
  echo
  read -rp "Votre choix : " choice

  case "$choice" in
    1)
      mapfile -t templates < <(find "${TEMPLATE_DIR}" -maxdepth 1 -type f \( -name "*.config" -o -name "*.conf" \) | sort)

      if [[ ${#templates[@]} -eq 0 ]]; then
        warn "Aucun template trouvé dans ${TEMPLATE_DIR}"
        local running_kernel
        running_kernel=$(uname -r)
        local debian_config="/boot/config-${running_kernel}"
        if [[ -f "$debian_config" ]]; then
          info "Création d'un template par défaut depuis la config Debian actuelle (${running_kernel})"
          cp "$debian_config" "${TEMPLATE_DIR}/kernelcustom-default.config"
          templates=("${TEMPLATE_DIR}/kernelcustom-default.config")
        else
          err "Impossible de créer un template : config Debian introuvable"
          read -rp "Entrée pour revenir..." _
          return 1
        fi
      fi

      echo "Templates disponibles :"
      for i in "${!templates[@]}"; do
        printf "%2d) %s\n" $((i+1)) "$(basename "${templates[$i]}")"
      done

      read -rp "Sélectionnez un template : " idx
      if ! [[ "$idx" =~ ^[0-9]+$ ]] || (( idx < 1 || idx > ${#templates[@]} )); then
        err "Choix invalide."
        read -rp "Entrée pour revenir..." _
        return 1
      fi

      local template_path="${templates[$((idx-1))]}"
      info "Copie du template sélectionné : $(basename "$template_path")"
      run_cmd cp "$template_path" "${BASE_DIR}/linux/.config"
      (cd "${BASE_DIR}/linux" && run_cmd make olddefconfig)
      if [[ "${DRYRUN:-0}" -eq 0 ]]; then
        (cd "${BASE_DIR}/linux" && make menuconfig)
      else
        info "[DRYRUN] make menuconfig ignoré"
      fi
      ;;
    2)
      local running_kernel
      running_kernel=$(uname -r)
      local current_config="/boot/config-${running_kernel}"

      if [[ ! -f "$current_config" ]]; then
        err "Fichier de configuration introuvable : $current_config"
        read -rp "Entrée pour revenir..." _
        return 1
      fi

      info "Copie de la configuration système actuelle (${running_kernel})"
      run_cmd cp "$current_config" "${BASE_DIR}/linux/.config"

      # Correction spécifique Ubuntu : désactiver les certificats Canonical
      if grep -qi ubuntu /etc/os-release; then
        info "Système Ubuntu détecté - adaptation de la configuration"
        sed -i 's/CONFIG_SYSTEM_TRUSTED_KEYS=.*/CONFIG_SYSTEM_TRUSTED_KEYS=""/' "${BASE_DIR}/linux/.config"
        sed -i 's/CONFIG_SYSTEM_REVOCATION_KEYS=.*/CONFIG_SYSTEM_REVOCATION_KEYS=""/' "${BASE_DIR}/linux/.config"
        warn "Certificats Canonical désactivés pour compatibilité avec sources kernel.org"
      fi

      info "Adaptation de la configuration à la nouvelle version"
      (cd "${BASE_DIR}/linux" && run_cmd make olddefconfig)

      info "Ouverture de menuconfig pour personnalisation"
      if [[ "${DRYRUN:-0}" -eq 0 ]]; then
        (cd "${BASE_DIR}/linux" && make menuconfig)
      else
        info "[DRYRUN] make menuconfig ignoré"
      fi
      ;;

    3)
      read -rp "Chemin vers votre fichier .config ou .conf sauvegardé : " saved_config
      if [[ ! -f "$saved_config" ]]; then
        err "Fichier introuvable : $saved_config"
        read -rp "Entrée pour revenir..." _
        return 1
      fi
      run_cmd cp "$saved_config" "${BASE_DIR}/linux/.config"
      (cd "${BASE_DIR}/linux" && run_cmd make olddefconfig)
      if [[ "${DRYRUN:-0}" -eq 0 ]]; then
        (cd "${BASE_DIR}/linux" && make menuconfig)
      else
        info "[DRYRUN] make menuconfig ignoré"
      fi
      ;;
    4)
      warn "Annulé."
      return 1
      ;;
    *)
      warn "Choix invalide."
      return 1
      ;;
  esac

  ok "Configuration terminée"
  read -rp "Entrée pour revenir..." _
}

launch_build() {
  # Désactiver set -e pour éviter les sorties prématurées
  set +e

  if [[ ! -d "${BASE_DIR}/linux" ]]; then
    warn "Le dossier ${BASE_DIR}/linux n'existe pas. Lance d'abord 'Téléchargement du kernel stable'."
    read -rp "Entrée pour revenir..." _
    return 0
  fi

  if [[ ! -f "${BASE_DIR}/linux/.config" ]]; then
    warn "Aucune configuration trouvée. Lance d'abord 'Choisir template config'."
    read -rp "Entrée pour revenir..." _
    return 0
  fi

  pre_checks || return 1
  detect_jobs

  # Demande du suffixe et méthode de compilation
  echo -ne "${BOLD}Entrez un suffixe pour les paquets (ex: -lab, -custom, vide pour aucun) : ${RESET}"
  read -r suffix

  echo -ne "${BOLD}Méthode de compilation [1=bindeb-pkg, 2=deb-pkg] (Entrée=1) : ${RESET}"
  read -r build_method
  [[ -z "$build_method" ]] && build_method="1"

  # Si un suffixe est donné, on l'utilisera directement dans LOCALVERSION
  local make_suffix=""
  if [[ -n "$suffix" ]]; then
    make_suffix="$suffix"
    suffix=""  # On vide suffix pour éviter le double renommage
  fi

  local start_time=$(date +%s)

  info "Compilation et packaging"

  # Détection de fakeroot / fakeroot-tcp
  # Détection de fakeroot / fakeroot-tcp et choix performance
 echo -ne "${BOLD}Utiliser fakeroot ? (compatibilité max mais plus lent) (o/N): ${RESET}"
 read -r use_fakeroot

 if [[ "${use_fakeroot,,}" =~ ^(o|oui|y|yes)$ ]]; then
  local fakeroot_cmd="fakeroot"
  if fakeroot --version 2>/dev/null | grep -qiE "unknown|bug"; then
    warn "Version de fakeroot potentiellement instable détectée — tentative avec fakeroot-tcp"
    if command -v fakeroot-tcp >/dev/null 2>&1; then
      fakeroot_cmd="fakeroot-tcp"
    else
      warn "fakeroot-tcp non trouvé — utilisation de fakeroot standard"
    fi
  fi
  
  info "Mode compatibilité activé (avec fakeroot)"
 else
  local fakeroot_cmd=""
  warn "Mode performance activé (sans fakeroot) - temps de compilation optimisé"
  info "Note: Vérifiez les permissions des paquets générés si nécessaire"
fi


  if [[ "${DRYRUN:-0}" -eq 1 ]]; then
    box "[DRYRUN] Simulation de compilation et création de faux paquets"
    mkdir -p "${REPO_DIR}"
    touch "${REPO_DIR}/linux-image-6.16.7${suffix}_amd64.deb"
    touch "${REPO_DIR}/linux-headers-6.16.7${suffix}_amd64.deb"
    touch "${REPO_DIR}/linux-libc-dev_6.16.7${suffix}_amd64.deb"
    ok "[DRYRUN] Faux paquets créés dans ${REPO_DIR}"
  else
    # Mode normal : compilation réelle
    box "Compilation du noyau et création des paquets"
    pushd "${BASE_DIR}/linux" >/dev/null || {
      warn "Impossible d'entrer dans ${BASE_DIR}/linux"
      read -rp "Entrée pour revenir..." _
      return 1
    }

    if ! ${fakeroot_cmd} make -j"${JOBS}" bindeb-pkg LOCALVERSION="${make_suffix}" 2>&1 | tee -a "${LOG_FILE}"; then
      err "Compilation échouée"
      popd >/dev/null
      read -rp "Entrée pour revenir..." _
      return 1
    fi

    popd >/dev/null

    # Déplacement des paquets générés vers le répertoire repo
    info "Déplacement des paquets vers ${REPO_DIR}"
    mkdir -p "${REPO_DIR}"

    # Les paquets sont générés dans le répertoire parent de linux/ (donc parent de BASE_DIR/linux)
    # Donc ils sont dans BASE_DIR/../
    local search_dirs=("${BASE_DIR}/../" "${BASE_DIR}/" "${SRC_BASE}/" "$(pwd)/../")
    local found_packages=0

    for search_dir in "${search_dirs[@]}"; do
      if [[ -d "$search_dir" ]]; then
        info "Recherche des paquets dans ${search_dir}"

        # Chercher et déplacer les paquets
        for pattern in "linux-image-*.deb" "linux-headers-*.deb" "linux-libc-dev_*.deb"; do
          for deb_file in "${search_dir}"${pattern}; do
            if [[ -f "$deb_file" ]]; then
              info "Paquet trouvé: $(basename "$deb_file")"

              # Appliquer le suffixe AVANT de déplacer
              if [[ -n "$suffix" ]]; then
                local dir_name=$(dirname "$deb_file")
                local base_name=$(basename "$deb_file" .deb)
                local new_name

                # Gérer le cas spécial où il y a déjà une version (ex: 6.16.7_6.16.7-1_amd64)
                if [[ "$base_name" =~ ^(linux-[^_]+)_([^_]+)_([^_]+)$ ]]; then
                  # Format: linux-image_version_arch
                  local package_name="${BASH_REMATCH[1]}"
                  local version="${BASH_REMATCH[2]}"
                  local arch="${BASH_REMATCH[3]}"
                  new_name="${dir_name}/${package_name}_${version}${suffix}_${arch}.deb"
                elif [[ "$base_name" =~ ^([^_]+)_([^_]+)$ ]]; then
                  # Format simple: package_arch
                  local name_part="${BASH_REMATCH[1]}"
                  local arch_part="${BASH_REMATCH[2]}"
                  new_name="${dir_name}/${name_part}${suffix}_${arch_part}.deb"
                else
                  # Fallback
                  new_name="${dir_name}/${base_name}${suffix}.deb"
                fi

                info "Application du suffixe: $(basename "$deb_file") -> $(basename "$new_name")"
                if mv "$deb_file" "$new_name" 2>/dev/null; then
                  deb_file="$new_name"
                else
                  warn "Échec du renommage, conservation du nom original"
                fi
              fi

              # Déplacer vers le repo
              info "Déplacement vers ${REPO_DIR}: $(basename "$deb_file")"
              mv "$deb_file" "${REPO_DIR}/"
              ((found_packages++))
            fi
          done
        done

        # Si on a trouvé des paquets, on peut arrêter la recherche
        if [[ $found_packages -gt 0 ]]; then
          break
        fi
      fi
    done

    if [[ $found_packages -eq 0 ]]; then
      warn "Aucun paquet .deb trouvé dans les répertoires de recherche"
      info "Vérification manuelle possible dans :"
      for dir in "${search_dirs[@]}"; do
        [[ -d "$dir" ]] && echo "  - $dir"
      done
    else
      ok "${found_packages} paquet(s) déplacé(s) avec succès"
    fi
  fi

  local end_time=$(date +%s)
  local duration=$((end_time - start_time))

  # Résumé final
  box "Résumé du build"
  if [[ -L "${BASE_DIR}/linux" ]]; then
    local real_path=$(readlink "${BASE_DIR}/linux")
    echo "Version du kernel : $(basename "${real_path}")"
  fi
  echo "Durée de compilation : ${duration} secondes"
  echo "Paquets générés :"

  # Vérifier les paquets dans le répertoire repo
  shopt -s nullglob
  local generated_packages=("${REPO_DIR}"/linux-*.deb)
  if [[ ${#generated_packages[@]} -gt 0 ]]; then
    ls -lh "${REPO_DIR}"/linux-*.deb | tee -a "${LOG_FILE}"
    echo "Emplacement : ${REPO_DIR}"
  else
    echo "Aucun paquet trouvé dans ${REPO_DIR}" | tee -a "${LOG_FILE}"

    # Diagnostic supplémentaire
    echo
    info "Diagnostic des emplacements possibles :"
    for search_path in "${BASE_DIR}/../" "${BASE_DIR}/" "${SRC_BASE}/"; do
      if [[ -d "$search_path" ]]; then
        local found_here=$(find "$search_path" -maxdepth 1 -name "linux-*.deb" -type f 2>/dev/null | wc -l)
        echo "  - ${search_path} : ${found_here} paquet(s)"
        if [[ $found_here -gt 0 ]]; then
          find "$search_path" -maxdepth 1 -name "linux-*.deb" -type f -exec basename {} \;
        fi
      fi
    done
  fi

  echo "Log complet : ${LOG_FILE}"
  echo

  ok "Build et packaging terminés avec succès !"
  echo
  info "Appuyez sur Entrée pour revenir au menu principal..."
  read -r _

  # Réactiver set -e
  set -e
}


build_menu() {
  while true; do
    clear
    box "Compiler et packager"
    echo "1) Télécharger le kernel stable"
    echo "2) Choisir template config"
    echo "3) Lancer compilation"
    echo "0) Retour"
    read -r ch
    case "$ch" in
      1) choose_kernel_version ;;
      2) choose_config_template ;;
      3) launch_build ;;
      0) break ;;
      *) warn "Choix invalide"; read -rp "Entrée..." _ ;;
    esac
  done
}

# =========================
# 4. Installation des dépendances
# =========================
install_dependencies() {
  box "Installation automatique des dépendances"

  info "Détection du système..."

  if command -v apt >/dev/null 2>&1; then
    info "Système Debian/Ubuntu détecté"

    # Mise à jour des sources
    info "Mise à jour des sources de paquets..."
    run_cmd sudo apt update

    # Liste des paquets essentiels
    local essential_packages=(
      "build-essential"     # Outils de compilation de base
      "bc"                 # Calculateur pour les scripts de build
      "bison"              # Générateur d'analyseurs syntaxiques
      "flex"               # Générateur d'analyseurs lexicaux
      "libssl-dev"         # Headers SSL
      "libelf-dev"         # Headers ELF
      "libdw-dev"
      "libncurses-dev"     # Headers ncurses pour menuconfig
      "fakeroot"           # Simulation des privilèges root
      "dpkg-dev"           # Outils de création de paquets Debian
      "libbpf-dev"         # Support BPF moderne
      "dwarves"            # Outils de debug (contient pahole)
      "xz-utils"           # Compression/décompression xz
      "debhelper"          # Outils d'aide pour les paquets Debian
      "git"                # Pour récupérer des sources git si besoin
      "gawk"
    )

    # Paquets optionnels mais recommandés
    local optional_packages=(
      "curl"               # Téléchargement des sources
      "wget"               # Alternative à curl
      "tar"                # Extraction d'archives
      "gzip"               # Compression gzip
      "make"               # Normalement dans build-essential
      "gcc"                # Normalement dans build-essential
      "jq"                 # Parsing JSON pour l'API kernel.org
      "rsync"              # Synchronisation de fichiers
      "ccache"             # Cache de compilation (accélère les rebuilds)
    )

    info "Installation des dépendances essentielles..."
    local failed_essential=()
    for package in "${essential_packages[@]}"; do
      if ! dpkg -s "$package" >/dev/null 2>&1; then
        info "Installation de $package..."
        if ! run_cmd sudo apt install -y "$package"; then
          failed_essential+=("$package")
        fi
      else
        ok "$package déjà installé"
      fi
    done

    info "Installation des dépendances optionnelles..."
    local failed_optional=()
    for package in "${optional_packages[@]}"; do
      if ! dpkg -s "$package" >/dev/null 2>&1; then
        info "Installation de $package..."
        if ! run_cmd sudo apt install -y "$package"; then
          failed_optional+=("$package")
        fi
      fi
    done

    # Résumé de l'installation
    echo
    if [[ ${#failed_essential[@]} -eq 0 ]]; then
      ok "Toutes les dépendances essentielles sont installées"
    else
      warn "Dépendances essentielles échouées: ${failed_essential[*]}"
    fi

    if [[ ${#failed_optional[@]} -gt 0 ]]; then
      info "Dépendances optionnelles échouées: ${failed_optional[*]} (non critique)"
    fi

    # Vérification finale
    info "Vérification finale des outils critiques..."
    local critical_tools=("gcc" "make" "fakeroot" "dpkg-deb")
    local missing_critical=()
    for tool in "${critical_tools[@]}"; do
      if ! command -v "$tool" >/dev/null 2>&1; then
        missing_critical+=("$tool")
      fi
    done

    if [[ ${#missing_critical[@]} -eq 0 ]]; then
      ok "Système prêt pour la compilation de kernels !"
    else
      err "Outils critiques manquants: ${missing_critical[*]}"
      warn "Vous devrez les installer manuellement avant de compiler"
    fi

  elif command -v dnf >/dev/null 2>&1; then
    info "Système Fedora/RHEL détecté"
    warn "Support Fedora/RHEL en cours de développement"
    info "Installez manuellement: dnf groupinstall 'Development Tools'"
    info "Et: dnf install ncurses-devel openssl-devel elfutils-libelf-devel bc bison flex"

  elif command -v pacman >/dev/null 2>&1; then
    info "Système Arch Linux détecté"
    warn "Support Arch Linux en cours de développement"
    info "Installez manuellement: pacman -S base-devel bc inetutils"

  elif command -v zypper >/dev/null 2>&1; then
    info "Système openSUSE détecté"
    warn "Support openSUSE en cours de développement"

  else
    warn "Distribution non reconnue"
    info "Installez manuellement les dépendances suivantes :"
    echo "  gcc, make, bc, bison, flex, libssl-dev, libelf-dev"
    echo "  libncurses-dev, fakeroot, dpkg-dev, build-essential"
  fi

  echo
  read -rp "Appuyez sur Entrée pour revenir au menu principal..."
}



# =========================
# Menu principal
# =========================
main_menu() {
  while true; do
    clear
    box "KernelCustom-Manager Fusion"
    echo "1) Gestion des kernels installés"
    echo "2) Gestion des paquets locaux"
    echo "3) Compiler et packager"
    echo "4) Installer les dépendances"
    echo "0) Quitter"
    read -r choice
    case "$choice" in
      1) kernels_menu ;;
      2) packages_menu ;;
      3) build_menu ;;
      4) install_dependencies ;;
      0) ok "Fin du programme"; exit 0 ;;
      *) warn "Choix invalide"; read -rp "Entrée..." _ ;;
    esac
  done
}

# Lancement du menu principal
main_menu