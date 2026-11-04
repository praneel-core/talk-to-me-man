"""Watches the local Ollama server so the UI can show whether Smart cleanup is ready.

States: "off" (server not reachable), "starting" (server up, model not loaded
yet / being loaded), "ready" (model loaded). When the server comes up, the model
is loaded in the background so your first correction isn't slow.
"""

import json
import threading
import time
import urllib.request
from urllib.parse import urlsplit

from . import config
from .llm import warm_up_model

POLL_SECONDS = 3.0


def _base_url() -> str:
    u = urlsplit(config.OLLAMA_URL)
    return f"{u.scheme}://{u.netloc}"


def probe() -> tuple[bool, bool]:
    """(server reachable, our model currently loaded)."""
    try:
        with urllib.request.urlopen(_base_url() + "/api/ps", timeout=1.0) as resp:
            models = json.loads(resp.read()).get("models", [])
    except Exception:
        return False, False
    wanted = config.OLLAMA_MODEL
    names = [m.get("name", "") for m in models]
    return True, any(n == wanted or (":" not in wanted and n.startswith(wanted + ":")) for n in names)


class OllamaMonitor:
    def __init__(self):
        self.state = "off"
        self._warming = False
        self._warmed_since_up = False

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _warm(self) -> None:
        self._warming = True
        try:
            warm_up_model()
        finally:
            self._warming = False

    def _run(self) -> None:
        while True:
            up, loaded = probe()
            if not up:
                self.state = "off"
                self._warmed_since_up = False
            elif loaded:
                self.state = "ready"
                self._warmed_since_up = True
            else:
                # server is up. Load the model once per "up" period (not again after
                # the idle timeout unloads it, which would pin 2 GB of memory forever).
                if config.USE_LLM and not self._warmed_since_up and not self._warming:
                    self._warmed_since_up = True
                    threading.Thread(target=self._warm, daemon=True).start()
                self.state = "starting" if (self._warming or not self._warmed_since_up) else "ready"
            time.sleep(POLL_SECONDS)
