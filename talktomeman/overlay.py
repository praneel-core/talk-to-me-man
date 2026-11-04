"""Floating frosted-glass pill shown while recording (like Wispr Flow).

States: listening (bars follow your voice), quiet (nothing heard for a while:
dimmed), thinking (pill shrinks to three pulsing dots while Whisper works). Must be created and driven
from the main thread (the menu bar app's timer, ~60 fps).
"""

import math
import time

import objc
from Quartz import CGColorCreateGenericGray
from AppKit import (
    NSAppearance,
    NSAppearanceNameVibrantDark,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSGradient,
    NSPanel,
    NSScreen,
    NSStatusWindowLevel,
    NSView,
    NSViewHeightSizable,
    NSViewWidthSizable,
    NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectMaterialHUDWindow,
    NSVisualEffectStateActive,
    NSVisualEffectView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
)

WIDTH, HEIGHT = 124, 38
PAD = 14  # transparent margin around the pill so the open animation can overshoot
BARS = 13
BAR_W, GAP = 4.0, 4.0
BOTTOM_MARGIN = 90
ATTACK, RELEASE = 0.55, 0.10  # loudness envelope: rises fast, falls slowly
BAR_SMOOTH = 0.35  # how quickly each bar chases its target
FADE_IN, FADE_OUT = 0.14, 0.09  # alpha per frame (~60 fps)
OPEN_FRAMES = 22  # spring-open duration
QUIET_LEVEL, QUIET_SECONDS = 0.12, 2.5  # envelope below this for this long = "quiet"
QUIET_ALPHA = 0.55
THINK_W, THINK_H = 54, 26  # the pill shrinks to this while Whisper works
SHRINK = 0.22  # per-frame easing of the pill size
DOT_R, DOT_GAP = 3.0, 9.0

# bars in the middle react more than the edges, like a voice envelope
_CENTER = (BARS - 1) / 2
PROFILE = [0.3 + 0.7 * math.exp(-(((i - _CENTER) / (BARS / 3.2)) ** 2)) for i in range(BARS)]


def _ease_out_back(t: float) -> float:
    """0 -> 1 with a slight overshoot (spring feel)."""
    c1, c3 = 1.4, 2.4
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


class _WaveView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(_WaveView, self).initWithFrame_(frame)
        if self is not None:
            self.levels = [0.0] * BARS
            self.thinking = False
            self.phase = 0.0
        return self

    def isFlipped(self):
        return False

    def drawRect_(self, rect):
        w, h = self.bounds().size.width, self.bounds().size.height
        if self.thinking:  # three softly pulsing dots
            x = w / 2 - DOT_GAP
            for i in range(3):
                a = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(self.phase * 5.0 - i * 1.0))
                r = DOT_R * (0.85 + 0.25 * a)
                NSColor.colorWithCalibratedRed_green_blue_alpha_(0.85, 0.88, 1.0, a).setFill()
                NSBezierPath.bezierPathWithOvalInRect_(((x - r, h / 2 - r), (2 * r, 2 * r))).fill()
                x += DOT_GAP
            return
        total = BARS * BAR_W + (BARS - 1) * GAP
        x = (w - total) / 2
        top, bottom = (1.0, 1.0, 1.0, 1.0), (0.80, 0.82, 1.0, 1.0)  # white to soft lilac
        grad = NSGradient.alloc().initWithStartingColor_endingColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(*top),
            NSColor.colorWithCalibratedRed_green_blue_alpha_(*bottom),
        )
        for lv in self.levels:
            bar_h = BAR_W + lv * (h - 14 - BAR_W)  # idle bars are round dots
            y = (h - bar_h) / 2
            if lv > 0.15:  # soft glow that grows with volume
                g = BAR_W * (0.8 + 1.6 * lv)
                NSColor.colorWithCalibratedRed_green_blue_alpha_(0.7, 0.75, 1.0, 0.18 * lv).setFill()
                NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    ((x - g / 2, y - g / 2), (BAR_W + g, bar_h + g)), (BAR_W + g) / 2, (BAR_W + g) / 2
                ).fill()
            path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                ((x, y), (BAR_W, bar_h)), BAR_W / 2, BAR_W / 2
            )
            grad.drawInBezierPath_angle_(path, 90)
            x += BAR_W + GAP


