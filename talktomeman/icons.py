"""Menu bar icons: monochrome SF Symbols (template images) that follow light/dark mode."""

from AppKit import (
    NSBezierPath,
    NSColor,
    NSCompositingOperationDestinationOut,
    NSCompositingOperationSourceOver,
    NSFontWeightBlack,
    NSFontWeightRegular,
    NSGradient,
    NSGraphicsContext,
    NSImage,
    NSImageSymbolConfiguration,
)


def symbol(name: str, weight=NSFontWeightRegular):
    """An SF Symbol as a template image, or None if unavailable (old macOS)."""
    try:
        img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
        if img is None:
            return None
        cfg = NSImageSymbolConfiguration.configurationWithPointSize_weight_(13, weight)
        img = img.imageWithSymbolConfiguration_(cfg)
        img.setTemplate_(True)
        return img
    except Exception:
        return None


CANVAS = 18.0  # canvas height
CANVAS_W = 23.0  # every state is drawn on the same canvas so the item never changes size; the extra width leaves room for the badge


def _glyph_rect(sym, badge: bool = False):
    """Where to draw `sym`: centred, or pushed to the left to make room for the badge."""
    w, h = sym.size().width, sym.size().height
    x = 0.5 if badge else (CANVAS_W - w) / 2
    return (x, (CANVAS - h) / 2), (w, h)


def _badge(kind: str | None) -> None:
    """Small status badge in the top-right corner, drawn into the current image.
    A transparent ring is cut out around it (like a notification badge) so it
    stays crisp against the glyph. 'dot' = solid, 'ring' = hollow."""
    if not kind:
        return
    cx, cy = CANVAS_W - 3.0, CANVAS - 2.8
    NSGraphicsContext.currentContext().setCompositingOperation_(NSCompositingOperationDestinationOut)
    NSColor.blackColor().setFill()
    NSBezierPath.bezierPathWithOvalInRect_(((cx - 3.1, cy - 3.1), (6.2, 6.2))).fill()
    NSGraphicsContext.currentContext().setCompositingOperation_(NSCompositingOperationSourceOver)
    NSColor.blackColor().setFill()
    NSColor.blackColor().setStroke()
    if kind == "dot":
        NSBezierPath.bezierPathWithOvalInRect_(((cx - 2.2, cy - 2.2), (4.4, 4.4))).fill()
    else:
        path = NSBezierPath.bezierPathWithOvalInRect_(((cx - 1.9, cy - 1.9), (3.8, 3.8)))
        path.setLineWidth_(1.2)
        path.stroke()


def status_dot(color, size: float = 10.0, glow: bool = False):
    """A small coloured, non-template dot: a soft-edged circle with a subtle
    highlight, so it looks like a physical indicator light. With `glow`, a faint
    halo of the same colour surrounds it (menu bar version)."""
    pad = 3.0 if glow else 0.0
    total = size + 2 * pad
    img = NSImage.alloc().initWithSize_((total, total))
    img.lockFocus()
    if glow:
        for i, a in enumerate((0.10, 0.16, 0.22)):
            g = pad - i
            color.colorWithAlphaComponent_(a).setFill()
            NSBezierPath.bezierPathWithOvalInRect_(((pad - g, pad - g), (size + 2 * g, size + 2 * g))).fill()
    base = NSBezierPath.bezierPathWithOvalInRect_(((pad + 0.5, pad + 0.5), (size - 1, size - 1)))
    NSGradient.alloc().initWithStartingColor_endingColor_(
        color.blendedColorWithFraction_ofColor_(0.35, NSColor.whiteColor()),
        color.blendedColorWithFraction_ofColor_(0.25, NSColor.blackColor()),
    ).drawInBezierPath_angle_(base, -90)
    NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.25).setStroke()
    base.setLineWidth_(0.6)
    base.stroke()
    img.unlockFocus()
    img.setTemplate_(False)
    return img


def framed(name: str, weight=NSFontWeightRegular, badge: str | None = None):
    """The symbol at its natural size, centred on the shared canvas."""
    sym = symbol(name, weight)
    if sym is None:
        return None
    img = NSImage.alloc().initWithSize_((CANVAS_W, CANVAS))
    img.lockFocus()
    sym.drawInRect_fromRect_operation_fraction_(
        _glyph_rect(sym, bool(badge)), ((0, 0), (0, 0)), NSCompositingOperationSourceOver, 1.0
    )
    _badge(badge)
    img.unlockFocus()
    img.setTemplate_(True)
    return img


def knockout(name: str, badge: float = 16.0):
    """The same glyph, same size and position as `framed`, punched out of a filled
    rounded square: a 'filled' variant for symbols with no .fill version."""
    sym = symbol(name)
    if sym is None:
        return None
    img = NSImage.alloc().initWithSize_((CANVAS_W, CANVAS))
    img.lockFocus()
    NSColor.blackColor().setFill()
    off = (CANVAS - badge) / 2
    bx = (CANVAS_W - badge) / 2
    NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        ((bx, off), (badge, badge)), badge * 0.28, badge * 0.28
    ).fill()
    sym.drawInRect_fromRect_operation_fraction_(
        _glyph_rect(sym), ((0, 0), (0, 0)), NSCompositingOperationDestinationOut, 1.0
    )
    img.unlockFocus()
    img.setTemplate_(True)
    return img


# menu bar looks: state -> (SF Symbol, "plain" | "bold" | "knockout"). Pick one in config.MENU_ICON.
STYLES = {
    "option": {"idle": ("option", "plain"), "rec": ("option", "bold"), "off": ("option", "plain")},
    "bubble": {"idle": ("text.bubble", "plain"), "rec": ("text.bubble.fill", "plain"), "off": ("text.bubble", "plain")},
    "waveform": {"idle": ("waveform", "plain"), "rec": ("waveform.circle.fill", "plain"), "off": ("waveform.slash", "plain")},
}
ERROR = ("exclamationmark.triangle", "plain")


def image_for(style: str, state: str, badge: str | None = None):
    """Template image for a state ('loading' looks like idle), or None."""
    spec = ERROR if state == "error" else STYLES[style]["idle" if state == "loading" else state]
    name, mode = spec
    if mode == "knockout":
        return knockout(name)
    return framed(name, NSFontWeightBlack if mode == "bold" else NSFontWeightRegular, badge)
