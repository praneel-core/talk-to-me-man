"""Floating waveform pill shown while recording (like Wispr Flow).

Must be created and driven from the main thread (the menu bar app's timer).
"""

import math
import time

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

WIDTH, HEIGHT = 124, 38
BARS = 13
BAR_W, GAP = 4.0, 4.0
BOTTOM_MARGIN = 90
ATTACK, RELEASE = 0.55, 0.10  # loudness envelope: rises fast, falls slowly
BAR_SMOOTH = 0.35  # how quickly each bar chases its target
FADE_IN, FADE_OUT = 0.14, 0.09  # alpha per frame (~60 fps)

# bars in the middle react more than the edges, like a voice envelope
_CENTER = (BARS - 1) / 2
PROFILE = [0.3 + 0.7 * math.exp(-(((i - _CENTER) / (BARS / 3.2)) ** 2)) for i in range(BARS)]


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
            bar_h = BAR_W + lv * (h - 14 - BAR_W)  # idle bars are round dots
            NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                ((x, (h - bar_h) / 2), (BAR_W, bar_h)), BAR_W / 2, BAR_W / 2
            ).fill()
            x += BAR_W + GAP


class Overlay:
    def __init__(self):
        self.panel = None
        self.view = None
        self.visible = False
        self.env = 0.0
        self.alpha = 0.0

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
        """Call from the main thread at ~60 fps."""
        if not recording and not self.visible:
            return
        if self.panel is None:
            self._build()
        if recording and not self.visible:
            self.view.levels = [0.0] * BARS
            self.env = 0.0
            self.alpha = 0.0
            self.panel.setAlphaValue_(0.0)
            self.panel.orderFrontRegardless()
            self.visible = True

        # smooth loudness envelope (sqrt makes quiet speech visible)
        target = min(1.0, math.sqrt(level) * 2.4) if recording else 0.0
        self.env += (target - self.env) * (ATTACK if target > self.env else RELEASE)

        # each bar wobbles at its own pace so the motion looks organic
        t = time.monotonic()
        for i in range(BARS):
            wobble = 0.65 + 0.35 * math.sin(t * (5.0 + i * 0.9) + i * 1.7)
            goal = self.env * PROFILE[i] * wobble
            cur = self.view.levels[i]
            self.view.levels[i] = cur + (goal - cur) * BAR_SMOOTH
        self.view.setNeedsDisplay_(True)

        # fade in / out
        if recording:
            self.alpha = min(1.0, self.alpha + FADE_IN)
        else:
            self.alpha = max(0.0, self.alpha - FADE_OUT)
            if self.alpha == 0.0:
                self.panel.orderOut_(None)
                self.visible = False
                return
        self.panel.setAlphaValue_(self.alpha)
