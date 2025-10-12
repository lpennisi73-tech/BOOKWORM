# KernelCustom Manager

**Gestionnaire de compilation et installation de kernels Linux personnalisés**  
*Édition Professionnelle v2.1*

![Python](https://img.shields.io/badge/Python-3.6+-blue.svg)
![GTK](https://img.shields.io/badge/GTK-3.0-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 📋 Description

KernelCustom Manager est une interface graphique complète pour gérer l'ensemble du cycle de vie des kernels Linux personnalisés : téléchargement, configuration, compilation, installation et gestion des versions installées.

### ✨ Fonctionnalités principales

- **Téléchargement automatique** des sources du kernel depuis kernel.org
- **Configuration flexible** : système actuel, fichiers personnalisés, ou menuconfig
- **Compilation optimisée** avec gestion multi-thread
- **Gestion complète** des kernels installés (liste, installation, suppression)
- **Profils de configuration** réutilisables (gaming, serveur, desktop, etc.)
- **Historique des compilations** avec statistiques de durée
- **Sauvegarde automatique** des configurations
- **Import/Export** de fichiers .config
- **Notifications système** à la fin des compilations
- **Détection automatique** de la dernière version stable

## 🚀 Installation

### Prérequis

- Python 3.6 ou supérieur
- GTK 3.0
- Outils de compilation (gcc, make, etc.)

### Installation automatique

```bash
# Cloner ou télécharger le projet
cd ~/KernelCustomManager

# Lancer le script d'installation
bash install.sh

# Ou installation manuelle des dépendances
sudo apt install python3 python3-gi gir1.2-gtk-3.0 gir1.2-notify-0.7 \
                 build-essential bc bison flex libssl-dev libelf-dev \
                 libncurses-dev fakeroot dpkg-dev curl tar xz-utils
```

### Structure du projet

```
KernelCustomManager/
├── kernelcustom_manager.py      # Point d'entrée principal
├── install.sh                   # Script d'installation
├── core/                        # Logique métier
│   ├── __init__.py
│   └── kernel_manager.py
├── gui/                         # Interface graphique
│   ├── __init__.py
│   ├── main_window.py
│   ├── kernels_tab.py
│   ├── packages_tab.py
│   ├── build_tab.py
│   ├── build_tab_config.py
│   ├── build_tab_compile.py
│   ├── profiles_tab.py
│   └── history_tab.py
├── utils/                       # Utilitaires
│   ├── __init__.py
│   └── dialogs.py
└── build/                       # Répertoire de travail (créé au premier lancement)
    ├── sources/                 # Sources des kernels téléchargés
    ├── linux -> sources/linux-X/ # Lien vers version active
    ├── kernels_repo/            # Paquets .deb compilés
    ├── logs/                    # Logs de compilation
    ├── configs/                 # Sauvegardes automatiques
    ├── profiles/                # Profils de configuration
    └── compilation_history.json # Historique
```

## 📖 Utilisation

### Lancement

```bash
cd ~/KernelCustomManager
./kernelcustom_manager.py
```

### Workflow typique

#### 1. Télécharger un kernel

1. Aller dans l'onglet **"Compiler"**
2. La dernière version stable est détectée automatiquement
3. Cliquer sur **"📥 Télécharger"**
4. Attendre le téléchargement et l'extraction

#### 2. Configurer le kernel

**Option A : Config système**
1. Cliquer sur **"⚙️ Configurer"**
2. Sélectionner **"Config système actuelle"**
3. Cocher **"Lancer menuconfig après"** si désiré
4. Valider

**Option B : Profil personnalisé**
1. Aller dans l'onglet **"Profils"**
2. Sélectionner un profil existant
3. Cliquer sur **"📂 Charger"**

**Option C : Fichier personnalisé**
1. Cliquer sur **"📁 Importer"**
2. Sélectionner votre fichier `.config`

#### 3. Compiler le kernel

1. Cliquer sur **"🔨 Compiler le kernel"**
2. Configurer les options :
   - **Threads** : nombre de cœurs CPU (détecté automatiquement)
   - **Suffixe** : identifiant personnalisé (ex: `-custom`, `-gaming`)
   - **Fakeroot** : recommandé pour compatibilité maximale
3. Lancer la compilation
4. Suivre la progression dans le terminal
5. Une notification apparaît à la fin

#### 4. Installer le kernel compilé

1. Aller dans l'onglet **"Paquets locaux"**
2. Sélectionner le paquet à installer
3. Cliquer sur **"📥 Installer"**
4. Choisir d'installer les headers (recommandé pour DKMS)
5. Entrer votre mot de passe (plusieurs fois pour sécurité)
6. Redémarrer le système

#### 5. Gérer les kernels installés

**Lister :**
- Onglet **"Kernels installés"**
- Le kernel actif est marqué d'un **✓**

**Supprimer :**
1. Sélectionner un kernel (sauf celui actif)
2. Cliquer sur **"🗑️ Supprimer"**
3. Confirmer (supprime image + headers automatiquement)

**Redémarrer :**
- Bouton **"🔄 Redémarrer"** disponible

## 🔧 Fonctionnalités avancées

### Profils de configuration

Les profils permettent de sauvegarder et réutiliser des configurations :

1. **Créer un profil**
   - Configurer le kernel comme désiré
   - Onglet **"Profils"** → **"💾 Sauvegarder"**
   - Donner un nom (ex: "gaming", "serveur", "desktop")
   - Ajouter une description optionnelle

2. **Utiliser un profil**
   - Onglet **"Profils"**
   - Sélectionner le profil
   - **"📂 Charger"**

### Historique des compilations

L'onglet **"Historique"** conserve :
- Date et heure de compilation
- Version du kernel
- Suffixe utilisé
- Durée de compilation
- Statut (réussi/échoué)
- Paquets générés

Limite : 50 dernières compilations

### Import/Export de configurations

**Export :**
- Sauvegarder votre `.config` actuel
- Partager avec d'autres utilisateurs
- Versionner vos configurations

**Import :**
- Charger une config d'un autre système
- Utiliser des configs de la communauté
- Restaurer une ancienne configuration

## ⚙️ Configuration

### Personnalisation du répertoire de travail

Par défaut : `~/KernelCustomManager/build/`

Pour changer, modifier `core/kernel_manager.py` ligne 18 :

```python
def __init__(self, base_dir=None):
    if base_dir is None:
        self.base_dir = Path("/votre/chemin/personnalisé")
    else:
        self.base_dir = Path(base_dir)
```

### Options de compilation

**Threads :**
- Par défaut : nombre de cœurs CPU détecté
- Recommandation : nombre de cœurs pour compilation rapide
- Maximum : nombre de cœurs × 2

**Suffixe :**
- Optionnel
- Format : `-nom` (tiret + minuscules/chiffres)
- Exemples : `-custom`, `-gaming`, `-server`

**Fakeroot :**
- ✅ Recommandé : compatibilité maximale
- ❌ Sans : ~2× plus rapide, mais peut échouer sur certaines configs

## 🐛 Dépannage

### Le téléchargement échoue

**Vérifications :**
```bash
# Connectivité
ping kernel.org

# Espace disque
df -h ~/KernelCustomManager

# Permissions
ls -la ~/KernelCustomManager/build/sources/
```

### La compilation échoue

**Causes courantes :**
1. **Dépendances manquantes**
   ```bash
   sudo apt install build-essential bc bison flex libssl-dev libelf-dev libncurses-dev
   ```

2. **Configuration invalide**
   - Relancer menuconfig
   - Vérifier les messages d'erreur dans le log

3. **Espace disque insuffisant**
   - Besoin : ~20-30 Go pour sources + compilation

**Logs :**
```bash
# Consulter le dernier log
ls -lt ~/KernelCustomManager/build/logs/
tail -100 ~/KernelCustomManager/build/logs/compile-*.log
```

### Erreur "kernel actif"

Vous ne pouvez pas supprimer le kernel sur lequel vous êtes démarré.

**Solution :**
1. Redémarrer sur un autre kernel (menu GRUB)
2. Supprimer l'ancien kernel
3. Redémarrer sur le kernel désiré

### Notifications ne fonctionnent pas

```bash
# Vérifier libnotify
sudo apt install libnotify-bin gir1.2-notify-0.7

# Tester manuellement
notify-send "Test" "Ceci est un test"
```

## 🔒 Sécurité

### Authentification

L'application utilise **pkexec** (PolicyKit) pour les opérations privilégiées :
- Installation de paquets
- Suppression de kernels
- Chaque commande demande le mot de passe séparément

**C'est normal et voulu** : sécurité maximale.

### Recommandations

- ✅ Toujours vérifier le kernel actif avant suppression
- ✅ Garder au moins 2 kernels fonctionnels
- ✅ Tester les nouveaux kernels avant de supprimer les anciens
- ✅ Sauvegarder les configs importantes comme profils
- ❌ Ne pas exécuter en root

## 📝 Logs et données

### Emplacements

```bash
~/KernelCustomManager/build/
├── logs/                        # Logs de compilation
├── configs/                     # Sauvegardes auto (.config)
├── profiles/                    # Profils utilisateur
└── compilation_history.json    # Historique JSON
```

### Nettoyage

**Supprimer les sources téléchargées :**
```bash
rm -rf ~/KernelCustomManager/build/sources/linux-*
```

**Nettoyer les logs anciens :**
```bash
find ~/KernelCustomManager/build/logs/ -mtime +30 -delete
```

**Effacer l'historique :**
- Onglet **"Historique"** → **"🗑️ Effacer"**

## 🤝 Contribution

### Signaler un bug

1. Vérifier que le bug n'existe pas déjà
2. Fournir :
   - Version Python : `python3 --version`
   - Distribution : `cat /etc/os-release`
   - Logs pertinents
   - Étapes de reproduction

### Proposer une fonctionnalité

Les suggestions sont les bienvenues ! Assurez-vous qu'elles correspondent à l'objectif du projet.

## 📜 Licence

MIT License - Libre d'utilisation, modification et distribution.

## 🙏 Remerciements

- **Kernel.org** pour les sources
- **GTK** pour le framework d'interface
- **Communauté Debian** pour le système de packaging

## 📚 Ressources

### Documentation

- [Kernel.org](https://www.kernel.org/)
- [Guide de compilation du kernel](https://kernelnewbies.org/KernelBuild)
- [GTK Documentation](https://docs.gtk.org/)

### Tutoriels

- [Configuration du kernel Linux](https://wiki.archlinux.org/title/Kernel)
- [Optimisation pour desktop](https://wiki.gentoo.org/wiki/Kernel/Optimization)
- [DKMS et modules](https://help.ubuntu.com/community/Kernel/DkmsDriverPackage)

## 📞 Support

Pour toute question ou problème :
1. Consultez d'abord la section **Dépannage**
2. Vérifiez les logs dans `build/logs/`
3. Ouvrez un ticket avec toutes les informations nécessaires

---

**Bon développement !** 🐧🚀