class Overlay:
    def __init__(self):
        self.panel = None
        self.pill = None
        self.view = None
        self.visible = False
        self.env = 0.0
        self.alpha = 0.0
        self.open_t = 0
        self.quiet_since = None
        self.w, self.h = WIDTH, HEIGHT

    def _build(self):
        screen = NSScreen.mainScreen().frame()
        pw, ph = WIDTH + 2 * PAD, HEIGHT + 2 * PAD
        x = screen.origin.x + (screen.size.width - pw) / 2
        y = screen.origin.y + BOTTOM_MARGIN - PAD
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            ((x, y), (pw, ph)),
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(False)
        panel.setLevel_(NSStatusWindowLevel)
        panel.setIgnoresMouseEvents_(True)
        panel.setHidesOnDeactivate_(False)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        root = NSView.alloc().initWithFrame_(((0, 0), (pw, ph)))
        panel.setContentView_(root)

        # frosted glass pill
        pill = NSVisualEffectView.alloc().initWithFrame_(((PAD, PAD), (WIDTH, HEIGHT)))
        pill.setMaterial_(NSVisualEffectMaterialHUDWindow)
        pill.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        pill.setState_(NSVisualEffectStateActive)
        pill.setAppearance_(NSAppearance.appearanceNamed_(NSAppearanceNameVibrantDark))
        pill.setWantsLayer_(True)
        layer = pill.layer()
        layer.setCornerRadius_(HEIGHT / 2)
        layer.setMasksToBounds_(True)
        layer.setBorderWidth_(1.0)
        layer.setBorderColor_(CGColorCreateGenericGray(1.0, 0.16))
        root.addSubview_(pill)

        view = _WaveView.alloc().initWithFrame_(((0, 0), (WIDTH, HEIGHT)))
        view.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        pill.addSubview_(view)
        self.panel, self.pill, self.view = panel, pill, view

    def _set_scale(self, scale: float) -> None:
        """Scale the pill around its centre (spring open / soft close)."""
        try:
            from Quartz import CGAffineTransformMakeScale

            layer = self.pill.layer()
            layer.setAnchorPoint_((0.5, 0.5))
            layer.setPosition_((PAD + WIDTH / 2, PAD + HEIGHT / 2))
            layer.setAffineTransform_(CGAffineTransformMakeScale(scale, scale))
        except Exception:
            pass

    def _set_size(self, w: float, h: float) -> None:
        self.w, self.h = w, h
        self.pill.setFrame_(((PAD + (WIDTH - w) / 2, PAD + (HEIGHT - h) / 2), (w, h)))
        self.pill.layer().setCornerRadius_(h / 2)

    def update(self, recording: bool, level: float, thinking: bool = False) -> None:
        """Call from the main thread at ~60 fps."""
        active = recording or thinking
        if not active and not self.visible:
            return
        if self.panel is None:
            self._build()
        if active and not self.visible:
            self.view.levels = [0.0] * BARS
            self.env = 0.0
            self.alpha = 0.0
            self.open_t = 0
            self.quiet_since = None
            self._set_size(WIDTH, HEIGHT)
            self.panel.setAlphaValue_(0.0)
            self._set_scale(0.7)
            self.panel.orderFrontRegardless()
            self.visible = True

        now = time.monotonic()
        self.view.thinking = thinking and not recording
        self.view.phase = now
        tw, th = (THINK_W, THINK_H) if self.view.thinking else (WIDTH, HEIGHT)
        if abs(self.w - tw) > 0.3 or abs(self.h - th) > 0.3:
            self._set_size(self.w + (tw - self.w) * SHRINK, self.h + (th - self.h) * SHRINK)

        # smooth loudness envelope (sqrt makes quiet speech visible)
        target = min(1.0, math.sqrt(level) * 2.4) if recording else 0.0
        self.env += (target - self.env) * (ATTACK if target > self.env else RELEASE)

        # quiet state: held the key but nothing heard for a while
        if recording and self.env < QUIET_LEVEL:
            self.quiet_since = self.quiet_since or now
        else:
            self.quiet_since = None
        quiet = self.quiet_since is not None and now - self.quiet_since > QUIET_SECONDS

        # each bar wobbles at its own pace so the motion looks organic
        for i in range(BARS):
            wobble = 0.65 + 0.35 * math.sin(now * (5.0 + i * 0.9) + i * 1.7)
            goal = self.env * PROFILE[i] * wobble
            cur = self.view.levels[i]
            self.view.levels[i] = cur + (goal - cur) * BAR_SMOOTH
        self.view.setNeedsDisplay_(True)

        # spring open
        if self.open_t < OPEN_FRAMES and active:
            self.open_t += 1
            self._set_scale(0.7 + 0.3 * _ease_out_back(self.open_t / OPEN_FRAMES))

        # fade in / out (dimmed when quiet)
        if active:
            goal_alpha = QUIET_ALPHA if quiet else 1.0
            if self.alpha < goal_alpha:
                self.alpha = min(goal_alpha, self.alpha + FADE_IN)
            else:
                self.alpha = max(goal_alpha, self.alpha - 0.03)
        else:
            self.alpha = max(0.0, self.alpha - FADE_OUT)
            self._set_scale(0.92 + 0.08 * self.alpha)
            if self.alpha == 0.0:
                self.panel.orderOut_(None)
                self.visible = False
                return
        self.panel.setAlphaValue_(self.alpha)
