"""
PolicyKit helper for privileged operations
Uses the kernelcustom-helper script with auth_admin_keep policy
"""

import subprocess
from pathlib import Path


class PkexecHelper:
    """Helper class for PolicyKit authenticated operations"""

    HELPER_PATH = "/usr/local/bin/kernelcustom-helper"

    @staticmethod
    def is_helper_installed():
        """Check if the helper script is installed"""
        return Path(PkexecHelper.HELPER_PATH).exists()

    @staticmethod
    def _run_helper(action, *args):
        """Run helper script with pkexec"""
        cmd = ["pkexec", PkexecHelper.HELPER_PATH, action] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        return result.returncode == 0, result.stdout, result.stderr

    @staticmethod
    def install_packages(*packages):
        """Install kernel packages"""
        return PkexecHelper._run_helper("install-packages", *packages)

    @staticmethod
    def remove_packages(*packages):
        """Remove kernel packages"""
        return PkexecHelper._run_helper("remove-packages", *packages)

    @staticmethod
    def reboot():
        """Reboot the system"""
        return PkexecHelper._run_helper("reboot")

    @staticmethod
    def copy_sources(source, dest):
        """Copy kernel sources to /usr/src/"""
        return PkexecHelper._run_helper("copy-sources", str(source), str(dest))

    @staticmethod
    def create_link(target, link):
        """Create symbolic link in /usr/src/"""
        return PkexecHelper._run_helper("create-link", str(target), str(link))

    @staticmethod
    def remove_sources(path):
        """Remove kernel sources from /usr/src/"""
        return PkexecHelper._run_helper("remove-sources", str(path))
