from __future__ import annotations

import shutil
import subprocess

from prism.foundation.constants import COMMANDS


class Installer:
    def install(self, dep: str) -> bool:
        """Install a single dependency."""
        command = COMMANDS.get(dep)

        if command is None:
            print(f"Unknown dependency: {dep}")
            return False

        if self.is_installed(dep):
            print(f"Already installed: {dep}")
            return True

        return self._run(command)

    def install_all(self) -> bool:
        """Install all configured dependencies."""
        success = True

        for dep in COMMANDS:
            if not self.install(dep):
                success = False

        return success

    def test(self, dep: str) -> bool:
        """Test whether a dependency is installed."""
        if dep not in COMMANDS:
            print(f"Unknown dependency: {dep}")
            return False

        installed = self.is_installed(dep)

        if installed:
            print(f"{dep}: installed")
        else:
            print(f"{dep}: not installed")

        return installed

    def test_all(self) -> dict[str, bool]:
        """Test all configured dependencies."""
        return {dep: self.test(dep) for dep in COMMANDS}

    def remove(self, dep: str) -> bool:
        """Remove a single dependency."""
        command = COMMANDS.get(f"{dep}-remove")

        if command is None:
            print(f"No remove command configured for: {dep}")
            return False

        if not self.is_installed(dep):
            print(f"Not installed: {dep}")
            return True

        return self._run(command)

    def _run(self, command: list[str]) -> bool:
        try:
            print(f"Running: {' '.join(command)}")

            subprocess.run(
                command,
                check=True,
            )

            return True

        except FileNotFoundError:
            print(f"Command not found: {command[0]}")
            return False

        except subprocess.CalledProcessError as exc:
            print(f"Command failed ({exc.returncode}): {' '.join(command)}")
            return False

    @staticmethod
    def is_installed(dep: str) -> bool:
        """Check whether the dependency's executable exists."""

        executables = {
            "v4l-utils": "cec-ctl",
            "uv": "uv",
            "dialog": "dialog",
            "mpv": "mpv",
        }

        executable = executables.get(dep)

        if executable is None:
            return False

        return shutil.which(executable) is not None
