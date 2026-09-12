<p align="center">
  <img src="assets/prism-logo.png" width="140" alt="PRISM OS">
</p>

<h1 align="center">PRISM OS</h1>

<p align="center">
  <strong>Pi Remote &amp; Integrated Screen Manager</strong><br>
  Designed for reliable media, display and TV control.
</p>

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/status-early%20development-orange" alt="Status"></a>
  <a href="#"><img src="https://img.shields.io/badge/platform-Raspberry%20Pi-red" alt="Platform"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python"></a>
  <a href="#"><img src="https://img.shields.io/badge/license-TBD-lightgrey" alt="License"></a>
</p>

## About

Turn a Raspberry Pi into a reliable HDMI-CEC media player / TV remote.

Prism plays images, text, video, and audio (in any combination) on a TV
connected over HDMI, and uses HDMI-CEC to power the TV on, claim itself as
the active input, and optionally put the TV to standby when it stops.
Everything is configured through a simple `dialog` text UI, and it can run
either as a one-off foreground command or as a systemd service that starts
on boot.

## How it works

- **Playback** is handled by a single long-lived `mpv` process, driven over
  its JSON IPC socket. Because mpv never restarts between items, moving
  between an image, a video, an audio track, or a "combined" sequence of
  all three is seamless -- no window flicker, no re-negotiating HDMI.
  Text is rendered to a PNG (via Pillow) and shown exactly like an image.
- **Media** comes from a `MediaProvider`, of which there are three:
  - `local` -- reads directly from a folder on the Pi.
  - `remote` -- downloads and caches files described by a JSON manifest URL.
  - `api` -- like `remote`, but built for a REST API (optional bearer
    token auth, `{"items": [...]}` response shape).
  Switching between them is just a config change -- nothing else in the
  codebase needs to know where media actually comes from.
- **CEC** is handled by `prism.display.cec.CEC`, a thin wrapper around
  `cec-ctl`. If no adapter is found, or it doesn't support CEC, Prism logs a
  warning and keeps playing media without TV control rather than crashing.

## Requirements

- A Raspberry Pi (or any Linux box) with an HDMI-CEC capable output.
- System packages: `mpv`, `dialog`, `v4l-utils` (provides `cec-ctl`), and
  [`uv`](https://docs.astral.sh/uv/) for installing/running the Python
  package itself.

Run `prism doctor --autofix` to check for (and install) all of these.

## Install

```bash
# From the project directory:
uv tool install .

# or, for local development:
uv sync
```

## Usage

```bash
# Check/install system dependencies (mpv, dialog, v4l-utils, uv)
prism doctor --autofix

# Configure media source, display timing, and CEC behaviour
prism config

# One-off CEC diagnostic: finds the adapter and any connected devices
prism cec-test

# Run the playback loop in the foreground (Ctrl+C to stop)
prism run

# Install as a systemd service that starts on boot
sudo prism service install
sudo prism service status
sudo prism service uninstall
```

## Configuration

`prism config` opens a `dialog`-based editor with three screens:

1. **Media source** -- choose `local` / `remote` / `api` and fill in the
   relevant path, URL, or endpoint (+ optional API key).
2. **Display settings** -- how long images/text are shown, whether to
   shuffle/loop the playlist, output volume, and fullscreen.
3. **HDMI-CEC settings** -- enable/disable CEC entirely, whether to power
   the TV on and claim active source at start, whether to put it into
   standby on exit, the CEC device path (blank = auto-detect), and the
   TV's logical address (normally `0`).

Settings are saved to `/etc/prism/config.yaml`. Nothing is written until
you choose **Save and exit**.

### `remote` / `api` manifest format

Both non-local providers expect a JSON document listing media items:

```json
[
  { "id": "welcome", "url": "https://example.com/welcome.png", "title": "Welcome" },
  { "id": "clip-1", "url": "https://example.com/clip.mp4", "duration": 30 }
]
```

The `api` provider also accepts `{"items": [...]}` as the top-level shape,
and sends `Authorization: Bearer <api_key>` if an API key is configured.
Downloaded files are cached locally so the same item isn't re-fetched on
every loop.

## Project layout

```
src/prism/
  cli/
    main.py       # cyclopts CLI: config, doctor, cec-test, run, service *
    config_ui.py  # dialog-based interactive configuration screens
  foundation/
    constants.py  # paths, env parsing, external dependency commands
    logger.py      # rotating file + colored console logging
  setup/
    installer.py  # installs external system deps (apt/curl)
    service.py     # installs/removes the systemd unit
  display/
    cec.py         # cec-ctl wrapper (HDMI-CEC control)
    player.py      # mpv JSON-IPC wrapper
    textrender.py  # renders text to a displayable PNG
  media/
    base.py        # MediaItem / MediaProvider interface
    local.py        # local-folder provider
    remote.py        # URL-manifest provider
    api.py           # REST API provider
    factory.py       # builds the right provider from config
  config.py       # PrismConfig schema + YAML load/save
  runtime.py      # ties provider + player + CEC into the playback loop
  util.py         # Doctor: detects/installs missing system dependencies
```

## Notes / known limitations

- `prism.cli.main` previously called `app()` at import time with no `main`
  function, even though `pyproject.toml`'s entry point pointed at
  `prism.cli.main:main`. That mismatch is fixed here -- `main()` now
  exists and is what actually gets invoked, both by the console script and
  by the systemd service.
- CEC discovery (`find_devices`) polls all 15 logical addresses one at a
  time; on some adapters/TVs this can take a few seconds. This is
  unchanged from the original implementation.
- The `remote`/`api` providers currently re-fetch the manifest on every
  loop through the playlist (so changes on the server show up
  automatically) but only re-download a *file* if it isn't already cached.