"""Generate docs/how-it-works.svg for the README (light theme only: it carries its own
background panel, so it looks the same on GitHub's light and dark themes).
Run from the repo root: python scripts/make_diagram.py"""

W = 940
CARD_X, CARD_W = 24, 892
NODE_X = 62
LEFT_X, LEFT_W = 100, 196
MID_X, MID_W = 330, 318
CHIP_X, CHIP_W = 684, 212

def esc(t): return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def wrap(text, width_px, px_per_char):
    n = max(8, int(width_px / px_per_char))
    lines, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + (1 if cur else 0) > n:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur: lines.append(cur)
    return lines

def chip_layout(chips):
    rows, x, row = [], 0, []
    for c in chips:
        w = len(c) * 6.9 + 18
        if x + w > CHIP_W and row:
            rows.append(row); row, x = [], 0
        row.append((c, x, w)); x += w + 6
    if row: rows.append(row)
    return rows

PHASES = [
 ("CAPTURE", [
  dict(tag="YOU", title="Hold Right Option", sub="and start talking",
       mid="The app notices the key press. It only leaves a note for a background worker, so your keyboard never lags.",
       chips=["pynput", "queue", "threading"]),
  dict(tag="YOU", title="Speak", sub="a small pill shows your voice",
       mid="The microphone records your voice and a soft “pop” plays. The bars in the pill move with how loud you are.",
       chips=["sounddevice", "numpy", "AppKit", "afplay"]),
 ]),
 ("UNDERSTAND", [
  dict(tag="YOU", title="Let go of the key", sub="the pill shows it is thinking",
       mid="The microphone stops and a soft “tink” plays. The recording stays in memory. It is never saved or sent anywhere.",
       chips=["numpy", "afplay", "threading"]),
  dict(tag="AUTOMATIC", title="Did you say anything?", sub="silence is ignored",
       mid="The audio is checked in tiny 30 ms slices. Silence or background noise stops here, so the transcriber cannot make up words.",
       chips=["numpy"]),
  dict(tag="AUTOMATIC", title="Speech becomes text", sub="on your Mac, offline",
       mid="The Whisper AI model runs on your Mac’s chip. Your personal word list helps it spell names and jargon correctly.",
       chips=["mlx-whisper", "MLX", "whisper-large-v3-turbo"]),
 ]),
 ("POLISH", [
  dict(tag="AUTOMATIC", title="Quick tidy", sub="simple rules",
       mid="Removes “um” and “uh”, fixes spacing and capitalises the first letter.",
       chips=["re"]),
  dict(tag="ONLY IF", title="You said just “comma”", sub="or “full stop”, “quotes”…",
       mid="Instead of adding new text, the app fixes the punctuation of what you dictated a moment ago (within 2 minutes).",
       chips=["pynput", "textproc"]),
  dict(tag="ONLY IF", title="You corrected yourself", sub="“Tuesday, no, Wednesday”",
       mid="A small AI on your Mac (Ollama) removes the mistake and changes nothing else. If it rewords too much, or Ollama is off, your text is kept as it is.",
       chips=["urllib", "Ollama", "qwen2.5:3b", "re"]),
 ]),
 ("DELIVER", [
  dict(tag="AUTOMATIC", title="Text appears", sub="right where your cursor is",
       mid="The text is copied, pasted with Cmd+V into the app you are using, and your previous clipboard is put back.",
       chips=["pyperclip", "pynput"]),
  dict(tag="AUTOMATIC", title="A check mark confirms", sub="then the pill fades away",
       mid="The text is also added to Recent dictations in the menu (kept in memory only, gone when the app quits).",
       chips=["AppKit", "deque"]),
 ]),
]

out, nodes = [], []
y = 24
# headline pill
out.append(f'<rect class="pill" x="{CARD_X}" y="{y}" width="446" height="30" rx="15"/>')
out.append(f'<text class="pilltxt" x="{CARD_X + 223}" y="{y + 20}" text-anchor="middle">Everything stays on your Mac: audio and text never leave it</text>')
out.append(f'<text class="legend" x="{CARD_X + CARD_W}" y="{y + 19}" text-anchor="end">YOU: your action   \u00b7   AUTOMATIC: the app does it   \u00b7   ONLY IF: special cases</text>')
y += 58
# column headers
for x, t in ((LEFT_X, "WHAT YOU DO"), (MID_X, "WHAT THE APP DOES"), (CHIP_X, "WHAT RUNS IT")):
    out.append(f'<text class="hd" x="{x}" y="{y}">{t}</text>')
