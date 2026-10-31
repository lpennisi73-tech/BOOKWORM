# 🔒 Scripts SecureBoot pour KernelCustom Manager

Ce répertoire contient les scripts pour gérer SecureBoot et l'enrollment de clés MOK.

## 📋 Liste des Scripts

### 1. `enroll_mok_key.sh` - Enrollment de la clé MOK
**Usage :** `./enroll_mok_key.sh`

Importe votre clé MOK dans le système pour autoriser le boot de kernels personnalisés avec SecureBoot activé.

**Ce que fait ce script :**
- ✅ Vérifie que vous êtes sur un système UEFI
- ✅ Vérifie le statut SecureBoot
- ✅ Liste les clés déjà enrollées
- ✅ Importe votre clé MOK (vous créerez un mot de passe temporaire)
- ✅ Vous guide pour le redémarrage et MOK Manager

**Quand l'utiliser :**
- Première fois que vous configurez SecureBoot pour vos kernels custom
- Après avoir généré une nouvelle clé MOK

---

### 2. `verify_mok_enrollment.sh` - Vérifier l'enrollment MOK
**Usage :** `./verify_mok_enrollment.sh`

Vérifie que votre clé MOK a été correctement enrollée après le redémarrage.

**Ce que fait ce script :**
- ✅ Vérifie le statut SecureBoot
- ✅ Liste les clés MOK enrollées
- ✅ Confirme que votre clé 'kernelcustom' est présente
- ✅ Vérifie la signature des modules kernel

**Quand l'utiliser :**
- Après avoir redémarré et validé l'enrollment dans MOK Manager
- Pour diagnostiquer des problèmes de boot

---

### 3. `fix_mok_not_appearing.sh` - Diagnostic MOK Manager
**Usage :** `./fix_mok_not_appearing.sh`

Diagnostique pourquoi MOK Manager ne s'affiche pas au redémarrage.

**Ce que fait ce script :**
- 🔍 Vérifie le statut SecureBoot
- 🔍 Liste les clés enrollées et en attente
- 🔍 Vérifie le bootloader UEFI (shim, MOK Manager)
- 🔍 Explique pourquoi MOK Manager n'apparaît pas
- 💡 Propose des solutions si un problème est détecté

**Quand l'utiliser :**
- Quand MOK Manager ne s'affiche pas alors que vous attendiez qu'il apparaisse
- Pour comprendre l'état actuel de votre configuration MOK

---

### 4. `resign_all_custom_kernels.sh` - Re-signer les kernels custom
**Usage :** `sudo ./resign_all_custom_kernels.sh`

Re-signe tous vos kernels personnalisés avec votre clé MOK enrollée.

**Ce que fait ce script :**
- 🔍 Détecte automatiquement tous les kernels custom installés
- ✍️ Re-signe tous les modules (.ko) avec votre clé MOK
- ✅ Vérifie la signature après l'opération

**Quand l'utiliser :**
- Quand vous obtenez "bad shim signature" au boot
- Après avoir enrollé votre clé MOK pour la première fois
- Quand vos kernels ont été signés avec la mauvaise clé

---

## 🚀 Workflow Complet SecureBoot

### Première configuration (kernel déjà compilé et installé) :

```bash
cd ~/Documents/BOOKWORM/KernelCustomManager/scripts/secureboot

# 1. Enroller votre clé MOK
./enroll_mok_key.sh
# → Créez un mot de passe quand demandé
# → Redémarrez

# Au redémarrage (écran bleu MOK Manager) :
# - Enroll MOK → Continue → Yes → [Mot de passe] → Reboot

# 2. Vérifier l'enrollment
./verify_mok_enrollment.sh

# 3. Re-signer vos kernels custom
sudo ./resign_all_custom_kernels.sh

# 4. Redémarrer et sélectionner votre kernel custom dans GRUB
sudo reboot
```

### Dépannage "bad shim signature" :

```bash
cd ~/Documents/BOOKWORM/KernelCustomManager/scripts/secureboot

# 1. Diagnostiquer le problème
./fix_mok_not_appearing.sh

# 2. Si la clé est déjà enrollée, re-signer les kernels
sudo ./resign_all_custom_kernels.sh

# 3. Redémarrer
sudo reboot
```

### Nouvelle compilation avec SecureBoot :

**Option A : Via l'interface graphique (RECOMMANDÉ)**
1. Lancez KernelCustom Manager
2. Compilez le kernel
3. Cochez "🔒 Signer pour SecureBoot" pendant la compilation
4. Installez et redémarrez

**Option B : Via scripts (si déjà compilé sans signature)**
```bash
# Re-signer après installation
cd ~/Documents/BOOKWORM/KernelCustomManager/scripts/secureboot
sudo ./resign_all_custom_kernels.sh
sudo reboot
```

---

## 📁 Fichiers Générés

Ces scripts utilisent/génèrent les fichiers suivants :

### Clés MOK (générées par KernelCustom Manager)
```
~/KernelCustomManager/build/secureboot/keys/
├── MOK.priv     # Clé privée (GARDEZ-LA SECRÈTE !)
├── MOK.der      # Certificat public (format DER, pour enrollment)
└── MOK.pem      # Certificat public (format PEM)
```

### Fichiers temporaires
```
~/KernelCustomManager/build/secureboot/
└── MOK_ENROLLMENT_REMINDER.txt  # Rappel des étapes (supprimé après vérification)
```

---

## ⚠️ Notes Importantes

### Sécurité
- **NE PARTAGEZ JAMAIS** votre fichier `MOK.priv`
- Gardez une copie de sauvegarde de vos clés MOK
- Le mot de passe MOK est temporaire (juste pour l'enrollment)

### Compatibilité
- Nécessite un système UEFI (pas BIOS Legacy)
- SecureBoot doit être activé dans le BIOS
- Testé sur Debian 13/14

### Outils requis
- `mokutil` (généralement pré-installé)
- `sign-file` (dans linux-headers)
- `openssl`

---

## 🆘 Problèmes Courants

### "MOK Manager ne s'affiche pas"
→ Utilisez `./fix_mok_not_appearing.sh` pour diagnostiquer

### "bad shim signature" au boot
→ Utilisez `sudo ./resign_all_custom_kernels.sh`

### "Clé MOK introuvable"
→ Lancez KernelCustom Manager → Onglet SecureBoot → Générer une clé

### "sign-file introuvable"
```bash
sudo apt install linux-headers-$(uname -r)
```

---

## 📚 Documentation Complète

Pour plus d'informations, consultez :
- `../../SECUREBOOT_TROUBLESHOOTING.md` - Guide de dépannage complet
- `../../QUICK_START_SECUREBOOT.md` - Démarrage rapide

---

## 🔄 Intégration Future

Ces scripts seront intégrés dans l'interface graphique de KernelCustom Manager pour une expérience utilisateur simplifiée. En attendant, ils peuvent être utilisés en ligne de commande.
