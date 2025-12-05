# 🚀 Démarrage Rapide - Résoudre "bad shim signature"

## ⚡ Solution en 3 Étapes

### 1️⃣ Enrollez votre clé MOK
```bash
cd ~/Documents/BOOKWORM/KernelCustomManager
./enroll_mok_key.sh
```
- Créez un mot de passe quand demandé (8-16 caractères)
- **NOTEZ-LE !** Vous en aurez besoin au redémarrage

### 2️⃣ Redémarrez et suivez MOK Manager
```bash
sudo reboot
```

Au redémarrage (écran bleu) :
1. **Enroll MOK** → Entrée
2. **Continue** → Entrée
3. **Yes** → Entrée
4. **Entrez votre mot de passe**
5. **Reboot** → Entrée

### 3️⃣ Vérifiez après redémarrage
```bash
cd ~/Documents/BOOKWORM/KernelCustomManager
./verify_mok_enrollment.sh
```

✅ Si tout est OK, votre kernel devrait maintenant booter !

---

## 📖 Guide Complet

Pour plus de détails et dépannage, consultez :
```bash
cat SECUREBOOT_TROUBLESHOOTING.md
```

---

## 🔧 Alternative Rapide (Désactiver SecureBoot)

Si vous devez booter **maintenant** :

1. Redémarrez → Entrez dans le BIOS (F2/F10/F12/DEL)
2. Security → Secure Boot → **Disabled**
3. Save & Exit

⚠️ Moins sécurisé, mais permet de booter immédiatement.

---

**Bonne chance ! 🎉**
