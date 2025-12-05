#!/bin/bash
#
# Script pour résoudre le problème "MOK Manager ne s'affiche pas au redémarrage"
# Ce script diagnostique et corrige les causes courantes
#
# Usage: ./fix_mok_not_appearing.sh
#

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Diagnostic: Pourquoi MOK Manager ne s'affiche pas   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Vérifier si mokutil est installé
if ! command -v mokutil &> /dev/null; then
    echo -e "${RED}❌ Erreur: mokutil n'est pas installé${NC}"
    exit 1
fi

# 1. Vérifier si SecureBoot est activé
echo -e "${CYAN}[1/6] Vérification du statut SecureBoot...${NC}"
SB_STATUS=$(mokutil --sb-state 2>&1 || echo "unknown")
echo -e "      Statut: ${GREEN}${SB_STATUS}${NC}"

if echo "${SB_STATUS}" | grep -q "disabled"; then
    echo -e "${YELLOW}⚠️  SecureBoot est désactivé - MOK Manager ne s'affichera pas${NC}"
    echo -e "${YELLOW}   Activez SecureBoot dans le BIOS pour utiliser MOK${NC}"
fi
echo ""

# 2. Vérifier les clés déjà enrollées
echo -e "${CYAN}[2/6] Vérification des clés MOK enrollées...${NC}"
ENROLLED=$(mokutil --list-enrolled 2>&1)

if echo "${ENROLLED}" | grep -q "MokListRT is empty"; then
    echo -e "      ${YELLOW}Aucune clé MOK enrollée${NC}"
    ENROLLED_STATUS="none"
else
    echo -e "      ${GREEN}✅ Clés MOK trouvées:${NC}"

    # Compter le nombre de clés
    KEY_COUNT=$(echo "${ENROLLED}" | grep -c "^\[key " || echo "0")
    echo -e "      ${GREEN}   Nombre de clés: ${KEY_COUNT}${NC}"

    # Chercher la clé kernelcustom
    if echo "${ENROLLED}" | grep -q "CN=kernelcustom"; then
        echo -e "      ${GREEN}   ✅ Votre clé 'kernelcustom' est déjà enrollée !${NC}"
        ENROLLED_STATUS="kernelcustom_found"
    else
        echo -e "      ${YELLOW}   ⚠️  Clé 'kernelcustom' non trouvée${NC}"
        ENROLLED_STATUS="other_keys"
    fi
fi
echo ""

# 3. Vérifier les clés en attente
echo -e "${CYAN}[3/6] Vérification des clés en attente d'enrollment...${NC}"
PENDING=$(mokutil --list-new 2>&1)

if echo "${PENDING}" | grep -q "MokNew is empty\|^$"; then
    echo -e "      ${GREEN}✅ Aucune clé en attente${NC}"
    PENDING_STATUS="none"
else
    echo -e "      ${YELLOW}⚠️  Il y a une clé en attente:${NC}"
    echo "${PENDING}" | head -n 10 | sed 's/^/      /'
    PENDING_STATUS="pending"
fi
echo ""

# 4. Vérifier l'état de shim et de bootx64.efi
echo -e "${CYAN}[4/6] Vérification du bootloader UEFI...${NC}"

# Chercher le point de montage EFI
EFI_MOUNT=$(findmnt -n -o TARGET --target /boot/efi 2>/dev/null || echo "")
if [ -z "${EFI_MOUNT}" ]; then
    EFI_MOUNT="/boot/efi"
    if [ ! -d "${EFI_MOUNT}" ]; then
        echo -e "      ${YELLOW}⚠️  Partition EFI non trouvée${NC}"
        BOOTLOADER_STATUS="not_found"
    else
        BOOTLOADER_STATUS="found"
    fi
else
    echo -e "      ${GREEN}✅ Partition EFI montée sur: ${EFI_MOUNT}${NC}"
    BOOTLOADER_STATUS="found"
fi

if [ "${BOOTLOADER_STATUS}" = "found" ]; then
    # Vérifier si shim existe
    SHIM_PATH="${EFI_MOUNT}/EFI/ubuntu/shimx64.efi"
    if [ -f "${SHIM_PATH}" ]; then
        echo -e "      ${GREEN}✅ shim trouvé: ${SHIM_PATH}${NC}"
    else
        echo -e "      ${YELLOW}⚠️  shim non trouvé à ${SHIM_PATH}${NC}"
    fi

    # Vérifier si mmx64.efi existe (MOK Manager)
    MOK_MANAGER="${EFI_MOUNT}/EFI/ubuntu/mmx64.efi"
    if [ -f "${MOK_MANAGER}" ]; then
        echo -e "      ${GREEN}✅ MOK Manager trouvé: ${MOK_MANAGER}${NC}"
    else
        echo -e "      ${RED}❌ MOK Manager manquant: ${MOK_MANAGER}${NC}"
        echo -e "      ${YELLOW}   Solution: sudo apt reinstall shim-signed${NC}"
    fi
fi
echo ""

# 5. Diagnostic de la cause
echo -e "${CYAN}[5/6] Diagnostic du problème...${NC}"
echo ""

ISSUE_FOUND=false

