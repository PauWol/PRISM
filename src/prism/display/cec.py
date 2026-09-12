from __future__ import annotations

import re
import subprocess
import time
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

    def __init__(self, device: str | None = None) -> None:
        self.device = device or self._find_adapter()
        self.logical_address = 4  # Playback Device 1
        self.physical_address = self._get_physical_address()

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
        timeout: float = 10.0,
    ) -> subprocess.CompletedProcess[str]:
        cmd = ["cec-ctl", "-d", self.device, *args]

        try:
            result = subprocess.run(
                cmd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise CECError(
                "cec-ctl was not found. Install the v4l-utils package."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise CECError(
                f"cec-ctl timed out after {timeout:.1f}s: {' '.join(cmd)}"
            ) from exc

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
        except CECError:
            return False

        output = result.stdout

        return (
            result.returncode == 0 and "Capabilities" in output and "Transmit" in output
        )

    def adapter_info(self) -> str:
        return self._run("--all", check=True).stdout

    def _get_physical_address(self) -> str:
        """
        Read the physical address reported by cec-ctl.

        Example:
            Physical Address : 3.0.0.0
        """
        result = self._run("--all", check=True)

        match = re.search(
            r"Physical Address\s*:\s*([0-9A-Fa-f]\."
            r"[0-9A-Fa-f]\."
            r"[0-9A-Fa-f]\."
            r"[0-9A-Fa-f])",
            result.stdout,
        )

        if not match:
            raise CECError("Could not determine CEC physical address from adapter.")

        return match.group(1)

    # ------------------------------------------------------------------
    # Logical address
    # ------------------------------------------------------------------

    def configure_playback(self) -> bool:
        """
        Register this Pi as a playback device.

        The Raspberry Pi adapter normally already exposes:
            Logical Address : 4 (Playback Device 1)
        """
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

            if not self._poll_acknowledged(output):
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
        """
        Turn the display on using Image View On.

        This is the exact cec-ctl operation verified on the Raspberry Pi:
            cec-ctl --to 0 --image-view-on
        """
        result = self._run(
            "--to",
            str(device),
            "--image-view-on",
        )

        return self._transmit_succeeded(result)

    def active_source(
        self,
        physical_address: str | None = None,
        device: int = 0,
    ) -> bool:
        """
        Tell the TV that this playback device is the active source.

        Uses the native cec-ctl command:

            cec-ctl --to 0 --active-source phys-addr=3.0.0.0
        """
        physical_address = physical_address or self.physical_address

        self._validate_physical_address(physical_address)

        result = self._run(
            "--to",
            str(device),
            "--active-source",
            f"phys-addr={physical_address}",
        )

        return self._transmit_succeeded(result)

    def wake_and_activate(
        self,
        device: int = 0,
        delay: float = 1.0,
    ) -> bool:
        """
        Wake the display and make this Pi the active HDMI-CEC source.

        Exact sequence:

            cec-ctl --to 0 --image-view-on
            sleep 1
            cec-ctl --to 0 --active-source phys-addr=3.0.0.0
        """
        if not self.power_on(device):
            return False

        time.sleep(delay)

        return self.active_source(
            physical_address=self.physical_address,
            device=device,
        )

    def standby(self, device: int = 0) -> bool:
        """Put the display into standby."""
        result = self._run(
            "--to",
            str(device),
            "--standby",
        )

        return self._transmit_succeeded(result)

    def power_status(self, device: int = 0) -> str | None:
        """Ask the display for its power state."""
        result = self._run(
            "--to",
            str(device),
            "--give-device-power-status",
        )

        if result.returncode != 0:
            return None

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
            if re.search(rf"\b{state}\b", result.stdout, re.IGNORECASE):
                if "NOT ACKNOWLEDGED" not in result.stdout.upper():
                    return state

        return None

    # ------------------------------------------------------------------
    # Fallback tests
    # ------------------------------------------------------------------

    def fallback_tests(
        self,
        device: int = 0,
    ) -> dict[str, bool | str | None]:
        """
        Try increasingly basic CEC operations.

        Useful when normal commands don't receive acknowledgements.
        """
        results: dict[str, bool | str | None] = {}

        # 1. Poll
        poll = self._run(
            "--to",
            str(device),
            "--poll",
        )
        results["poll"] = self._poll_acknowledged(poll.stdout)

        # 2. Power status
        results["power_status"] = self.power_status(device)

        # 3. Physical address
        physical = self._run(
            "--to",
            str(device),
            "--give-physical-address",
        )
        results["physical_address"] = self._transmit_succeeded(physical)

        # 4. Vendor ID
        vendor = self._run(
            "--to",
            str(device),
            "--give-device-vendor-id",
        )
        results["vendor_id"] = self._transmit_succeeded(vendor)

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
            "physical_address": self.physical_address,
            "logical_address": self.logical_address,
            "playback_configured": False,
            "devices": [],
            "best_device": None,
        }

        if not self.supports_cec():
            return result

        result["cec_supported"] = True

        result["playback_configured"] = self.configure_playback()
        result["logical_address"] = self.logical_address

        # Refresh the physical address after playback configuration.
        try:
            self.physical_address = self._get_physical_address()
            result["physical_address"] = self.physical_address
        except CECError:
            pass

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
    def _validate_physical_address(address: str) -> None:
        if not re.fullmatch(
            r"[0-9A-Fa-f]\.[0-9A-Fa-f]\.[0-9A-Fa-f]\.[0-9A-Fa-f]",
            address,
        ):
            raise ValueError("Physical address must look like 3.0.0.0")

    @staticmethod
    def _poll_acknowledged(output: str) -> bool:
        """
        Poll replies explicitly contain ACK/acknowledgement information.
        """
        upper = output.upper()

        return "NOT ACKNOWLEDGED" not in upper and (
            "ACK" in upper or "ACKNOWLEDGED" in upper
        )

    @staticmethod
    def _transmit_succeeded(
        result: subprocess.CompletedProcess[str],
    ) -> bool:
        """
        Transmission commands do not necessarily print 'ACKNOWLEDGED'.

        Your working output contains:

            Transmit ...
            Sequence: ...

        Therefore returncode is the primary success signal, while an
        explicit 'NOT ACKNOWLEDGED' means failure.
        """
        if result.returncode != 0:
            return False

        return "NOT ACKNOWLEDGED" not in result.stdout.upper()


# ----------------------------------------------------------------------
# Standalone test
# ----------------------------------------------------------------------

if __name__ == "__main__":
    cec = CEC()

    print(f"CEC adapter:       {cec.device}")
    print(f"CEC physical addr: {cec.physical_address}")
    print(f"CEC logical addr:  {cec.logical_address}")

    if not cec.supports_cec():
        raise SystemExit("CEC is not supported by the adapter.")

    print("\nWaking display and selecting Pi as active source...")

    if cec.wake_and_activate():
        print("CEC wake + active source: OK")
    else:
        print("CEC wake + active source: FAILED")

    print("\nDevices:")

    for device in cec.find_devices():
        print(f"  {device.logical_address}: {device.name}")

    print(f"\nBest device: {cec.find_best_device()}")
