from __future__ import annotations

import logging
import random
import time
from pathlib import Path

from prism.config import PrismConfig
from prism.display.cec import CEC, CECError
from prism.display.player import MpvPlayer
from prism.display.textrender import render_text_file_to_image
from prism.media.base import MediaItem, MediaKind, MediaProvider
from prism.media.factory import build_provider

logger = logging.getLogger(__name__)

MPV_SOCKET = Path("/tmp/prism-mpv.sock")


class PrismRuntime:
    """
    Owns the whole running session: it pulls the playlist from whatever
    MediaProvider is configured, hands each item to mpv (rendering text to
    an image first), and manages the TV over CEC around the edges (power
    on / claim active source at start, optional standby at stop).

    CEC failures never take the whole thing down -- if no adapter is found,
    or it doesn't support CEC, Prism logs a warning and keeps playing media
    without TV control.
    """

    def __init__(self, config: PrismConfig | None = None) -> None:
        self.config = config or PrismConfig.load()
        self.provider: MediaProvider = build_provider(self.config)
        self.player = MpvPlayer(
            socket_path=MPV_SOCKET,
            fullscreen=self.config.display.fullscreen,
            volume=self.config.display.volume,
        )
        self.cec: CEC | None = None
        self._stop = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _init_cec(self) -> None:
        if not self.config.cec.enabled:
            logger.info("CEC disabled in config; skipping TV control")
            return

        try:
            self.cec = CEC(device=self.config.cec.device or None)
        except CECError as exc:
            logger.warning("No CEC adapter found, continuing without TV control: %s", exc)
            self.cec = None
            return

        if not self.cec.supports_cec():
            logger.warning("CEC adapter found but doesn't support CEC; disabling TV control")
            self.cec = None
            return

        self.cec.configure_playback()

        if self.config.cec.power_on_at_start:
            self.cec.power_on(self.config.cec.tv_logical_address)

        if self.config.cec.active_source:
            self.cec.active_source()

    def start(self) -> None:
        self._init_cec()
        self.player.start()

    def stop(self) -> None:
        self._stop = True

        try:
            self.player.stop()
        except Exception:
            logger.exception("Error stopping mpv")

        if self.cec is not None and self.config.cec.standby_at_stop:
            try:
                self.cec.standby(self.config.cec.tv_logical_address)
            except CECError:
                logger.exception("Failed to put TV into standby")

        self.provider.close()

    # ------------------------------------------------------------------
    # Playback loop
    # ------------------------------------------------------------------

    def _playlist(self) -> list[MediaItem]:
        items = self.provider.list_items()

        if self.config.display.shuffle:
            items = list(items)
            random.shuffle(items)

        return items

    def run_forever(self) -> None:
        """Start everything and play the configured playlist until stopped
        (Ctrl+C, or `.stop()` called from elsewhere), looping if
        `display.loop` is set."""
        self.start()

        try:
            while not self._stop:
                items = self._playlist()

                if not items:
                    logger.warning("No media found; retrying in 30s")
                    self._sleep(30)
                    continue

                for item in items:
                    if self._stop:
                        break
                    self._play_item(item)

                if not self.config.display.loop:
                    break
        finally:
            self.stop()

    def _sleep(self, seconds: float) -> None:
        # Broken into short chunks so a stop request is honoured quickly
        # even during the "no media, retry later" backoff.
        end = time.monotonic() + seconds
        while not self._stop and time.monotonic() < end:
            time.sleep(0.5)

    def _play_item(self, item: MediaItem) -> None:
        try:
            local_path = self.provider.resolve(item)
        except Exception:
            logger.exception("Failed to resolve media item %r; skipping", item.id)
            return

        duration = item.duration
        is_still = item.kind in (MediaKind.IMAGE, MediaKind.TEXT)

        if item.kind is MediaKind.TEXT:
            local_path = render_text_file_to_image(
                local_path,
                cache_dir=Path(self.config.source.cache_dir).expanduser() / "text",
            )
            duration = duration or self.config.display.text_duration
        elif item.kind is MediaKind.IMAGE:
            duration = duration or self.config.display.image_duration

        logger.info("Playing %s (%s)", item.id, item.kind.value)

        self.player.play_file(local_path, duration=duration if is_still else None)

        if is_still:
            self.player.wait_until_idle(timeout=(duration or 10) + 10)
        else:
            # Video/audio: no artificial cap, just a generous safety net.
            self.player.wait_until_idle(timeout=6 * 60 * 60)
