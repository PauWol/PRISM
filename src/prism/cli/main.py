from __future__ import annotations

from cyclopts import App

app = App(
    name="prism",
    help="Turn a Raspberry Pi into a reliable HDMI-CEC media player / TV remote.",
)

service_app = App(name="service", help="Manage the prism systemd service.")
app.command(service_app)


@app.command
def config() -> None:
    """Open the interactive `dialog`-based configuration screen."""
    from prism.cli.config_ui import run_config_ui

    run_config_ui()


@app.command
def doctor(autofix: bool = False) -> None:
    """Check (and optionally install) missing external dependencies
    (v4l-utils, dialog, uv, mpv)."""
    from prism.util import Doctor

    Doctor().run(autofix)


@app.command
def cec_test() -> None:
    """Run a one-off CEC discovery/diagnostic test and print the results."""
    from prism.display.cec import CEC

    cec = CEC()
    result = cec.test()

    print(f"CEC adapter: {result['adapter']}")
    print(f"CEC supported: {result['cec_supported']}")
    print(f"Playback configured: {result['playback_configured']}")

    print("\nDevices:")
    for device in result["devices"]:
        print(f"  {device['logical_address']}: {device['name']}")

    print(f"\nBest device: {result['best_device']}")


@app.command
def run() -> None:
    """Run the media/CEC playback loop in the foreground (Ctrl+C to stop)."""
    from prism.foundation.logger import setup_logging
    from prism.runtime import PrismRuntime

    setup_logging()

    runtime = PrismRuntime()

    try:
        runtime.run_forever()
    except KeyboardInterrupt:
        runtime.stop()


@service_app.command(name="install")
def service_install(start: bool = True) -> None:
    """Install prism as a systemd service that starts automatically on
    boot (requires root)."""
    from prism.setup.service import ServiceManager

    ServiceManager().install(start=start)


@service_app.command(name="uninstall")
def service_uninstall() -> None:
    """Remove the prism systemd service (requires root)."""
    from prism.setup.service import ServiceManager

    ServiceManager().uninstall()


@service_app.command(name="status")
def service_status() -> None:
    """Show the status of the prism systemd service."""
    from prism.setup.service import ServiceManager

    ServiceManager().status()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
