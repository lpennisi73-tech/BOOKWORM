#!/bin/bash
#
# Script d'enrollment automatique de clé MOK pour SecureBoot
# Utilise la clé générée par KernelCustom Manager
#
# Usage: ./enroll_mok_key.sh
#

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Chemin vers la clé MOK
MOK_KEY="${HOME}/KernelCustomManager/build/secureboot/keys/MOK.der"

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   KernelCustom Manager - Enrollment de clé MOK        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Vérifier si on est sur un système UEFI
if [ ! -d "/sys/firmware/efi" ]; then
    echo -e "${RED}❌ Erreur: Ce système n'utilise pas UEFI${NC}"
    echo -e "${YELLOW}   SecureBoot n'est disponible que sur les systèmes UEFI${NC}"
    exit 1
fi

# Vérifier si mokutil est installé
if ! command -v mokutil &> /dev/null; then
    echo -e "${RED}❌ Erreur: mokutil n'est pas installé${NC}"
    echo -e "${YELLOW}   Installation requise:${NC}"
    echo -e "   sudo apt install mokutil"
    exit 1
fi

# Vérifier si la clé MOK existe
if [ ! -f "${MOK_KEY}" ]; then
    echo -e "${RED}❌ Erreur: Clé MOK introuvable${NC}"
    echo -e "${YELLOW}   Chemin attendu: ${MOK_KEY}${NC}"
    echo -e ""
    echo -e "${BLUE}💡 Pour générer une clé MOK:${NC}"
    echo -e "   1. Lancez KernelCustom Manager"
    echo -e "   2. Allez dans l'onglet 'SecureBoot'"
    echo -e "   3. Allez dans l'onglet '✍️ Signature'"
    echo -e "   4. Cliquez sur 'Générer une nouvelle clé'"
    exit 1
fi

# Afficher le statut SecureBoot actuel
echo -e "${BLUE}🔍 Vérification du statut SecureBoot...${NC}"
SB_STATUS=$(mokutil --sb-state 2>&1 || echo "unknown")
echo -e "   Statut: ${GREEN}${SB_STATUS}${NC}"
echo ""

# Vérifier les clés déjà enrollées
echo -e "${BLUE}🔑 Clés MOK actuellement enrollées:${NC}"
ENROLLED=$(mokutil --list-enrolled 2>&1)
if echo "${ENROLLED}" | grep -q "MokListRT is empty"; then
    echo -e "   ${YELLOW}Aucune clé MOK enrollée${NC}"
else
    echo "${ENROLLED}" | grep -A 3 "Subject:" | head -n 4 | sed 's/^/   /'
fi
echo ""

# Vérifier les clés en attente
echo -e "${BLUE}⏳ Clés en attente d'enrollment:${NC}"
PENDING=$(mokutil --list-new 2>&1)
if echo "${PENDING}" | grep -q "MokNew is empty" || [ -z "${PENDING}" ]; then
    echo -e "   ${YELLOW}Aucune clé en attente${NC}"
else
    echo "${PENDING}" | grep -A 3 "Subject:" | head -n 4 | sed 's/^/   /'
    echo ""
    echo -e "${YELLOW}⚠️  Il y a déjà une clé en attente d'enrollment${NC}"
    echo -e "${YELLOW}   Vous devez d'abord redémarrer pour l'enroller${NC}"
    read -p "$(echo -e ${YELLOW}Voulez-vous continuer quand même ? [y/N]: ${NC})" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi
echo ""

# Afficher les informations sur la clé à importer
echo -e "${BLUE}📄 Informations sur la clé à importer:${NC}"
echo -e "   Chemin: ${MOK_KEY}"
openssl x509 -in "${MOK_KEY}" -inform DER -noout -subject -dates 2>/dev/null | sed 's/^/   /' || echo "   (impossible de lire les détails)"
echo ""

# Demander confirmation
echo -e "${YELLOW}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║  Cette opération va importer votre clé MOK            ║${NC}"
echo -e "${YELLOW}║  Vous devrez:                                          ║${NC}"
echo -e "${YELLOW}║  1. Créer un mot de passe temporaire (8-16 caractères)║${NC}"
echo -e "${YELLOW}║  2. Redémarrer votre système                           ║${NC}"
echo -e "${YELLOW}║  3. Dans MOK Manager: Enroll MOK → Continue → Yes     ║${NC}"
echo -e "${YELLOW}║  4. Entrer le mot de passe créé                       ║${NC}"
echo -e "${YELLOW}║  5. Redémarrer à nouveau                               ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

read -p "$(echo -e ${GREEN}Voulez-vous continuer ? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⏹️  Opération annulée${NC}"
    exit 0
