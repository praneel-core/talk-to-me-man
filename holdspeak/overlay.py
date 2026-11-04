"""Floating waveform pill shown while recording (like Wispr Flow).

Must be created and driven from the main thread (the menu bar app's timer).
"""

import math

import objc
from AppKit import (
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSPanel,
    NSScreen,
    NSStatusWindowLevel,
    NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
)

WIDTH, HEIGHT = 150, 44
BARS = 17
BAR_W, GAP = 4.0, 4.0
BOTTOM_MARGIN = 90


class _WaveView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(_WaveView, self).initWithFrame_(frame)
        if self is not None:
            self.levels = [0.0] * BARS
        return self

    def drawRect_(self, rect):
        w, h = self.bounds().size.width, self.bounds().size.height
        NSColor.colorWithCalibratedWhite_alpha_(0.08, 0.92).setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            self.bounds(), h / 2, h / 2
        ).fill()
        total = BARS * BAR_W + (BARS - 1) * GAP
        x = (w - total) / 2
        NSColor.whiteColor().setFill()
        for lv in self.levels:
            bar_h = 4 + lv * (h - 16)
            NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                ((x, (h - bar_h) / 2), (BAR_W, bar_h)), BAR_W / 2, BAR_W / 2
            ).fill()
            x += BAR_W + GAP


class Overlay:
    def __init__(self):
        self.panel = None
        self.view = None
        self.visible = False

    def _build(self):
        screen = NSScreen.mainScreen().frame()
        x = screen.origin.x + (screen.size.width - WIDTH) / 2
        y = screen.origin.y + BOTTOM_MARGIN
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            ((x, y), (WIDTH, HEIGHT)),
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(True)
        panel.setLevel_(NSStatusWindowLevel)
        panel.setIgnoresMouseEvents_(True)
        panel.setHidesOnDeactivate_(False)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        view = _WaveView.alloc().initWithFrame_(((0, 0), (WIDTH, HEIGHT)))
        panel.setContentView_(view)
        self.panel, self.view = panel, view

    def update(self, recording: bool, level: float) -> None:
        """Call from the main thread ~20x/second."""
        if recording:
            if self.panel is None:
                self._build()
            if not self.visible:
                self.view.levels = [0.0] * BARS
                self.panel.orderFrontRegardless()
                self.visible = True
            # sqrt makes quiet speech visible; the bar edges fade for a softer look
            lv = min(1.0, math.sqrt(level) * 2.2)
            self.view.levels = self.view.levels[1:] + [lv]
            self.view.setNeedsDisplay_(True)
        elif self.visible:
            self.panel.orderOut_(None)
            self.visible = False
