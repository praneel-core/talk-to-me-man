"""Menu bar icons: monochrome SF Symbols (template images) that follow light/dark mode."""

from AppKit import (
    NSFontWeightRegular,
    NSImage,
    NSImageSymbolConfiguration,
)


def symbol(name: str):
    """An SF Symbol as a template image, or None if unavailable (old macOS)."""
    try:
        img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
        if img is None:
            return None
        cfg = NSImageSymbolConfiguration.configurationWithPointSize_weight_(13, NSFontWeightRegular)
        img = img.imageWithSymbolConfiguration_(cfg)
        img.setTemplate_(True)
        return img
    except Exception:
        return None
