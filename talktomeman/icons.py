"""Menu bar icons: monochrome SF Symbols (template images) that follow light/dark mode."""

from AppKit import (
    NSBezierPath,
    NSColor,
    NSCompositingOperationDestinationOut,
    NSCompositingOperationSourceOver,
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


CANVAS = 18.0  # every state is drawn on the same canvas so the item never changes size


def _centered(sym, canvas: float):
    """Rect that centres `sym` at its natural size on the canvas."""
    w, h = sym.size().width, sym.size().height
    return ((canvas - w) / 2, (canvas - h) / 2), (w, h)


def framed(name: str):
    """The symbol at its natural size, centred on the shared canvas."""
    sym = symbol(name)
    if sym is None:
        return None
    img = NSImage.alloc().initWithSize_((CANVAS, CANVAS))
    img.lockFocus()
    sym.drawInRect_fromRect_operation_fraction_(
        _centered(sym, CANVAS), ((0, 0), (0, 0)), NSCompositingOperationSourceOver, 1.0
    )
    img.unlockFocus()
    img.setTemplate_(True)
    return img


def knockout(name: str, badge: float = 16.0):
    """The same glyph, same size and position as `framed`, punched out of a filled
    rounded square: a 'filled' variant for symbols with no .fill version."""
    sym = symbol(name)
    if sym is None:
        return None
    img = NSImage.alloc().initWithSize_((CANVAS, CANVAS))
    img.lockFocus()
    NSColor.blackColor().setFill()
    off = (CANVAS - badge) / 2
    NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        ((off, off), (badge, badge)), badge * 0.28, badge * 0.28
    ).fill()
    sym.drawInRect_fromRect_operation_fraction_(
        _centered(sym, CANVAS), ((0, 0), (0, 0)), NSCompositingOperationDestinationOut, 1.0
    )
    img.unlockFocus()
    img.setTemplate_(True)
    return img


# menu bar looks: state -> (SF Symbol, "plain" | "knockout"). Pick one in config.MENU_ICON.
STYLES = {
    "option": {"idle": ("option", "plain"), "rec": ("option", "knockout"), "off": ("option", "plain")},
    "bubble": {"idle": ("text.bubble", "plain"), "rec": ("text.bubble.fill", "plain"), "off": ("text.bubble", "plain")},
    "waveform": {"idle": ("waveform", "plain"), "rec": ("waveform.circle.fill", "plain"), "off": ("waveform.slash", "plain")},
}
ERROR = ("exclamationmark.triangle", "plain")


def image_for(style: str, state: str):
    """Template image for a state ('loading' looks like idle), or None."""
    spec = ERROR if state == "error" else STYLES[style]["idle" if state == "loading" else state]
    name, mode = spec
    return knockout(name) if mode == "knockout" else framed(name)
