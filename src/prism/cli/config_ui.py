"""
Interactive, `dialog`-based configuration screens.

This is deliberately a thin layer over `prism.config.PrismConfig` -- every
screen just edits fields on the dataclasses and the caller decides when to
persist them (only on explicit "Save and exit").
"""

from __future__ import annotations

import subprocess

from dialog import Dialog

from prism.config import PrismConfig


class ConfigUI:
    def __init__(self, config: PrismConfig | None = None) -> None:
        self.config = config or PrismConfig.load()
        self.dialog = Dialog(dialog="dialog", autowidgetsize=True)
        self.dialog.set_background_title("Prism Configuration")

    # ------------------------------------------------------------------
    # Main menu
    # ------------------------------------------------------------------

    def run(self) -> PrismConfig:
        try:
            self._run_menu()
        finally:
            # `dialog` draws straight to the terminal and doesn't clean up
            # after itself -- without this, its last screen (and any
            # leftover borders/backtitle) stays visible once we exit.
            self._restore_terminal()

        return self.config

    def _run_menu(self) -> None:
        while True:
            code, tag = self.dialog.menu(
                "What would you like to configure?",
                choices=[
                    ("1", "Media source"),
                    ("2", "Display settings"),
                    ("3", "HDMI-CEC settings"),
                    ("4", "Save and exit"),
                    ("5", "Exit without saving"),
                ],
            )

            if code != self.dialog.OK or tag == "5":
                return

            if tag == "1":
                self._edit_source()
            elif tag == "2":
                self._edit_display()
            elif tag == "3":
                self._edit_cec()
            elif tag == "4":
                problems = self.config.validate()

                if problems:
                    self.dialog.msgbox(
                        "Please fix the following before saving:\n\n"
                        + "\n".join(f"- {p}" for p in problems)
                    )
                    continue

                if self._save_with_feedback():
                    return

    def _save_with_feedback(self) -> bool:
        """Save the config, showing a friendly dialog on failure instead of
        letting a raw traceback (e.g. a permissions error) blow past the
        `dialog` UI. Returns True if the caller should exit the menu."""
        try:
            path = self.config.save()
        except OSError as exc:
            self.dialog.msgbox(
                "Couldn't save the configuration:\n\n"
                f"{exc}\n\n"
                "If you're saving to /etc/prism, try running this again "
                "with sudo, or run `prism config` as your normal user to "
                "save to ~/.config/prism instead (this is what the "
                "systemd service uses too)."
            )
            return False

        self.dialog.msgbox(f"Saved configuration to {path}")
        return True

    @staticmethod
    def _restore_terminal() -> None:
        try:
            subprocess.run(["clear"], check=False)
        except FileNotFoundError:
            # `clear` isn't installed for some reason -- fall back to a
            # raw ANSI "clear screen + move cursor home" sequence.
            print("\033[2J\033[H", end="")

    # ------------------------------------------------------------------
    # Media source
    # ------------------------------------------------------------------

    def _edit_source(self) -> None:
        source = self.config.source

        code, tag = self.dialog.radiolist(
            "Where should media come from?",
            choices=[
                ("local", "Local folder on this device", source.type == "local"),
                ("remote", "Remote URL / playlist manifest", source.type == "remote"),
                ("api", "API server (with optional auth)", source.type == "api"),
            ],
        )

        if code != self.dialog.OK:
            return

        source.type = tag

        if tag == "local":
            code, text = self.dialog.inputbox(
                "Local media folder:", init=source.local_path
            )
            if code == self.dialog.OK:
                source.local_path = text

        elif tag == "remote":
            code, text = self.dialog.inputbox(
                "Manifest URL (returns a JSON list of media):", init=source.remote_url
            )
            if code == self.dialog.OK:
                source.remote_url = text

            code, text = self.dialog.inputbox(
                "Local cache directory:", init=source.cache_dir
            )
            if code == self.dialog.OK:
                source.cache_dir = text

        elif tag == "api":
            code, text = self.dialog.inputbox(
                "API endpoint:", init=source.api_endpoint
            )
            if code == self.dialog.OK:
                source.api_endpoint = text

            code, text = self.dialog.inputbox(
                "API key (leave blank if none):", init=source.api_key
            )
            if code == self.dialog.OK:
                source.api_key = text

            code, text = self.dialog.inputbox(
                "Local cache directory:", init=source.cache_dir
            )
            if code == self.dialog.OK:
                source.cache_dir = text

    # ------------------------------------------------------------------
    # Display settings
    # ------------------------------------------------------------------

    def _edit_display(self) -> None:
        display = self.config.display

        code, values = self.dialog.form(
            "Display settings",
            [
                ("Image duration (s)", 1, 1, str(display.image_duration), 1, 25, 10, 0),
                ("Text duration (s)", 2, 1, str(display.text_duration), 2, 25, 10, 0),
                ("Volume (0-100)", 3, 1, str(display.volume), 3, 25, 10, 0),
            ],
        )

        if code == self.dialog.OK:
            try:
                display.image_duration = float(values[0])
                display.text_duration = float(values[1])
                display.volume = max(0, min(100, int(values[2])))
            except ValueError:
                self.dialog.msgbox("Please enter numeric values; nothing was changed.")

        code, tags = self.dialog.checklist(
            "Playback behaviour",
            choices=[
                ("shuffle", "Shuffle the playlist", display.shuffle),
                ("loop", "Loop the playlist forever", display.loop),
                ("fullscreen", "Fullscreen output", display.fullscreen),
            ],
        )

        if code == self.dialog.OK:
            display.shuffle = "shuffle" in tags
            display.loop = "loop" in tags
            display.fullscreen = "fullscreen" in tags

    # ------------------------------------------------------------------
    # CEC settings
    # ------------------------------------------------------------------

    def _edit_cec(self) -> None:
        cec = self.config.cec

        code, tags = self.dialog.checklist(
            "HDMI-CEC behaviour",
            choices=[
                ("enabled", "Enable CEC control", cec.enabled),
                ("active_source", "Claim active source on start", cec.active_source),
                ("power_on_at_start", "Power on the TV at start", cec.power_on_at_start),
                ("standby_at_stop", "Put the TV to standby on exit", cec.standby_at_stop),
            ],
        )

        if code == self.dialog.OK:
            cec.enabled = "enabled" in tags
            cec.active_source = "active_source" in tags
            cec.power_on_at_start = "power_on_at_start" in tags
            cec.standby_at_stop = "standby_at_stop" in tags

        code, text = self.dialog.inputbox(
            "CEC device (leave blank to auto-detect):", init=cec.device
        )
        if code == self.dialog.OK:
            cec.device = text

        code, text = self.dialog.inputbox(
            "TV logical address (usually 0):", init=str(cec.tv_logical_address)
        )
        if code == self.dialog.OK:
            try:
                cec.tv_logical_address = int(text)
            except ValueError:
                self.dialog.msgbox(
                    "Logical address must be an integer; keeping the previous value."
                )


def run_config_ui() -> PrismConfig:
    return ConfigUI().run()
