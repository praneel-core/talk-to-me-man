"""Menu bar wrapper around the dictation core.

  ⏳ loading   🎙 ready   🔴 recording   ⏸ paused
Menu: pause/resume, toggle Ollama smart cleanup, quit.
"""

import math
import threading

import rumps
from pynput import keyboard

from . import config, core, icons
from .overlay import Overlay

# emoji titles are only a fallback if SF Symbols aren't available
IDLE, BUSY, REC, OFF = "🎙", "⏳", "🔴", "⏸"
SYMBOLS = {"loading": "mic", "idle": "mic", "off": "mic.slash", "error": "exclamationmark.triangle"}
FALLBACK = {"loading": BUSY, "idle": IDLE, "rec": REC, "off": OFF, "error": "⚠️"}


class DictateApp(rumps.App):
    def __init__(self):
        super().__init__(BUSY, quit_button="Quit Dictate")
        self.enabled = True
        self.listener = None
        self.ready = False
        self.failed = False
        self.icon_state = None
        self.frame = 0
        self.overlay = Overlay()

        self.status = rumps.MenuItem("Loading models...")
        self.toggle = rumps.MenuItem("Enabled", callback=self.on_toggle)
        self.toggle.state = 1
        self.llm_item = rumps.MenuItem("Smart cleanup (Ollama)", callback=self.on_llm)
        self.llm_item.state = 1 if config.USE_LLM else 0
        self.menu = [self.status, None, self.toggle, self.llm_item, None]

        threading.Thread(target=self.load, daemon=True).start()

    def load(self):
        """Warm up the models in the background, then start the hotkey listener."""
        try:
            core.warm_up()
            self.start_listener()
            self.ready = True
            self.status.title = "Ready: hold Right Option to dictate"
        except Exception as e:
            self.failed = True
            self.status.title = f"Error: {e}"

    def start_listener(self):
        self.listener = keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release
        )
        self.listener.start()

    def _button(self):
        try:
            return self._nsapp.nsstatusitem.button()
        except Exception:
            return None

    def _state(self) -> str:
        if self.failed:
            return "error"
        if not self.ready:
            return "loading"
        if not self.enabled:
            return "off"
        return "rec" if core.recording else "idle"

    def _apply_icon(self, state: str) -> None:
        """Set the menu bar icon; falls back to an emoji title without SF Symbols."""
        button = self._button()
        img = icons.symbol(SYMBOLS[state]) if state in SYMBOLS else None
        if state == "rec":
            levels = self.overlay.view.levels if self.overlay.view else [0.0] * icons.WAVE_BARS
            step = max(1, len(levels) // icons.WAVE_BARS)
            img = icons.waveform(levels[1::step])
        if button is not None and img is not None:
            button.setImage_(img)
            self.title = ""
        else:
            self.title = FALLBACK[state]

    @rumps.timer(1 / 60)
    def refresh_ui(self, _):
        """Update icon and waveform overlay on the main thread, from the real state."""
        self.frame += 1
        if self.ready:
            self.overlay.update(core.recording, core.level, core.pending > 0, core.done_count)
        state = self._state()
        if state != self.icon_state or (state == "rec" and self.frame % 3 == 0):
            self.icon_state = state
            self._apply_icon(state)
        button = self._button()
        if button is not None:  # gentle pulse while the models load
            button.setAlphaValue_(0.45 + 0.35 * (0.5 + 0.5 * math.sin(self.frame / 9)) if state == "loading" else 1.0)

    @rumps.timer(5)
    def check_listener(self, _):
        """Restart the key listener if it ever died."""
        if self.listener is not None and not self.listener.is_alive():
            print("(key listener died, restarting)", flush=True)
            self.start_listener()

    def on_press(self, key):
        if self.enabled:
            core.on_press(key)

    def on_release(self, key):
        core.on_release(key)

    def on_toggle(self, sender):
        sender.state = not sender.state
        self.enabled = bool(sender.state)

    def on_llm(self, sender):
        sender.state = not sender.state
        config.USE_LLM = bool(sender.state)


def main():
    app = DictateApp()

    # Menu-bar only: hide the Dock icon / "Python" app menu. Must run on the
    # main thread once the app loop has started, so do it from a timer.
    def hide_dock(timer):
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyAccessory
        )
        timer.stop()

    rumps.Timer(hide_dock, 1).start()
    app.run()


if __name__ == "__main__":
    main()
