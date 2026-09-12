from __future__ import annotations

from pathlib import Path

from prism.config import PrismConfig
from prism.media.api import ApiMediaProvider
from prism.media.base import MediaProvider
from prism.media.local import LocalMediaProvider
from prism.media.remote import RemoteMediaProvider


def build_provider(config: PrismConfig) -> MediaProvider:
    """Instantiate the MediaProvider described by `config.source`."""
    source = config.source

    if source.type == "local":
        return LocalMediaProvider(Path(source.local_path))

    if source.type == "remote":
        return RemoteMediaProvider(
            manifest_url=source.remote_url,
            cache_dir=Path(source.cache_dir),
        )

    if source.type == "api":
        return ApiMediaProvider(
            endpoint=source.api_endpoint,
            cache_dir=Path(source.cache_dir),
            api_key=source.api_key or None,
        )

    raise ValueError(f"Unknown media source type: {source.type!r}")
