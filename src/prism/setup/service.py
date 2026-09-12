from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

SERVICE_NAME = "prism.service"
SERVICE_PATH = Path("/etc/systemd/system") / SERVICE_NAME

UNIT_TEMPLATE = """\
[Unit]
Description=Prism CEC media player
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
User={user}
Environment=HOME={home}
Environment=XDG_RUNTIME_DIR=/run/user/{uid}

[Install]
WantedBy=multi-user.target
"""


class ServiceError(RuntimeError):
    pass


class ServiceManager:
    """Installs/removes/queries the `prism run` systemd unit, so Prism can
    start automatically on boot instead of needing to be launched by
    hand every time."""

    def __init__(self, service_path: Path = SERVICE_PATH) -> None:
        self.service_path = service_path

    # ------------------------------------------------------------------
    # Unit generation
    # ------------------------------------------------------------------

    @staticmethod
    def _exec_start() -> str:
        exe = shutil.which("prism")
        if exe:
            return f"{exe} run"
        return f"{sys.executable} -m prism.cli.main run"

    def _unit_contents(self) -> str:
        user = os.environ.get("SUDO_USER") or os.environ.get("USER", "root")
        home = os.path.expanduser(f"~{user}")

        try:
            import pwd

            uid = pwd.getpwnam(user).pw_uid
        except (ImportError, KeyError):
            uid = 0

        return UNIT_TEMPLATE.format(
            exec_start=self._exec_start(),
            user=user,
            home=home,
            uid=uid,
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def install(self, start: bool = True) -> None:
        self._require_root()

        self.service_path.write_text(self._unit_contents(), encoding="utf-8")

        self._systemctl("daemon-reload")
        self._systemctl("enable", SERVICE_NAME)

        if start:
            self._systemctl("restart", SERVICE_NAME)

        print(f"Installed {SERVICE_NAME} -> {self.service_path}")
        print("It will now start automatically on boot.")

    def uninstall(self) -> None:
        self._require_root()

        self._systemctl("disable", "--now", SERVICE_NAME)

        if self.service_path.is_file():
            self.service_path.unlink()

        self._systemctl("daemon-reload")

        print(f"Removed {SERVICE_NAME}")

    def status(self) -> None:
        subprocess.run(
            ["systemctl", "status", SERVICE_NAME, "--no-pager"], check=False
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _require_root() -> None:
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            raise ServiceError(
                "This action requires root -- try: sudo prism service install"
            )

    @staticmethod
    def _systemctl(*args: str) -> None:
        subprocess.run(["systemctl", *args], check=True)
