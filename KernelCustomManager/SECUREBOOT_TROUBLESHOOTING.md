# 🔒 Guide de Dépannage SecureBoot - "bad shim signature"

Ce guide vous aide à résoudre l'erreur de boot **"bad shim signature"** avec KernelCustom Manager.

---

## 🎯 Diagnostic de l'Erreur

L'erreur **"bad shim signature"** apparaît quand :

1. ✅ SecureBoot est **activé** sur votre système UEFI
2. ❌ Votre kernel personnalisé **n'est pas signé** ou signé avec une clé non-enrollée
3. ❌ Les modules kernel **ne sont pas signés** avec votre clé MOK enrollée

---

## 🚀 Solution Rapide (Automatisée)

### Étape 1 : Enrollment de la Clé MOK

Exécutez le script d'enrollment automatique :

```bash
cd ~/Documents/BOOKWORM/KernelCustomManager
./enroll_mok_key.sh
```

Le script va :
- ✅ Vérifier votre configuration UEFI/SecureBoot
- ✅ Vérifier que la clé MOK existe
- ✅ Afficher les clés déjà enrollées
- ✅ Importer la clé MOK (vous créerez un mot de passe)
- ✅ Sauvegarder un fichier de rappel avec les instructions

### Étape 2 : Redémarrer

```bash
sudo reboot
```

### Étape 3 : MOK Manager (Écran Bleu au Boot)

Au redémarrage, un écran bleu **"MOK Manager"** apparaîtra automatiquement :

```
┌──────────────────────────────────────┐
│  Perform MOK management              │
│                                      │
│  > Enroll MOK           ← SÉLECTIONNER
│    Enroll key from disk              │
│    Delete MOK                        │
│    Continue boot                     │
└──────────────────────────────────────┘
```

**Suivez ces étapes :**

1. Sélectionnez **"Enroll MOK"** → Entrée
2. Sélectionnez **"Continue"** → Entrée
3. Sélectionnez **"Yes"** → Entrée
4. **Entrez le mot de passe** créé à l'étape 1
5. Sélectionnez **"Reboot"** → Entrée

### Étape 4 : Vérifier l'Enrollment

Après le redémarrage, vérifiez que tout est correct :

```bash
cd ~/Documents/BOOKWORM/KernelCustomManager
./verify_mok_enrollment.sh
```

✅ Si le script affiche **"Votre clé MOK est enrollée avec succès !"**, passez à l'étape suivante.

---

## 🔐 Signature des Modules Kernel

Maintenant que votre clé MOK est enrollée, vous devez **signer les modules** de votre kernel personnalisé.

### Option A : Via l'Interface Graphique

1. Lancez KernelCustom Manager :
   ```bash
   python3 ~/Documents/BOOKWORM/KernelCustomManager/kernelcustom_manager.py
   ```

2. Allez dans l'onglet **"SecureBoot"**

3. Allez dans l'onglet **"✍️ Signature"**

4. Dans la section **"Signer des modules"** :
   - Sélectionnez le répertoire de votre kernel : `/lib/modules/6.17.0-7-generic/`
   - Ou le répertoire de build si le kernel n'est pas encore installé
   - Cliquez sur **"Signer les modules"**

5. Attendez que tous les modules soient signés (peut prendre quelques minutes)

6. Redémarrez :
   ```bash
   sudo reboot
   ```

### Option B : Via Script (Pour Kernel Déjà Compilé)

Créez et exécutez ce script pour signer automatiquement :

```bash
#!/bin/bash
# sign_current_kernel.sh

KERNEL_VERSION=$(uname -r)
KERNEL_DIR="/lib/modules/${KERNEL_VERSION}"
PRIV_KEY="${HOME}/KernelCustomManager/build/secureboot/keys/MOK.priv"
CERT="${HOME}/KernelCustomManager/build/secureboot/keys/MOK.der"

# Trouver sign-file
SIGN_FILE="/usr/src/linux-headers-${KERNEL_VERSION}/scripts/sign-file"

if [ ! -f "${SIGN_FILE}" ]; then
    echo "Erreur: sign-file introuvable"
    exit 1
fi

# Signer tous les modules
echo "Signature des modules dans ${KERNEL_DIR}..."
sudo find "${KERNEL_DIR}" -name '*.ko' -exec ${SIGN_FILE} sha256 ${PRIV_KEY} ${CERT} {} \;

echo "✅ Signature terminée !"
```

Rendez-le exécutable et lancez-le :
```bash
chmod +x sign_current_kernel.sh
./sign_current_kernel.sh
sudo reboot
```

---

## 🔄 Workflow Complet pour Futurs Kernels

Pour compiler un nouveau kernel avec signature automatique :

### 1. Lancez KernelCustom Manager
```bash
python3 ~/Documents/BOOKWORM/KernelCustomManager/kernelcustom_manager.py
```

