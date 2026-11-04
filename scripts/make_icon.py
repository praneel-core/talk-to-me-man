"""Render a 🎙 app icon (.icns). Usage: make_icon.py OUT.icns  (macOS only)."""

import os
import subprocess
import sys
import tempfile

from AppKit import (
    NSAttributedString,
    NSBezierPath,
    NSBitmapImageFileTypePNG,
    NSBitmapImageRep,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSImage,
)


def render(px: int):
    img = NSImage.alloc().initWithSize_((px, px))
    img.lockFocus()
    NSColor.colorWithCalibratedRed_green_blue_alpha_(0.12, 0.14, 0.22, 1).setFill()
    NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        ((0, 0), (px, px)), px * 0.22, px * 0.22
    ).fill()
    text = NSAttributedString.alloc().initWithString_attributes_(
        "🎙", {NSFontAttributeName: NSFont.systemFontOfSize_(px * 0.62)}
    )
    size = text.size()
    text.drawAtPoint_(((px - size.width) / 2, (px - size.height) / 2))
    img.unlockFocus()
    rep = NSBitmapImageRep.alloc().initWithData_(img.TIFFRepresentation())
    return rep.representationUsingType_properties_(NSBitmapImageFileTypePNG, {})


def main(out: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "Dictate.iconset")
        os.makedirs(iconset)
        for n in (16, 32, 128, 256, 512):
            render(n).writeToFile_atomically_(f"{iconset}/icon_{n}x{n}.png", True)
            render(n * 2).writeToFile_atomically_(f"{iconset}/icon_{n}x{n}@2x.png", True)
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out], check=True)


if __name__ == "__main__":
    main(sys.argv[1])
