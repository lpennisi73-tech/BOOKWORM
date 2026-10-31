# 🚀 KernelCustom Manager v3.0

[![Version](https://img.shields.io/badge/version-3.0-blue.svg)](https://github.com/lpennisi73-tech/BOOKWORM.git)
[![Debian](https://img.shields.io/badge/Debian-14%20forky-a80030.svg)](https://www.debian.org/)
[![Python](https://img.shields.io/badge/python-3-green.svg)](https://www.python.org/)
[![GTK](https://img.shields.io/badge/GTK-4%20%2B%20libadwaita-orange.svg)](https://www.gtk.org/)
[![License](https://img.shields.io/badge/license-GPL--2.0-red.svg)](../LICENSE)
[![Language](https://img.shields.io/badge/language-FR%20%7C%20EN-yellow.svg)](translations/)

**KernelCustom Manager** est un gestionnaire complet de kernels Linux et de drivers GPU pour **Debian 14 « forky »**, avec une interface **GTK4 + libadwaita**, pour :
- 🔧 Compiler des kernels personnalisés et les installer en paquets `.deb`
- 🔒 Les faire démarrer avec SecureBoot (clé MOK, signature des modules et de vmlinuz)
- 🎮 Installer et gérer des drivers GPU (NVIDIA, AMD, Intel)
- 📂 Gérer les sources de `/usr/src` (pour DKMS)
- 💾 Créer des profils de configuration
- 📜 Suivre l'historique des compilations et des installations
- 🧹 Nettoyer le dossier de travail
- ⏮️ Effectuer des rollbacks de drivers en cas de problème

---

## ✨ Fonctionnalités Principales

L'interface est organisée en 9 onglets : **Kernels installés**, **Paquets locaux**, **Compiler**, **Pilotes GPU**, **SecureBoot**, **Sources système**, **Profils**, **Historique** et **Nettoyage**.

### 🔩 **Gestion des Kernels**
- Téléchargement des sources depuis kernel.org (dernière version stable proposée)
- Configuration à partir de la config du système ou d'un fichier, puis `make nconfig` (optionnel)
- Compilation multi-threadée dans un terminal, en paquets `.deb` (`make bindeb-pkg`), avec notification de fin
- Gestion des kernels installés (liste, suppression ; le kernel en cours d'exécution est protégé)
- Installation des paquets `.deb` compilés
- Profils pour sauvegarder et restaurer des configurations

### 📂 **Sources système**
- Installation ou liens des sources et headers dans `/usr/src` (pour DKMS)
- Suppression sécurisée (jamais de vrais headers Debian)

### 🧹 **Nettoyage** 🆕
- Inventaire de l'espace occupé : objets de compilation, archives, journaux, téléchargements, sources, paquets…
- Les sources et headers du kernel en cours d'exécution, et ceux utilisés par `/usr/src`, sont protégés

### 🎮 **Gestion des Drivers GPU**
- **Support multi-fabricants** : NVIDIA, AMD, Intel (AMD et Intel : pilotes libres Mesa + firmware des dépôts Debian)
- **Détection automatique** : GPU, distribution, serveur d'affichage (X11/Wayland)
- **Installation intelligente** :
  - Depuis les dépôts Debian (recommandé)
  - NVIDIA : depuis le site officiel avec web scraping dynamique (avancé)
  - Installation NVIDIA automatisée avec service systemd
- **Système de rollback** : Sauvegarde automatique avant installation
- **Historique complet** : Traçabilité de toutes les opérations
- **Interface à 3 onglets** : Installation, Historique, Rollback

### 🔒 **Gestion SecureBoot**
- **Assistant** : diagnostic complet (UEFI, SecureBoot, clé MOK, signatures des modules, de l'initrd et de vmlinuz) et bouton pour corriger
- **Détection automatique** : Statut UEFI et SecureBoot
- **Gestion des clés MOK** :
  - Lister les clés enrollées
  - Importer/Supprimer des clés
  - Réinitialisation complète
- **Signature** :
  - Génération d'une clé MOK RSA-2048
  - Signature des modules et de l'image vmlinuz d'un kernel installé
  - Signature manuelle de modules .ko
  - Vérification des signatures existantes
- **Automatisation intelligente** :
  - Signature des modules pendant la compilation (cochée par défaut si SecureBoot est actif et qu'une clé MOK existe)
  - Génération de clés à la demande
- **Interface à 5 onglets** : Assistant, Statut, Clés MOK, Signature, Historique

### 🛡️ **Sécurité**
- Aucun `sudo` ni `bash -c` : les opérations root passent par un **helper avec liste blanche d'actions**, autorisé par PolicyKit (voir [POLICYKIT_README](docs/POLICYKIT_README.md))
- Toutes les commandes sont lancées avec des listes d'arguments, jamais via un shell

### 🌍 **Multilingue**
- Français 🇫🇷
- Anglais 🇬🇧
- Changement de langue à la volée

---

## 📦 Installation

KernelCustom Manager est distribué sous forme de **paquet Debian** (Debian 14 « forky »).
Le paquet installe l'application, les helpers privilégiés, la policy PolicyKit,
le lanceur du menu et toutes les dépendances (outils de compilation, GTK4, libadwaita…).

### Construire et installer le paquet
```bash
sudo apt install git debhelper dh-python
git clone https://github.com/lpennisi73-tech/BOOKWORM.git
cd BOOKWORM/KernelCustomManager

dpkg-buildpackage -us -uc -b          # crée ../kernelcustom-manager_<version>_all.deb
sudo apt install ../kernelcustom-manager_*_all.deb
```

### Mettre à jour
Après un `git pull` (ou une modification du code), reconstruire puis réinstaller le paquet :
```bash
cd BOOKWORM/KernelCustomManager
rm -f ../kernelcustom-manager_*      # anciens paquets : un seul .deb doit correspondre au motif
dpkg-buildpackage -us -uc -b && sudo apt install ../kernelcustom-manager_*_all.deb
```

L'application est ensuite dans le menu (« KernelCustom Manager ») ou en ligne de commande :
```bash
kernelcustom-manager
```

### Désinstaller
```bash
sudo apt remove kernelcustom-manager   # garde vos données
sudo apt purge kernelcustom-manager    # supprime aussi /var/lib/kernelcustom-manager
```
Vos données (sources, paquets compilés, clés MOK) restent dans
`~/.local/share/kernelcustom-manager/` : supprimez ce dossier à la main si vous n'en avez plus besoin.

---

## 🚀 Démarrage Rapide

### 1. **Installer un Driver GPU**

```bash
# Lancer KernelCustom Manager (menu ou commande)
kernelcustom-manager

# Dans l'interface :
# 1. Aller dans l'onglet "Pilotes GPU"
# 2. Cliquer sur "🔄 Actualiser" pour détecter votre GPU
# 3. Choisir une méthode d'installation :
#    - Depuis dépôts (recommandé) : sélectionner un driver et cliquer "Installer"
#    - Depuis site officiel (avancé) : cliquer "Récupérer dernière version"
# 4. Redémarrer après installation
```

### 2. **Compiler un Kernel Personnalisé**

```bash
# 1. Aller dans l'onglet "Compiler"
# 2. Entrer une version (ex: 7.3.1)
# 3. Cliquer "📥 Télécharger"
# 4. Cliquer "⚙️ Configurer" (choisir config système)
# 5. Cliquer "🔨 Compiler le kernel" : la compilation s'ouvre dans un terminal
# 6. Attendre la notification de fin de compilation
# 7. Aller dans "Paquets locaux" et installer
```

### 3. **Créer une Sauvegarde de Driver**

```bash
# Dans l'onglet "Pilotes GPU" :
# 1. Cliquer sur "💾 Créer sauvegarde"
# 2. La sauvegarde est enregistrée dans ~/.local/share/kernelcustom-manager/drivers_backup/
# 3. Consulter l'onglet "⏮️ Rollback" pour voir toutes les sauvegardes
```

### 4. **Utiliser SecureBoot avec un Kernel Personnalisé** 🔒

```bash
# Première utilisation - Configuration initiale
# 1. Aller dans l'onglet "SecureBoot" → "🚀 Assistant"
# 2. Lire le diagnostic : si la clé MOK manque, cliquer "Démarrer l'Enrollment"
#    (la clé est créée dans ~/.local/share/kernelcustom-manager/secureboot/keys/MOK.der)
# 3. Redémarrer le système
# 4. Au boot, dans le MOK Manager : sélectionner "Enroll MOK", entrer le mot de passe, redémarrer

# Compiler un kernel signé
# 1. Aller dans l'onglet "Compiler", télécharger et configurer un kernel
# 2. Cliquer "🔨 Compiler le kernel" : "Signer pour SecureBoot" est coché par défaut
# 3. Installer le kernel compilé depuis "Paquets locaux"
# 4. AVANT de redémarrer : "SecureBoot" → "🚀 Assistant", actualiser le diagnostic,
#    puis "Re-signer les Modules" en cochant "Signer aussi les images vmlinuz"
#    (sans vmlinuz signé, shim refuse de démarrer le kernel)
```

---

## 📖 Documentation

- **[Guide Utilisateur](docs/USER_GUIDE.md)** - Instructions détaillées d'utilisation
- **[Guide Contributeur](docs/CONTRIBUTING.md)** - Comment contribuer au projet
- **[Architecture](docs/ARCHITECTURE.md)** - Structure du code et design
- **[PolicyKit et helpers](docs/POLICYKIT_README.md)** - Opérations privilégiées
- **[Changelog Debian](debian/changelog)** - Historique des versions du paquet

---

## 🏗️ Architecture

```
KernelCustomManager/
├── kernelcustom_manager.py         # Point d'entrée (Adw.Application)
├── bin/kernelcustom-manager        # Lanceur installé dans /usr/bin
├── core/                           # Logique métier (sans GTK)
│   ├── kernel_manager.py           # Kernels, profils, historique
│   ├── build_runner.py             # Compilation dans le terminal (script autonome)
│   ├── sources_manager.py          # Sources de /usr/src
│   ├── driver_manager.py           # Drivers GPU
│   ├── secureboot_manager.py       # SecureBoot, clés MOK, signatures
│   └── cleanup_manager.py          # Nettoyage du dossier de travail
├── gui/                            # Interface GTK4 + libadwaita
│   ├── main_window.py              # Fenêtre principale (table des 9 onglets)
│   ├── widgets.py                  # Widgets communs (listes, sections…)
│   └── *_tab.py                    # Un module par onglet
├── utils/                          # Utilitaires transverses
│   ├── paths.py                    # Tous les chemins (programme, données XDG)
│   ├── dialogs.py                  # Dialogues asynchrones, run_task (threads)
│   ├── i18n.py                     # Internationalisation
│   ├── pkexec_helper.py            # Seul point d'appel de pkexec
│   └── terminal.py                 # Ouverture d'un terminal
├── helpers/                        # Programmes root (pkexec), installés dans /usr/libexec
├── translations/                   # fr.json, en.json
├── data/                           # .desktop, icône, page de manuel
└── debian/                         # Paquet Debian
```

Détails techniques : [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## 🎯 Fonctionnalités Avancées

### 🤖 Installation NVIDIA Intelligente
KernelCustom Manager détecte automatiquement votre environnement graphique (X11/Wayland) et choisit la meilleure méthode d'installation :

- **X11/Wayland** : Crée un service systemd qui installe le driver au prochain redémarrage
- **TTY** : Installation directe sans redémarrage
- **Arrêt automatique** du display manager (gdm3/lightdm/sddm)
- **Auto-nettoyage** du service après installation

### 🌐 Web Scraping Dynamique
Les versions officielles sont récupérées en temps réel :
- **NVIDIA** : `https://download.nvidia.com/XFree86/Linux-x86_64/latest.txt`
- **AMD / Intel** : pilotes libres (Mesa + firmware) depuis les dépôts Debian uniquement

### 💾 Système de Rollback Professionnel
Avant chaque installation, KernelCustom Manager propose de créer une sauvegarde :
- Informations du driver actuel
- Liste des paquets installés
- Métadonnées système (distro, display server)
- Restauration 1-clic depuis l'interface

### 📜 Historique Complet
Toutes les opérations sont enregistrées :
```json
{
  "timestamp": "2025-10-28T14:30:00",
  "action": "install",
  "vendor": "NVIDIA",
  "driver_name": "nvidia-driver",
  "driver_version": "550.127.05",
  "source": "repository",
  "success": true,
  "display_server": "Wayland",
  "distro": "debian forky/sid"
}
```

### 🔒 SecureBoot Intelligent

#### Qu'est-ce que SecureBoot ?
SecureBoot est une fonctionnalité de sécurité UEFI qui empêche le chargement de code non signé au démarrage. Cela pose problème pour les kernels personnalisés, car leurs modules ne sont pas signés par défaut.

#### Solution KernelCustom Manager
KernelCustom Manager simplifie grandement ce processus complexe :

**🎯 Workflow automatisé :**
1. **Diagnostic** : l'assistant vérifie UEFI, SecureBoot, la clé MOK et les signatures des kernels personnalisés
2. **Génération de clé** : crée la clé MOK RSA-2048 si nécessaire
3. **Enrôlement guidé** : import de la clé, puis validation dans le MOK Manager au redémarrage
4. **Signature à la compilation** : les modules sont signés avant la création des paquets
5. **Signature après installation** : modules et vmlinuz du kernel installé, en une opération

**📊 Exemple de workflow complet :**
```bash
# 1. Vérification initiale
SecureBoot détecté comme activé ✅
→ Assistant : "Clé MOK non enrôlée" → Démarrer l'Enrollment
→ Clé générée : MOK.priv + MOK.der
→ Redémarrer → MOK Manager → Enroll MOK → mot de passe → Redémarrer

# 2. Compilation
"Signer pour SecureBoot" coché par défaut ✅
→ Modules signés avant make bindeb-pkg

# 3. Installation puis signature de vmlinuz
→ Assistant : "vmlinuz non signé" → Re-signer (avec vmlinuz)
→ Diagnostic tout vert : SecureBoot + Kernel personnalisé fonctionnels ✅
```

**🔐 Sécurité :**
- Clés stockées dans `~/.local/share/kernelcustom-manager/secureboot/keys/`
- Support des formats DER, PEM, CER
- Historique de toutes les opérations
- Pas de bypass des protections UEFI natives

**⚡ Fonctionnalités avancées :**
- Vérification du statut SecureBoot (3 méthodes de détection)
- Gestion complète des clés MOK (liste, import, suppression, reset)
- Signature manuelle de modules individuels
- Vérification des signatures existantes
- Support des kernels avec suffixes personnalisés

---

## 🔧 Configuration

### Variables d'Environnement
```bash
# Dossier de travail (par défaut : ~/.local/share/kernelcustom-manager)
export XDG_DATA_HOME="/chemin/personnalisé"   # → $XDG_DATA_HOME/kernelcustom-manager
export KCM_DATA_DIR="/chemin/exact"           # chemin exact (prioritaire, utile pour les tests)

# Préférences (langue) : ~/.config/kernelcustom-manager (ou $XDG_CONFIG_HOME)

# Langue (par défaut : système)
export LANG=fr_FR.UTF-8  # ou en_US.UTF-8
```

### Fichiers de Configuration

> Depuis la v3.0, le dossier `~/KernelCustomManager/build` des versions précédentes est **déplacé automatiquement** au premier lancement. Les liens symboliques internes sont mis à jour. Si des liens de `/usr/src` (DKMS) pointaient vers l'ancien dossier, un lien de compatibilité est conservé à l'ancien emplacement.

```
~/.local/share/kernelcustom-manager/
├── configs/                  # Configurations kernel sauvegardées
├── profiles/                 # Profils utilisateur
├── drivers_backup/           # Sauvegardes de drivers
├── sources/                  # Sources des kernels téléchargés
├── linux -> sources/linux-X.Y.Z   # Arbre de compilation actif
├── kernels_repo/             # Paquets .deb compilés
├── logs/                     # Journaux de compilation et de l'application
├── archive/                  # Archives téléchargées
├── secureboot/               # Dossier SecureBoot
│   ├── keys/                 # Clés de signature générées
│   ├── backups/              # Sauvegardes de clés
│   └── secureboot_history.json  # Historique des opérations SecureBoot
├── drivers_history.json      # Historique des opérations drivers
└── compilation_history.json  # Historique des compilations
```

---

## 🤝 Contribution

Les contributions sont les bienvenues ! Consultez [CONTRIBUTING.md](docs/CONTRIBUTING.md) pour :
- Signaler des bugs
- Proposer des fonctionnalités
- Soumettre des pull requests
- Tester sur différents matériels

### 🙏 Contributeurs Recherchés
Nous cherchons des testeurs avec :
- **GPU NVIDIA** : RTX 4000/3000, GTX 1000 series
- **GPU AMD** : Radeon RX 7000/6000, Vega
- **GPU Intel** : Iris Xe, Arc A-series
- **Distribution** : Debian 14 (Forky)

---

## 📊 Comparaison avec Autres Outils

| Fonctionnalité | KernelCustom Manager | nvidia-detect | Driver Manager | nvidia-settings |
|----------------|---------------------|----------------|----------------|-----------------|
| Support NVIDIA | ✅ Complet | ✅ Basique | ✅ Basique | ✅ Config uniquement |
| Support AMD | ✅ Complet | ❌ | ✅ Basique | ❌ |
| Support Intel | ✅ Complet | ❌ | ❌ | ❌ |
| Web Scraping | ✅ Temps réel | ❌ | ❌ | ❌ |
| Rollback | ✅ Professionnel | ❌ | ❌ | ❌ |
| Historique | ✅ Complet | ❌ | ❌ | ❌ |
| Installation Wayland | ✅ Automatique | ⚠️ Manuel | ⚠️ Manuel | ⚠️ Manuel |
| Compilation Kernel | ✅ Intégré | ❌ | ❌ | ❌ |
| Gestion SecureBoot | ✅ Automatique | ❌ | ❌ | ❌ |
| Signature modules | ✅ Intégré | ❌ | ❌ | ❌ |
| Interface | ✅ GTK4 + libadwaita | 🖥️ CLI | ✅ GTK basique | ✅ Qt |

---

## ⚠️ Avertissements

### Drivers depuis Sites Officiels
L'installation depuis le site officiel NVIDIA est une **opération avancée** :
- Peut nécessiter un redémarrage en mode console
- Peut causer des problèmes de compatibilité
- Complique les mises à jour automatiques
- **L'installation depuis les dépôts Debian (section non-free) est recommandée**

### Compilation de Kernels
La compilation de kernels personnalisés :
- Nécessite ~20 GB d'espace disque
- Prend 30-90 minutes selon votre CPU
- Peut rendre le système non bootable si mal configuré
- **Créez toujours un point de restauration avant**

### SecureBoot et Kernels Personnalisés
Utilisation de kernels personnalisés avec SecureBoot activé :
- **Nécessite** la signature des modules kernel
- **KernelCustom Manager simplifie** grandement ce processus
- **Première utilisation** : génération de clés + import dans MOK Manager
- **Compilations suivantes** : signature automatique
- **IMPORTANT** : Ne désactivez jamais SecureBoot sans comprendre les implications de sécurité

---

## 🐛 Dépannage

### L'application ne se lance pas
```bash
# Lancer depuis un terminal pour voir les erreurs
kernelcustom-manager

# Vérifier les dépendances
python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')"

# Consulter le journal de l'application
less ~/.local/share/kernelcustom-manager/logs/kernelcustom-manager.log
```

### Le driver NVIDIA ne s'installe pas
```bash
# Vérifier que nouveau est désactivé
lsmod | grep nouveau

# Vérifier le display server
echo $XDG_SESSION_TYPE

# Consulter les logs
journalctl -u kernelcustom-nvidia-install.service
```

### Erreur de compilation kernel
```bash
# Vérifier l'espace disque
df -h ~/.local/share/kernelcustom-manager/

# Les dépendances de compilation sont installées avec le paquet ; pour les réinstaller :
sudo apt install --reinstall kernelcustom-manager

# Consulter le log
less ~/.local/share/kernelcustom-manager/logs/compile-AAAAMMJJ-HHMMSS.log
```

### Problèmes avec SecureBoot
```bash
# Vérifier le statut SecureBoot
mokutil --sb-state

# Lister les clés MOK enrollées
mokutil --list-enrolled

# Vérifier qu'un module est signé
modinfo -F sig_id /path/to/module.ko

# Réinstaller les dépendances SecureBoot
sudo apt install --reinstall mokutil openssl

# Consulter l'historique SecureBoot
cat ~/.local/share/kernelcustom-manager/secureboot/secureboot_history.json

# Emplacement des clés générées
ls -la ~/.local/share/kernelcustom-manager/secureboot/keys/

# Si le kernel personnalisé ne boot pas avec SecureBoot activé
# (démarrer sur le kernel Debian depuis "Options avancées" dans GRUB)
# 1. Vérifier que vmlinuz est signé : sbverify --list /boot/vmlinuz-VERSION
# 2. Vérifier que les modules sont signés : /usr/sbin/modinfo -F signer /lib/modules/VERSION/kernel/fs/mbcache.ko
# 3. Vérifier que la clé MOK est bien enrôlée : mokutil --list-enrolled
# 4. Vérifier les logs du kernel : journalctl -k -b -1 | grep -i signature
```

---

## 📝 License

Ce projet est sous licence **GPL-2.0**. Voir le fichier [LICENSE](../LICENSE) pour plus de détails.

---

## 🔗 Liens

- **Dépôt Git** : https://github.com/lpennisi73-tech/BOOKWORM.git
- **Issues** : Contactez le mainteneur
- **Documentation** : [docs/](docs/)
- **Changelog** : [debian/changelog](debian/changelog)

---

## 👤 Auteur

**BOOKWORM** - Développeur principal

Avec l'aide de **Claude AI** (Anthropic) pour :
- Module de gestion des drivers GPU v2.2
- Module de gestion SecureBoot v2.3
- Portage v3.0 : GTK4 + libadwaita, helpers en Python, paquet Debian

---

## 🌟 Remerciements

- La communauté Linux pour les outils open source
- Les mainteneurs de GTK, libadwaita et Python GObject
- NVIDIA, AMD, et Intel pour la documentation des drivers
- Tous les contributeurs et testeurs

---

## 📅 Historique des Versions

### v3.0 (2026-11-01) - GTK4 + paquet Debian 📦
- 🎨 **Interface GTK4 + libadwaita** : fenêtre adaptative, dialogues asynchrones, notifications de bureau
- 📦 **Paquet Debian** `kernelcustom-manager` (remplace `install.sh`), vérifié par lintian
- 🛡️ **Sécurité** : helpers root en Python avec liste blanche d'actions, plus aucun `sudo`, `bash -c` ni `shell=True`
- 🐍 **Tout en Python** : compilation, sources `/usr/src` et SecureBoot (fin des scripts bash)
- 🧹 **Nouvel onglet Nettoyage**
- 🔒 **SecureBoot** : assistant de diagnostic, signature de vmlinuz, signature à la compilation réactivée
- 📁 **Dossier de travail XDG** `~/.local/share/kernelcustom-manager` (migration automatique de `~/KernelCustomManager/build`)
- 🎯 **Debian 14 uniquement** : support d'Ubuntu et des autres distributions retiré, AMD via les dépôts Debian
- 🐛 Corrections : compilation qui ne se lançait pas avec la signature, notifications invisibles, modules signés vus comme non signés, validation du nom des profils

### v2.3 (2025-12-05) - SecureBoot Edition 🔒
- ✨ **Module SecureBoot complet** (1200+ lignes de code)
  - Détection automatique UEFI et SecureBoot
  - Gestion complète des clés MOK
  - Génération de clés de signature RSA-2048
  - Signature automatique des modules kernel
  - Intégration dans le workflow de compilation
  - Interface à 4 onglets
- 🤖 **Automatisation intelligente**
  - Proposition automatique de signature si SecureBoot activé
  - Génération de clés à la demande
  - Workflow guidé pour l'enrollment MOK
- 🌍 50+ nouvelles traductions (FR/EN)

### v2.2 (2025-10-28) - Professional Edition 🚀
- ✨ **Module Drivers GPU complet** (2886 lignes de code)
  - Support NVIDIA, AMD, Intel
  - Web scraping dynamique
  - Installation intelligente avec systemd
  - Système de rollback professionnel
  - Historique des opérations
  - Interface à 3 onglets
- 🌐 Détection automatique distribution et display server
- 💾 Système de sauvegarde/restauration
- 🌍 90+ traductions ajoutées (FR/EN)

### v2.1
- 🔧 Support PolicyKit
- 🌍 Support multilingue (FR/EN)
- 🎨 Interface améliorée

### v2.0
- 🚀 Version initiale publique
- 🔩 Compilation et gestion de kernels
- 📦 Installation de paquets locaux
- 💾 Système de profils

---

**⭐ Si vous trouvez ce projet utile, n'hésitez pas à le partager !**

**🎥 Une vidéo de démonstration sera bientôt disponible sur notre chaîne !**
