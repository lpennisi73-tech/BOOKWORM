#!/bin/bash
#
# Script pour signer les images vmlinuz des kernels personnalisés
#
# Usage: sudo ./sign_vmlinuz.sh
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
echo -e "${BLUE}║   Signature des Images Kernel (vmlinuz) avec sbsign   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Chemins
SUDO_USER_HOME=$(eval echo ~${SUDO_USER})
PRIV_KEY="${SUDO_USER_HOME}/KernelCustomManager/build/secureboot/keys/MOK.priv"
CERT="${SUDO_USER_HOME}/KernelCustomManager/build/secureboot/keys/MOK.pem"

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

# Vérifier que sbsign est installé
if ! command -v sbsign &> /dev/null; then
    echo -e "${RED}❌ sbsign n'est pas installé${NC}"
    echo -e "${YELLOW}   Installation...${NC}"
    apt update
    apt install -y sbsigntool
fi

echo -e "${GREEN}✅ sbsign est disponible${NC}"
echo ""

# Trouver les kernels custom
CUSTOM_KERNELS=$(ls /boot/vmlinuz-*kernelcustom* 2>/dev/null || true)

if [ -z "${CUSTOM_KERNELS}" ]; then
    echo -e "${YELLOW}⚠️  Aucun kernel custom trouvé dans /boot${NC}"
    exit 0
fi

echo -e "${CYAN}Kernels custom détectés:${NC}"
echo "${CUSTOM_KERNELS}" | sed 's/^/   /'
echo ""

# Demander confirmation
echo -e "${YELLOW}⚠️  Cette opération va signer les images vmlinuz${NC}"
echo -e "${YELLOW}   avec votre clé MOK enrollée.${NC}"
echo ""
read -p "$(echo -e ${GREEN}Continuer ? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⏹️  Opération annulée${NC}"
    exit 0
fi
echo ""

# Signer chaque kernel
SIGNED_COUNT=0
FAILED_COUNT=0

for vmlinuz in ${CUSTOM_KERNELS}; do
    kernel_name=$(basename "${vmlinuz}")
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}Signature de: ${kernel_name}${NC}"

    # Signer le kernel
    if sbsign --key "${PRIV_KEY}" --cert "${CERT}" --output "${vmlinuz}.signed" "${vmlinuz}" 2>/dev/null; then
        # Remplacer l'original par la version signée
        mv "${vmlinuz}.signed" "${vmlinuz}"
        echo -e "   ${GREEN}✅ Signé avec succès${NC}"
        SIGNED_COUNT=$((SIGNED_COUNT + 1))

        # Vérifier la signature
        if sbverify --cert "${CERT}" "${vmlinuz}" &>/dev/null; then
            echo -e "   ${GREEN}✅ Signature vérifiée${NC}"
        fi
    else
        echo -e "   ${RED}❌ Échec de la signature${NC}"
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi
    echo ""
done

# Résumé
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  RÉSUMÉ                                                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Kernels signés avec succès: ${GREEN}${SIGNED_COUNT}${NC}"
echo -e "Kernels échoués:           ${RED}${FAILED_COUNT}${NC}"
echo ""

if [ ${FAILED_COUNT} -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ SIGNATURE RÉUSSIE !                               ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}PROCHAINES ÉTAPES:${NC}"
    echo -e "  1. Mettez à jour GRUB:"
    echo -e "     ${GREEN}sudo update-grub${NC}"
    echo ""
    echo -e "  2. Redémarrez votre système:"
    echo -e "     ${GREEN}sudo reboot${NC}"
    echo ""
    echo -e "  3. Au démarrage, sélectionnez un kernel custom"
    echo -e "     L'erreur 'bad shim' devrait disparaître !"
    echo ""
else
    echo -e "${YELLOW}⚠️  Certains kernels n'ont pas pu être signés${NC}"
    echo ""
fi
