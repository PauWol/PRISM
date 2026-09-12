from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


class MediaKind(str, enum.Enum):
    IMAGE = "image"
    TEXT = "text"
    VIDEO = "video"
    AUDIO = "audio"


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}
TEXT_EXTENSIONS = {".txt", ".md"}


def detect_kind(path: Path) -> MediaKind | None:
    """Guess a MediaKind from a file extension. Returns None for anything
    unrecognized, so callers can skip it rather than guess wrong."""
    suffix = path.suffix.lower()

    if suffix in IMAGE_EXTENSIONS:
        return MediaKind.IMAGE
    if suffix in VIDEO_EXTENSIONS:
        return MediaKind.VIDEO
    if suffix in AUDIO_EXTENSIONS:
        return MediaKind.AUDIO
    if suffix in TEXT_EXTENSIONS:
        return MediaKind.TEXT

    return None


@dataclass
class MediaItem:
    """A single piece of displayable/playable content."""

    id: str
    kind: MediaKind
    title: str = ""

    # Resolved, local path mpv/Pillow can actually read. Populated by
    # MediaProvider.resolve() -- may be None until then for remote items.
    local_path: Path | None = None

    # Wherever this came from (a local path, or a remote URL), kept around
    # so a provider can re-resolve/re-download it if the cache is cleared.
    source_ref: str = ""

    # Seconds to display for (images/text only). None = use the display
    # config's default duration.
    duration: float | None = None

    metadata: dict = field(default_factory=dict)


@runtime_checkable
class MediaProvider(Protocol):
    """
    Anything that can list playable content and guarantee it's available on
    local disk. `local`, `remote`, and `api` providers all implement this
    same, small interface, so the playback runtime doesn't need to know or
    care where the media actually comes from.
    """

    name: str

    def list_items(self) -> list[MediaItem]:
        """Return the current playlist, in playback order."""
        ...

    def resolve(self, item: MediaItem) -> Path:
        """Ensure `item` is available locally (downloading it if needed)
        and return its local path."""
        ...

    def close(self) -> None:
        """Release any resources (connections, temp files, etc.)."""
        ...
