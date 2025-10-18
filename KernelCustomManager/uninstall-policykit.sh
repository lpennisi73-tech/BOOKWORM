#!/bin/bash
#
# Uninstall PolicyKit helper for KernelCustom Manager
#

echo "🔐 Désinstallation du helper PolicyKit..."

# Remove helper script
if sudo rm -f /usr/local/bin/kernelcustom-helper 2>/dev/null; then
    echo "   ✓ Helper supprimé"
else
    echo "   ⚠️  Impossible de supprimer le helper (sudo requis)"
fi

# Remove PolicyKit rules
if sudo rm -f /usr/share/polkit-1/actions/com.kernelcustom.manager.policy 2>/dev/null; then
    echo "   ✓ Règles PolicyKit supprimées"
else
    echo "   ⚠️  Impossible de supprimer les règles PolicyKit (sudo requis)"
fi

echo ""
echo "✅ Désinstallation terminée"
echo "   L'application continuera de fonctionner mais demandera"
echo "   le mot de passe plus souvent (méthode standard pkexec)"
