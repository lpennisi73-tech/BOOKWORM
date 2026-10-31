#!/bin/bash
#
# Script pour re-signer tous les kernels personnalisés avec la clé MOK enrollée
#
# Usage: sudo ./resign_all_custom_kernels.sh
#

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Vérifier qu'on est root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Ce script doit être exécuté en tant que root${NC}"
    echo -e "${YELLOW}   Utilisez: sudo $0${NC}"
    exit 1
fi

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Re-signature des Kernels Custom avec Clé MOK        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Chemins
SUDO_USER_HOME=$(eval echo ~${SUDO_USER})
PRIV_KEY="${SUDO_USER_HOME}/KernelCustomManager/build/secureboot/keys/MOK.priv"
CERT="${SUDO_USER_HOME}/KernelCustomManager/build/secureboot/keys/MOK.der"

# Vérifier que les clés existent
if [ ! -f "${PRIV_KEY}" ] || [ ! -f "${CERT}" ]; then
    echo -e "${RED}❌ Erreur: Clés MOK introuvables${NC}"
    echo -e "${YELLOW}   Attendu: ${PRIV_KEY}${NC}"
    echo -e "${YELLOW}            ${CERT}${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Clés MOK trouvées${NC}"
echo -e "   Clé privée: ${PRIV_KEY}"
echo -e "   Certificat: ${CERT}"
echo ""

# Trouver sign-file
SIGN_FILE=""
for candidate in \
    "/usr/src/linux-headers-$(uname -r)/scripts/sign-file" \
    "/usr/lib/linux-kbuild-*/scripts/sign-file" \
    "/usr/src/linux-headers-*/scripts/sign-file"; do

    if [ -f "$candidate" ] 2>/dev/null; then
        SIGN_FILE="$candidate"
        break
    fi
done

# Si pas trouvé, chercher dans tous les répertoires
if [ -z "${SIGN_FILE}" ]; then
    SIGN_FILE=$(find /usr/src /usr/lib -name "sign-file" 2>/dev/null | head -1)
fi

if [ -z "${SIGN_FILE}" ] || [ ! -f "${SIGN_FILE}" ]; then
    echo -e "${RED}❌ Erreur: sign-file introuvable${NC}"
    echo -e "${YELLOW}   Installez les headers du kernel:${NC}"
    echo -e "   sudo apt install linux-headers-$(uname -r)"
    exit 1
fi

echo -e "${GREEN}✅ Outil de signature trouvé${NC}"
echo -e "   sign-file: ${SIGN_FILE}"
echo ""

# Lister les kernels custom à signer
CUSTOM_KERNELS=$(ls -d /lib/modules/6.17.10-kernelcustom* 2>/dev/null || true)

if [ -z "${CUSTOM_KERNELS}" ]; then
    echo -e "${YELLOW}⚠️  Aucun kernel custom trouvé${NC}"
    echo -e "   Recherche dans: /lib/modules/6.17.10-kernelcustom*"
    exit 0
fi

echo -e "${CYAN}Kernels custom détectés:${NC}"
echo "${CUSTOM_KERNELS}" | sed 's/^/   /'
echo ""

# Compter le total de modules
TOTAL_MODULES=0
for kernel_dir in ${CUSTOM_KERNELS}; do
    count=$(find "${kernel_dir}" -name '*.ko' 2>/dev/null | wc -l)
    TOTAL_MODULES=$((TOTAL_MODULES + count))
done

echo -e "${CYAN}Total de modules à signer: ${TOTAL_MODULES}${NC}"
echo ""

# Demander confirmation
echo -e "${YELLOW}⚠️  Cette opération va re-signer tous les modules kernel custom${NC}"
echo -e "${YELLOW}   avec votre clé MOK enrollée.${NC}"
echo ""
read -p "$(echo -e ${GREEN}Continuer ? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⏹️  Opération annulée${NC}"
    exit 0
fi
echo ""

# Fonction pour signer un module
sign_module() {
    local module="$1"
    local result=0

    # Retirer la signature existante si présente
    ${SIGN_FILE} sha256 "${PRIV_KEY}" "${CERT}" "${module}" 2>/dev/null || result=$?

    return $result
}

# Signer tous les modules de chaque kernel
SIGNED_COUNT=0
FAILED_COUNT=0

for kernel_dir in ${CUSTOM_KERNELS}; do
    kernel_name=$(basename "${kernel_dir}")
    echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Signature: ${kernel_name}${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"

    module_count=$(find "${kernel_dir}" -name '*.ko' 2>/dev/null | wc -l)
    echo -e "${CYAN}   Modules à signer: ${module_count}${NC}"

    current=0
    while IFS= read -r module; do
        current=$((current + 1))

        # Afficher progression tous les 100 modules
        if [ $((current % 100)) -eq 0 ]; then
            echo -e "   ${CYAN}Progression: ${current}/${module_count}...${NC}"
        fi

        if sign_module "${module}"; then
            SIGNED_COUNT=$((SIGNED_COUNT + 1))
        else
            echo -e "   ${RED}❌ Échec: $(basename ${module})${NC}"
            FAILED_COUNT=$((FAILED_COUNT + 1))
        fi
    done < <(find "${kernel_dir}" -name '*.ko' 2>/dev/null)

    echo -e "   ${GREEN}✅ Terminé: ${current} modules traités${NC}"
    echo ""
done

# Résumé
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  RÉSUMÉ                                                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Modules signés avec succès: ${GREEN}${SIGNED_COUNT}${NC}"
echo -e "Modules échoués:           ${RED}${FAILED_COUNT}${NC}"
echo ""

if [ ${FAILED_COUNT} -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ SIGNATURE RÉUSSIE !                               ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}PROCHAINES ÉTAPES:${NC}"
    echo -e "  1. Redémarrez votre système:"
    echo -e "     ${GREEN}sudo reboot${NC}"
    echo ""
    echo -e "  2. Au démarrage, sélectionnez un kernel custom dans GRUB"
    echo -e "     (Options avancées pour Debian GNU/Linux → 6.17.10-kernelcustom...)"
    echo ""
    echo -e "  3. Votre kernel devrait maintenant booter sans erreur !"
    echo ""
else
    echo -e "${YELLOW}⚠️  Certains modules n'ont pas pu être signés${NC}"
    echo -e "${YELLOW}   Le kernel pourrait quand même fonctionner${NC}"
    echo -e "${YELLOW}   si ces modules ne sont pas critiques.${NC}"
    echo ""
fi

# Vérifier un module pour confirmer
echo -e "${CYAN}🔍 Vérification d'un module signé...${NC}"
TEST_MODULE=$(find /lib/modules/6.17.10-kernelcustom* -name '*.ko' 2>/dev/null | head -1)
if [ -n "${TEST_MODULE}" ]; then
    SIG_INFO=$(modinfo -F sig_id "${TEST_MODULE}" 2>/dev/null || echo "")
    SIGNER=$(modinfo -F signer "${TEST_MODULE}" 2>/dev/null || echo "")

    if [ -n "${SIG_INFO}" ]; then
        echo -e "   ${GREEN}✅ Signature détectée: ${SIG_INFO}${NC}"
        echo -e "   ${GREEN}   Signataire: ${SIGNER}${NC}"
    else
        echo -e "   ${RED}❌ Aucune signature détectée${NC}"
    fi
fi

echo ""
