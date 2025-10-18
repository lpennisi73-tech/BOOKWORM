# KernelCustom Manager

**Linux Custom Kernel Compilation and Installation Manager**
*Professional Edition v2.2*

![Python](https://img.shields.io/badge/Python-3.6+-blue.svg)
![GTK](https://img.shields.io/badge/GTK-3.0-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 📋 Description

KernelCustom Manager is a comprehensive graphical interface for managing the entire lifecycle of custom Linux kernels: downloading, configuring, compiling, installing, and managing installed versions.

### ✨ Main Features

- **Automatic download** of kernel sources from kernel.org
- **Flexible configuration**: current system, custom files, or menuconfig
- **Optimized compilation** with multi-threading support
- **Complete management** of installed kernels (list, install, remove)
- **Reusable configuration profiles** (gaming, server, desktop, etc.)
- **Compilation history** with duration statistics
- **Automatic backup** of configurations
- **Import/Export** of .config files
- **System notifications** at the end of compilations
- **Automatic detection** of the latest stable version
- **Multi-language support** (English/French)

## 🚀 Installation

### Prerequisites

- Python 3.6 or higher
- GTK 3.0
- Compilation tools (gcc, make, etc.)

### Automatic Installation

```bash
# Clone or download the project
cd ~/KernelCustomManager

# Run the installation script
bash install.sh

# Or manually install dependencies
sudo apt install python3 python3-gi gir1.2-gtk-3.0 gir1.2-notify-0.7 \
                 build-essential bc bison flex libssl-dev libelf-dev \
                 libncurses-dev fakeroot dpkg-dev curl tar xz-utils
```

### Project Structure

```
KernelCustomManager/
├── kernelcustom_manager.py      # Main entry point
├── install.sh                   # Installation script
├── core/                        # Business logic
│   ├── __init__.py
│   └── kernel_manager.py
├── gui/                         # Graphical interface
│   ├── __init__.py
│   ├── main_window.py
│   ├── kernels_tab.py
│   ├── packages_tab.py
│   ├── build_tab.py
│   ├── build_tab_config.py
│   ├── build_tab_compile.py
│   ├── profiles_tab.py
│   ├── history_tab.py
│   └── sources_tab.py
├── utils/                       # Utilities
│   ├── __init__.py
│   ├── dialogs.py
│   └── i18n.py                  # Internationalization
├── translations/                # Translation files
│   ├── en.json
│   └── fr.json
└── build/                       # Working directory (created at first launch)
    ├── sources/                 # Downloaded kernel sources
    ├── linux -> sources/linux-X/ # Link to active version
    ├── kernels_repo/            # Compiled .deb packages
    ├── logs/                    # Compilation logs
    ├── configs/                 # Automatic backups
    ├── profiles/                # Configuration profiles
    └── compilation_history.json # History
```

## 📖 Usage

### Launch

```bash
cd ~/KernelCustomManager
./kernelcustom_manager.py
```

### Typical Workflow

#### 1. Download a kernel

1. Go to the **"Compile"** tab
2. The latest stable version is automatically detected
3. Click **"📥 Download"**
4. Wait for download and extraction

#### 2. Configure the kernel

**Option A: System config**
1. Click **"⚙️ Configure"**
2. Select **"Current system config"**
3. Check **"Launch menuconfig after"** if desired
4. Validate

**Option B: Custom profile**
1. Go to the **"Profiles"** tab
2. Select an existing profile
3. Click **"📂 Load"**

**Option C: Custom file**
1. Click **"📁 Import"**
2. Select your `.config` file

#### 3. Compile the kernel

1. Click **"🔨 Compile Kernel"**
2. Configure options:
   - **Threads**: number of CPU cores (automatically detected)
   - **Suffix**: custom identifier (e.g., `-custom`, `-gaming`)
   - **Fakeroot**: recommended for maximum compatibility
3. Start compilation
4. Follow progress in the terminal
5. A notification appears at the end

#### 4. Install the compiled kernel

1. Go to the **"Local Packages"** tab
2. Select the package to install
3. Click **"📥 Install"**
4. Choose whether to install headers (recommended for DKMS)
5. Enter your password (multiple times for security)
6. Restart the system

#### 5. Manage installed kernels

**List:**
- **"Installed Kernels"** tab
- The active kernel is marked with **✓**

**Remove:**
1. Select a kernel (except the active one)
2. Click **"🗑️ Remove"**
3. Confirm (removes image + headers automatically)

**Reboot:**
- **"🔄 Reboot"** button available

## 🌐 Language Selection

The application supports multiple languages. Use the language selector (🌐) in the top-right corner of the window to switch between:
- **English**
- **Français**

The language preference is saved and will persist between sessions. Restart the application after changing the language.

## 🔧 Advanced Features

### Configuration Profiles

Profiles allow you to save and reuse configurations:

1. **Create a profile**
   - Configure the kernel as desired
   - **"Profiles"** tab → **"💾 Save"**
   - Give it a name (e.g., "gaming", "server", "desktop")
   - Add an optional description

2. **Use a profile**
   - **"Profiles"** tab
   - Select the profile
   - **"📂 Load"**

### Compilation History

The **"History"** tab keeps:
- Date and time of compilation
- Kernel version
- Suffix used
- Compilation duration
- Status (success/failed)
- Generated packages

Limit: Last 50 compilations

### Import/Export Configurations

**Export:**
- Save your current `.config`
- Share with other users
- Version your configurations

**Import:**
- Load a config from another system
- Use community configs
- Restore an old configuration

## ⚙️ Configuration

### Customizing the Working Directory

Default: `~/KernelCustomManager/build/`

To change, modify `core/kernel_manager.py` line 18:

```python
def __init__(self, base_dir=None):
    if base_dir is None:
        self.base_dir = Path("/your/custom/path")
    else:
        self.base_dir = Path(base_dir)
```

### Compilation Options

**Threads:**
- Default: number of detected CPU cores
- Recommendation: number of cores for fast compilation
- Maximum: number of cores × 2

**Suffix:**
- Optional
- Format: `-name` (dash + lowercase/numbers)
- Examples: `-custom`, `-gaming`, `-server`

**Fakeroot:**
- ✅ Recommended: maximum compatibility
- ❌ Without: ~2× faster, but may fail on some configs

## 🐛 Troubleshooting

### Download fails

**Checks:**
```bash
# Connectivity
ping kernel.org

# Disk space
df -h ~/KernelCustomManager

# Permissions
ls -la ~/KernelCustomManager/build/sources/
```

### Compilation fails

**Common causes:**
1. **Missing dependencies**
   ```bash
   sudo apt install build-essential bc bison flex libssl-dev libelf-dev libncurses-dev
   ```

2. **Invalid configuration**
   - Relaunch menuconfig
   - Check error messages in the log

3. **Insufficient disk space**
   - Required: ~20-30 GB for sources + compilation

**Logs:**
```bash
# View the latest log
ls -lt ~/KernelCustomManager/build/logs/
tail -100 ~/KernelCustomManager/build/logs/compile-*.log
```

### "Active kernel" error

You cannot remove the kernel you are currently booted on.

**Solution:**
1. Reboot to another kernel (GRUB menu)
2. Remove the old kernel
3. Reboot to the desired kernel

### Notifications not working

```bash
# Check libnotify
sudo apt install libnotify-bin gir1.2-notify-0.7

# Test manually
notify-send "Test" "This is a test"
```

## 🔒 Security

### Authentication

The application uses **pkexec** (PolicyKit) for privileged operations:
- Package installation
- Kernel removal
- Each command asks for password separately

**This is normal and intended**: maximum security.

### Recommendations

- ✅ Always verify active kernel before removal
- ✅ Keep at least 2 working kernels
- ✅ Test new kernels before removing old ones
- ✅ Save important configs as profiles
- ❌ Do not run as root

## 📝 Logs and Data

### Locations

```bash
~/KernelCustomManager/build/
├── logs/                        # Compilation logs
├── configs/                     # Auto backups (.config)
├── profiles/                    # User profiles
└── compilation_history.json    # JSON history
```

### Cleanup

**Remove downloaded sources:**
```bash
rm -rf ~/KernelCustomManager/build/sources/linux-*
```

**Clean old logs:**
```bash
find ~/KernelCustomManager/build/logs/ -mtime +30 -delete
```

**Clear history:**
- **"History"** tab → **"🗑️ Clear"**

## 🤝 Contributing

### Report a bug

1. Check that the bug doesn't already exist
2. Provide:
   - Python version: `python3 --version`
   - Distribution: `cat /etc/os-release`
   - Relevant logs
   - Steps to reproduce

### Suggest a feature

Suggestions are welcome! Make sure they align with the project's goals.

## 📜 License

MIT License - Free to use, modify, and distribute.

## 🙏 Acknowledgments

- **Kernel.org** for the sources
- **GTK** for the interface framework
- **Debian Community** for the packaging system

## 📚 Resources

### Documentation

- [Kernel.org](https://www.kernel.org/)
- [Kernel Build Guide](https://kernelnewbies.org/KernelBuild)
- [GTK Documentation](https://docs.gtk.org/)

### Tutorials

- [Linux Kernel Configuration](https://wiki.archlinux.org/title/Kernel)
- [Desktop Optimization](https://wiki.gentoo.org/wiki/Kernel/Optimization)
- [DKMS and Modules](https://help.ubuntu.com/community/Kernel/DkmsDriverPackage)

## 📞 Support

For any questions or issues:
1. First consult the **Troubleshooting** section
2. Check logs in `build/logs/`
3. Open a ticket with all necessary information

---

**Happy developing!** 🐧🚀
