# KernelCustom-Manager Fusion

Un outil complet et convivial pour compiler, packager et gérer des kernels Linux personnalisés. Conçu pour simplifier la compilation de kernels tant pour les débutants que pour les administrateurs systèmes expérimentés.

## 🚀 Fonctionnalités

- **Compilation automatisée** de kernels Linux avec packaging .deb
- **Installation automatique** des dépendances système
- **Gestion intelligente** des paquets générés (installation/suppression)
- **Sauvegarde automatique** avant modifications du système
- **Interface intuitive** avec menus interactifs
- **Support des suffixes** personnalisés pour vos kernels
- **Portabilité complète** - fonctionne partout où vous copiez le dossier

## 📋 Prérequis

- Système basé sur Debian/Ubuntu (support d'autres distributions en cours)
- Privilèges sudo
- Connexion internet pour télécharger les sources

## 🔧 Installation

1. Clonez ou téléchargez ce repository
2. Rendez le script exécutable :
   ```bash
   chmod +x KernelCustom-Manager-Fusion.sh
   ```
3. Lancez le script :
   ```bash
   ./KernelCustom-Manager-Fusion.sh
   ```

## 📖 Guide d'utilisation

### Premier lancement

1. **Installer les dépendances** (Option 4)
   - Installation automatique de tous les outils nécessaires
   - Détection automatique de votre distribution
   - Vérification de l'installation

### Compiler votre premier kernel

2. **Télécharger le kernel stable** (Option 3 → 1)
   - Détection automatique de la dernière version stable
   - Téléchargement et extraction automatiques

3. **Choisir la configuration** (Option 3 → 2)
   - Templates personnalisés
   - Configuration Debian actuelle
   - Configuration sauvegardée
   - Interface menuconfig pour personnalisation

4. **Lancer la compilation** (Option 3 → 3)
   - Détection automatique du nombre de cœurs
   - Suffixe personnalisé optionnel
   - Création automatique des paquets .deb

### Gérer vos kernels

5. **Installer un kernel** (Option 2 → 2)
   - Installation automatique des headers correspondants
   - Sauvegarde de sécurité avant installation

6. **Supprimer un kernel** (Option 1 → 2)
   - Protection contre la suppression du kernel actif
   - Suppression automatique des headers associés
   - Sauvegarde de sécurité avant suppression

## 📁 Structure du projet

```
KernelCustom/
├── kernels_repo/     # Paquets .deb générés
├── logs/            # Logs de compilation
├── archive/         # Sauvegardes de sécurité
├── sources/         # Sources des kernels
├── templates/       # Templates de configuration
└── script.sh        # Script principal
```

## ⚡ Fonctionnalités avancées

Optimisation des performances de compilation
KernelCustom-Manager propose un choix entre deux modes de compilation :

Mode compatibilité (avec fakeroot) : Garantit la compatibilité maximale et les bonnes permissions des paquets générés
Mode performance (sans fakeroot) : Jusqu'à 2x plus rapide grâce au parallélisme optimal

Temps de compilation observés (VM 8 cœurs, 8GB RAM) :

Avec fakeroot : ~3h15
Sans fakeroot : ~1h38 (gain de ~50%)
Recompilation après modification : ~11 minutes

Cette optimisation est particulièrement bénéfique dans les environnements virtualisés ou sur du matériel avec des ressources limitées.

### Installation automatique des dépendances

Le script installe automatiquement :
- **Essentiels** : build-essential, bc, bison, flex, libssl-dev, libelf-dev, libncurses-dev, fakeroot, dpkg-dev, libbpf-dev, dwarves, xz-utils, debhelper, git
- **Optionnels** : curl, wget, tar, gzip, jq, rsync, ccache

### Gestion intelligente des paquets

- **Installation** : Proposition automatique d'installer les headers avec l'image du kernel
- **Suppression** : Détection et suppression des headers correspondants
- **Protection** : Impossible de supprimer le kernel actuellement en cours d'utilisation

### Sauvegardes de sécurité

Avant chaque opération critique, le script crée automatiquement :
- Snapshots ZFS/Btrfs (si disponibles)
- Sauvegardes tar des fichiers critiques
- Sauvegardes stockées dans le dossier `archive/`



## 🎯 Cas d'usage

- **Développeurs** : Tester des patches ou fonctionnalités kernel
- **Administrateurs** : Déployer des kernels optimisés pour leur infrastructure
- **Étudiants** : Apprendre la compilation de kernels sans complexité
- **Enthusiastes** : Créer des kernels personnalisés pour leurs besoins

## 🛠️ Dépannage

### Erreurs de compilation
- Vérifiez l'espace disque disponible (>10GB recommandé)
- Vérifiez les dépendances avec l'option 4
- Consultez les logs dans le dossier `logs/`

### Problèmes de boot
- Les sauvegardes automatiques permettent un rollback rapide
- Le kernel précédent reste disponible dans GRUB

### Support des distributions
- Support natif : Debian, Ubuntu
- Support expérimental : Fedora, Arch, openSUSE
- Contribution communautaire bienvenue

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :
- Signaler des bugs
- Proposer des améliorations
- Ajouter le support d'autres distributions
- Améliorer la documentation

## 📄 Licence 

Ce projet est distribué sous licence libre pour encourager l'apprentissage et le partage dans la communauté GNU/Linux.

## 🙏 Remerciements

Développé pour démocratiser la compilation de kernels Linux et rendre accessible à tous une technologie habituellement réservée aux experts.

## 📺 Démonstration

## 🎥 Ma vidéo sur KernelCustom


[![Regarder sur YouTube](https://img.youtube.com/vi/NCacsn1uFr0/0.jpg)](https://youtu.be/NCacsn1uFr0)


---

**"Fini la galère de compilation de kernels !"**
