"""Menu bar wrapper around the dictation core.

  ⏳ loading   🎙 ready   🔴 recording   ⏸ paused
Menu: pause/resume, toggle Ollama smart cleanup, quit.
"""

import threading

import rumps
from pynput import keyboard

from . import config, core
from .overlay import Overlay

IDLE, BUSY, REC, OFF = "🎙", "⏳", "🔴", "⏸"


class DictateApp(rumps.App):
    def __init__(self):
        super().__init__(BUSY, quit_button="Quit Dictate")
        self.enabled = True
        self.listener = None
        self.ready = False
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
            self.title = "⚠️"
            self.status.title = f"Error: {e}"

    def start_listener(self):
        self.listener = keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release
        )
        self.listener.start()

    @rumps.timer(0.05)
    def refresh_ui(self, _):
        """Update icon and waveform overlay on the main thread, from the real recording state."""
        if not self.ready:
            return
        self.overlay.update(core.recording, core.level)
        title = OFF if not self.enabled else REC if core.recording else IDLE
        if title != self.title:
            self.title = title

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
