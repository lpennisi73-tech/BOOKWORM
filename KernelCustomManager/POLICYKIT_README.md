# PolicyKit Authentication System

## 🔐 Overview

KernelCustom Manager uses PolicyKit to handle privileged operations securely. With the new system, **you only need to enter your password once every 5 minutes** instead of multiple times for each operation.

## How It Works

### Traditional Method (without PolicyKit helper)
- Install package → password ❌
- Install headers → password ❌
- Fix dependencies → password ❌
- **Total: 3 password prompts**

### New Method (with PolicyKit helper)
- Install both packages + fix deps → password ✅
- **Total: 1 password prompt**

The authentication is cached for **5 minutes**, so subsequent operations won't require re-authentication.

## Installation

The PolicyKit helper is **automatically installed** when you run `install.sh`. It installs two components:

1. **Helper script**: `/usr/local/bin/kernelcustom-helper`
   - Handles all privileged operations
   - Executed via `pkexec` with PolicyKit

2. **PolicyKit rules**: `/usr/share/polkit-1/actions/com.kernelcustom.manager.policy`
   - Defines authentication policies
   - Enables `auth_admin_keep` (5-minute cache)

## Security

The PolicyKit system is **more secure** than alternatives like `sudo NOPASSWD` because:

- ✅ Still requires password authentication
- ✅ Uses system-wide PolicyKit framework
- ✅ Auditable through system logs
- ✅ Can be revoked by system administrator
- ✅ Works with any authentication method (password, fingerprint, etc.)

## Supported Operations

The helper script supports these operations:

- `install-packages` - Install kernel .deb packages
- `remove-packages` - Remove kernel packages with autoremove
- `reboot` - Reboot the system
- `copy-sources` - Copy kernel sources to /usr/src/
- `create-link` - Create symbolic links in /usr/src/
- `remove-sources` - Remove kernel sources from /usr/src/

## Fallback Mode

If the PolicyKit helper is **not installed**, the application automatically falls back to the traditional method using direct `pkexec` calls. This means:

- ⚠️ You'll be asked for password multiple times
- ✅ Application still works normally
- ℹ️ No data loss or functionality issues

## Manual Installation

If you skipped the automatic installation, you can install manually:

```bash
# Install helper and rules
sudo cp kernelcustom-helper /usr/local/bin/
sudo chmod +x /usr/local/bin/kernelcustom-helper
sudo cp com.kernelcustom.manager.policy /usr/share/polkit-1/actions/
```

## Uninstallation

To remove the PolicyKit helper:

```bash
# Run uninstall script
./uninstall-policykit.sh

# Or manually
sudo rm /usr/local/bin/kernelcustom-helper
sudo rm /usr/share/polkit-1/actions/com.kernelcustom.manager.policy
```

## Verification

To check if the helper is installed:

```bash
# Check helper
ls -l /usr/local/bin/kernelcustom-helper

# Check PolicyKit rules
ls -l /usr/share/polkit-1/actions/com.kernelcustom.manager.policy
```

## Troubleshooting

### Password still asked multiple times

**Possible causes:**
1. PolicyKit rules not installed correctly
2. PolicyKit daemon not running
3. System configuration overrides

**Solutions:**
```bash
# Reinstall PolicyKit components
./uninstall-policykit.sh
sudo cp kernelcustom-helper /usr/local/bin/
sudo chmod +x /usr/local/bin/kernelcustom-helper
sudo cp com.kernelcustom.manager.policy /usr/share/polkit-1/actions/

# Restart PolicyKit daemon
sudo systemctl restart polkit
```

### Operation fails with permission error

**Check:**
```bash
# Verify helper has correct permissions
ls -l /usr/local/bin/kernelcustom-helper
# Should show: -rwxr-xr-x (executable)

# Test helper manually
pkexec /usr/local/bin/kernelcustom-helper
# Should show usage message
```

## Technical Details

### PolicyKit Policy Configuration

The policy uses `auth_admin_keep` which means:
- Requires admin authentication
- Keeps authorization for 5 minutes
- Applies to same user session

```xml
<defaults>
  <allow_any>auth_admin</allow_any>
  <allow_inactive>auth_admin</allow_inactive>
  <allow_active>auth_admin_keep</allow_active>
</defaults>
```

### Helper Script Security

The helper script:
- Only accepts specific predefined actions
- Validates all arguments
- Uses `set -e` to fail fast on errors
- Runs with elevated privileges only when needed
- Logs all operations through PolicyKit

## Compatibility

**Supported distributions:**
- Ubuntu 18.04+
- Debian 10+
- Fedora 30+
- Arch Linux
- Linux Mint
- Pop!_OS
- Any distribution with PolicyKit/polkit

**Requirements:**
- PolicyKit (polkit) installed
- pkexec command available
- D-Bus running

---

**For more information**, see the main README.md
