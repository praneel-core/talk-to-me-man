"""Menu bar wrapper around the dictation core.

  ⏳ loading   🎙 ready   🔴 recording   ⏸ paused
Menu: pause/resume, toggle Ollama smart cleanup, quit.
"""

import math
import threading

import rumps
import objc
from AppKit import NSColor, NSView
from Quartz import CGColorCreateGenericRGB
from pynput import keyboard

from . import config, core, icons
from .ollama_status import OllamaMonitor
from .overlay import Overlay


class _DotView(NSView):
    """The coloured status dot; lets clicks fall through to the menu bar button."""

    def hitTest_(self, point):
        return None


def _cg(color):
    c = color.colorUsingColorSpaceName_("NSCalibratedRGBColorSpace")
    return CGColorCreateGenericRGB(c.redComponent(), c.greenComponent(), c.blueComponent(), 1.0)


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
        self.ollama = OllamaMonitor()
        self.ollama_shown = None

        self.status = rumps.MenuItem("Loading models...")
        self.toggle = rumps.MenuItem("Enabled", callback=self.on_toggle)
        self.toggle.state = 1
        self.llm_item = rumps.MenuItem("Smart cleanup (Ollama)", callback=self.on_llm)
        self.llm_item.state = 1 if config.USE_LLM else 0
        self.ollama_item = rumps.MenuItem("Ollama: checking...", callback=lambda _: None)
        self.dot_view = None  # coloured dot laid over the menu bar icon (main thread only)
        if config.OLLAMA_INDICATOR == "badge":
            self.menu = [self.status, self.ollama_item, None, self.toggle, self.llm_item, None]
        else:
            self.menu = [self.status, None, self.toggle, self.llm_item, None]

        self.ollama.start()
        threading.Thread(target=self.load, daemon=True).start()

    def load(self):
        """Warm up the models in the background, then start the hotkey listener."""
        try:
            core.warm_up(llm=False)  # Ollama is warmed by the monitor
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

    def _ollama_state(self) -> str:
        return self.ollama.state if config.USE_LLM else "disabled"

    def _badge(self) -> str | None:
        """What the icon image reserves/draws in its top-right corner."""
        if config.OLLAMA_INDICATOR == "dot":
            return "space"  # room for the coloured dot view laid over the icon
        return {"off": "dot", "starting": "ring"}.get(self._ollama_state())

    def _update_dot(self) -> None:
        """Coloured dot on the icon's top-right corner: green ready, orange
        starting (pulsing), red not running. A subview of the status button, so
        the glyph underneath stays a template image that follows light/dark mode."""
        if config.OLLAMA_INDICATOR != "dot":
            return
        button = self._button()
        if button is None:
            return
        if self.dot_view is None:
            d = 6.0
            v = _DotView.alloc().initWithFrame_(((0, 0), (d, d)))
            v.setWantsLayer_(True)
            layer = v.layer()
            layer.setCornerRadius_(d / 2)
            layer.setBorderWidth_(0.5)
            layer.setBorderColor_(CGColorCreateGenericRGB(0, 0, 0, 0.35))
            layer.setShadowOffset_((0, 0))
            layer.setShadowRadius_(3.0)
            layer.setShadowOpacity_(0.9)
            layer.setMasksToBounds_(False)
            button.addSubview_(v)
            self.dot_view = v
        st = self._ollama_state()
        v = self.dot_view
        if st != self.ollama_shown:
            self.ollama_shown = st
            if st == "disabled":
                v.setHidden_(True)
                button.setToolTip_("Smart cleanup off")
            else:
                title, color = {
                    "ready": ("Ollama ready", NSColor.systemGreenColor()),
                    "starting": ("Ollama starting...", NSColor.systemOrangeColor()),
                    "off": ("Ollama not running (cleanup skipped)", NSColor.systemRedColor()),
                }[st]
                v.setHidden_(False)
                v.layer().setBackgroundColor_(_cg(color))
                v.layer().setShadowColor_(_cg(color))
                button.setToolTip_(title)
        # keep it on the icon's corner (the image is centred in the button)
        b = button.bounds().size
        cx = (b.width - icons.CANVAS_W) / 2 + icons.BADGE_CENTER[0]
        cy = (b.height - icons.CANVAS) / 2 + icons.BADGE_CENTER[1]
        if button.isFlipped():  # y grows downwards in a flipped view
            cy = b.height - cy
        v.setFrameOrigin_((cx - 3.0, cy - 3.0))
        v.setAlphaValue_(0.5 + 0.5 * (0.5 + 0.5 * math.sin(self.frame / 8)) if st == "starting" else 1.0)

    def _update_ollama_item(self) -> None:
        if config.OLLAMA_INDICATOR != "badge":
            return
        st = self._ollama_state()
        if st == self.ollama_shown:
            return
        self.ollama_shown = st
        title, color = {
            "ready": ("Ollama ready", NSColor.systemGreenColor()),
            "starting": ("Ollama starting...", NSColor.systemOrangeColor()),
            "off": ("Ollama not running (cleanup skipped)", NSColor.systemGrayColor()),
            "disabled": ("Smart cleanup off", NSColor.systemGrayColor()),
        }[st]
        self.ollama_item.title = title
        try:
            self.ollama_item._menuitem.setImage_(icons.status_dot(color))
        except Exception:
            pass

    def _apply_icon(self, state: str, badge: str | None) -> None:
        """Set the menu bar icon; falls back to an emoji title without SF Symbols."""
        button = self._button()
        img = icons.image_for(config.MENU_ICON, state, badge)
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
        state, badge = self._state(), self._badge()
        self._update_ollama_item()
        self._update_dot()
        if (state, badge) != self.icon_state:
            self.icon_state = (state, badge)
            self._apply_icon(state, badge)
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
