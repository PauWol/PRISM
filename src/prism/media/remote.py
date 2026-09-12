from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import requests

from prism.media.base import MediaItem, detect_kind


def _safe_name(value: str) -> str:
    """Turn an arbitrary id/url into something safe to use as a filename."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in value) or "item"


def parse_entries(entries: list[dict]) -> list[MediaItem]:
    """Turn a list of {"id"?, "url", "title"?, "duration"?} dicts into
    MediaItems, skipping anything with an unrecognized file type."""
    items: list[MediaItem] = []

    for entry in entries:
        url = entry["url"]
        suffix = Path(urlparse(url).path).suffix
        kind = detect_kind(Path(f"x{suffix}"))

        if kind is None:
            continue

        items.append(
            MediaItem(
                id=str(entry.get("id", url)),
                kind=kind,
                title=entry.get("title", ""),
                source_ref=url,
                duration=entry.get("duration"),
            )
        )

    return items


class RemoteMediaProvider:
    """
    Reads a JSON manifest from a URL describing a playlist of media, e.g.:

        [
          {"id": "1", "url": "https://example.com/a.jpg", "title": "A"},
          {"id": "2", "url": "https://example.com/b.mp4", "duration": 12}
        ]

    Each item is downloaded into a local cache directory the first time
    it's needed, then reused on subsequent runs (until the cache is
    cleared).
    """

    name = "remote"

    def __init__(
        self,
        manifest_url: str,
        cache_dir: Path,
        timeout: float = 15.0,
    ) -> None:
        self.manifest_url = manifest_url
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {}

    def list_items(self) -> list[MediaItem]:
        response = requests.get(
            self.manifest_url, headers=self._headers(), timeout=self.timeout
        )
        response.raise_for_status()

        return parse_entries(response.json())

    def resolve(self, item: MediaItem) -> Path:
        if item.local_path and item.local_path.is_file():
            return item.local_path

        suffix = Path(urlparse(item.source_ref).path).suffix or ""
        target = self.cache_dir / f"{_safe_name(item.id)}{suffix}"

        if not target.is_file():
            response = requests.get(
                item.source_ref,
                headers=self._headers(),
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()

            tmp_path = target.with_suffix(target.suffix + ".part")

            with tmp_path.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    fh.write(chunk)

            tmp_path.replace(target)

        item.local_path = target
        return target

    def close(self) -> None:
        pass
