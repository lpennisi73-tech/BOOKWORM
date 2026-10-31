# PolicyKit et helpers privilégiés

KernelCustom Manager ne lance jamais `sudo` ni `pkexec bash -c`. Toutes les opérations root
passent par **deux programmes Python** installés en `root:root` dans
`/usr/libexec/kernelcustom-manager/` et autorisés par PolicyKit.

| Programme | Action polkit | Authentification | Rôle |
|---|---|---|---|
| `kernelcustom-helper` | `com.kernelcustom.manager.helper` | `auth_admin_keep` (mot de passe mémorisé quelques minutes) | Liste blanche d'actions validées |
| `kernelcustom-nvidia-installer` | `com.kernelcustom.manager.nvidia` | `auth_admin` (**à chaque fois**) | Exécuter l'installeur NVIDIA `.run` (code tiers en root) |

## Actions de `kernelcustom-helper`

| Action | Validation |
|---|---|
| `apt-install [--update] PAQUET…` | noms de paquets Debian valides |
| `install-debs FICHIER.deb…` | fichiers appartenant à l'utilisateur, paquets `linux-image*`, `linux-headers*`, `linux-libc-dev*` uniquement |
| `remove-packages [--autoremove] PAQUET…` | noms valides, **refuse le kernel en cours d'exécution** |
| `reboot` | — |
| `mokutil-diagnose` | — (renvoie aussi `EFI_SHIM:` / `EFI_MOKMANAGER:` : la partition EFI n'est lisible que par root) |
| `mokutil-list-enrolled`, `mokutil-list-new` | — |
| `mokutil-import [--wait] CLÉ`, `mokutil-delete [--wait] CLÉ`, `mokutil-reset [--wait]` | clé `.der/.cer/.crt` appartenant à l'utilisateur |
| `sources-install SOURCES [--headers HEADERS]` | dossiers `linux-*` appartenant à l'utilisateur ; refuse d'écraser une entrée existante de `/usr/src` ; copie en `root:root` |
| `sources-link SOURCES VERSION [--headers HEADERS]` | idem ; crée `/usr/src/linux-VERSION`, `linux`, `linux-headers-VERSION`, `linux-headers` (refuse d'écraser un vrai dossier) |
| `sources-remove VERSION` | lien ou copie ; refuse un dossier appartenant à un paquet Debian ; **ne supprime jamais de vrais headers** (uniquement des liens) |
| `sign-kernel VERSION --sign-file … --key … --cert-der … [--cert-pem … --vmlinuz …] [--no-initramfs]` | version valide, `/lib/modules/VERSION` existe, `sign-file` appartient à root (ainsi que ses dossiers parents), clés appartenant à l'utilisateur appelant, vmlinuz dans `/boot` |

Règles du helper :
- **Autonome** : il n'importe aucun module de l'application (qui peut être dans un dossier modifiable par l'utilisateur) et s'exécute avec `python3 -I`.
- Aucune commande lancée via un shell, uniquement des listes d'arguments.
- Toute erreur de validation renvoie le code 2 avec `ERROR: …` sur stderr.

## Actions de `kernelcustom-nvidia-installer`

| Action | Rôle |
|---|---|
| `run FICHIER.run` | Copie le `.run` dans `/var/lib/kernelcustom-manager/nvidia/` (root, 0700) puis l'exécute (`--silent --no-questions`) |
| `schedule FICHIER.run` | Copie le `.run` puis active `kernelcustom-nvidia-install.service`, qui l'installe au prochain démarrage avant le gestionnaire d'affichage |
| `boot-install` | Appelé par le service systemd : arrête le gestionnaire d'affichage, installe, nettoie, redémarre |
| `cancel` | Annule une installation programmée |
| `uninstall` | Lance `/usr/bin/nvidia-uninstall --silent` (si présent et appartenant à root) |

## Installation (depuis le dépôt)

```bash
./install.sh            # installe dépendances, helpers et policy
./uninstall-policykit.sh
```

Équivalent manuel :
```bash
sudo install -d -m 0755 /usr/libexec/kernelcustom-manager
sudo install -m 0755 helpers/kernelcustom-helper helpers/kernelcustom-nvidia-installer /usr/libexec/kernelcustom-manager/
sudo install -m 0644 com.kernelcustom.manager.policy /usr/share/polkit-1/actions/
```

> ⚠️ Après toute modification de `helpers/*`, il faut **réinstaller** les helpers : l'application utilise toujours la copie installée dans `/usr/libexec`, jamais celle du dépôt.

## Vérification

```bash
pkaction --verbose --action-id com.kernelcustom.manager.helper
pkexec /usr/libexec/kernelcustom-manager/kernelcustom-helper mokutil-diagnose
```

## Côté application

`utils/pkexec_helper.py` (`PkexecHelper`) est le **seul** endroit qui appelle `pkexec`.
`run()` attend la fin et renvoie `(succès, stdout, erreur)`. `stream()` lit la sortie ligne par ligne, par exemple pour la progression de `sign-kernel`. Les codes 126 et 127 de pkexec (authentification annulée ou refusée) sont traduits en messages lisibles.
