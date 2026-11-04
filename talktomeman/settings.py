"""Tiny JSON store for choices made in the menu (microphone, Smart cleanup)."""

import json
from pathlib import Path

PATH = Path.home() / ".config" / "talktomeman" / "settings.json"


def load() -> dict:
    try:
        return json.loads(PATH.read_text())
    except (OSError, ValueError):
        return {}


def save(**changes) -> None:
    data = load()
    data.update(changes)
    try:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(data, indent=2))
    except OSError:
        pass