fi
echo ""

# Importer la clé MOK
echo -e "${BLUE}🔐 Importation de la clé MOK...${NC}"
echo -e "${YELLOW}⚠️  Vous allez devoir créer un mot de passe temporaire${NC}"
echo -e "${YELLOW}   NOTEZ-LE BIEN ! Vous en aurez besoin au redémarrage${NC}"
echo ""

if sudo mokutil --import "${MOK_KEY}"; then
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ Clé MOK importée avec succès !                    ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Créer un fichier de rappel
    REMINDER_FILE="${HOME}/KernelCustomManager/build/secureboot/MOK_ENROLLMENT_REMINDER.txt"
    cat > "${REMINDER_FILE}" << EOF
╔════════════════════════════════════════════════════════════════════════╗
║         RAPPEL: Enrollment de clé MOK en attente                      ║
╚════════════════════════════════════════════════════════════════════════╝

Date: $(date)
Clé importée: ${MOK_KEY}

PROCHAINES ÉTAPES:
==================

1. REDÉMARRER votre système
   $ sudo reboot

2. AU REDÉMARRAGE - Un écran bleu "MOK Manager" apparaîtra:

   ┌──────────────────────────────────────┐
   │  Perform MOK management              │
   │                                      │
   │  > Enroll MOK           ← SÉLECTIONNER
   │    Enroll key from disk              │
   │    Delete MOK                        │
   │    Continue boot                     │
   └──────────────────────────────────────┘

3. Sélectionnez "Enroll MOK" et appuyez sur Entrée

4. Sélectionnez "Continue" et appuyez sur Entrée

5. Sélectionnez "Yes" pour confirmer

6. ENTREZ LE MOT DE PASSE que vous avez créé lors de l'import

7. Sélectionnez "Reboot"

8. Votre système redémarrera avec la clé MOK enrollée

VÉRIFICATION APRÈS REDÉMARRAGE:
================================

Pour vérifier que l'enrollment a réussi:

    $ mokutil --list-enrolled | grep -i "MOK"

Votre clé MOK devrait apparaître dans la liste.

DÉPANNAGE:
===========

Si MOK Manager n'apparaît pas au redémarrage:
  - La clé est peut-être déjà enrollée (vérifiez avec mokutil --list-enrolled)
  - Réessayez l'import: sudo mokutil --import ${MOK_KEY}

Si vous avez oublié le mot de passe:
  - Réimportez la clé: sudo mokutil --import ${MOK_KEY}
  - Cela créera une nouvelle demande d'enrollment

Si SecureBoot refuse toujours le kernel:
  - Vérifiez que les modules sont signés: modinfo -F sig_id /path/to/module.ko
  - Resignez les modules avec KernelCustom Manager

╔════════════════════════════════════════════════════════════════════════╗
║  Ce fichier sera automatiquement supprimé après vérification          ║
╚════════════════════════════════════════════════════════════════════════╝
EOF

    echo -e "${BLUE}📋 Instructions détaillées sauvegardées dans:${NC}"
    echo -e "   ${REMINDER_FILE}"
    echo ""
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  🔄 REDÉMARRAGE REQUIS                                ║${NC}"
    echo -e "${YELLOW}║                                                        ║${NC}"
    echo -e "${YELLOW}║  Au redémarrage, MOK Manager apparaîtra automatiquement║${NC}"
    echo -e "${YELLOW}║  Suivez les instructions à l'écran:                    ║${NC}"
    echo -e "${YELLOW}║                                                        ║${NC}"
    echo -e "${YELLOW}║  1. Enroll MOK                                         ║${NC}"
    echo -e "${YELLOW}║  2. Continue                                           ║${NC}"
    echo -e "${YELLOW}║  3. Yes                                                ║${NC}"
    echo -e "${YELLOW}║  4. Entrez le mot de passe que vous venez de créer    ║${NC}"
    echo -e "${YELLOW}║  5. Reboot                                             ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""

    read -p "$(echo -e ${GREEN}Voulez-vous redémarrer maintenant ? [y/N]: ${NC})" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}🔄 Redémarrage dans 5 secondes...${NC}"
        sleep 5
        sudo reboot
    else
        echo -e "${YELLOW}⚠️  N'oubliez pas de redémarrer plus tard !${NC}"
    fi
else
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ❌ Échec de l'importation de la clé MOK              ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Causes possibles:${NC}"
    echo -e "  - Mot de passe invalide (doit faire 8-16 caractères)"
    echo -e "  - Permissions insuffisantes"
    echo -e "  - Clé déjà importée"
    echo ""
    exit 1
fi
