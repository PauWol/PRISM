from __future__ import annotations

from pathlib import Path

import requests

from prism.media.base import MediaItem
from prism.media.remote import RemoteMediaProvider, parse_entries


class ApiMediaProvider(RemoteMediaProvider):
    """
    Like RemoteMediaProvider, but built for a proper API server:

    - accepts an optional bearer token (`api_key`)
    - accepts either a bare list, or {"items": [...]}, as the response shape

    This is the provider to point at your own backend once you have one --
    everything else (caching, download, kind-detection) is inherited from
    RemoteMediaProvider unchanged.
    """

    name = "api"

    def __init__(
        self,
        endpoint: str,
        cache_dir: Path,
        api_key: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        super().__init__(manifest_url=endpoint, cache_dir=cache_dir, timeout=timeout)
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    def list_items(self) -> list[MediaItem]:
        response = requests.get(
            self.manifest_url, headers=self._headers(), timeout=self.timeout
        )
        response.raise_for_status()

        payload = response.json()
        entries = payload.get("items", []) if isinstance(payload, dict) else payload

        return parse_entries(entries)