y += 20
n = 0
for phase, rows in PHASES:
    out.append(f'<text class="phase" x="{CARD_X + 4}" y="{y + 12}">{phase}</text>')
    out.append(f'<path class="rule" d="M{CARD_X + 4 + len(phase) * 9 + 14},{y + 8} L{CARD_X + CARD_W},{y + 8}"/>')
    y += 28
    for r in rows:
        n += 1
        title = wrap(r["title"], LEFT_W, 8.2)
        sub = wrap(r["sub"], LEFT_W, 6.6)
        mid = wrap(r["mid"], MID_W, 6.8)
        chips = chip_layout(r["chips"])
        left_h = 14 + 20 * len(title) + 16 * len(sub)
        mid_h = 20 * len(mid)
        chip_h = 28 * len(chips) - 6
        h = max(88, max(left_h, mid_h, chip_h) + 46)
        out.append(f'<rect class="card" x="{CARD_X}" y="{y}" width="{CARD_W}" height="{h}" rx="16"/>')
        cy = y + h / 2
        nodes.append((NODE_X - 14, cy))
        out.append(f'<circle class="node" cx="{NODE_X - 14}" cy="{cy}" r="13"/>')
        out.append(f'<text class="nodetxt" x="{NODE_X - 14}" y="{cy + 4.5}" text-anchor="middle">{n}</text>')
        # left column (vertically centred)
        ty = y + (h - left_h) / 2 + 10
        out.append(f'<text class="tag tag-{r["tag"].replace(" ", "")}" x="{LEFT_X}" y="{ty}">{r["tag"]}</text>')
        ty += 22
        for l in title:
            out.append(f'<text class="title" x="{LEFT_X}" y="{ty}">{esc(l)}</text>'); ty += 20
        ty -= 4
        for l in sub:
            out.append(f'<text class="sub" x="{LEFT_X}" y="{ty}">{esc(l)}</text>'); ty += 16
        # middle (vertically centred)
        ty = y + (h - mid_h) / 2 + 14
        for l in mid:
            out.append(f'<text class="mid" x="{MID_X}" y="{ty}">{esc(l)}</text>'); ty += 20
        # chips (vertically centred)
        cyy = y + (h - chip_h) / 2
        for row in chips:
            for c, x0, w in row:
                out.append(f'<rect class="chip" x="{CHIP_X + x0}" y="{cyy}" width="{w}" height="22" rx="11"/>')
                out.append(f'<text class="chiptxt" x="{CHIP_X + x0 + w / 2}" y="{cyy + 15}" text-anchor="middle">{esc(c)}</text>')
            cyy += 28
        # faint column dividers
        out.append(f'<path class="div" d="M{MID_X - 18},{y + 18} L{MID_X - 18},{y + h - 18}"/>')
        out.append(f'<path class="div" d="M{CHIP_X - 18},{y + 18} L{CHIP_X - 18},{y + h - 18}"/>')
        y += h + 14
    y += 4
# background band
y += 2
out.append(f'<rect class="band" x="{CARD_X}" y="{y}" width="{CARD_W}" height="58" rx="16"/>')
out.append(f'<text class="phase" x="{CARD_X + 24}" y="{y + 24}">ALWAYS RUNNING IN THE BACKGROUND</text>')
out.append(f'<text class="mid" x="{CARD_X + 24}" y="{y + 44}">Watches whether Ollama is ready (checks every 3 seconds, loads the model when it appears) and shows the dot on the menu bar icon.</text>')
H = y + 58 + 24
# timeline line behind cards (drawn first)
first, last = nodes[0], nodes[-1]
timeline = f'<path class="line" d="M{NODE_X - 14},{nodes[0][1]} L{NODE_X - 14},{nodes[-1][1]}"/>'

css = """
:root{--bg:#f9fafb;--card:#ffffff;--border:#e4e7ec;--text:#101828;--sub:#667085;--chip:#f2f4f7;--chiptxt:#344054;--accent:#6d5efc;--accentsoft:#ece9ff;--shadow:rgba(16,24,40,.07)}
text{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Segoe UI',Inter,Helvetica,Arial,sans-serif}
.card{fill:var(--card);stroke:var(--border);stroke-width:1;filter:url(#sh)}
.band{fill:var(--card);stroke:var(--border);stroke-width:1.2;stroke-dasharray:6 5}
.panel{fill:var(--bg);stroke:var(--border);stroke-width:1}
.pill{fill:var(--accentsoft)}
.pilltxt{font-size:12.5px;font-weight:600;fill:var(--accent)}
.legend{font-size:11.5px;fill:var(--sub)}
.hd{font-size:10.5px;font-weight:700;letter-spacing:1.6px;fill:var(--sub)}
.phase{font-size:11px;font-weight:800;letter-spacing:2px;fill:var(--accent)}
.rule{stroke:var(--border);stroke-width:1}
.line{stroke:var(--accent);stroke-opacity:.28;stroke-width:2}
.node{fill:var(--accent)}
.nodetxt{font-size:12px;font-weight:700;fill:#fff}
.tag{font-size:9.5px;font-weight:800;letter-spacing:1.4px;fill:var(--sub)}
.tag-ONLYIF{fill:var(--accent)}
.title{font-size:15px;font-weight:650;fill:var(--text)}
.sub{font-size:12px;fill:var(--sub)}
.mid{font-size:13px;fill:var(--text);fill-opacity:.88}
.chip{fill:var(--chip)}
.chiptxt{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11.5px;fill:var(--chiptxt)}
.div{stroke:var(--border);stroke-width:1}
"""
defs = ('<defs><filter id="sh" x="-5%" y="-10%" width="110%" height="130%">'
        '<feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="#101828" flood-opacity="0.07"/></filter></defs>')
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
       'aria-label="What happens when you dictate: capture, understand, polish and deliver, with the technology behind each step">'
       f'<style>{css}</style>{defs}\n<rect class="panel" x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22"/>\n{timeline}\n' + "\n".join(out) + "\n</svg>\n")
open("docs/how-it-works.svg", "w").write(svg)
print("written", len(svg), "height", H)
