from __future__ import annotations

from pathlib import Path

from prism.media.base import MediaItem, detect_kind


class LocalMediaProvider:
    """Reads media straight from a local directory. This is the simplest
    provider -- drop files into `directory` and they show up in the
    playlist, in name-sorted order."""

    name = "local"

    def __init__(self, directory: Path, recursive: bool = True) -> None:
        self.directory = Path(directory).expanduser()
        self.recursive = recursive

    def list_items(self) -> list[MediaItem]:
        if not self.directory.is_dir():
            return []

        pattern = "**/*" if self.recursive else "*"
        items: list[MediaItem] = []

        for candidate in sorted(self.directory.glob(pattern)):
            if not candidate.is_file():
                continue

            kind = detect_kind(candidate)
            if kind is None:
                continue

            items.append(
                MediaItem(
                    id=str(candidate.relative_to(self.directory)),
                    kind=kind,
                    title=candidate.stem,
                    local_path=candidate,
                    source_ref=str(candidate),
                )
            )

        return items

    def resolve(self, item: MediaItem) -> Path:
        if item.local_path is None:
            item.local_path = Path(item.source_ref)

        return item.local_path

    def close(self) -> None:
        pass
