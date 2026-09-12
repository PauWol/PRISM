"""
Prism's persistent configuration.

Everything Prism needs to know in order to run -- where media comes from,
how it should be displayed, and how HDMI-CEC should behave -- lives in a
single YAML file (by default `/etc/prism/config.yaml`). This module defines
that schema and how to load/save it.

The `dialog`-based editor in `prism.cli.config_ui` reads and writes this
same `PrismConfig` object.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

from prism.foundation.constants import CONFIG_FILE

VALID_SOURCE_TYPES = ("local", "remote", "api")


@dataclass
class SourceConfig:
    """Where media comes from. Kept generic so a `local` setup today can be
    switched to `remote`/`api` later without touching any other code."""

    type: str = "local"  # one of VALID_SOURCE_TYPES

    # Used when type == "local"
    local_path: str = "~/prism/media"

    # Used when type == "remote": a URL returning a JSON list of
    # {"id", "url", "title"?, "duration"?} objects.
    remote_url: str = ""

    # Used when type == "api": an endpoint returning either that same list,
    # or {"items": [...]}. api_key (optional) is sent as a Bearer token.
    api_endpoint: str = ""
    api_key: str = ""

    # Used by both "remote" and "api": where downloaded files are cached.
    cache_dir: str = "~/.cache/prism/media"


@dataclass
class DisplayConfig:
    """How long items are shown and how the player behaves."""

    image_duration: float = 10.0
    text_duration: float = 10.0
    shuffle: bool = False
    loop: bool = True
    volume: int = 80
    fullscreen: bool = True


@dataclass
class CecConfig:
    """How Prism talks to the TV over HDMI-CEC."""

    enabled: bool = True
    device: str = ""  # blank = auto-detect the adapter under /dev
    power_on_at_start: bool = True
    standby_at_stop: bool = False
    active_source: bool = True
    tv_logical_address: int = 0  # 0 == TV


def _filtered(dataclass_type: type, data: dict[str, Any]) -> dict[str, Any]:
    """Drop unknown keys so old/foreign config files don't crash loading."""
    valid_names = {f.name for f in fields(dataclass_type)}
    return {key: value for key, value in data.items() if key in valid_names}


@dataclass
class PrismConfig:
    source: SourceConfig = field(default_factory=SourceConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    cec: CecConfig = field(default_factory=CecConfig)

    @classmethod
    def load(cls, path: Path | None = None) -> "PrismConfig":
        """Load config from `path` (default: CONFIG_FILE). Missing file ->
        defaults, so Prism always has something sensible to run with."""
        path = path or CONFIG_FILE

        if not path.is_file():
            return cls()

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

        return cls(
            source=SourceConfig(**_filtered(SourceConfig, raw.get("source") or {})),
            display=DisplayConfig(**_filtered(DisplayConfig, raw.get("display") or {})),
            cec=CecConfig(**_filtered(CecConfig, raw.get("cec") or {})),
        )

    def save(self, path: Path | None = None) -> Path:
        """Write config to `path` (default: CONFIG_FILE), creating parent
        directories as needed."""
        path = path or CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "source": asdict(self.source),
            "display": asdict(self.display),
            "cec": asdict(self.cec),
        }

        path.write_text(
            yaml.safe_dump(data, sort_keys=False),
            encoding="utf-8",
        )

        return path

    def validate(self) -> list[str]:
        """Return a list of human-readable problems, if any."""
        problems: list[str] = []

        if self.source.type not in VALID_SOURCE_TYPES:
            problems.append(
                f"source.type must be one of {VALID_SOURCE_TYPES}, got {self.source.type!r}"
            )

        if self.source.type == "local" and not self.source.local_path:
            problems.append("source.local_path must be set for a local source")

        if self.source.type == "remote" and not self.source.remote_url:
            problems.append("source.remote_url must be set for a remote source")

        if self.source.type == "api" and not self.source.api_endpoint:
            problems.append("source.api_endpoint must be set for an api source")

        if self.display.volume < 0 or self.display.volume > 100:
            problems.append("display.volume must be between 0 and 100")

        return problems


def default_config_path() -> Path:
    return CONFIG_FILE