### 2. Compilez le Kernel avec Signature
- Onglet **"Compiler"**
- Téléchargez et configurez votre kernel
- Cliquez **"🔨 Compiler le kernel"**
- ✅ **COCHEZ** "🔒 Signer pour SecureBoot"
- Attendez la fin de la compilation

### 3. Installez le Kernel
- Onglet **"Paquets locaux"**
- Installez les `.deb` générés

### 4. Redémarrez
```bash
sudo reboot
```

✅ Votre kernel personnalisé devrait maintenant booter avec SecureBoot activé !

---

## 🛟 Solutions Alternatives

### Solution 1 : Désactiver Temporairement SecureBoot

Si vous devez booter **immédiatement** :

1. Redémarrez et entrez dans le **BIOS/UEFI**
   - Généralement : **F2**, **F10**, **F12**, ou **DEL** au démarrage
   - Varie selon le fabricant (HP, Dell, Lenovo, ASUS, etc.)

2. Cherchez l'option **"Secure Boot"**
   - Généralement dans : *Security* → *Secure Boot* → *Enabled/Disabled*

3. **Désactivez** Secure Boot

4. **Sauvegardez et quittez** (Save & Exit)

⚠️ **Attention** : Cela réduit la sécurité. Réactivez SecureBoot après avoir enrollé votre clé MOK.

### Solution 2 : Utiliser un Kernel Standard (Sans Signature)

Si vous ne voulez pas gérer les signatures :

```bash
# Lister les kernels installés
dpkg --list | grep linux-image

# Installer un kernel Ubuntu standard
sudo apt install linux-image-generic

# Redémarrer et sélectionner le kernel standard dans GRUB
sudo reboot
```

Les kernels Ubuntu standards sont **déjà signés** et fonctionnent avec SecureBoot.

---

## 🔍 Diagnostic et Dépannage

### Vérifier le Statut SecureBoot
```bash
mokutil --sb-state
# Sortie attendue : "SecureBoot enabled"
```

### Lister les Clés MOK Enrollées
```bash
mokutil --list-enrolled
# Doit afficher votre clé avec "Kernel Module Signing Key"
```

### Vérifier qu'un Module est Signé
```bash
modinfo -F sig_id /lib/modules/$(uname -r)/kernel/drivers/net/e1000/e1000.ko
# Si vide : module non signé
# Si affiché : module signé
```

### Vérifier les Logs du Kernel
```bash
dmesg | grep -i "signature"
dmesg | grep -i "secureboot"
```

### Réinitialiser Complètement les Clés MOK
```bash
mokutil --reset
sudo reboot
# Dans MOK Manager : Reset MOK → Yes → Mot de passe → Reboot
```

---

## 📚 Ressources

- **Documentation UEFI SecureBoot** : https://uefi.org/specifications
- **Ubuntu SecureBoot Guide** : https://wiki.ubuntu.com/UEFI/SecureBoot
- **Kernel Module Signing** : https://www.kernel.org/doc/html/latest/admin-guide/module-signing.html

---

## ❓ FAQ

### Q : Pourquoi MOK Manager n'apparaît pas au redémarrage ?

**R :** Causes possibles :
- La clé est déjà enrollée (vérifiez avec `mokutil --list-enrolled`)
- Vous avez annulé l'import
- Problème avec votre firmware UEFI
- **Solution** : Réessayez `./enroll_mok_key.sh`

### Q : J'ai oublié le mot de passe MOK

**R :** Pas de problème :
```bash
./enroll_mok_key.sh
```
Cela créera une nouvelle demande d'enrollment avec un nouveau mot de passe.

### Q : Mon kernel boot maintenant, mais il y a des erreurs "module signature verification failed"

**R :** Certains modules ne sont pas signés :
1. Lancez KernelCustom Manager
2. Onglet SecureBoot → Signature
3. Signez les modules manquants

### Q : Puis-je utiliser plusieurs clés MOK ?

**R :** Oui ! Vous pouvez enroller autant de clés MOK que nécessaire. Utilisez `mokutil --list-enrolled` pour voir toutes les clés.

### Q : Dois-je resigner après une mise à jour du kernel ?

**R :** Oui, si vous recompilez ou mettez à jour un kernel personnalisé. Les kernels Ubuntu standards sont déjà signés.

### Q : Quelle est la différence entre SecureBoot et UEFI ?

**R :**
- **UEFI** : Le firmware qui remplace le BIOS classique
- **SecureBoot** : Une fonctionnalité de sécurité UEFI qui vérifie les signatures des bootloaders et kernels

---

## 🆘 Besoin d'Aide ?

Si vous avez toujours des problèmes :

1. Vérifiez les logs :
   ```bash
   cat ~/KernelCustomManager/build/secureboot/secureboot_history.json
   ```

2. Consultez le README :
   ```bash
   less ~/Documents/BOOKWORM/KernelCustomManager/README.md
   ```

3. Ouvrez une issue sur GitHub :
   https://github.com/lpennisi73-tech/BOOKWORM/issues

---

**Bonne chance ! 🚀**
