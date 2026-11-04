"""Menu bar icons: monochrome SF Symbols (template images) that follow light/dark mode."""

from AppKit import (
    NSBezierPath,
    NSColor,
    NSCompositingOperationDestinationOut,
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


def knockout(name: str, size: float = 18.0):
    """The symbol punched out of a filled rounded square: a 'filled' variant for
    symbols that have no .fill version (e.g. the Option key)."""
    sym = symbol(name)
    if sym is None:
        return None
    img = NSImage.alloc().initWithSize_((size, size))
    img.lockFocus()
    NSColor.blackColor().setFill()
    NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        ((0, 0), (size, size)), size * 0.28, size * 0.28
    ).fill()
    inset = size * 0.2
    sym.drawInRect_fromRect_operation_fraction_(
        ((inset, inset), (size - 2 * inset, size - 2 * inset)),
        ((0, 0), (0, 0)),
        NSCompositingOperationDestinationOut,
        1.0,
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
    return knockout(name) if mode == "knockout" else symbol(name)