# Cas 1: Clé déjà enrollée
if [ "${ENROLLED_STATUS}" = "kernelcustom_found" ] && [ "${PENDING_STATUS}" = "none" ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ PAS DE PROBLÈME DÉTECTÉ !                         ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}Votre clé MOK 'kernelcustom' est déjà enrollée.${NC}"
    echo ""
    echo -e "${BLUE}Raison pour laquelle MOK Manager ne s'affiche pas:${NC}"
    echo -e "  ${GREEN}➜${NC} MOK Manager s'affiche UNIQUEMENT quand une nouvelle clé"
    echo -e "    est en attente d'enrollment (via mokutil --import)"
    echo ""
    echo -e "  ${GREEN}➜${NC} Comme votre clé est déjà enrollée, il est NORMAL que"
    echo -e "    MOK Manager ne s'affiche pas au redémarrage"
    echo ""
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  PROCHAINES ÉTAPES                                     ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "1. ${CYAN}Vérifiez que vos modules kernel sont signés:${NC}"
    echo -e "   ./verify_mok_enrollment.sh"
    echo ""
    echo -e "2. ${CYAN}Si vous avez un kernel personnalisé, signez-le:${NC}"
    echo -e "   - Lancez KernelCustom Manager"
    echo -e "   - Onglet SecureBoot → Signature"
    echo -e "   - Signez les modules"
    echo ""
    echo -e "3. ${CYAN}Si vous voulez réenroller une nouvelle clé:${NC}"
    echo -e "   a) Supprimez l'ancienne clé:"
    echo -e "      ${YELLOW}sudo mokutil --delete-all${NC}"
    echo -e "      ${YELLOW}sudo reboot${NC}"
    echo -e "      (Dans MOK Manager: Delete All → Yes → Mot de passe)"
    echo ""
    echo -e "   b) Générez et enrollez une nouvelle clé:"
    echo -e "      ${YELLOW}./enroll_mok_key.sh${NC}"
    echo ""
    ISSUE_FOUND=false

# Cas 2: Clé en attente mais n'apparaît pas
elif [ "${PENDING_STATUS}" = "pending" ]; then
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  ⚠️  PROBLÈME: Clé en attente mais MOK ne s'affiche pas║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${RED}Il y a une clé en attente mais MOK Manager ne s'affiche pas.${NC}"
    echo ""
    echo -e "${CYAN}Causes possibles:${NC}"
    echo ""
    echo -e "1. ${YELLOW}Shim est endommagé ou obsolète${NC}"
    echo -e "   Solution:"
    echo -e "   ${GREEN}sudo apt update && sudo apt reinstall shim-signed grub-efi-amd64-signed${NC}"
    echo ""
    echo -e "2. ${YELLOW}UEFI ne boot pas via shim${NC}"
    echo -e "   Solution:"
    echo -e "   a) Redémarrez dans le BIOS (F2/F10/F12/DEL)"
    echo -e "   b) Boot Manager → Vérifiez que 'ubuntu' est premier"
    echo -e "   c) Si nécessaire: sudo efibootmgr -v"
    echo ""
    echo -e "3. ${YELLOW}Fast Boot interfère${NC}"
    echo -e "   Solution:"
    echo -e "   a) Redémarrez dans le BIOS"
    echo -e "   b) Désactivez Fast Boot / Quick Boot"
    echo -e "   c) Sauvegardez et redémarrez"
    echo ""
    echo -e "4. ${YELLOW}Clé corrompue${NC}"
    echo -e "   Solution:"
    echo -e "   ${GREEN}sudo mokutil --reset${NC}"
    echo -e "   ${GREEN}sudo reboot${NC}"
    echo -e "   Puis réessayez: ./enroll_mok_key.sh"
    echo ""
    ISSUE_FOUND=true

# Cas 3: Aucune clé ni enrollée ni en attente
else
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  ℹ️  Aucune clé MOK détectée                          ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Vous devez d'abord importer une clé MOK.${NC}"
    echo ""
    echo -e "${GREEN}Solution:${NC}"
    echo -e "  ./enroll_mok_key.sh"
    echo ""
    ISSUE_FOUND=false
fi

echo ""

# 6. Tests supplémentaires
echo -e "${CYAN}[6/6] Tests supplémentaires recommandés...${NC}"
echo ""

echo -e "Pour forcer l'apparition de MOK Manager (test):"
echo -e "${YELLOW}sudo mokutil --reset${NC}"
echo -e "${YELLOW}sudo reboot${NC}"
echo ""
echo -e "⚠️  ${RED}ATTENTION:${NC} Cela supprimera toutes les clés MOK enrollées !"
echo ""

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  RÉSUMÉ DU DIAGNOSTIC                                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "SecureBoot:     ${SB_STATUS}"
echo -e "Clés enrollées: ${ENROLLED_STATUS}"
echo -e "Clés en attente: ${PENDING_STATUS}"
echo -e "Bootloader:     ${BOOTLOADER_STATUS}"
echo ""

if [ "${ISSUE_FOUND}" = false ] && [ "${ENROLLED_STATUS}" = "kernelcustom_found" ]; then
    echo -e "${GREEN}✅ Votre configuration MOK est correcte !${NC}"
    echo -e "${GREEN}   MOK Manager n'a PAS BESOIN de s'afficher.${NC}"
elif [ "${ISSUE_FOUND}" = true ]; then
    echo -e "${RED}⚠️  Un problème a été détecté. Suivez les solutions ci-dessus.${NC}"
else
    echo -e "${YELLOW}ℹ️  Lancez ./enroll_mok_key.sh pour commencer.${NC}"
fi

echo ""
