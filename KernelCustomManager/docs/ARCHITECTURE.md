# KernelCustom Manager - Architecture Documentation

Technical documentation explaining the design, structure, and implementation of KernelCustom Manager.

## Table of Contents
- [Overview](#overview)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Core Components](#core-components)
- [GUI Components](#gui-components)
- [Data Flow](#data-flow)
- [Design Patterns](#design-patterns)
- [Key Features Implementation](#key-features-implementation)
- [Security Considerations](#security-considerations)
- [Performance Optimizations](#performance-optimizations)
- [Future Improvements](#future-improvements)

---

## Overview

KernelCustom Manager is a **desktop application** built with Python and GTK 3.0, designed to manage Linux kernel compilation and GPU driver installation on Ubuntu/Debian systems.

### Design Philosophy
1. **User-Friendly**: Complex operations made simple through GUI
2. **Safety-First**: Confirmation dialogs, backups, rollback capabilities
3. **Modular**: Clear separation between business logic and UI
4. **Extensible**: Easy to add new features or GPU vendors
5. **Transparent**: User always knows what's happening (progress dialogs, logs)

---

## Technology Stack

### Core Technologies
```
Python 3.8+
├── GTK 3.0 (via PyGObject)          # GUI framework
├── GLib                              # Event loop, threading
└── PolicyKit (pkexec)                # Privilege elevation

System Integration
├── dpkg/apt                          # Package management
├── systemd                           # Service management (NVIDIA installation)
├── lspci                             # Hardware detection
└── /proc, /sys                       # Kernel interfaces
```

### Key Libraries
- **gi (PyGObject)**: Python bindings for GTK
- **pathlib**: Modern file path handling
- **json**: Configuration and history storage
- **subprocess**: External command execution
- **urllib**: Web scraping for latest driver versions
- **threading**: Non-blocking operations

---

## Project Structure

```
KernelCustomManager/
├── kernelcustom_manager.py         # Entry point (80 lines)
│   └── Initializes I18n, DriverManager, MainWindow
│
├── core/                           # Business Logic Layer
│   ├── kernel_manager.py           # Kernel operations (900+ lines)
│   │   ├── Download kernels from kernel.org
│   │   ├── Compile with make
│   │   ├── Manage installed kernels
│   │   └── Profile management
│   │
│   └── driver_manager.py           # GPU driver operations (2886 lines) ⭐
│       ├── GPU detection (NVIDIA/AMD/Intel)
│       ├── Distribution detection
│       ├── Display server detection
│       ├── Repository driver listing
│       ├── Web scraping (NVIDIA/AMD official sites)
│       ├── Smart installation (systemd for X11/Wayland)
│       ├── Backup/rollback system
│       └── History tracking
│
├── gui/                            # Presentation Layer
│   ├── main_window.py              # Main window & stack navigation
│   ├── kernels_tab.py              # Installed kernels management
│   ├── packages_tab.py             # Local .deb packages
│   ├── build_tab.py                # Kernel compilation interface
│   ├── drivers_tab.py              # GPU driver management (1058 lines) ⭐
│   │   ├── 3-tab interface (Installation/History/Rollback)
│   │   ├── System info bar
│   │   ├── Repository driver listing
│   │   ├── Official driver scraping/installation
│   │   └── Backup/restore interface
│   ├── profiles_tab.py             # Configuration profiles
│   ├── history_tab.py              # Compilation history
│   └── sources_tab.py              # /usr/src/ management (DKMS)
│
├── utils/                          # Utility Layer
│   ├── dialogs.py                  # Reusable dialog helpers
│   │   ├── ProgressDialog (threaded operations)
│   │   ├── MultiStepProgressDialog (complex workflows)
│   │   ├── OptionsDialog (installation options)
│   │   └── YesNoDialog (confirmations)
│   │
│   ├── i18n.py                     # Internationalization
│   │   ├── JSON-based translations
│   │   ├── Locale detection
│   │   └── Dynamic language switching
│   │
│   └── pkexec_helper.py            # Privilege escalation
│       ├── Safe command execution as root
│       └── PolicyKit integration
│
└── translations/                   # Language Files
    ├── fr.json                     # French (331 lines)
    └── en.json                     # English (331 lines)
```

---

## Core Components

### 1. KernelManager (`core/kernel_manager.py`)

**Responsibility**: All kernel-related operations

**Key Methods:**
```python
class KernelManager:
    def __init__(self, base_dir=None)
        # Initialize build directory structure

    def download_kernel(self, version, progress_callback=None) -> bool
        # Download kernel tarball from kernel.org
        # Extract to build/linux-{version}/

    def get_latest_stable_version(self) -> str
        # Fetch latest stable kernel from kernel.org JSON API

    def configure_kernel(self, version, use_system_config=True, config_path=None) -> bool
        # Copy base config to kernel source
        # Optionally run menuconfig

    def compile_kernel(self, version, threads, suffix, use_fakeroot=True) -> subprocess.Popen
        # Launch compilation in terminal
        # Return process handle for monitoring

    def get_installed_kernels(self) -> list
        # Query dpkg for installed linux-image* packages

    def remove_kernel(self, version) -> bool
        # Remove kernel packages via apt
        # Cannot remove active kernel
```

**Design Decisions:**
- Uses **pathlib.Path** for cross-platform path handling
- Downloads to **user home directory** (~/.cache or ~/KernelCustomManager) to avoid requiring root
- Compilation happens in **terminal** for real-time user feedback
- **Threaded downloads** with progress callbacks

**Data Storage:**
```
~/KernelCustomManager/build/
├── linux-6.11.1/              # Extracted source
├── packages/                   # Compiled .deb files
├── configs/                    # Saved .config files
├── profiles/                   # JSON profile metadata
├── logs/                       # Compilation logs
└── compilation_history.json    # History tracking
```

---

### 2. DriverManager (`core/driver_manager.py`) ⭐ New in v2.2

**Responsibility**: GPU driver detection, installation, backup, and rollback

**Architecture:**
```python
class DriverManager:
    def __init__(self, base_dir=None)
        # Initialize driver directories
        self.distro_info = self.detect_distribution()
        self.display_server = self.detect_display_server()
```

#### 2.1 GPU Detection
```python
def detect_gpu(self) -> dict
    """
    Parse lspci output to identify GPU vendor and model.

    Returns:
        {
            'vendor': 'NVIDIA' | 'AMD' | 'Intel' | None,
            'model': 'GeForce RTX 3060',
            'pci_id': '10de:2503'
        }
    """
    # Uses lspci -nn to get PCI IDs
    # Matches against known vendor IDs:
    # - NVIDIA: 10de
    # - AMD: 1002
    # - Intel: 8086
```

**Implementation Details:**
- Parses `lspci -nn` output with regex
- Handles multiple GPUs (returns primary/first found)
- Robust error handling for missing lspci

#### 2.2 Distribution Detection
```python
def detect_distribution(self) -> dict
    """
    Detect Ubuntu/Debian version and codename.

    Returns:
        {
            'name': 'ubuntu',
            'version': '24.04',
            'codename': 'noble',
            'pretty_name': 'Ubuntu 24.04 LTS'
        }
    """
    # 1. Try /etc/os-release (modern standard)
    # 2. Fallback to lsb_release -a
    # 3. Fallback to /etc/debian_version
```

**Codename Mapping:**
```python
UBUNTU_CODENAMES = {
    '24.04': 'noble',
    '22.04': 'jammy',
    '20.04': 'focal',
    # ...
}
```

Used for constructing repository package names and AMD download URLs.

#### 2.3 Display Server Detection
```python
def detect_display_server(self) -> str
    """
    Detect X11, Wayland, or TTY.

    Returns: 'X11' | 'Wayland' | 'TTY' | 'Unknown'
    """
    # Method 1: Check $XDG_SESSION_TYPE
    # Method 2: Check $WAYLAND_DISPLAY
    # Method 3: Check $DISPLAY
    # Method 4: Parse 'ps aux' for Xorg/wayland process
```

**Why it matters:** NVIDIA installation method depends on this:
- **X11/Wayland**: Must stop display manager → Use systemd service
- **TTY**: Direct installation (display manager already stopped)

#### 2.4 Repository Driver Listing
```python
def get_available_drivers_from_repos(self) -> list
    """
    List installable drivers from apt repositories.

    Returns:
        [
            {
                'name': 'nvidia-driver-550',
                'version': '550.127.05-0ubuntu1',
                'description': 'NVIDIA driver metapackage',
                'recommended': True  # Based on ubuntu-drivers
            },
            ...
        ]
    """
    # 1. Run 'apt-cache search' for vendor-specific patterns
    # 2. Get versions with 'apt-cache policy'
    # 3. Check 'ubuntu-drivers list' for recommended flag
```

**Vendor-Specific Patterns:**
- **NVIDIA**: `nvidia-driver-*`
- **AMD**: `xserver-xorg-video-amdgpu`, `mesa-vulkan-drivers`, `amdgpu-*`
- **Intel**: `xserver-xorg-video-intel`, `intel-media-va-driver`, `mesa-vulkan-drivers`

#### 2.5 Web Scraping
```python
def scrape_nvidia_latest_version(self) -> dict
    """
    Fetch latest NVIDIA driver from official site.

    Process:
    1. Download https://download.nvidia.com/XFree86/Linux-x86_64/latest.txt
    2. Parse version number
    3. Construct download URL
    4. Get file size via HEAD request

    Returns:
        {
            'version': '560.35.03',
            'url': 'https://us.download.nvidia.com/XFree86/Linux-x86_64/560.35.03/NVIDIA-Linux-x86_64-560.35.03.run',
            'size': '350 MB',
            'date': '2024-10-15'
        }
    """
```

```python
def scrape_amd_latest_version(self) -> dict
    """
    Fetch latest AMD AMDGPU-PRO driver.

    Process:
    1. Construct URL based on detected Ubuntu codename
       https://repo.radeon.com/amdgpu-install/latest/ubuntu/{codename}/amdgpu-install_*.deb
    2. Try adaptive fallbacks if codename not supported
    3. Get file info

    Returns: Similar structure to NVIDIA
    """
```

**Intel Note:** Intel doesn't provide proprietary downloads (open source drivers only).

#### 2.6 Smart NVIDIA Installation
```python
def install_nvidia_intelligently(self, run_file_path) -> bool
    """
    Install NVIDIA .run file with display server awareness.

    Decision Tree:

    if display_server in ['X11', 'Wayland']:
        # Graphical session active - cannot install directly
        create_systemd_service()
        # Service will run on next boot:
        # 1. Stop display manager (gdm3/lightdm/sddm)
        # 2. Run NVIDIA installer
        # 3. Clean up service file
        # 4. Reboot
        return True

    elif display_server == 'TTY':
        # Already in console mode - install directly
        run_nvidia_installer()
        return True
    """
```

**Systemd Service Template:**
```ini
[Unit]
Description=KernelCustom Manager NVIDIA Driver Installation
After=multi-user.target
Before=display-manager.service

[Service]
Type=oneshot
ExecStartPre=/bin/systemctl stop gdm3.service lightdm.service sddm.service
ExecStart=/bin/bash -c "cd /tmp && chmod +x nvidia-installer.run && ./nvidia-installer.run --silent --accept-license"
ExecStartPost=/bin/rm /etc/systemd/system/kernelcustom-nvidia-install.service
ExecStartPost=/bin/systemctl daemon-reload
ExecStartPost=/bin/systemctl reboot

[Install]
WantedBy=multi-user.target
```

**Why this approach:**
- X11/Wayland sessions lock GPU resources
- NVIDIA installer requires exclusive GPU access
- Systemd ensures installation happens at proper boot stage
- Self-cleaning (service removes itself after execution)

#### 2.7 Backup System
```python
def create_driver_backup(self) -> dict
    """
    Save current driver state for rollback.

    What's saved:
    {
        "backup_id": "backup_20251028_143000",
        "timestamp": "2025-10-28T14:30:00.123456",
        "gpu_vendor": "NVIDIA",
        "gpu_model": "GeForce RTX 3060",
        "driver_name": "nvidia-driver-535",
        "driver_version": "535.183.01",
        "packages": [
            "nvidia-driver-535",
            "nvidia-dkms-535",
            "nvidia-utils-535",
            "libnvidia-gl-535"
        ],
        "distro": "ubuntu 24.04",
        "display_server": "Wayland",
        "notes": ""
    }

    Saved to: ~/KernelCustomManager/build/drivers_backup/{backup_id}.json
    """
```

**Backup Strategy:**
- Lightweight (metadata only, not actual driver files)
- Package list allows reinstallation from repositories
- System context helps troubleshoot restore issues
- Timestamped for easy identification

#### 2.8 History Tracking
```python
def add_to_history(self, action, vendor, driver_name, driver_version,
                   source, success, error_msg=None)
    """
    Record operation in history.

    Entry format:
    {
        "timestamp": "2025-10-28T14:30:00.123456",
        "action": "install" | "remove" | "rollback",
        "vendor": "NVIDIA" | "AMD" | "Intel",
        "driver_name": "nvidia-driver-550",
        "driver_version": "550.127.05",
        "source": "repository" | "official" | "backup",
        "success": true,
        "error_msg": null,
        "display_server": "Wayland",
        "distro": "ubuntu 24.04"
    }

    Appended to: ~/KernelCustomManager/build/drivers_history.json
    """
```

**Data Structure:**
```python
{
    "entries": [
        { /* history entry */ },
        { /* history entry */ },
        ...
    ]
}
```

---

## GUI Components

### Main Window Architecture

```python
class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, application, i18n, driver_manager):
        # GTK Stack for tab navigation
        self.stack = Gtk.Stack()
        self.stack_switcher = Gtk.StackSwitcher()

        # Register tabs
        self.stack.add_titled(create_kernels_tab(), "kernels", "Installed Kernels")
        self.stack.add_titled(create_drivers_tab(), "drivers", "GPU Drivers")
        # ... more tabs
```

**Stack-Based Navigation:**
- Uses `Gtk.Stack` instead of `Gtk.Notebook`
- Cleaner modern UI
- Easy to add/remove tabs
- Supports transitions (optional)

---

### Tab Design Pattern

All tabs follow a consistent structure:

```python
def create_TAB_NAME_tab(main_window):
    """
    Factory function that creates and returns a Gtk.Box containing the tab UI.

    Args:
        main_window: Reference to MainWindow for accessing shared resources

    Returns:
        Gtk.Box: The tab container
    """
    # Access shared resources
    kernel_manager = main_window.kernel_manager
    i18n = main_window.i18n

    # Create UI
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

    # Add widgets
    # ...

    # Define callbacks
    def on_button_clicked(button):
        # Handle action
        pass

    # Connect signals
    button.connect("clicked", on_button_clicked)

    return vbox
```

**Why factory functions instead of classes:**
- Simpler for straightforward tabs
- Less boilerplate
- Easier to refactor if needed
- Closure-based state management

---

### Drivers Tab (v2.2) ⭐

**3-Tab Nested Structure:**
```python
def create_drivers_tab(main_window):
    notebook = Gtk.Notebook()

    # Tab 1: Installation
    notebook.append_page(
        create_installation_tab(...),
        Gtk.Label(label="Installation")
    )

    # Tab 2: History
    notebook.append_page(
        create_history_tab(...),
        Gtk.Label(label="📜 History")
    )

    # Tab 3: Rollback
    notebook.append_page(
        create_rollback_tab(...),
        Gtk.Label(label="⏮️ Rollback")
    )
```

**Installation Tab Layout:**
```
┌─────────────────────────────────────────────────────┐
│ System Info Bar                                     │
│ GPU: NVIDIA RTX 3060 | Driver: nvidia-driver-535    │
│ Distribution: ubuntu 24.04 | Display: Wayland       │
├─────────────────────────────────────────────────────┤
│ Current State                                       │
│ [🔄 Refresh] [💾 Create Backup]                    │
├─────────────────────────────────────────────────────┤
│ Drivers from Repositories (Recommended)             │
│ ┌────────────────────────────────────────────────┐ │
│ │ TreeView:                                      │ │
│ │ ⭐ nvidia-driver-550  550.127.05  recommended  │ │
│ │   nvidia-driver-535  535.183.01               │ │
│ │   nvidia-driver-525  525.147.05               │ │
│ └────────────────────────────────────────────────┘ │
│ [📥 Install from repositories]                     │
├─────────────────────────────────────────────────────┤
│ Official Drivers (Advanced)                         │
│ [🌐 Fetch Latest Version]                          │
│ Latest: 560.35.03 | Size: 350 MB | Date: 2024-10-15│
│ [⚠️ Download and install]                          │
├─────────────────────────────────────────────────────┤
│ [🗑️ Remove proprietary driver]                     │
└─────────────────────────────────────────────────────┘
```

---

### Progress Dialog Pattern

**Simple Progress:**
```python
from utils.dialogs import ProgressDialog

def do_long_operation():
    dialog = ProgressDialog(parent, i18n._("dialog.download.title"))

    def worker():
        # Do work in background
        result = perform_operation()
        GLib.idle_add(finish, result)

    def finish(result):
        dialog.close()
        # Update UI with result
        return False  # Remove GLib source

    threading.Thread(target=worker, daemon=True).start()
    dialog.run()
```

**Multi-Step Progress:**
```python
from utils.dialogs import MultiStepProgressDialog

dialog = MultiStepProgressDialog(
    parent,
    "Installing Driver",
    steps=[
        "Preparing installation...",
        "Installing packages...",
        "Configuring system...",
        "Finalizing..."
    ]
)

for step in range(4):
    dialog.set_step(step)
    # Do step work
    time.sleep(2)

dialog.close()
```

**Threading Model:**
```
Main Thread (GTK UI)
    ↓
Create ProgressDialog
    ↓
Launch Worker Thread
    ↓ (async)
Worker does heavy lifting
    ↓
Use GLib.idle_add() to update UI
    ↓
Main Thread updates UI safely
```

**Why GLib.idle_add:**
- GTK is **not thread-safe**
- All UI updates must happen on main thread
- `GLib.idle_add(callback, *args)` schedules callback on main thread
- Returns False to prevent callback from repeating

---

## Data Flow

### Example: Installing NVIDIA Driver from Repository

```
User clicks "Install from repositories"
    ↓
GUI: drivers_tab.py → on_install_from_repos()
    ↓
[Confirmation Dialog]
    ↓
[Backup Creation Prompt]
    ├─ Yes → driver_manager.create_driver_backup()
    └─ No → Continue
    ↓
[Progress Dialog + Thread Launch]
    ↓
Worker Thread:
    ├─ driver_manager.get_current_driver() [for history]
    ├─ pkexec_helper.run_privileged([
    │     "apt", "install", "-y", "nvidia-driver-550"
    │  ])
    └─ driver_manager.add_to_history(...)
    ↓
GLib.idle_add(finish_callback, success)
    ↓
Main Thread:
    ├─ dialog.close()
    ├─ Show success/error message
    ├─ Show reboot prompt
    └─ refresh_gpu_info()
```

### Example: Web Scraping and Installing Official NVIDIA Driver

```
User clicks "Fetch Latest Version"
    ↓
[Progress Dialog: "Fetching..."]
    ↓
Worker Thread:
    ├─ driver_manager.scrape_nvidia_latest_version()
    │     ├─ urllib.request.urlopen(latest.txt)
    │     ├─ Parse version
    │     ├─ Construct download URL
    │     └─ HEAD request for file size
    └─ GLib.idle_add(display_result)
    ↓
Main Thread: Update UI with version info
    ↓
User clicks "Download and install"
    ↓
[Warning Dialog: Advanced operation!]
    ↓
[Backup Prompt]
    ↓
[Download Dialog + Progress]
    ↓
Worker Thread:
    ├─ urllib.request.urlretrieve(url, callback=progress_hook)
    ├─ Save to /tmp/nvidia-installer.run
    └─ GLib.idle_add(install_phase)
    ↓
Main Thread: driver_manager.install_nvidia_intelligently()
    ↓
IF display_server in [X11, Wayland]:
    ├─ Create systemd service
    ├─ Enable service
    └─ Show "Reboot required" message
ELSE:
    ├─ pkexec install directly
    └─ Show "Reboot recommended" message
```

---

## Design Patterns

### 1. Factory Pattern (Tab Creation)
```python
def create_kernels_tab(main_window) -> Gtk.Box:
    # Creates and configures tab
    return vbox
```

**Benefits:**
- Encapsulation of tab creation logic
- Easy testing (mock main_window)
- Consistent interface across tabs

### 2. Observer Pattern (GTK Signals)
```python
button.connect("clicked", on_button_clicked)
liststore.connect("row-changed", on_row_changed)
```

**Benefits:**
- Decoupled event handling
- Multiple observers possible
- Standard GTK pattern

### 3. Singleton Pattern (Managers)
```python
# In main_window.py
self.kernel_manager = KernelManager()
self.driver_manager = DriverManager()

# Shared across all tabs
```

**Benefits:**
- Single source of truth
- Shared state (detected GPU, distro info)
- Efficient resource usage

### 4. Template Method (Privileged Operations)
```python
# pkexec_helper.py
def run_privileged(command_list, input_data=None):
    # Standard pattern for all privileged ops
    result = subprocess.run(
        ["pkexec"] + command_list,
        input=input_data,
        capture_output=True
    )
    return result.returncode == 0
```

**Benefits:**
- Consistent error handling
- Security auditing easier
- Easy to add logging

### 5. Strategy Pattern (Driver Installation)
```python
# Different installation strategies based on context
if source == "repository":
    install_from_repository(driver_name)
elif source == "official":
    if vendor == "NVIDIA":
        install_nvidia_from_run_file()
    elif vendor == "AMD":
        install_amd_from_deb()
```

---

## Key Features Implementation

### 1. Smart NVIDIA Installation

**Challenge:** NVIDIA .run installer requires exclusive GPU access, but user is typically in a graphical session.

**Solution:** Systemd one-shot service
- Runs at boot before display manager starts
- Has GPU access in early boot stage
- Self-cleaning (removes itself after execution)

**Alternative Considered:**
- Switching to TTY programmatically: Rejected (requires X server kill, too disruptive)
- Asking user to manually switch to TTY: Rejected (poor UX)
- Installing in background: Rejected (doesn't work, GPU is locked)

**Implementation:**
```python
service_content = f"""[Unit]
Description=KernelCustom Manager NVIDIA Driver Installation
After=multi-user.target
Before=display-manager.service

[Service]
Type=oneshot
ExecStartPre=/bin/systemctl stop gdm3.service lightdm.service sddm.service
ExecStart=/bin/bash -c "cd /tmp && chmod +x {run_filename} && ./{run_filename} --silent --accept-license"
ExecStartPost=/bin/rm /etc/systemd/system/kernelcustom-nvidia-install.service
ExecStartPost=/bin/systemctl daemon-reload
ExecStartPost=/bin/systemctl reboot

[Install]
WantedBy=multi-user.target
"""

# Write service file with pkexec
# Enable service
# Prompt user to reboot
```

### 2. Web Scraping

**NVIDIA:**
```
URL: https://download.nvidia.com/XFree86/Linux-x86_64/latest.txt
Content: 560.35.03

Parse version → Construct download URL:
https://us.download.nvidia.com/XFree86/Linux-x86_64/560.35.03/NVIDIA-Linux-x86_64-560.35.03.run
```

**AMD:**
```
Base: https://repo.radeon.com/amdgpu-install/latest/ubuntu/{codename}/
Example: .../ubuntu/noble/amdgpu-install_6.2.60200-1_all.deb

Strategy:
1. Detect Ubuntu codename (noble, jammy, focal)
2. Construct URL with codename
3. Fallback to previous Ubuntu version if 404
```

**Challenges:**
- AMD URL structure changes between releases
- Need to handle 404 gracefully
- File naming conventions vary

**Solution:**
- Adaptive URL construction
- Multiple fallback attempts
- Clear error messages to user

### 3. Backup/Rollback System

**Design Decision:** Store metadata, not actual driver files

**Rationale:**
- Driver files are large (hundreds of MB)
- Already available in apt cache or can be re-downloaded
- Metadata is sufficient to recreate state
- Saves disk space

**Rollback Process:**
```python
def restore_from_backup(backup_id):
    # 1. Load backup metadata
    with open(f"{backup_id}.json") as f:
        backup = json.load(f)

    # 2. Remove current proprietary drivers
    remove_proprietary_drivers(gpu_vendor)

    # 3. Reinstall from backup package list
    for package in backup['packages']:
        install_package(package)

    # 4. Record in history
    add_to_history("rollback", ...)
```

**Limitations:**
- Only works if packages still exist in repositories
- Cannot restore unofficial/downloaded drivers
- System state (kernel version, etc.) must be compatible

---

## Security Considerations

### 1. Privilege Escalation

**PolicyKit (pkexec) is used instead of sudo:**
- GUI-friendly password prompt
- User doesn't need to be in sudoers
- Action-based authorization (could be restricted per-operation)
- Audit trail

**What requires privileges:**
```python
# Package operations
apt install, apt remove

# System file writes
Writing to /usr/src/
Writing to /etc/systemd/system/

# Service management
systemctl enable/disable/start/stop
```

**Security Best Practices:**
- ✅ Minimal commands run with pkexec
- ✅ Command arguments validated before execution
- ✅ No shell expansion in commands
- ✅ User confirmation before destructive operations
- ❌ Never store passwords
- ❌ No arbitrary command execution

### 2. Web Scraping Safety

**Risks:**
- Malicious redirects
- Man-in-the-middle attacks
- Malformed download files

**Mitigations:**
- Use **HTTPS only** for downloads
- Validate file extensions (.run for NVIDIA, .deb for AMD)
- Check file sizes (reject unreasonably small/large files)
- Provide download URLs to user for verification
- Warn about risks of official installations

### 3. Input Validation

```python
def validate_version(version_str):
    """Ensure kernel version format is valid."""
    if not re.match(r'^\d+\.\d+\.\d+(-rc\d+)?$', version_str):
        raise ValueError("Invalid version format")
```

**Validated Inputs:**
- Kernel version strings
- File paths (no traversal attacks)
- Package names (alphanumeric + dashes only)

---

## Performance Optimizations

### 1. Threaded Operations

All long-running operations run in background threads:
```python
threading.Thread(target=download_kernel, daemon=True).start()
```

**Benefits:**
- UI remains responsive
- User can cancel operations
- Progress updates in real-time

**GTK Thread Safety:**
```python
# WRONG - crashes
def worker():
    label.set_text("Done")  # Called from worker thread!

# CORRECT
def worker():
    GLib.idle_add(lambda: label.set_text("Done"))
```

### 2. Caching

```python
class DriverManager:
    def __init__(self):
        # Detect once, cache results
        self.distro_info = self.detect_distribution()
        self.display_server = self.detect_display_server()
```

**What's cached:**
- Distribution info (doesn't change during session)
- Display server type (doesn't change during session)
- GPU info (could change if user hotplugs, but rare)

**What's NOT cached:**
- Installed packages (changes with install/remove)
- Current driver (changes with install/remove)
- Available drivers from repos (could change with apt update)

### 3. Lazy Loading

```python
# Tabs are created on-demand by GTK Stack
# Only active tab's callbacks are executed
```

### 4. Efficient Data Structures

```python
# Use pathlib.Path instead of string concatenation
build_dir = Path.home() / "KernelCustomManager" / "build"
kernel_dir = build_dir / f"linux-{version}"

# JSON for configuration (fast parsing, human-readable)
# Not XML (verbose) or pickle (not human-readable)
```

---

## Future Improvements

### High Priority
1. **Automated Testing**
   - Unit tests for core logic
   - Mock subprocess calls
   - Test GPU detection with fixtures

2. **More GPU Vendors**
   - Nouveau (NVIDIA open source)
   - Radeon (AMD open source) - explicit management
   - Intel Arc discrete GPUs - better support

3. **Kernel Configuration Presets**
   - Gaming preset (low latency, no overhead)
   - Server preset (security hardened)
   - Development preset (debugging enabled)

4. **Better Error Recovery**
   - Auto-rollback on failed installation
   - GRUB entry manipulation for safe kernel testing
   - Emergency boot repair mode

### Medium Priority
5. **More Distributions**
   - Fedora support
   - Arch Linux support
   - OpenSUSE support

6. **Kernel Patch Management**
   - Apply patches before compilation
   - Patch library (grsecurity, Zen kernel, etc.)
   - Custom patch support

7. **Driver Performance Monitoring**
   - FPS benchmarks before/after driver change
   - Power consumption tracking
   - Temperature monitoring

8. **Cloud Features**
   - Profile sharing (community configs)
   - Backup to cloud
   - Update notifications

### Low Priority
9. **CLI Interface**
   - Scriptable operations
   - Remote management
   - Cron job support

10. **Flatpak/Snap Packaging**
    - Sandboxed installation
    - Automatic updates
    - Cross-distro compatibility

---

## Code Metrics (v2.2)

```
Total Lines of Code: ~7,000

core/kernel_manager.py:      900
core/driver_manager.py:      2886 ⭐
gui/main_window.py:          300
gui/drivers_tab.py:          1058 ⭐
gui/kernels_tab.py:          250
gui/build_tab.py:            400
gui/packages_tab.py:         200
gui/profiles_tab.py:         180
gui/history_tab.py:          150
gui/sources_tab.py:          300
utils/dialogs.py:            250
utils/i18n.py:               80
utils/pkexec_helper.py:      50

translations/fr.json:        331 lines
translations/en.json:        331 lines

Comments/Docstrings:         ~15% of code
```

**v2.2 Additions:**
- **+2886 lines** in driver_manager.py
- **+1058 lines** in drivers_tab.py
- **+90 translation keys** (French + English)

---

## Contributing to Architecture

When adding new features:

1. **Follow existing patterns**
   - Use factory functions for tabs
   - Separate business logic (core/) from UI (gui/)
   - Use utils/ for shared code

2. **Threading rules**
   - Long operations in threads
   - UI updates via GLib.idle_add
   - Always use daemon=True for threads

3. **Translations**
   - Add keys to both fr.json and en.json
   - Use i18n._("key.subkey") for all user-visible text

4. **Error handling**
   - Validate inputs
   - Use try/except for external commands
   - Show user-friendly error messages

5. **Documentation**
   - Update ARCHITECTURE.md for major changes
   - Add docstrings to public methods
   - Comment complex logic

---

## Conclusion

KernelCustom Manager v2.2 is a **modular, safe, and user-friendly** tool for kernel and GPU driver management. The architecture prioritizes:

- **Safety**: Confirmations, backups, rollbacks
- **User Experience**: Progress dialogs, clear messages, automated workflows
- **Maintainability**: Separated concerns, consistent patterns, documented code
- **Extensibility**: Easy to add new GPU vendors, distributions, or features

The codebase is structured to make contributions straightforward while maintaining quality and reliability.

---

**For questions about architecture or design decisions, contact the maintainer or open a discussion in the project repository.**
