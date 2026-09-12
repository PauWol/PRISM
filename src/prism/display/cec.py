from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CECDevice:
    logical_address: int
    name: str
    raw: str


class CECError(RuntimeError):
    pass


class CEC:
    """Small Linux cec-ctl wrapper for HDMI-CEC."""

    def __init__(self, device: str | None = None):
        self.device = device or self._find_adapter()
        self.logical_address = 4  # Playback Device 1

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    @staticmethod
    def _find_adapter() -> str:
        devices = sorted(Path("/dev").glob("cec*"))

        if not devices:
            raise CECError("No CEC adapter found under /dev")

        for device in devices:
            if device.name.startswith("cec") and device.name[3:].isdigit():
                return str(device)

        raise CECError("No usable CEC adapter found")

    def _run(
        self,
        *args: str,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        cmd = ["cec-ctl", "-d", self.device, *args]

        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

        if check and result.returncode != 0:
            raise CECError(result.stdout)

        return result

    # ------------------------------------------------------------------
    # Adapter support
    # ------------------------------------------------------------------

    def supports_cec(self) -> bool:
        """Check that the adapter exists and supports CEC transmission."""

        try:
            result = self._run("--all")
        except FileNotFoundError:
            return False

        output = result.stdout

        return (
            result.returncode == 0 and "Capabilities" in output and "Transmit" in output
        )

    def adapter_info(self) -> str:
        return self._run("--all", check=True).stdout

    # ------------------------------------------------------------------
    # Logical address
    # ------------------------------------------------------------------

    def configure_playback(self) -> bool:
        """Register this Pi as a playback device."""

        result = self._run("--playback")

        if result.returncode != 0:
            return False

        match = re.search(
            r"Logical Address\s+:\s+(\d+)\s+\(Playback Device",
            result.stdout,
        )

        if match:
            self.logical_address = int(match.group(1))

        return True

    # ------------------------------------------------------------------
    # Device discovery
    # ------------------------------------------------------------------

    def find_devices(self) -> list[CECDevice]:
        """Poll all CEC logical addresses and return responding devices."""

        devices: list[CECDevice] = []

        # 0-14 are normal CEC logical addresses.
        for address in range(15):
            result = self._run("--to", str(address), "--poll")

            output = result.stdout

            if "ACK" not in output.upper():
                continue

            # Avoid accidentally discovering ourselves.
            if address == self.logical_address:
                continue

            devices.append(
                CECDevice(
                    logical_address=address,
                    name=self._logical_name(address),
                    raw=output,
                )
            )

        return devices

    @staticmethod
    def _logical_name(address: int) -> str:
        names = {
            0: "TV",
            1: "Recording Device 1",
            2: "Recording Device 2",
            3: "Tuner 1",
            4: "Playback Device 1",
            5: "Audio System",
            6: "Tuner 2",
            7: "Tuner 3",
            8: "Playback Device 2",
            9: "Recording Device 3",
            10: "Tuner 4",
            11: "Playback Device 3",
            12: "Reserved",
            13: "Reserved",
            14: "Free Use",
        }

        return names.get(address, f"CEC Device {address}")

    def find_best_device(self) -> CECDevice | None:
        """
        Prefer the TV/display, then audio system, then any other device.
        """

        devices = self.find_devices()

        if not devices:
            return None

        priority = {
            0: 0,  # TV
            5: 1,  # Audio system
        }

        return min(
            devices,
            key=lambda d: priority.get(d.logical_address, 10),
        )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def power_on(self, device: int = 0) -> bool:
        """Send Image View On."""

        result = self._run(
            "--to",
            str(device),
            "--image-view-on",
        )

        return self._acknowledged(result.stdout)

    def standby(self, device: int = 0) -> bool:
        """Put the display into standby."""

        result = self._run(
            "--to",
            str(device),
            "--standby",
        )

        return self._acknowledged(result.stdout)

    def power_status(self, device: int = 0) -> str | None:
        """Ask the display for its power state."""

        result = self._run(
            "--to",
            str(device),
            "--give-device-power-status",
        )

        match = re.search(
            r"Power Status.*?:\s*(ON|STANDBY|IN TRANSITION TO ON|"
            r"IN TRANSITION TO STANDBY)",
            result.stdout,
            re.IGNORECASE,
        )

        if match:
            return match.group(1).upper()

        # cec-ctl versions may format the response differently.
        for state in ("ON", "STANDBY"):
            if re.search(rf"\b{state}\b", result.stdout):
                if "Not Acknowledged" not in result.stdout:
                    return state

        return None

    def active_source(self, physical_address: str = "1.0.0.0") -> bool:
        """
        Tell the CEC network that this Pi is the active source.

        Uses the raw CEC command because cec-ctl versions differ in their
        --active-source argument syntax.

        0x82 = Active Source
        """

        payload = physical_address.replace(".", "")

        if len(payload) != 4:
            raise ValueError("Physical address must look like 1.0.0.0")

        byte1 = int(payload[:2], 16)
        byte2 = int(payload[2:], 16)

        result = self._run(
            "--to",
            "15",
            "--custom-command",
            f"cmd=0x82,payload=0x{byte1:02x}:0x{byte2:02x}",
        )

        return self._acknowledged(result.stdout)

    # ------------------------------------------------------------------
    # Fallback tests
    # ------------------------------------------------------------------

    def fallback_tests(self, device: int = 0) -> dict[str, bool | str | None]:
        """
        Try increasingly basic CEC operations.

        Useful when normal commands don't receive acknowledgements.
        """

        results: dict[str, bool | str | None] = {}

        # 1. Poll
        poll = self._run("--to", str(device), "--poll")
        results["poll"] = self._acknowledged(poll.stdout)

        # 2. Power status
        results["power_status"] = self.power_status(device)

        # 3. Physical address
        physical = self._run(
            "--to",
            str(device),
            "--give-physical-address",
        )
        results["physical_address"] = self._acknowledged(physical.stdout)

        # 4. Vendor ID
        vendor = self._run(
            "--to",
            str(device),
            "--give-device-vendor-id",
        )
        results["vendor_id"] = self._acknowledged(vendor.stdout)

        return results

    # ------------------------------------------------------------------
    # Complete diagnostic
    # ------------------------------------------------------------------

    def test(self) -> dict:
        """
        Run a complete CEC detection and capability test.
        """

        result = {
            "adapter": self.device,
            "cec_supported": False,
            "playback_configured": False,
            "devices": [],
            "best_device": None,
        }

        if not self.supports_cec():
            return result

        result["cec_supported"] = True

        result["playback_configured"] = self.configure_playback()

        devices = self.find_devices()

        result["devices"] = [
            {
                "logical_address": device.logical_address,
                "name": device.name,
            }
            for device in devices
        ]

        best = self.find_best_device()

        if best:
            result["best_device"] = {
                "logical_address": best.logical_address,
                "name": best.name,
            }

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _acknowledged(output: str) -> bool:
        upper = output.upper()

        return "NOT ACKNOWLEDGED" not in upper and (
            "ACKNOWLEDGED" in upper or "ACK" in upper
        )


if __name__ == "__main__":
    cec = CEC()

    result = cec.test()

    print(f"CEC adapter: {result['adapter']}")
    print(f"CEC supported: {result['cec_supported']}")
    print(f"Playback configured: {result['playback_configured']}")

    print("\nDevices:")

    for device in result["devices"]:
        print(f"  {device['logical_address']}: {device['name']}")

    print(f"\nBest device: {result['best_device']}")
