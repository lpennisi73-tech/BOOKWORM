#!/bin/bash
#
# Script de vérification de l'enrollment MOK
# À exécuter après le redémarrage pour confirmer que l'enrollment a réussi
#
# Usage: ./verify_mok_enrollment.sh
#

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Vérification de l'enrollment MOK                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Vérifier mokutil
if ! command -v mokutil &> /dev/null; then
    echo -e "${RED}❌ Erreur: mokutil n'est pas installé${NC}"
    exit 1
fi

# Vérifier le statut SecureBoot
echo -e "${BLUE}🔍 Statut SecureBoot:${NC}"
SB_STATUS=$(mokutil --sb-state 2>&1 || echo "unknown")
echo -e "   ${GREEN}${SB_STATUS}${NC}"
echo ""

# Vérifier les clés enrollées
echo -e "${BLUE}🔑 Clés MOK enrollées:${NC}"
ENROLLED=$(mokutil --list-enrolled 2>&1)

if echo "${ENROLLED}" | grep -q "MokListRT is empty"; then
    echo -e "${RED}❌ Aucune clé MOK enrollée${NC}"
    echo ""
    echo -e "${YELLOW}La clé n'a pas été enrollée. Causes possibles:${NC}"
    echo -e "  1. Vous n'avez pas suivi la procédure dans MOK Manager"
    echo -e "  2. Vous avez entré un mauvais mot de passe"
    echo -e "  3. Vous avez sélectionné 'Continue boot' au lieu de 'Enroll MOK'"
    echo ""
    echo -e "${YELLOW}💡 Pour réessayer:${NC}"
    echo -e "   ./enroll_mok_key.sh"
    exit 1
else
    echo "${ENROLLED}" | head -n 20
    echo ""

    # Chercher notre clé spécifique
    if echo "${ENROLLED}" | grep -q "Kernel Module Signing Key"; then
        echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  ✅ Votre clé MOK est enrollée avec succès !          ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"

        # Supprimer le fichier de rappel s'il existe
        REMINDER_FILE="${HOME}/KernelCustomManager/build/secureboot/MOK_ENROLLMENT_REMINDER.txt"
        if [ -f "${REMINDER_FILE}" ]; then
            rm -f "${REMINDER_FILE}"
            echo -e "${BLUE}📝 Fichier de rappel supprimé${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Une clé MOK est enrollée mais ce n'est peut-être pas la vôtre${NC}"
        echo -e "${YELLOW}   Vérifiez que le CN contient 'Kernel Module Signing Key'${NC}"
    fi
fi

echo ""

# Vérifier les clés en attente
echo -e "${BLUE}⏳ Clés en attente:${NC}"
PENDING=$(mokutil --list-new 2>&1)

if echo "${PENDING}" | grep -q "MokNew is empty"; then
    echo -e "   ${GREEN}Aucune clé en attente${NC}"
else
    echo -e "${YELLOW}⚠️  Il reste des clés en attente d'enrollment${NC}"
    echo "${PENDING}" | head -n 10
fi

echo ""

# Vérifier qu'un module kernel est signé (si possible)
echo -e "${BLUE}🔐 Vérification des modules kernel signés:${NC}"

# Chercher quelques modules communs
KERNEL_VERSION=$(uname -r)
TEST_MODULES=(
    "/lib/modules/${KERNEL_VERSION}/kernel/drivers/net/e1000/e1000.ko"
    "/lib/modules/${KERNEL_VERSION}/kernel/fs/ext4/ext4.ko"
    "/lib/modules/${KERNEL_VERSION}/kernel/net/ipv4/tcp_cubic.ko"
)

FOUND_MODULE=""
for module in "${TEST_MODULES[@]}"; do
    if [ -f "${module}" ]; then
        FOUND_MODULE="${module}"
        break
    fi
done

if [ -n "${FOUND_MODULE}" ]; then
    echo -e "   Test avec: $(basename ${FOUND_MODULE})"
    SIG_INFO=$(modinfo -F sig_id "${FOUND_MODULE}" 2>/dev/null || echo "")

    if [ -n "${SIG_INFO}" ]; then
        echo -e "   ${GREEN}✅ Module signé: ${SIG_INFO}${NC}"
    else
        echo -e "   ${YELLOW}⚠️  Module non signé${NC}"
        echo -e "   ${YELLOW}   Si c'est un kernel personnalisé, signez les modules:${NC}"
        echo -e "   ${YELLOW}   - Lancez KernelCustom Manager${NC}"
        echo -e "   ${YELLOW}   - Onglet SecureBoot → Signature${NC}"
        echo -e "   ${YELLOW}   - Sélectionnez le répertoire du kernel${NC}"
        echo -e "   ${YELLOW}   - Cliquez 'Signer les modules'${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  Aucun module test trouvé${NC}"
fi

echo ""

# Résumé final
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  RÉSUMÉ                                                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

if echo "${ENROLLED}" | grep -q "Kernel Module Signing Key"; then
    echo -e "${GREEN}✅ Clé MOK: Enrollée${NC}"
    echo -e "${GREEN}✅ SecureBoot: ${SB_STATUS}${NC}"
    echo ""
    echo -e "${BLUE}🎉 Configuration réussie !${NC}"
    echo ""
    echo -e "${YELLOW}PROCHAINES ÉTAPES pour un kernel personnalisé:${NC}"
    echo -e "  1. Compiler votre kernel avec KernelCustom Manager"
    echo -e "  2. Cocher 'Signer pour SecureBoot' lors de la compilation"
    echo -e "  3. Installer le kernel compilé"
    echo -e "  4. Redémarrer"
    echo ""
    echo -e "${YELLOW}OU si le kernel est déjà installé:${NC}"
    echo -e "  1. Lancez KernelCustom Manager"
    echo -e "  2. Onglet SecureBoot → Signature"
    echo -e "  3. Signez les modules du kernel installé"
    echo -e "  4. Redémarrez"
else
    echo -e "${RED}❌ Clé MOK: Non enrollée${NC}"
    echo ""
    echo -e "${YELLOW}Réessayez l'enrollment:${NC}"
    echo -e "  ./enroll_mok_key.sh"
fi

echo ""
