from __future__ import annotations

import json
import socket
import subprocess
import time
from pathlib import Path


class MpvError(RuntimeError):
    pass


class MpvPlayer:
    """
    Thin wrapper around a long-lived `mpv` process, controlled over its
    JSON IPC socket (https://mpv.io/manual/stable/#json-ipc).

    mpv is started once, in idle mode, and kept running for the whole
    session -- individual images/text-cards/videos/audio tracks are loaded
    into it one after another with `loadfile ... replace`. This is what
    makes "combined mode" (moving seamlessly between images, video, and
    audio) reliable: there's no per-item process restart, no window
    flicker, and no re-negotiating the HDMI/CEC link.

    Only the real `mpv` binary is required -- no Python bindings to
    libmpv, which keeps installation on a Raspberry Pi simple.
    """

    def __init__(
        self,
        socket_path: Path,
        fullscreen: bool = True,
        volume: int = 80,
        extra_args: list[str] | None = None,
    ) -> None:
        self.socket_path = Path(socket_path)
        self.fullscreen = fullscreen
        self.volume = volume
        self.extra_args = extra_args or []

        self._proc: subprocess.Popen | None = None
        self._sock: socket.socket | None = None
        self._req_id = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self.socket_path.exists():
            self.socket_path.unlink()

        args = [
            "mpv",
            "--idle=yes",
            "--force-window=yes",
            f"--input-ipc-server={self.socket_path}",
            f"--volume={self.volume}",
            "--image-display-duration=inf",  # duration is set per-item instead
            "--loop-playlist=no",
            "--no-terminal",
            "--osc=no",
            "--really-quiet",
        ]

        if self.fullscreen:
            args.append("--fullscreen=yes")

        args.extend(self.extra_args)

        self._proc = subprocess.Popen(args)
        self._connect(timeout=10.0)

    def _connect(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self.socket_path.exists():
                try:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.connect(str(self.socket_path))
                    self._sock = sock
                    return
                except OSError:
                    pass

            time.sleep(0.1)

        raise MpvError("Timed out waiting for mpv's IPC socket to appear")

    def stop(self) -> None:
        if self._sock is not None:
            try:
                self.command("quit")
            except MpvError:
                pass
            finally:
                self._sock.close()
                self._sock = None

        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ------------------------------------------------------------------
    # IPC
    # ------------------------------------------------------------------

    def command(self, *args) -> object:
        if self._sock is None:
            raise MpvError("mpv is not running (call start() first)")

        self._req_id += 1
        payload = json.dumps({"command": list(args), "request_id": self._req_id}) + "\n"

        try:
            self._sock.sendall(payload.encode("utf-8"))
            return self._read_response(self._req_id)
        except OSError as exc:
            raise MpvError(f"Lost connection to mpv: {exc}") from exc

    def _read_response(self, request_id: int, timeout: float = 5.0) -> object:
        self._sock.settimeout(timeout)
        buffer = b""

        while True:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise MpvError("mpv closed the IPC connection")

            buffer += chunk

            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if not line.strip():
                    continue

                message = json.loads(line)

                # Unsolicited events (e.g. "property-change") don't carry
                # our request_id -- skip them and keep reading.
                if message.get("request_id") == request_id:
                    if message.get("error") not in (None, "success"):
                        raise MpvError(str(message))
                    return message.get("data")

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play_file(self, path: Path, duration: float | None = None) -> None:
        """Replace whatever is currently playing with `path`. If `duration`
        is given (images/rendered text), mpv will treat that as end-of-file
        after that many seconds; otherwise it plays to the file's natural
        end (video/audio)."""
        self.command("set_property", "image-display-duration", duration or "inf")
        self.command("loadfile", str(path), "replace")

    def set_volume(self, volume: int) -> None:
        self.command("set_property", "volume", volume)

    def wait_until_idle(self, poll_interval: float = 0.5, timeout: float | None = None) -> None:
        """Block until the current item finishes playing (mpv's
        `idle-active` property becomes true), mpv exits, or `timeout`
        elapses -- whichever comes first. The timeout is a safety net so a
        stuck/corrupt file can't wedge the whole playlist forever."""
        deadline = None if timeout is None else time.monotonic() + timeout

        while True:
            if not self.is_alive():
                return

            try:
                if self.command("get_property", "idle-active"):
                    return
            except MpvError:
                return

            if deadline is not None and time.monotonic() > deadline:
                return

            time.sleep(poll_interval)
