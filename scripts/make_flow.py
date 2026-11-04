"""Generate docs/flow.svg for the README. Run from the repo root: python scripts/make_flow.py"""
W, H = 830, 940
CX, RX = 300, 655  # main column centre, right column centre
BW, BH = 300, 58

out = []
def esc(t): return t.replace("&", "&amp;").replace("<", "&lt;")
def box(cx, top, title, sub, cls="box", w=BW, h=BH, dashed=False):
    x = cx - w / 2
    out.append(f'<rect class="{cls}"{" stroke-dasharray=\"5 4\"" if dashed else ""} x="{x}" y="{top}" width="{w}" height="{h}" rx="12"/>')
    ty = top + (h / 2 - 4 if sub else h / 2 + 5)
    out.append(f'<text class="t {cls}t" x="{cx}" y="{ty}" text-anchor="middle">{esc(title)}</text>')
    if sub:
        out.append(f'<text class="s {cls}s" x="{cx}" y="{top + h / 2 + 15}" text-anchor="middle">{esc(sub)}</text>')
def diamond(cx, top, title, sub, w=290, h=100):
    cy = top + h / 2
    out.append(f'<polygon class="box" points="{cx},{top} {cx + w / 2},{cy} {cx},{top + h} {cx - w / 2},{cy}"/>')
    out.append(f'<text class="t" x="{cx}" y="{cy - 3}" text-anchor="middle">{esc(title)}</text>')
    out.append(f'<text class="s" x="{cx}" y="{cy + 15}" text-anchor="middle">{esc(sub)}</text>')
def line(pts, label=None, lpos=None, dashed=False):
    import math
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    ang = math.atan2(y1 - y0, x1 - x0)
    k = 9  # arrowhead size; the line stops a little short so the head sits on the edge
    bx, by = x1 - k * 0.8 * math.cos(ang), y1 - k * 0.8 * math.sin(ang)
    body = pts[:-1] + [(bx, by)]
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in body)
    out.append(f'<path class="ln" d="{d}" fill="none"{" stroke-dasharray=\"4 4\"" if dashed else ""}/>')
    px, py = -math.sin(ang), math.cos(ang)
    tri = [(x1, y1), (x1 - k * math.cos(ang) + 4.2 * px, y1 - k * math.sin(ang) + 4.2 * py), (x1 - k * math.cos(ang) - 4.2 * px, y1 - k * math.sin(ang) - 4.2 * py)]
    out.append('<polygon class="head" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in tri) + '"/>')
    if label:
        out.append(f'<text class="s lbl" x="{lpos[0]}" y="{lpos[1]}">{esc(label)}</text>')

# ---- nodes (top-down) ----
y_start, y_rel, y_speech, y_whisper, y_clean = 24, 112, 200, 288, 376
y_d1, y_d2 = 462, 590
y_llm, y_guard = 606, 692
y_paste, y_end = 784, 870
box(CX, y_start, "Hold Right Option", "mic opens, start sound, waveform pill", "accent")
box(CX, y_rel, "Release the key", "mic closes, the audio stays in memory")
box(CX, y_speech, "Check there is speech", "silence and noise never reach Whisper")
box(RX, y_speech + 6, "Ignored", "nothing is pasted", "ghost", w=200, h=46, dashed=True)
box(CX, y_whisper, "Whisper transcribes", "on-device mlx-whisper, with your word list")
box(CX, y_clean, "Quick cleanup", "removes um and uh, tidies spacing")
diamond(CX, y_d1, "Spoken punctuation?", "“comma”, “full stop”, “quotes”")
box(RX, y_d1 + 22, "Edit the previous text", "within 2 min, re-pasted with the fix", w=250, h=56)
diamond(CX, y_d2, "Correction cue?", "“no”, “I mean”, repeated words")
box(RX, y_llm, "Ollama fixes the correction", "local model; if off, your text is kept", "accent", w=250, h=58)
box(RX, y_guard, "Safety check", "reworded too much? keep your text", w=250, h=58)
box(CX, y_paste, "Paste into the focused app", "Cmd+V via the clipboard, which is then restored")
box(CX, y_end, "Check mark appears", "saved to Recent dictations", "accent")

# ---- arrows ----
def bottom(y, h=BH): return y + h
line([(CX, bottom(y_start, 58)), (CX, y_rel)])
line([(CX, bottom(y_rel)), (CX, y_speech)])
line([(CX, bottom(y_speech)), (CX, y_whisper)], "speech", (CX + 8, y_speech + BH + 20))
line([(CX + BW / 2, y_speech + 29), (RX - 100, y_speech + 29)], "no speech", (CX + BW / 2 + 14, y_speech + 22), dashed=True)
line([(CX, bottom(y_whisper)), (CX, y_clean)])
line([(CX, bottom(y_clean)), (CX, y_d1)])
line([(CX, y_d1 + 100), (CX, y_d2)], "no", (CX + 8, y_d1 + 100 + 14))
line([(CX + 145, y_d1 + 50), (RX - 125, y_d1 + 50)], "yes", (CX + 160, y_d1 + 42))
line([(CX, y_d2 + 100), (CX, y_paste)], "no", (CX + 8, y_d2 + 100 + 24))
line([(CX + 145, y_d2 + 50), (RX - 125, y_d2 + 50)])
line([(RX, y_llm + 58), (RX, y_guard)])
line([(RX, y_guard + 58), (RX, y_paste + 29), (CX + BW / 2, y_paste + 29)])
line([(RX + 125, y_d1 + 50), (806, y_d1 + 50), (806, y_end + 29), (CX + BW / 2, y_end + 29)])
line([(CX, bottom(y_paste)), (CX, y_end)])
out_lines = out
# yes label for d2 (placed after arrow)
out.append(f'<text class="s lbl" x="{CX + 160}" y="{y_d2 + 42}">yes</text>')

css = """
:root{--fill:#f6f8fa;--stroke:#8c959f;--text:#1f2328;--sub:#59636e;--accent:#0969da;--accentfill:#ddf4ff}
@media (prefers-color-scheme:dark){:root{--fill:#161b22;--stroke:#6e7681;--text:#e6edf3;--sub:#9198a1;--accent:#58a6ff;--accentfill:#10243e}}
text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}
.box{fill:var(--fill);stroke:var(--stroke);stroke-width:1.4}
.accent{fill:var(--accentfill);stroke:var(--accent);stroke-width:1.6}
.ghost{fill:none;stroke:var(--stroke);stroke-width:1.2}
.t{font-size:15px;font-weight:600;fill:var(--text)}
.s{font-size:11.5px;fill:var(--sub)}
.accentt{fill:var(--accent)}
.lbl{font-size:11.5px;font-weight:600;fill:var(--sub)}
.ln{stroke:var(--stroke);stroke-width:1.6}
.head{fill:var(--stroke)}
"""
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Flow of a dictation: hold key, record, check for speech, transcribe, clean up, optional punctuation edit or Ollama correction, paste">
<style>{css}</style>
''' + "\n".join(out) + "\n</svg>\n"
open("docs/flow.svg", "w").write(svg)
print("written", len(svg))
