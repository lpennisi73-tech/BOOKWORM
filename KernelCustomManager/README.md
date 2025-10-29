# 🚀 KernelCustom Manager - Professional Edition v2.2

[![Version](https://img.shields.io/badge/version-2.2-blue.svg)](https://github.com/lpennisi73-tech/BOOKWORM.git)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![GTK](https://img.shields.io/badge/GTK-3.0-orange.svg)](https://www.gtk.org/)
[![License](https://img.shields.io/badge/license-GPL--3.0-red.svg)](LICENSE)
[![Language](https://img.shields.io/badge/language-FR%20%7C%20EN-yellow.svg)](translations/)

**KernelCustom Manager** est un gestionnaire complet de kernels Linux et de drivers GPU pour Ubuntu/Debian, offrant une interface graphique intuitive pour :
- 🔧 Compiler et gérer des kernels personnalisés
- 🎮 Installer et gérer des drivers GPU (NVIDIA, AMD, Intel)
- 💾 Créer des profils de configuration
- 📜 Suivre l'historique des installations
- ⏮️ Effectuer des rollbacks en cas de problème

---

## ✨ Fonctionnalités Principales

### 🔩 **Gestion des Kernels**
- Téléchargement automatique des sources kernel depuis kernel.org
- Configuration via menuconfig avec templates
- Compilation multi-threadée optimisée
- Gestion des kernels installés (liste, suppression)
- Installation de paquets .deb locaux
- Système de profils pour sauvegarder/restaurer configurations

### 🎮 **Gestion des Drivers GPU (v2.2)** 🆕
- **Support multi-fabricants** : NVIDIA, AMD, Intel
- **Détection automatique** : GPU, distribution, serveur d'affichage (X11/Wayland)
- **Installation intelligente** :
  - Depuis dépôts Ubuntu/Debian (recommandé)
  - Depuis sites officiels avec web scraping dynamique
  - Installation NVIDIA automatisée avec service systemd
- **Système de rollback** : Sauvegarde automatique avant installation
- **Historique complet** : Traçabilité de toutes les opérations
- **Interface à 3 onglets** : Installation, Historique, Rollback

### 🌍 **Multilingue**
- Français 🇫🇷
- Anglais 🇬🇧
- Changement de langue à la volée

---

## 📦 Installation

### Prérequis
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-notify-0.7

# Outils de compilation (pour kernels)
sudo apt install build-essential libncurses-dev bison flex libssl-dev libelf-dev
```

### Installation
```bash
# Cloner le dépôt
git clone https://github.com/lpennisi73-tech/BOOKWORM.git
cd KernelCustomManagerENGUI/KernelCustomManager

# Lancer l'application
python3 kernelcustom_manager.py
```

---

## 🚀 Démarrage Rapide

### 1. **Installer un Driver GPU**

```bash
# Lancer KernelCustom Manager
python3 kernelcustom_manager.py

# Dans l'interface :
# 1. Aller dans l'onglet "Drivers GPU"
# 2. Cliquer sur "🔄 Actualiser" pour détecter votre GPU
# 3. Choisir une méthode d'installation :
#    - Depuis dépôts (recommandé) : sélectionner un driver et cliquer "Installer"
#    - Depuis site officiel (avancé) : cliquer "Récupérer dernière version"
# 4. Redémarrer après installation
```

### 2. **Compiler un Kernel Personnalisé**

```bash
# 1. Aller dans l'onglet "Compiler"
# 2. Entrer une version (ex: 6.11.1)
# 3. Cliquer "📥 Télécharger"
# 4. Cliquer "⚙️ Configurer" (choisir config système)
# 5. Cliquer "🔨 Compiler le kernel"
# 6. Attendre la fin de la compilation
# 7. Aller dans "Paquets locaux" et installer
```

### 3. **Créer une Sauvegarde de Driver**

```bash
# Dans l'onglet "Drivers GPU" :
# 1. Cliquer sur "💾 Créer sauvegarde"
# 2. La sauvegarde est enregistrée dans ~/KernelCustomManager/build/drivers_backup/
# 3. Consulter l'onglet "⏮️ Rollback" pour voir toutes les sauvegardes
```

---

## 📖 Documentation

- **[Guide Utilisateur](docs/USER_GUIDE.md)** - Instructions détaillées d'utilisation
- **[Guide Contributeur](docs/CONTRIBUTING.md)** - Comment contribuer au projet
- **[Architecture](docs/ARCHITECTURE.md)** - Structure du code et design
- **[Changelog](CHANGELOG.md)** - Historique des versions

---

## 🏗️ Architecture

```
KernelCustomManager/
├── kernelcustom_manager.py         # Point d'entrée principal
├── core/                           # Logique métier
│   ├── kernel_manager.py           # Gestion des kernels
│   └── driver_manager.py           # Gestion des drivers GPU (v2.2)
├── gui/                            # Interface graphique GTK3
│   ├── main_window.py              # Fenêtre principale
│   ├── kernels_tab.py              # Onglet kernels installés
│   ├── packages_tab.py             # Onglet paquets locaux
│   ├── build_tab.py                # Onglet compilation
│   ├── drivers_tab.py              # Onglet drivers GPU (v2.2)
│   ├── profiles_tab.py             # Onglet profils
│   ├── history_tab.py              # Onglet historique
│   └── sources_tab.py              # Onglet sources système
├── utils/                          # Utilitaires
│   ├── dialogs.py                  # Dialogues helper
│   ├── i18n.py                     # Internationalisation
│   └── pkexec_helper.py            # Opérations privilégiées
└── translations/                   # Traductions
    ├── fr.json                     # Français
    └── en.json                     # Anglais
```

---

## 🎯 Fonctionnalités Avancées (v2.2)

### 🤖 Installation NVIDIA Intelligente
KernelCustom Manager détecte automatiquement votre environnement graphique (X11/Wayland) et choisit la meilleure méthode d'installation :

- **X11/Wayland** : Crée un service systemd qui installe le driver au prochain redémarrage
- **TTY** : Installation directe sans redémarrage
- **Arrêt automatique** du display manager (gdm3/lightdm/sddm)
- **Auto-nettoyage** du service après installation

### 🌐 Web Scraping Dynamique
Les versions officielles sont récupérées en temps réel :
- **NVIDIA** : `https://download.nvidia.com/XFree86/Linux-x86_64/latest.txt`
- **AMD** : URLs adaptatives selon votre distribution Ubuntu

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
  "driver_name": "nvidia-driver-550",
  "driver_version": "550.127.05",
  "source": "repository",
  "success": true,
  "display_server": "Wayland",
  "distro": "ubuntu 24.04"
}
```

---

## 🔧 Configuration

### Variables d'Environnement
```bash
# Dossier de travail (par défaut : ~/KernelCustomManager/build)
export KERNELCUSTOM_BUILD_DIR="/chemin/personnalisé"

# Langue (par défaut : système)
export LANG=fr_FR.UTF-8  # ou en_US.UTF-8
```

### Fichiers de Configuration
```
~/KernelCustomManager/build/
├── configs/                  # Configurations kernel sauvegardées
├── profiles/                 # Profils utilisateur
├── drivers_backup/           # Sauvegardes de drivers
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
- **Distributions** : Ubuntu 22.04/24.04, Debian 11/12, Linux Mint

---

## 📊 Comparaison avec Autres Outils

| Fonctionnalité | KernelCustom Manager | ubuntu-drivers | Driver Manager | nvidia-settings |
|----------------|---------------------|----------------|----------------|-----------------|
| Support NVIDIA | ✅ Complet | ✅ Basique | ✅ Basique | ✅ Config uniquement |
| Support AMD | ✅ Complet | ❌ | ✅ Basique | ❌ |
| Support Intel | ✅ Complet | ❌ | ❌ | ❌ |
| Web Scraping | ✅ Temps réel | ❌ | ❌ | ❌ |
| Rollback | ✅ Professionnel | ❌ | ❌ | ❌ |
| Historique | ✅ Complet | ❌ | ❌ | ❌ |
| Installation Wayland | ✅ Automatique | ⚠️ Manuel | ⚠️ Manuel | ⚠️ Manuel |
| Compilation Kernel | ✅ Intégré | ❌ | ❌ | ❌ |
| Interface | ✅ GTK3 moderne | 🖥️ CLI | ✅ GTK basique | ✅ Qt |

---

## ⚠️ Avertissements

### Drivers depuis Sites Officiels
L'installation depuis les sites officiels (NVIDIA.com, AMD.com) est une **opération avancée** :
- Peut nécessiter un redémarrage en mode console
- Peut causer des problèmes de compatibilité
- Complique les mises à jour automatiques
- **L'installation depuis les dépôts Ubuntu est recommandée**

### Compilation de Kernels
La compilation de kernels personnalisés :
- Nécessite ~20 GB d'espace disque
- Prend 30-90 minutes selon votre CPU
- Peut rendre le système non bootable si mal configuré
- **Créez toujours un point de restauration avant**

---

## 🐛 Dépannage

### L'application ne se lance pas
```bash
# Vérifier les dépendances
python3 -c "import gi; gi.require_version('Gtk', '3.0')"

# Vérifier les permissions
ls -la ~/KernelCustomManager/build/
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
df -h ~/KernelCustomManager/

# Vérifier les dépendances de compilation
sudo apt install build-essential libncurses-dev bison flex libssl-dev libelf-dev

# Consulter le log
cat ~/KernelCustomManager/build/logs/compile_XXXXXXXX.log
```

---

## 📝 License

Ce projet est sous licence **GPL-3.0**. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## 🔗 Liens

- **Dépôt Git** : https://github.com/lpennisi73-tech/BOOKWORM.git
- **Issues** : Contactez le mainteneur
- **Documentation** : [docs/](docs/)
- **Changelog** : [CHANGELOG.md](CHANGELOG.md)

---

## 👤 Auteur

**BOOKWORM** - Développeur principal

Avec l'aide de **Claude AI** (Anthropic) pour le module de gestion des drivers GPU v2.2

---

## 🌟 Remerciements

- La communauté Linux pour les outils open source
- Les mainteneurs de GTK3 et Python GObject
- NVIDIA, AMD, et Intel pour la documentation des drivers
- Tous les contributeurs et testeurs

---

## 📅 Historique des Versions

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
