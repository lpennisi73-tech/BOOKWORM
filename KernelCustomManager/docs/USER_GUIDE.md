# KernelCustom Manager - User Guide

Complete guide for using KernelCustom Manager Professional Edition v2.2

## Table of Contents
- [Getting Started](#getting-started)
- [GPU Driver Management](#gpu-driver-management)
- [Kernel Compilation](#kernel-compilation)
- [Kernel Management](#kernel-management)
- [Local Packages](#local-packages)
- [Configuration Profiles](#configuration-profiles)
- [System Sources](#system-sources)
- [History](#history)
- [Troubleshooting](#troubleshooting)

---

## Getting Started

### First Launch

1. **Launch the application**:
```bash
cd KernelCustomManagerENGUI/KernelCustomManager
python3 kernelcustom_manager.py
```

2. **Language Selection**:
   - The application detects your system language automatically
   - Supported: French (Français) and English
   - Change language via the menu if needed

3. **Main Interface**:
   - The application uses a tabbed interface
   - Each tab represents a different feature
   - Privileged operations will prompt for your password via PolicyKit

### System Requirements

- Ubuntu 22.04/24.04 or Debian 11/12/13
- Python 3.8 or newer
- GTK 3.0
- At least 20 GB free disk space (for kernel compilation)
- Internet connection (for downloading kernels/drivers)

---

## GPU Driver Management

### Overview
The GPU Drivers tab allows you to install, manage, and roll back GPU drivers for NVIDIA, AMD, and Intel graphics cards.

### Features
- 🔍 Automatic GPU detection
- 📦 Installation from Ubuntu/Debian repositories (recommended)
- 🌐 Installation from official websites (advanced)
- 💾 Backup and rollback system
- 📜 Complete operation history
- 🖥️ X11/Wayland support

---

### 1. Detecting Your GPU

**Steps:**
1. Go to the **"GPU Drivers"** tab
2. Click **"🔄 Refresh"** button
3. The system will display:
   - **Detected GPU**: Your graphics card model
   - **Current driver**: The driver currently in use
   - **Distribution**: Your Ubuntu/Debian version
   - **Display Server**: X11 or Wayland

**What you'll see:**
```
Detected GPU: NVIDIA GeForce RTX 3060
Current driver: nvidia-driver-535 (535.183.01)
Distribution: ubuntu 24.04 (noble)
Display Server: Wayland
```

**Troubleshooting:**
- If no GPU is detected, check: `lspci | grep -i vga`
- If driver version is unknown, run: `nvidia-smi` (NVIDIA) or `glxinfo | grep "OpenGL version"` (AMD/Intel)

---

### 2. Installing Drivers from Repositories (Recommended)

This is the **safest and easiest method** for most users.

**For NVIDIA:**
1. After clicking Refresh, available drivers appear in the **"Drivers from Repositories"** section
2. Look for drivers marked with **⭐ (recommended)**
3. Select a driver (e.g., `nvidia-driver-550`)
4. Click **"📥 Install from repositories"**
5. Confirm the installation dialog
6. If prompted, create a backup (recommended)
7. Wait for installation to complete
8. Reboot your system

**For AMD:**
1. Available drivers will show: `mesa-vulkan-drivers`, `xserver-xorg-video-amdgpu`
2. Select the driver
3. Click **"📥 Install from repositories"**
4. Reboot after installation

**For Intel:**
1. Intel drivers are usually pre-installed
2. Additional packages available: `intel-media-va-driver`, `mesa-vulkan-drivers`
3. Install if needed for improved video acceleration

**Advantages:**
- ✅ Stable and tested by Ubuntu/Debian
- ✅ Automatic updates via apt
- ✅ Easy to remove or change
- ✅ No risk of breaking your system

---

### 3. Installing Drivers from Official Sites (Advanced)

**⚠️ WARNING**: This method is for advanced users only!

**Why use this method?**
- You need the absolute latest driver version
- You need a specific driver not in repositories
- You're testing beta drivers

**Risks:**
- May require stopping your graphical session
- Can cause system instability
- Complicates future updates
- May not work with all kernel versions

**Steps for NVIDIA:**
1. Click **"🌐 Fetch Latest Version"** in the "Official Drivers" section
2. The application will scrape the NVIDIA website for the latest version
3. You'll see:
   ```
   Latest official version: 560.35.03
   Size: ~350 MB
   Date: 2024-10-15
   ```
4. Click **"⚠️ Download and install"**
5. Confirm the warning dialog
6. Choose whether to create a backup (strongly recommended!)
7. The application will:
   - Download the `.run` file
   - Detect if you're using X11/Wayland
   - On X11/Wayland: Create a systemd service for installation on next reboot
   - On TTY: Install directly
8. Reboot your system
9. After reboot, the driver will be installed automatically

**What happens during intelligent installation:**
```
🤖 NVIDIA Smart Installation

System detected: Wayland
Action: Creating systemd service

The driver will be installed on next reboot:
1. Display manager will be stopped
2. Driver will be installed
3. System will reboot automatically
4. Service will clean itself up

You can monitor with: journalctl -u kernelcustom-nvidia-install.service
```

**Steps for AMD:**
1. Click **"🌐 Fetch Latest Version"**
2. Application scrapes AMD website for the latest AMDGPU-PRO driver
3. Download and installation follow similar process to NVIDIA

**Intel Note:**
Intel drivers are open source and integrated into the kernel. Official website installation is not supported (not needed).

---

### 4. Creating Backups

Backups allow you to roll back to your previous driver if something goes wrong.

**Manual Backup:**
1. Go to **"GPU Drivers"** tab
2. Click **"💾 Create Backup"** button
3. Backup is saved with timestamp
4. Find it in: `~/KernelCustomManager/build/drivers_backup/`

**Automatic Backup:**
- Before installing a new driver, the application will prompt:
  ```
  Create a backup?

  It is recommended to create a backup of the current driver
  before installing a new one.

  This will allow you to roll back if there are issues.

  Do you want to create a backup now?
  ```
- Choose **Yes** to create backup automatically

**What's saved in a backup:**
```json
{
  "backup_id": "backup_20251028_143000",
  "timestamp": "2025-10-28T14:30:00",
  "gpu_vendor": "NVIDIA",
  "gpu_model": "GeForce RTX 3060",
  "driver_name": "nvidia-driver-535",
  "driver_version": "535.183.01",
  "packages": [
    "nvidia-driver-535",
    "nvidia-dkms-535",
    "nvidia-utils-535"
  ],
  "distro": "ubuntu 24.04",
  "display_server": "Wayland"
}
```

---

### 5. Rolling Back Drivers

If a new driver causes problems, you can restore a previous backup.

**Steps:**
1. Go to **"⏮️ Rollback"** tab
2. You'll see a list of all backups:
   ```
   Backup ID              Driver             Distribution
   backup_20251028_143000 nvidia-driver-535  ubuntu 24.04
   backup_20251027_091500 nvidia-driver-530  ubuntu 24.04
   ```
3. Select the backup you want to restore
4. Click **"⏮️ Restore Backup"**
5. Confirm the restoration dialog
6. The application will:
   - Remove current proprietary driver
   - Restore packages from backup
   - Revert to open source driver if needed
7. Reboot your system

**When to use rollback:**
- New driver causes crashes or freezes
- Performance is worse with new driver
- Compatibility issues with your applications
- Screen flickering or artifacts

---

### 6. Viewing Driver History

All driver operations are recorded for reference.

**Accessing History:**
1. Go to **"📜 History"** tab
2. View complete operation log

**What's recorded:**
- Date and time of operation
- Action (Installation, Removal, Rollback)
- Vendor (NVIDIA, AMD, Intel)
- Driver name and version
- Source (repository, official website, backup)
- Success/failure status
- Distribution and display server

**Example:**
```
Date                  Action        Vendor   Driver             Source        Status
2025-10-28 14:30:00  Installation  NVIDIA   nvidia-driver-550  repository    ✅ Success
2025-10-27 09:15:00  Installation  NVIDIA   nvidia-driver-535  repository    ✅ Success
2025-10-26 16:45:00  Removal       NVIDIA   nvidia-driver-530  -             ✅ Success
```

---

### 7. Removing Proprietary Drivers

You can return to open source drivers at any time.

**Steps:**
1. Click **"🗑️ Remove proprietary driver"** button
2. Confirm removal dialog
3. Optional: Create backup before removal
4. The application will remove all proprietary driver packages
5. Reboot

**What happens after removal:**
- **NVIDIA**: System uses `nouveau` open source driver
- **AMD**: System uses `radeon` or `amdgpu` open source driver
- **Intel**: No change (already uses open source drivers)

**When to remove:**
- Switching to open source drivers
- Troubleshooting graphics issues
- Preparing for kernel upgrade
- Selling/repurposing the computer

---

## Kernel Compilation

### Overview
Compile custom Linux kernels with your own configuration.

### Why Compile a Custom Kernel?
- Enable/disable specific features
- Optimize for your hardware
- Test bleeding-edge kernel versions
- Learn about kernel development
- Apply custom patches

---

### 1. Downloading Kernel Sources

**Steps:**
1. Go to **"Compile"** tab
2. Enter kernel version in the field (e.g., `6.11.1`)
3. Click **"📥 Download"**
4. Progress dialog appears showing download status
5. Click the **🔄** button to check for latest stable version

**Version formats:**
- Stable: `6.11.1`, `6.10.5`
- Latest: Click 🔄 button to auto-fill
- RC versions: `6.12-rc3` (release candidates)

**What's downloaded:**
- Source code tarball from kernel.org
- Extracted to: `~/KernelCustomManager/build/linux-X.X.X/`
- Size: ~1-2 GB

---

### 2. Configuring the Kernel

After downloading, you must configure the kernel before compilation.

**Configuration Methods:**

#### Method 1: Use Current System Config (Recommended)
1. Click **"⚙️ Configure"**
2. Select **"Current system config"**
3. Optionally check **"Run menuconfig afterwards"**
4. Click **"Configure"**

This copies your current working kernel config (`/boot/config-$(uname -r)`) as the base.

#### Method 2: Load a Custom .config File
1. Click **"⚙️ Configure"**
2. Select **"Load a .config file"**
3. Browse to your `.config` file
4. Optionally check **"Run menuconfig afterwards"**
5. Click **"Configure"**

#### Method 3: Import Configuration
1. Click **"📁 Import"**
2. Select a previously saved `.config` file
3. Configuration is loaded

**Using menuconfig:**
- Text-based configuration interface
- Navigate with arrow keys
- Space to select/deselect options
- `/` to search
- Save and exit when done

---

### 3. Compiling the Kernel

**Steps:**
1. Ensure kernel is downloaded and configured
2. Click **"🔨 Compile Kernel"**
3. Compilation options dialog appears:

**Compilation Options:**
```
Number of threads: [8]
  → Use CPU core count for fastest compilation
  → Example: 8 cores = 8 threads

Suffix (optional): [-custom]
  → Adds suffix to kernel version
  → Example: 6.11.1-custom
  → Leave empty for no suffix

☑ Use fakeroot (recommended)
  → Builds .deb packages without root privileges
  → Always recommended unless you have specific reasons

Estimated time: 30-90 minutes
```

4. Click **"🔨 Compile"**
5. Terminal window opens showing compilation progress
6. Wait for compilation to complete (grab a coffee!)

**Compilation output:**
```
=== KERNEL COMPILATION ===
Version: 6.11.1
Threads: 8
Suffix: -custom
Fakeroot: yes

Compilation will start...

[Compilation progress shows here]

✅ COMPILATION SUCCESSFUL!
Moving packages...
✓ linux-image-6.11.1-custom_6.11.1-custom-1_amd64.deb moved
✓ linux-headers-6.11.1-custom_6.11.1-custom-1_amd64.deb moved

Press Enter to close...
```

**Compiled packages location:**
`~/KernelCustomManager/build/packages/`

---

### 4. Installation After Compilation

**Steps:**
1. Go to **"Local Packages"** tab
2. Select your compiled kernel packages:
   - `linux-image-X.X.X`
   - `linux-headers-X.X.X` (optional but recommended)
3. Click **"📥 Install"**
4. Choose whether to install headers
5. Wait for installation
6. Reboot to use the new kernel

**Verifying installation:**
```bash
# After reboot
uname -r
# Should show: 6.11.1-custom
```

---

### 5. Troubleshooting Compilation

**Compilation fails immediately:**
- Check disk space: `df -h ~/KernelCustomManager/`
- Need ~20 GB free
- Install dependencies: `sudo apt install build-essential libncurses-dev bison flex libssl-dev libelf-dev`

**Compilation fails midway:**
- Check compilation log in terminal
- Common issues:
  - Missing dependencies
  - Invalid configuration
  - Corrupted source files

**"No kernel source found":**
- Download kernel first with **"📥 Download"** button

**"No configuration found":**
- Configure kernel first with **"⚙️ Configure"** button

---

## Kernel Management

### Overview
Manage installed kernels on your system.

### 1. Viewing Installed Kernels

**"Installed Kernels"** tab shows:
- Active kernel (highlighted in green)
- All installed kernel packages
- Version numbers
- Package sizes

**Columns:**
- **Package**: Package name
- **Version**: Kernel version
- **Size**: Disk space used

---

### 2. Removing Old Kernels

**Steps:**
1. Select a kernel from the list
2. Click **"🗑️ Remove"**
3. Confirm removal dialog showing packages to be removed:
   ```
   The following packages will be removed:

   • linux-image-6.10.5-generic
   • linux-headers-6.10.5-generic
   • linux-modules-6.10.5-generic

   This action is irreversible!
   ```
4. Click **OK** to proceed
5. Packages are removed

**Important:**
- ⚠️ You **cannot** remove the active kernel
- Keep at least 2 kernels for safety (current + fallback)
- Removes all associated packages automatically

---

### 3. Rebooting

**Quick reboot:**
1. Click **"🔄 Reboot"** button
2. Confirm reboot dialog
3. System reboots immediately

**Changing kernel at boot:**
- Hold **Shift** during boot to see GRUB menu
- Select **"Advanced options for Ubuntu"**
- Choose kernel version
- Press Enter to boot

---

## Local Packages

### Overview
Install locally compiled kernel packages or downloaded .deb files.

### Installing Packages

**Steps:**
1. Go to **"Local Packages"** tab
2. Packages list shows all `.deb` files in:
   - `~/KernelCustomManager/build/packages/`
3. Select packages to install (Ctrl+Click for multiple)
4. Click **"📥 Install"**
5. Optional: Check **"Also install headers"** if available
6. Installation proceeds

**What gets installed:**
- Selected kernel image
- Modules (automatically)
- Headers (if selected)

**After installation:**
- Reboot to use new kernel
- New kernel appears in GRUB menu

---

## Configuration Profiles

### Overview
Save and reuse kernel configurations across different compilation sessions.

### 1. Saving a Profile

**Steps:**
1. Configure a kernel (see [Configuring the Kernel](#2-configuring-the-kernel))
2. Go to **"Profiles"** tab
3. Click **"💾 Save"**
4. Enter profile details:
   ```
   Profile name: gaming
   Description: Optimized for gaming with low latency
   ```
5. Click **"💾 Save"**
6. Profile is saved

**Profile storage:**
`~/KernelCustomManager/build/profiles/gaming.json`

**What's saved:**
- Complete `.config` file
- Profile name and description
- Creation timestamp

---

### 2. Loading a Profile

**Steps:**
1. Download kernel sources first
2. Go to **"Profiles"** tab
3. Select a profile from the list
4. Click **"📂 Load"**
5. Confirm loading dialog
6. Configuration is applied to current kernel source

**When to use profiles:**
- Testing different configurations
- Maintaining separate configs for desktop/laptop
- Sharing configurations with others
- Quickly reverting to known-good configs

---

### 3. Managing Profiles

**Viewing profiles:**
The Profiles tab shows:
- **Name**: Profile identifier
- **Description**: What this profile is for
- **Date**: When it was created

**Deleting profiles:**
1. Select a profile
2. Click **"🗑️ Delete"**
3. Confirm deletion
4. Profile is permanently removed

---

## System Sources

### Overview
Manage kernel source code in `/usr/src/` for DKMS compatibility.

### Why Use This Feature?

**DKMS (Dynamic Kernel Module Support)** allows third-party drivers to be automatically recompiled for new kernels. Examples:
- VirtualBox modules
- NVIDIA proprietary drivers
- Third-party hardware drivers

DKMS looks for kernel sources in `/usr/src/linux-headers-X.X.X/`

---

### 1. Copying Sources to /usr/src/

**Steps:**
1. Compile a kernel first
2. Go to **"System Sources"** tab
3. In the **"Available Sources"** section, select a kernel version
4. Click **"📥 Copy to /usr/src/"**
5. Confirm the action:
   ```
   Copy kernel 6.11.1 sources to /usr/src/?

   This will take ~1-2 GB of disk space.
   ```
6. Enter your password (PolicyKit)
7. Sources are copied to `/usr/src/linux-headers-6.11.1/`

**When to do this:**
- After compiling a custom kernel
- Before installing DKMS-based drivers
- When third-party drivers fail to build

---

### 2. Creating Symbolic Links

**Simple Link:**
1. Select a kernel version from "Available Sources"
2. Click **"🔗 Simple symbolic link"**
3. Creates link: `/usr/src/linux → /usr/src/linux-headers-X.X.X`

**Link with Suffix (for DKMS):**
1. Click **"🔗 Link with suffix (DKMS)"**
2. Enter full version with suffix:
   ```
   Base version: 6.11.1
   Enter the full version with suffix
   (must match installed headers)

   Full version: 6.11.1-custom
   ```
3. Click **"Create link"**
4. Link created for DKMS compatibility

**Use cases:**
- DKMS expects specific header paths
- Custom kernels with suffixes need matching links
- Ensuring driver compatibility

---

### 3. Removing Sources

**Steps:**
1. In the **"Installed Sources"** section, select a kernel
2. Click **"🗑️ Remove"** button
3. Confirm removal:
   ```
   Remove kernel 6.10.5 sources from /usr/src/?

   This action is irreversible!
   ```
4. Sources are deleted from `/usr/src/`

**When to remove:**
- Cleaning up old kernel sources
- Freeing disk space
- Removing unused DKMS build environments

---

## History

### Overview
Track all kernel compilation operations.

### Viewing Compilation History

**"History"** tab shows:
- **Date**: When compilation occurred
- **Version**: Kernel version compiled
- **Suffix**: Custom suffix used (if any)
- **Duration**: How long compilation took
- **Status**: ✅ Success or ❌ Failed

**Example:**
```
Date                 Version   Suffix    Duration  Status
2025-10-28 14:30:00 6.11.1    -custom   45m 23s   ✅ Success
2025-10-27 09:15:00 6.10.5    -gaming   52m 10s   ✅ Success
2025-10-26 16:45:00 6.10.3              ❌ Failed
```

### Clearing History

**Steps:**
1. Click **"🗑️ Clear"** button
2. Confirm:
   ```
   Clear all compilation history?

   This action is irreversible.
   ```
3. History is cleared

**History storage:**
`~/KernelCustomManager/build/compilation_history.json`

---

## Troubleshooting

### Application Won't Start

**Check GTK dependencies:**
```bash
python3 -c "import gi; gi.require_version('Gtk', '3.0')"
```

If error, install:
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0
```

**Check permissions:**
```bash
ls -la ~/KernelCustomManager/build/
```

Fix if needed:
```bash
chmod -R 755 ~/KernelCustomManager/build/
```

---

### GPU Driver Issues

#### NVIDIA Driver Won't Install

**Check nouveau is blacklisted:**
```bash
lsmod | grep nouveau
```

If nouveau is loaded, blacklist it:
```bash
sudo bash -c "echo 'blacklist nouveau' > /etc/modprobe.d/blacklist-nouveau.conf"
sudo update-initramfs -u
sudo reboot
```

**Check installation service (if using systemd method):**
```bash
journalctl -u kernelcustom-nvidia-install.service
```

**Common errors:**
- "ERROR: Unable to load the kernel module"
  - Secure Boot may be enabled
  - Disable Secure Boot in BIOS or sign the module

- "ERROR: An NVIDIA kernel module 'nvidia' appears to already be loaded"
  - Reboot and try installation from TTY (Ctrl+Alt+F3)

#### AMD Driver Issues

**Check AMDGPU is loaded:**
```bash
lsmod | grep amdgpu
```

**Check OpenGL:**
```bash
glxinfo | grep "OpenGL renderer"
```

Should show your AMD GPU, not "llvmpipe" (software rendering).

#### Intel Driver Issues

Intel drivers rarely have issues as they're built into the kernel.

**Check driver:**
```bash
lsmod | grep -E "i915|xe"
```

**Update Mesa for better performance:**
```bash
sudo apt update
sudo apt install mesa-vulkan-drivers intel-media-va-driver
```

---

### Kernel Compilation Issues

#### Not Enough Disk Space

**Check available space:**
```bash
df -h ~/KernelCustomManager/
```

**Free up space:**
```bash
# Remove old compilation logs
rm ~/KernelCustomManager/build/logs/*.log

# Remove old kernel sources
rm -rf ~/KernelCustomManager/build/linux-*

# Remove old packages
rm ~/KernelCustomManager/build/packages/*.deb
```

#### Compilation Fails

**Check compilation log:**
```bash
ls -lt ~/KernelCustomManager/build/logs/
cat ~/KernelCustomManager/build/logs/compile_XXXXXXXX.log
```

**Common issues:**

1. **Missing dependencies:**
```bash
sudo apt install build-essential libncurses-dev bison flex libssl-dev libelf-dev
```

2. **Invalid kernel configuration:**
- Run `make menuconfig` and ensure config is valid
- Use system config as base instead of custom config

3. **Corrupted source files:**
- Delete source directory
- Re-download kernel

#### Kernel Won't Boot After Installation

**Boot into previous kernel:**
1. Reboot
2. Hold Shift to show GRUB menu
3. Select "Advanced options"
4. Choose previous working kernel
5. Boot

**Remove problematic kernel:**
1. Boot into working kernel
2. Open KernelCustom Manager
3. Remove the problematic kernel

**Recover from unbootable system:**
If GRUB doesn't show:
1. Boot from Ubuntu live USB
2. Mount your system partition
3. Chroot into it
4. Remove problematic kernel
5. Update GRUB

---

### PolicyKit Authentication Issues

**Password prompt doesn't appear:**
```bash
# Check PolicyKit is running
systemctl status polkit
```

**Permission denied errors:**
- Ensure your user is in sudo group:
```bash
groups $USER
```

Should include "sudo". If not:
```bash
sudo usermod -aG sudo $USER
```
Then log out and back in.

---

### Display Server Detection Issues

**Check what you're running:**
```bash
echo $XDG_SESSION_TYPE
```

Should show "x11" or "wayland".

**If detection fails:**
```bash
# Check environment
env | grep -E "WAYLAND|DISPLAY|XDG"

# Check running processes
ps aux | grep -E "wayland|Xorg"
```

---

### General Tips

1. **Always create backups** before major changes
2. **Keep at least 2 kernels** installed
3. **Test in a VM first** if possible
4. **Read error messages carefully**
5. **Check logs** in `~/KernelCustomManager/build/logs/`
6. **Monitor disk space** regularly
7. **Update system** before major operations: `sudo apt update && sudo apt upgrade`

---

## Advanced Usage

### Command Line Operations

While KernelCustom Manager is GUI-based, you can perform operations manually:

**Check installed kernels:**
```bash
dpkg -l | grep linux-image
```

**Remove kernel manually:**
```bash
sudo apt remove linux-image-6.10.5-generic
sudo apt autoremove
```

**Manually compile kernel:**
```bash
cd ~/KernelCustomManager/build/linux-6.11.1/
make -j$(nproc) bindeb-pkg
```

### Environment Variables

**Change build directory:**
```bash
export KERNELCUSTOM_BUILD_DIR="/path/to/custom/dir"
python3 kernelcustom_manager.py
```

**Force language:**
```bash
export LANG=fr_FR.UTF-8
python3 kernelcustom_manager.py
```

---

## FAQ

**Q: How much disk space do I need?**
A: At least 20 GB for kernel compilation, plus space for packages and backups.

**Q: How long does kernel compilation take?**
A: 30-90 minutes depending on CPU and configuration. Modern 8-core CPUs typically take 40-50 minutes.

**Q: Can I use custom kernel patches?**
A: Yes! Download source, apply patches manually, then use "⚙️ Configure" to load existing config.

**Q: Is it safe to remove old kernels?**
A: Yes, but keep at least 2 kernels: current and one fallback.

**Q: Should I install drivers from repositories or official sites?**
A: **Repositories** for most users (stable, easy updates). **Official sites** only if you need specific features or latest versions.

**Q: What happens if driver installation fails?**
A: Use the Rollback feature to restore your previous driver. If system won't boot, use TTY (Ctrl+Alt+F3) or boot from live USB.

**Q: Can I use this on other distributions?**
A: Designed for Ubuntu/Debian. May work on derivatives (Linux Mint, Pop!_OS) but not tested on Fedora, Arch, etc.

**Q: How do I report bugs?**
A: Contact the maintainer via https://git-srv.bookworm.ddns.net/BOOKWORM or see [CONTRIBUTING.md](CONTRIBUTING.md).

**Q: Can I contribute translations?**
A: Yes! See [CONTRIBUTING.md](CONTRIBUTING.md) for instructions on adding new languages.

---

## Getting Help

- **Documentation**: Read this guide and [ARCHITECTURE.md](ARCHITECTURE.md)
- **Issues**: Check existing issues at the project repository
- **Community**: Video demonstrations coming soon on the project channel
- **Contributions**: See [CONTRIBUTING.md](CONTRIBUTING.md) for how to help

---

**Enjoy using KernelCustom Manager!**

If you find this tool useful, consider contributing by testing on different hardware or improving documentation.
