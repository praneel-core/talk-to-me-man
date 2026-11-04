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

    @staticmethod
    def _active() -> bool:
        # `pressing` flips the instant the key goes down, before the mic has opened
        return core.recording or core.pressing

    def _state(self) -> str:
        if self.failed:
            return "error"
        if not self.ready:
            return "loading"
        if not self.enabled:
            return "off"
        return "rec" if self._active() else "idle"

    def _apply_icon(self, state: str) -> None:
        """Set the menu bar icon; falls back to an emoji title without SF Symbols."""
        button = self._button()
        img = icons.image_for(config.MENU_ICON, state)
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
            self.overlay.update(self._active(), core.level, core.pending > 0, core.done_count)
        state = self._state()
        if state != self.icon_state:
            self.icon_state = state
            self._apply_icon(state)
        button = self._button()
        if button is not None:  # gentle pulse while loading, dimmed when paused
            if state == "loading":
                alpha = 0.45 + 0.35 * (0.5 + 0.5 * math.sin(self.frame / 9))
            else:
                alpha = 0.4 if state == "off" else 1.0
            button.setAlphaValue_(alpha)

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
