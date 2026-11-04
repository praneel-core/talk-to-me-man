"""Floating frosted-glass pill shown while recording (like Wispr Flow).

listening: bars follow your voice (dimmed if nothing is heard for a while)
thinking:  the bars melt into three pulsing dots while Whisper works
done:      the dots turn into a check mark, then the pill fades away

Everything (size, bar-to-dot morph, check) is driven by springs, so the pill
behaves like one physical object. Must be created and driven from the main
thread (the menu bar app's timer, ~60 fps).
"""

import math
import time

import objc
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
    NSWorkspace,
)
from Quartz import CGAffineTransformMakeScale, CGColorCreateGenericGray

WIDTH, HEIGHT = 112, 34
THINK_W, THINK_H = 50, 24  # pill size while Whisper works
CHECK_S = 30  # pill size (a circle) while the check mark shows
PAD = 14  # transparent margin around the pill so the springs can overshoot
BARS = 11
BAR_W, GAP = 4.0, 4.0
DOT_R, DOT_GAP = 3.0, 9.0
IDLE_H = 2.5  # height of the bars when nothing is heard
BOTTOM_MARGIN = 90

ATTACK, RELEASE = 0.55, 0.10  # loudness envelope: rises fast, falls slowly
BAR_SMOOTH = 0.35  # how quickly each bar chases its target
FADE_IN, FADE_OUT = 0.14, 0.09  # alpha per frame (~60 fps)
OPEN_FRAMES = 22  # spring-open duration
DONE_FRAMES = 34  # how long the check mark stays (~0.55 s)
QUIET_LEVEL, QUIET_SECONDS = 0.12, 2.5  # envelope below this for this long = "quiet"
QUIET_ALPHA = 0.55
SPRING_K, SPRING_DAMP = 0.16, 0.74  # slightly underdamped: a hint of overshoot

_CENTER = (BARS - 1) / 2
# bars in the middle react more than the edges, like a voice envelope
PROFILE = [0.3 + 0.7 * math.exp(-(((i - _CENTER) / (BARS / 3.2)) ** 2)) for i in range(BARS)]
_DOT_BARS = (int(_CENTER) - 1, int(_CENTER), int(_CENTER) + 1)  # bars that become the dots


def _ease_out_back(t: float) -> float:
    """0 -> 1 with a slight overshoot (spring feel)."""
    c1, c3 = 1.4, 2.4
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


class _Spring:
    def __init__(self, x: float):
        self.x, self.v = x, 0.0

    def step(self, target: float) -> float:
        self.v = (self.v + (target - self.x) * SPRING_K) * SPRING_DAMP
        self.x += self.v
        return self.x

    def snap(self, x: float) -> None:
        self.x, self.v = x, 0.0


