"""Menu bar wrapper around the dictation core.

Icon: ⌥ (bold while recording) with a coloured Ollama status dot on its corner.
Menu: recent dictations, pause, Smart cleanup, microphone, launch at login,
vocabulary, log, about, quit. A status line at the top appears only when
something needs attention (loading, error, missing permission).
"""

import math
import os
import subprocess
import threading
from pathlib import Path

import pyperclip
import rumps
import sounddevice as sd
from AppKit import NSColor, NSView
from ApplicationServices import AXIsProcessTrusted
from pynput import keyboard
from Quartz import CGColorCreateGenericRGB, CGPreflightListenEventAccess

from . import __version__, config, core, icons, settings
from .ollama_status import OllamaMonitor
from .overlay import Overlay


class _DotView(NSView):
    """The coloured status dot; lets clicks fall through to the menu bar button."""

    def hitTest_(self, point):
        return None


def _clear(menu) -> None:
    """rumps' clear() fails on a submenu that has never had an item added."""
    if getattr(menu, "_menu", None) is not None:
        menu.clear()


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
        self.error = ''
        self.icon_state = None
        self.frame = 0
        self.overlay = Overlay()
        self.ollama = OllamaMonitor()
        self.ollama_shown = None

        self.hist_seen = -1
        self.perm_msg = None
        self._login_state = None  # set by a worker thread, applied on the main thread
        self._mic_names: list[str] = []

        # status line: only visible when something needs attention
        self.status = rumps.MenuItem("Loading models...", callback=self.on_status)
        self.recent = rumps.MenuItem("Recent dictations")
        self.toggle = rumps.MenuItem("Pause dictation", callback=self.on_toggle)
        self.llm_item = rumps.MenuItem("Smart cleanup (Ollama)", callback=self.on_llm)
        self.llm_item.state = 1 if config.USE_LLM else 0
        self.mic_menu = rumps.MenuItem("Microphone")
        self.login_item = rumps.MenuItem("Launch at login", callback=self.on_login)
        self.words_item = rumps.MenuItem("Edit vocabulary...", callback=self.on_words)
        self.log_item = rumps.MenuItem("Show log", callback=self.on_log)
        self.about_item = rumps.MenuItem(f"About Talk To Me Man  v{__version__}", callback=self.on_about)
        self.ollama_item = rumps.MenuItem("Ollama: checking...", callback=lambda _: None)
        self.dot_view = None  # coloured dot laid over the menu bar icon (main thread only)
        items = [self.status, self.recent, None, self.toggle, self.llm_item, None,
                 self.mic_menu, self.login_item, self.words_item, self.log_item, None, self.about_item]
        if config.OLLAMA_INDICATOR == "badge":
            items.insert(1, self.ollama_item)
        self.menu = items
        self._refresh_recent()
        self._refresh_mics()

        self.ollama.start()
        threading.Thread(target=self._read_login_item, daemon=True).start()
        threading.Thread(target=self.load, daemon=True).start()

    def load(self):
        """Warm up the models in the background, then start the hotkey listener."""
        try:
            core.warm_up(llm=False)  # Ollama is warmed by the monitor
            self.start_listener()
            self.ready = True
        except Exception as e:
            self.failed = True
            self.error = str(e)

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
        if core.done_count != self.hist_seen:
            self._refresh_recent()
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
        """Restart the key listener if it ever died; keep the status line current."""
        if self.listener is not None and not self.listener.is_alive():
            print("(key listener died, restarting)", flush=True)
            self.start_listener()
        self._update_status()
        if self._login_state is not None:
            self.login_item.state = 1 if self._login_state else 0

    @rumps.timer(30)
    def refresh_mics(self, _):
        """Pick up microphones plugged in since last time (only while idle)."""
        if core.recording or core.pressing:
            return
        try:
            with core.lock:
                sd._terminate()
                sd._initialize()
        except Exception:
            pass
        self._refresh_mics()

    # ---- status line -------------------------------------------------
    def _update_status(self) -> None:
        """Show the top line only when something needs attention."""
        if self.failed:
            text, self.perm_msg = f"Error: {self.error}", None
        elif not self.ready:
            text, self.perm_msg = "Loading models...", None
        elif not AXIsProcessTrusted():
            text, self.perm_msg = "Grant Accessibility access...", "Privacy_Accessibility"
        elif not CGPreflightListenEventAccess():
            text, self.perm_msg = "Grant Input Monitoring access...", "Privacy_ListenEvent"
        else:
            text, self.perm_msg = None, None
        item = self.status._menuitem
        if text is None:
            item.setHidden_(True)
        else:
            self.status.title = ("\u26a0\ufe0f  " if self.perm_msg else "") + text
            item.setHidden_(False)

    def on_status(self, _):
        if self.perm_msg:
            subprocess.Popen(["open", f"x-apple.systempreferences:com.apple.preference.security?{self.perm_msg}"])

    # ---- recent dictations --------------------------------------------
    def _refresh_recent(self) -> None:
        self.hist_seen = core.done_count
        _clear(self.recent)
        if not core.history:
            self.recent.add(rumps.MenuItem("No dictations yet"))
            return
        for text in core.history:
            label = text if len(text) <= 60 else text[:59] + "\u2026"
            item = rumps.MenuItem(label, callback=self.on_copy)
            item.full_text = text
            self.recent.add(item)

    def on_copy(self, sender):
        pyperclip.copy(sender.full_text)

    # ---- microphone ----------------------------------------------------
    def _refresh_mics(self) -> None:
        try:
            names = sorted({d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0})
        except Exception:
            names = []
        if names == self._mic_names and len(self.mic_menu):
            self._mark_mic()
            return
        self._mic_names = names
        _clear(self.mic_menu)
        self.mic_menu.add(rumps.MenuItem("System default", callback=self.on_mic))
        for n in names:
            self.mic_menu.add(rumps.MenuItem(n, callback=self.on_mic))
        self._mark_mic()

    def _mark_mic(self) -> None:
        chosen = config.INPUT_DEVICE
        for title, item in self.mic_menu.items():
            item.state = 1 if (title == "System default" and not chosen) or title == chosen else 0

    def on_mic(self, sender):
        config.INPUT_DEVICE = None if sender.title == "System default" else sender.title
        settings.save(input_device=config.INPUT_DEVICE)
        self._mark_mic()

    # ---- launch at login -------------------------------------------------
    APP_PATH = str(Path.home() / "Applications" / "Dictate.app")

    @staticmethod
    def _osascript(script: str) -> str:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
        return r.stdout.strip()

    def _read_login_item(self) -> None:
        try:
            names = self._osascript('tell application "System Events" to get the name of every login item')
            self._login_state = "Dictate" in names
        except Exception:
            self._login_state = False

    def on_login(self, sender):
        turn_on = not sender.state
        sender.state = 1 if turn_on else 0

        def work():
            try:
                if turn_on:
                    self._osascript(
                        'tell application "System Events" to make login item at end with properties '
                        f'{{path:"{self.APP_PATH}", hidden:false}}'
                    )
                else:
                    self._osascript('tell application "System Events" to delete (every login item whose name is "Dictate")')
            except Exception as e:
                print(f"(login item change failed: {e})", flush=True)
            self._read_login_item()

        threading.Thread(target=work, daemon=True).start()

    # ---- shortcuts -----------------------------------------------------------
    def on_words(self, _):
        path = config.USER_WORDS_FILE
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Your own names / jargon, one per line. Restart the app to apply.\n")
        subprocess.Popen(["open", "-t", str(path)])

    def on_log(self, _):
        subprocess.Popen(["open", "/tmp/dictate.log"])

    def on_about(self, _):
        subprocess.Popen(["open", "https://github.com/praneel-core/talk-to-me-man"])

    def on_press(self, key):
        if self.enabled:
            core.on_press(key)

    def on_release(self, key):
        core.on_release(key)

    def on_toggle(self, sender):
        sender.state = not sender.state  # checked = paused
        self.enabled = not sender.state

    def on_llm(self, sender):
        sender.state = not sender.state
        config.USE_LLM = bool(sender.state)
        settings.save(use_llm=config.USE_LLM)


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
