#!/bin/bash
#
# Désinstalle les helpers privilégiés et la policy PolicyKit de KernelCustom Manager
#

echo "🔐 Désinstallation des helpers privilégiés..."

sudo rm -rf /usr/libexec/kernelcustom-manager && echo "   ✓ Helpers supprimés"
sudo rm -f /usr/local/bin/kernelcustom-helper
sudo rm -f /usr/share/polkit-1/actions/com.kernelcustom.manager.policy && echo "   ✓ Règles PolicyKit supprimées"

echo ""
echo "✅ Désinstallation terminée"
echo "   Les opérations privilégiées (installation de kernels, SecureBoot, pilotes)"
echo "   ne fonctionneront plus tant que ./install.sh n'aura pas été relancé."