class _WaveView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(_WaveView, self).initWithFrame_(frame)
        if self is not None:
            self.levels = [0.0] * BARS
            self.m = 0.0  # 0 = bars, 1 = dots
            self.c = 0.0  # check mark progress
            self.phase = 0.0
        return self

    def isFlipped(self):
        return False

    def drawRect_(self, rect):
        w, h = self.bounds().size.width, self.bounds().size.height
        m, c = _clamp01(self.m), _clamp01(self.c)
        total = BARS * BAR_W + (BARS - 1) * GAP
        x0 = (w - total) / 2
        for i, lv in enumerate(self.levels):
            bx = x0 + i * (BAR_W + GAP)
            # silent bars flatten into one thin continuous line (they widen to touch
            # each other) instead of a row of dots; they separate as you get louder
            widen = GAP * (1 - min(1.0, lv * 6)) * (1 - m)
            bh = IDLE_H + lv * (HEIGHT - 14 - IDLE_H)
            bx -= widen / 2
            if i in _DOT_BARS:
                k = _DOT_BARS.index(i)
                pulse = 0.5 + 0.5 * math.sin(self.phase * 4.5 - k * 1.1)
                dot_d = 2 * DOT_R * (0.85 + 0.3 * pulse)
                dot_x = w / 2 + (k - 1) * DOT_GAP - dot_d / 2
                bw = _lerp(BAR_W + widen, dot_d, m)
                bh = _lerp(bh, dot_d, m)
                x = _lerp(bx, dot_x, m)
                alpha = _lerp(1.0, 0.4 + 0.6 * pulse, m) * (1 - c)
            else:  # outer bars melt away
                bw, x = BAR_W + widen, bx
                alpha = (1 - m) ** 2
            if alpha <= 0.01:
                continue
            y = (h - bh) / 2
            if lv > 0.15 and m < 0.5:  # soft glow that grows with volume
                g = BAR_W * (0.8 + 1.6 * lv)
                NSColor.colorWithCalibratedRed_green_blue_alpha_(0.7, 0.75, 1.0, 0.18 * lv * (1 - 2 * m)).setFill()
                NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    ((x - g / 2, y - g / 2), (bw + g, bh + g)), (bw + g) / 2, (bw + g) / 2
                ).fill()
            top = NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 1.0, 1.0, alpha)
            bottom = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                _lerp(0.80, 0.85, m), _lerp(0.82, 0.88, m), 1.0, alpha
            )
            path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                ((x, y), (bw, bh)), min(bw, bh) / 2, min(bw, bh) / 2
            )
            NSGradient.alloc().initWithStartingColor_endingColor_(top, bottom).drawInBezierPath_angle_(path, 90)
        if c > 0.01:
            self._draw_check(w / 2, h / 2, c)

    def _draw_check(self, cx: float, cy: float, t: float) -> None:
        pts = [(cx - 5.5, cy + 0.5), (cx - 1.5, cy - 3.5), (cx + 5.5, cy + 4.0)]
        path = NSBezierPath.bezierPath()
        path.setLineWidth_(2.2)
        path.setLineCapStyle_(1)  # round
        path.setLineJoinStyle_(1)
        path.moveToPoint_(pts[0])
        first = _clamp01(t / 0.4)
        path.lineToPoint_((_lerp(pts[0][0], pts[1][0], first), _lerp(pts[0][1], pts[1][1], first)))
        if t > 0.4:
            second = _clamp01((t - 0.4) / 0.6)
            path.lineToPoint_((_lerp(pts[1][0], pts[2][0], second), _lerp(pts[1][1], pts[2][1], second)))
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.92, 0.95, 1.0, 1.0).setStroke()
        path.stroke()


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
        self.done_t = None  # frames the check has been showing, None = not showing
        self.done_seen = 0
        self.was_thinking = False
        self.reduce_motion = False
        self.sw, self.sh = _Spring(WIDTH), _Spring(HEIGHT)
        self.sm, self.sc = _Spring(0.0), _Spring(0.0)
        self.target = (WIDTH, HEIGHT, 0.0, 0.0)  # w, h, morph, check

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

    def _set_size(self, w: float, h: float) -> None:
        w, h = max(w, 8.0), max(h, 8.0)
        self.pill.setFrame_(((PAD + (WIDTH - w) / 2, PAD + (HEIGHT - h) / 2), (w, h)))
        self.pill.layer().setCornerRadius_(h / 2)

    def _set_scale(self, scale: float) -> None:
        """Scale the pill around its centre (spring open / soft close)."""
        try:
            layer = self.pill.layer()
            layer.setAnchorPoint_((0.5, 0.5))
            layer.setPosition_((PAD + WIDTH / 2, PAD + HEIGHT / 2))
            layer.setAffineTransform_(CGAffineTransformMakeScale(scale, scale))
        except Exception:
            pass

    def update(self, recording: bool, level: float, thinking: bool = False, done_count: int = 0) -> None:
        """Call from the main thread at ~60 fps."""
        thinking = thinking and not recording
        # transcription just finished: show a check if something was pasted
        if self.was_thinking and not thinking and not recording:
            if done_count != self.done_seen:
                self.done_t = 0
        self.was_thinking = thinking
        if not thinking:
            self.done_seen = done_count
        if recording:
            self.done_t = None

        active = recording or thinking or self.done_t is not None
        if not active and not self.visible:
            return
        if self.panel is None:
            self._build()
        if active and not self.visible:
            try:
                self.reduce_motion = bool(NSWorkspace.sharedWorkspace().accessibilityDisplayShouldReduceMotion())
            except Exception:
                self.reduce_motion = False
            self.view.levels = [0.0] * BARS
            self.view.m = self.view.c = 0.0
            self.env = 0.0
            self.alpha = 0.0
            self.open_t = 0
            self.quiet_since = None
            for sp, v in ((self.sw, WIDTH), (self.sh, HEIGHT), (self.sm, 0.0), (self.sc, 0.0)):
                sp.snap(v)
            self.target = (WIDTH, HEIGHT, 0.0, 0.0)
            self._set_size(WIDTH, HEIGHT)
            self.panel.setAlphaValue_(0.0)
            self._set_scale(1.0 if self.reduce_motion else 0.7)
            self.panel.orderFrontRegardless()
            self.visible = True

        now = time.monotonic()

        # where should the pill be heading? (kept as-is while fading out)
        if self.done_t is not None:
            self.target = (CHECK_S, CHECK_S, 1.0, 1.0)
            self.done_t += 1
            if self.done_t > DONE_FRAMES:
                self.done_t = None
        elif thinking:
            self.target = (THINK_W, THINK_H, 1.0, 0.0)
        elif recording:
            self.target = (WIDTH, HEIGHT, 0.0, 0.0)
        tw, th, tm, tc = self.target
        if self.reduce_motion:
            for sp, v in ((self.sw, tw), (self.sh, th), (self.sm, tm), (self.sc, tc)):
                sp.snap(v)
        else:
            self.sw.step(tw), self.sh.step(th), self.sm.step(tm), self.sc.step(tc)
        self._set_size(self.sw.x, self.sh.x)
        self.view.m, self.view.c, self.view.phase = self.sm.x, self.sc.x, now

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
        if self.open_t < OPEN_FRAMES and active and not self.reduce_motion:
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
            if not self.reduce_motion:
                self._set_scale(0.92 + 0.08 * self.alpha)
            if self.alpha == 0.0:
                self.panel.orderOut_(None)
                self.visible = False
                return
        self.panel.setAlphaValue_(self.alpha)
