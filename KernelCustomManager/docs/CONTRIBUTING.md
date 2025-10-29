# Contributing to KernelCustom Manager

Thank you for considering contributing to KernelCustom Manager! This document provides guidelines for contributing to the project.

## Table of Contents
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Reporting Bugs](#reporting-bugs)
- [Requesting Features](#requesting-features)

---

## How Can I Contribute?

### 1. Testing on Different Hardware
We are actively seeking testers with various GPU configurations:

#### NVIDIA GPUs
- RTX 4000 series (4090, 4080, 4070, etc.)
- RTX 3000 series (3090, 3080, 3070, 3060, etc.)
- GTX 1000 series (1080 Ti, 1070, 1060, etc.)
- Older generations (GTX 900/700 series)

#### AMD GPUs
- Radeon RX 7000 series (7900 XTX, 7900 XT, 7800 XT, etc.)
- Radeon RX 6000 series (6900 XT, 6800 XT, 6700 XT, etc.)
- Radeon RX 5000 series (Navi)
- Vega series (Vega 64, Vega 56)

#### Intel GPUs
- Arc A-series (A770, A750, A380)
- Iris Xe Graphics
- Integrated graphics (UHD Graphics 770, etc.)

#### Distributions to Test
- Ubuntu 22.04 LTS (Jammy Jellyfish)
- Ubuntu 24.04 LTS (Noble Numbat)
- Debian 11 (Bullseye)
- Debian 12 (Bookworm)
- Linux Mint 21.x
- Linux Mint 22.x
- Pop!_OS 22.04

#### Display Servers
- X11
- Wayland (especially important!)
- Hybrid X11/Wayland setups

### 2. Bug Reports
Found a bug? Please report it! See [Reporting Bugs](#reporting-bugs) below.

### 3. Feature Requests
Have an idea for a new feature? See [Requesting Features](#requesting-features) below.

### 4. Code Contributions
Want to fix a bug or implement a feature? See [Development Setup](#development-setup) and [Submitting Changes](#submitting-changes).

### 5. Documentation
Help improve documentation by:
- Fixing typos or unclear explanations
- Adding examples
- Translating to other languages
- Creating video tutorials

---

## Development Setup

### Prerequisites
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-notify-0.7

# Development tools
sudo apt install git python3-pip

# Optional: for kernel compilation testing
sudo apt install build-essential libncurses-dev bison flex libssl-dev libelf-dev
```

### Clone and Run
```bash
# Clone the repository
git clone https://github.com/lpennisi73-tech/BOOKWORM.git
cd BOOKWORM

# Run the application
python3 kernelcustom_manager.py
```

### Project Structure
```
KernelCustomManager/
├── kernelcustom_manager.py         # Entry point
├── core/                           # Business logic
│   ├── kernel_manager.py           # Kernel operations
│   └── driver_manager.py           # GPU driver operations
├── gui/                            # GTK3 interface
│   ├── main_window.py              # Main window
│   ├── kernels_tab.py              # Kernels tab
│   ├── packages_tab.py             # Packages tab
│   ├── build_tab.py                # Build tab
│   ├── drivers_tab.py              # Drivers tab (v2.2)
│   ├── profiles_tab.py             # Profiles tab
│   ├── history_tab.py              # History tab
│   └── sources_tab.py              # Sources tab
├── utils/                          # Utilities
│   ├── dialogs.py                  # Dialog helpers
│   ├── i18n.py                     # Internationalization
│   └── pkexec_helper.py            # Privileged operations
└── translations/                   # Translation files
    ├── fr.json                     # French
    └── en.json                     # English
```

---

## Code Style Guidelines

### Python Style
We follow PEP 8 with some modifications:

#### General Rules
- **Indentation**: 4 spaces (no tabs)
- **Line length**: 100 characters maximum (flexible for readability)
- **Encoding**: UTF-8
- **Python version**: 3.8+ compatible

#### Naming Conventions
```python
# Classes: PascalCase
class DriverManager:
    pass

# Functions and methods: snake_case
def detect_gpu():
    pass

# Constants: UPPER_SNAKE_CASE
DEFAULT_TIMEOUT = 30

# Private methods: _leading_underscore
def _internal_helper():
    pass
```

#### Imports
```python
# Standard library first
import os
import sys
from pathlib import Path

# Third-party libraries
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

# Local modules
from core.kernel_manager import KernelManager
from utils.i18n import I18n
```

#### Documentation
```python
def install_driver(driver_name, version, source):
    """
    Install a GPU driver from the specified source.

    Args:
        driver_name (str): Name of the driver package
        version (str): Version number
        source (str): Source ('repository' or 'official')

    Returns:
        bool: True if installation succeeded, False otherwise

    Raises:
        ValueError: If driver_name is empty
        RuntimeError: If installation fails
    """
    pass
```

### GTK3 Guidelines
```python
# Use GLib.idle_add for UI updates from threads
def _background_task():
    result = do_work()
    GLib.idle_add(update_ui, result)

# Always destroy dialogs after use
dialog = Gtk.Dialog()
response = dialog.run()
dialog.destroy()

# Use context managers when possible
with open(file_path, 'r') as f:
    data = f.read()
```

### Error Handling
```python
# Always catch specific exceptions
try:
    result = risky_operation()
except FileNotFoundError as e:
    logger.error(f"File not found: {e}")
    return False
except PermissionError as e:
    logger.error(f"Permission denied: {e}")
    return False

# Use logging instead of print
import logging
logger = logging.getLogger(__name__)
logger.info("Operation started")
logger.error("Operation failed")
```

---

## Testing

### Manual Testing Checklist

#### GPU Drivers Tab
- [ ] GPU detection works correctly
- [ ] Current driver is displayed accurately
- [ ] Repository drivers list is populated
- [ ] Web scraping fetches correct versions
- [ ] Installation from repositories succeeds
- [ ] Installation from official site succeeds (NVIDIA/AMD)
- [ ] Backup creation works
- [ ] Rollback restores previous state
- [ ] History records all operations
- [ ] Removal of proprietary drivers works

#### Kernel Management
- [ ] Kernel download completes successfully
- [ ] Configuration methods work (system config, file import)
- [ ] Compilation completes without errors
- [ ] Compiled packages appear in local packages
- [ ] Installation of compiled kernel works
- [ ] Removal of installed kernels works

#### System-Specific Tests
- [ ] Application runs on X11
- [ ] Application runs on Wayland
- [ ] PolicyKit authentication works
- [ ] Notifications appear correctly
- [ ] Language switching works (FR/EN)

### Testing NVIDIA Installation

**IMPORTANT**: Test NVIDIA installation carefully as it can interrupt your graphical session.

1. **Before testing**:
   - Create a backup of your current driver
   - Save all your work
   - Have a TTY terminal ready (Ctrl+Alt+F3)

2. **On X11**:
   - Application should create systemd service
   - Check service with: `systemctl status kernelcustom-nvidia-install.service`
   - Reboot and verify installation

3. **On Wayland**:
   - Same as X11 (systemd service approach)
   - Verify Wayland continues working after reboot

4. **On TTY**:
   - Installation should proceed directly
   - No systemd service should be created

### Reporting Test Results

When testing, please provide:
```
**Hardware:**
- GPU: [Model and manufacturer]
- CPU: [Model]
- RAM: [Amount]

**Software:**
- Distribution: [Name and version]
- Kernel: [uname -r output]
- Display Server: [X11/Wayland]
- Desktop Environment: [GNOME/KDE/XFCE/etc.]

**Test Results:**
- Feature tested: [e.g., NVIDIA driver installation from repository]
- Steps taken: [Detailed steps]
- Expected result: [What should happen]
- Actual result: [What actually happened]
- Logs: [Attach relevant logs]

**Screenshots:**
[If applicable]
```

---

## Submitting Changes

### 1. Fork and Branch
```bash
# Fork the repository on the Git server
# Then clone your fork
git clone https://github.com/lpennisi73-tech/BOOKWORM
cd KernelCustomManager

# Create a feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Your Changes
- Follow the code style guidelines
- Add comments for complex logic
- Update translations if you modify UI text
- Test your changes thoroughly

### 3. Commit Your Changes
```bash
# Stage your changes
git add .

# Commit with a descriptive message
git commit -m "Add support for nouveau driver detection

- Added nouveau driver detection in driver_manager.py
- Updated GUI to display nouveau version
- Added French/English translations
- Tested on Ubuntu 22.04 with GTX 1060"
```

**Commit Message Guidelines:**
- Use present tense ("Add feature" not "Added feature")
- First line: short summary (50 chars max)
- Blank line, then detailed description if needed
- Reference issues: "Fixes #123" or "Related to #456"

### 4. Push and Create Pull Request
```bash
# Push to your fork
git push origin feature/your-feature-name

# Create a pull request on the Git server
# Include:
# - Clear title describing the change
# - Detailed description of what and why
# - Testing performed
# - Screenshots (if UI changes)
```

### Pull Request Template
```markdown
## Description
Brief description of changes

## Motivation
Why is this change needed?

## Changes Made
- Added X
- Modified Y
- Fixed Z

## Testing
- [ ] Tested on Ubuntu 22.04
- [ ] Tested on Debian 12
- [ ] Tested with NVIDIA GPU
- [ ] Tested with AMD GPU
- [ ] Tested on X11
- [ ] Tested on Wayland

## Screenshots
[If applicable]

## Additional Notes
[Any other relevant information]
```

---

## Reporting Bugs

### Before Reporting
1. **Check existing issues** to avoid duplicates
2. **Test on latest version** to ensure bug still exists
3. **Gather logs and system information**

### Bug Report Template
```markdown
**Bug Description**
A clear description of the bug

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happens

**Screenshots**
[If applicable]

**System Information:**
- OS: [e.g., Ubuntu 24.04]
- Kernel: [uname -r output]
- GPU: [Model]
- Display Server: [X11/Wayland]
- KernelCustom Manager version: [e.g., v2.2]

**Logs:**
```
[Paste relevant logs here]
- Application logs: Check terminal output
- NVIDIA logs: /var/log/nvidia-installer.log
- System logs: journalctl -xe
```

**Additional Context**
Any other relevant information
```

### Where to Report
Contact the maintainer at: https://github.com/lpennisi73-tech/BOOKWORM/

---

## Requesting Features

### Feature Request Template
```markdown
**Feature Description**
Clear description of the proposed feature

**Use Case**
Why is this feature needed? Who would benefit?

**Proposed Solution**
How would you like this implemented?

**Alternatives Considered**
Other approaches you've thought about

**Additional Context**
- Related issues/features
- Examples from other tools
- Mock-ups or diagrams (if applicable)
```

### Feature Scope
Features that align with project goals:
- ✅ Improved GPU driver management
- ✅ Better kernel compilation options
- ✅ Enhanced backup/rollback capabilities
- ✅ Support for more distributions
- ✅ Additional language translations
- ✅ UI/UX improvements
- ✅ Performance optimizations

Features outside project scope:
- ❌ Non-Linux platforms (Windows, macOS)
- ❌ Proprietary/closed-source additions
- ❌ Features requiring external paid services

---

## Translation Contributions

### Adding a New Language

1. **Copy existing translation file**:
```bash
cp translations/en.json translations/YOUR_LANGUAGE.json
# e.g., cp translations/en.json translations/es.json
```

2. **Translate all strings**:
```json
{
  "window": {
    "title": "KernelCustom Manager",
    "subtitle": "Professional Edition v2.2"
  },
  "button": {
    "refresh": "🔄 Actualizar",
    "install": "📥 Instalar"
  }
}
```

3. **Update i18n.py** to support the new language:
```python
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'fr': 'Français',
    'es': 'Español'  # Add your language
}
```

4. **Test thoroughly** to ensure:
   - All UI elements are translated
   - No text overflow in dialogs
   - Special characters display correctly

---

## Code Review Process

### What Reviewers Look For
- Code follows style guidelines
- Changes are well-tested
- Translations are updated (if UI changes)
- No regressions introduced
- Documentation updated (if needed)
- Commit messages are clear

### Review Timeline
- Small fixes: 1-3 days
- Medium features: 3-7 days
- Large features: 1-2 weeks

### After Review
- Address reviewer feedback
- Update pull request with changes
- Request re-review when ready

---

## Questions?

If you have questions about contributing:
1. Check this document first
2. Read the [USER_GUIDE.md](USER_GUIDE.md)
3. Contact the maintainer

---

## Thank You!

Your contributions make KernelCustom Manager better for everyone. Whether you're reporting bugs, testing on different hardware, submitting code, or improving documentation, we appreciate your help!

**Special thanks to all contributors and testers who help make this project possible.**

---

## License

By contributing to KernelCustom Manager, you agree that your contributions will be licensed under the GPL-3.0 license.
