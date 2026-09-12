from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEFAULT_SIZE = (1920, 1080)
DEFAULT_FONT_SIZE = 64
BACKGROUND = (10, 10, 10)
FOREGROUND = (240, 240, 240)

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
)


def _load_font(size: int) -> ImageFont.ImageFont:
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)

    # Falls back to Pillow's built-in bitmap font if no truetype font is
    # found on the system -- ugly, but never crashes.
    return ImageFont.load_default()


def render_text_to_image(
    text: str,
    cache_dir: Path,
    size: tuple[int, int] = DEFAULT_SIZE,
    font_size: int = DEFAULT_FONT_SIZE,
) -> Path:
    """
    Render `text`, centered on a plain background, to a cached PNG so mpv
    can display it exactly like any other image. Repeated calls with the
    same text reuse the cached file instead of re-rendering.
    """
    cache_dir = Path(cache_dir).expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256(f"{text}|{size}|{font_size}".encode("utf-8")).hexdigest()[:16]
    target = cache_dir / f"text_{digest}.png"

    if target.is_file():
        return target

    image = Image.new("RGB", size, BACKGROUND)
    draw = ImageDraw.Draw(image)
    font = _load_font(font_size)

    wrapped = textwrap.fill(text.strip(), width=40) or " "

    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    position = ((size[0] - text_w) / 2 - bbox[0], (size[1] - text_h) / 2 - bbox[1])
    draw.multiline_text(position, wrapped, font=font, fill=FOREGROUND, align="center")

    tmp = target.with_name(target.name + ".part")
    image.save(tmp, format="PNG")
    tmp.replace(target)

    return target


def render_text_file_to_image(path: Path, cache_dir: Path, **kwargs) -> Path:
    """Convenience wrapper: render the contents of a text file."""
    return render_text_to_image(
        Path(path).read_text(encoding="utf-8"), cache_dir, **kwargs
    )
