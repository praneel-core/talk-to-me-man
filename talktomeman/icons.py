"""Menu bar icons: monochrome template images that follow light/dark mode."""

from AppKit import (
    NSBezierPath,
    NSColor,
    NSFontWeightMedium,
    NSImage,
    NSImageSymbolConfiguration,
)

SIZE = (20, 18)
WAVE_BARS = 5
_BAR_W, _BAR_GAP = 2.4, 1.8


def symbol(name: str):
    """An SF Symbol as a template image, or None if unavailable (old macOS)."""
    try:
        img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
        if img is None:
            return None
        cfg = NSImageSymbolConfiguration.configurationWithPointSize_weight_(15, NSFontWeightMedium)
        img = img.imageWithSymbolConfiguration_(cfg)
        img.setTemplate_(True)
        return img
    except Exception:
        return None


def waveform(levels: list[float]):
    """A tiny live waveform (template image) from levels in 0..1."""
    img = NSImage.alloc().initWithSize_(SIZE)
    img.lockFocus()
    NSColor.blackColor().setFill()
    total = WAVE_BARS * _BAR_W + (WAVE_BARS - 1) * _BAR_GAP
    x = (SIZE[0] - total) / 2
    for lv in levels[:WAVE_BARS]:
        h = 3.0 + max(0.0, min(1.0, lv)) * 11.0
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            ((x, (SIZE[1] - h) / 2), (_BAR_W, h)), _BAR_W / 2, _BAR_W / 2
        ).fill()
        x += _BAR_W + _BAR_GAP
    img.unlockFocus()
    img.setTemplate_(True)
    return img
