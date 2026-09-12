from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def path(value: str | Path) -> Path:
    """Return a normalized Path with '~' expanded."""
    return Path(value).expanduser()


HOME_DIR = path(os.getenv("HOME", "~"))

ENV_PATH = HOME_DIR / "prism" / ".env"

CONFIG_DIR = Path("/etc/prism")
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def load_dot_env() -> bool:
    """Load Prism's .env file if it exists."""
    if not ENV_PATH.is_file():
        return False

    return load_dotenv(
        dotenv_path=ENV_PATH,
        override=False,
    )


ENV_LOADED = load_dot_env()


def get_env(key: str, default: object) -> str | object:
    """Return an environment variable or its default value."""
    value = os.getenv(key)

    if value is None:
        return default

    return value


def get_env_str(key: str, default: str) -> str:
    """Return an environment variable as a string."""
    return os.getenv(key, default)


def get_env_bool(key: str, default: bool = False) -> bool:
    """Parse a boolean environment variable."""
    value = os.getenv(key)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def get_env_int(key: str, default: int) -> int:
    """Parse an integer environment variable."""
    value = os.getenv(key)

    if value is None:
        return default

    try:
        return int(value.strip())
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {key!r} must be an integer, got {value!r}"
        ) from exc


def get_env_float(key: str, default: float) -> float:
    """Parse a floating-point environment variable."""
    value = os.getenv(key)

    if value is None:
        return default

    try:
        return float(value.strip())
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {key!r} must be a float, got {value!r}"
        ) from exc


def set_env(key: str, value: object) -> None:
    """Set or update a value in Prism's .env file."""
    ENV_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines = (
        ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.is_file() else []
    )

    prefix = f"{key}="
    new_line = f"{key}={value}"

    for index, line in enumerate(lines):
        if line.strip().startswith(prefix):
            lines[index] = new_line
            break
    else:
        lines.append(new_line)

    ENV_PATH.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


DEFAULT_ENV: dict[str, str] = {
    "TERMINAL_NO_COLOR": "0",
    "PYTHONUNBUFFERED": "1",
    # Logging
    "LOG_LEVEL": "INFO",
    "LOG_CONSOLE": "1",
    "LOG_JSON": "0",
    "LOG_ROTATE": "1",
    "LOG_MAX_BYTES": "10485760",
    "LOG_BACKUP_COUNT": "2",
}

TERMINAL_NO_COLOR = get_env_bool(
    "TERMINAL_NO_COLOR",
    False,
)


def _default_log_file() -> Path:
    """
    Return Prism's default log location.

    Root/system installation:
        /var/log/prism/prism.log

    User installation:
        ~/.local/state/prism/prism.log
    """
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return Path("/var/log/prism/prism.log")

    return HOME_DIR / ".local" / "state" / "prism" / "prism.log"


LOG_LEVEL = get_env_str(
    "LOG_LEVEL",
    DEFAULT_ENV["LOG_LEVEL"],
)

LOG_FILE = path(
    get_env_str(
        "LOG_FILE",
        str(_default_log_file()),
    )
)

LOG_CONSOLE = get_env_bool(
    "LOG_CONSOLE",
    True,
)

LOG_JSON = get_env_bool(
    "LOG_JSON",
    False,
)

LOG_ROTATE = get_env_bool(
    "LOG_ROTATE",
    True,
)

LOG_MAX_BYTES = get_env_int(
    "LOG_MAX_BYTES",
    10 * 1024 * 1024,
)

LOG_BACKUP_COUNT = get_env_int(
    "LOG_BACKUP_COUNT",
    2,
)

EXTERNAL_DEPENDENCIES = (
    "v4l-utils",
    "dialog",
    "uv",
)

COMMANDS = {
    "v4l-utils": [
        "sudo",
        "apt",
        "install",
        "-y",
        "v4l-utils",
    ],
    "dialog": [
        "sudo",
        "apt",
        "install",
        "-y",
        "dialog",
    ],
    "uv": [
        "sh",
        "-c",
        "curl -LsSf https://astral.sh/uv/install.sh | sh",
    ],
    "v4l-utils-remove": [
        "sudo",
        "apt",
        "remove",
        "-y",
        "v4l-utils",
    ],
    "dialog-remove": [
        "sudo",
        "apt",
        "remove",
        "-y",
        "dialog",
    ],
    "uv-remove": [
        "rm",
        "-f",
        "~/.local/bin/uv",
        "~/.local/bin/uvx",
    ],
}


def make_default_env() -> Path | None:
    """
    Create Prism's default .env file.

    Returns:
        Created path, or None if it already exists.
    """
    if ENV_PATH.exists():
        return None

    ENV_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    content = "\n".join(f"{key}={value}" for key, value in DEFAULT_ENV.items())

    ENV_PATH.write_text(
        content + "\n",
        encoding="utf-8",
    )

    return ENV_PATH
