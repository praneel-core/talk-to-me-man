"""Generate docs/internals.svg (technical view for the README).
Run from the repo root: python scripts/make_internals.py"""

W = 920
LX, LW = 40, 290  # stage column
TX, TW = 372, 508  # technology column
PAD_Y = 26

def esc(t): return t.replace("&", "&amp;").replace("<", "&lt;")

# (title, what happens, [(library, detail), ...])
ROWS = [
    ("Hold Right Option", "key press detected",
     [("pynput", "keyboard.Listener, a macOS event tap"),
      ("queue.SimpleQueue", "the callback only queues “press”;"),
      ("", "a worker thread does the slow work")]),
    ("Record", "mic opens, start sound",
     [("sounddevice", "InputStream (PortAudio → CoreAudio)"),
      ("", "16 kHz mono float32, chunks kept as numpy arrays"),
      ("afplay", "plays the start sound")]),
    ("Live feedback", "runs in parallel while recording",
     [("PyObjC / AppKit", "NSPanel + NSVisualEffectView pill, 60 fps"),
      ("rumps", "menu bar app; ⌥ icon from SF Symbols"),
      ("", "mic loudness (RMS) drives the bars")]),
    ("Release", "mic closes, stop sound",
     [("afplay", "plays the stop sound (Tink)"),
      ("numpy", "np.concatenate → one float32 array"),
      ("threading", "own thread; a lock keeps MLX single-threaded")]),
    ("Speech check", "silence and noise are dropped",
     [("numpy", "RMS of every 30 ms frame, first 0.3 s skipped"),
      ("", "(our own start sound leaks into the mic)")]),
    ("Transcribe", "audio → text, fully on-device",
     [("mlx-whisper", "whisper-large-v3-turbo, MLX on the Apple GPU"),
      ("", "prompt = a punctuated sentence + your word list"),
      ("Hugging Face cache", "weights downloaded once (~1.5 GB)")]),
    ("Clean up", "light, rule-based",
     [("re", "regex removes um/uh, tidies spacing, capitalises"),
      ("", "drops Whisper echoing its own prompt")]),
    ("Spoken punctuation?", "“comma”, “quotes” → edit last paste, stop",
     [("textproc", "dict lookup, edits the previous text"),
      ("pynput", "Shift+Left selects it, Cmd+V pastes the fix")]),
    ("Correction cue?", "“no”, “I mean”, repeats → Ollama",
     [("re", "cue regex decides whether the LLM is needed"),
      ("urllib", "POST localhost:11434/api/chat (localhost only)"),
      ("Ollama", "qwen2.5:3b, temperature 0, minimal-edit prompt"),
      ("", "guard: reworded by >15% → keep original")]),
    ("Paste", "into the focused app",
     [("pyperclip", "pbcopy / pbpaste for the clipboard"),
      ("pynput", "Cmd+V, then the old clipboard is restored")]),
    ("Confirm", "done",
     [("overlay", "check mark appears, then the pill fades away"),
      ("collections.deque", "last 5 texts → Recent dictations (memory only)")]),
]
LINE = 17
out = []
y = 70
centers = []
for i, (title, what, techs) in enumerate(ROWS, 1):
    h = max(58, 26 + LINE * len(techs))
    # stage box
    accent = i in (1, 6, 9, 11)
    out.append(f'<rect class="{"accent" if accent else "box"}" x="{LX}" y="{y}" width="{LW}" height="{h}" rx="12"/>')
    out.append(f'<circle class="num" cx="{LX + 24}" cy="{y + h / 2}" r="12"/>')
    out.append(f'<text class="n" x="{LX + 24}" y="{y + h / 2 + 4}" text-anchor="middle">{i}</text>')
    out.append(f'<text class="t{" accentt" if accent else ""}" x="{LX + 48}" y="{y + h / 2 - 3}">{esc(title)}</text>')
    out.append(f'<text class="s" x="{LX + 48}" y="{y + h / 2 + 14}">{esc(what)}</text>')
    # tech panel
    out.append(f'<rect class="tech" x="{TX}" y="{y}" width="{TW}" height="{h}" rx="12"/>')
    ty = y + (h - LINE * len(techs)) / 2 + 13
    for lib, detail in techs:
        if lib:
            out.append(f'<text class="m" x="{TX + 16}" y="{ty}"><tspan class="lib">{esc(lib)}</tspan><tspan class="d">  {esc(detail)}</tspan></text>')
        else:
            out.append(f'<text class="m d" x="{TX + 16}" y="{ty}">{esc(detail)}</text>')
        ty += LINE
    # connector stage -> tech
    out.append(f'<path class="dot" d="M{LX + LW},{y + h / 2} L{TX},{y + h / 2}"/>')
    centers.append((y, h))
    y += h + PAD_Y
H = y - PAD_Y + 90
# arrows between stages (down the left column)
import math
def arrow(x, y0, y1):
    out.append(f'<path class="ln" d="M{x},{y0} L{x},{y1 - 7}"/>')
    out.append(f'<polygon class="head" points="{x},{y1} {x - 4.5},{y1 - 9} {x + 4.5},{y1 - 9}"/>')
for (y0, h0), (y1, _) in zip(centers, centers[1:]):
    arrow(LX + LW / 2, y0 + h0, y1)
# column headers
out.append(f'<text class="hd" x="{LX}" y="44">STAGE</text>')
out.append(f'<text class="hd" x="{TX}" y="44">WHAT RUNS IT</text>')
# background services band
by = y - PAD_Y + 26
out.append(f'<rect class="ghost" x="{LX}" y="{by}" width="{TX + TW - LX}" height="44" rx="12" stroke-dasharray="5 4"/>')
out.append(f'<text class="m" x="{LX + 16}" y="{by + 19}"><tspan class="lib">Always running</tspan><tspan class="d">  OllamaMonitor thread polls GET /api/ps every 3 s,</tspan></text>')
out.append(f'<text class="m d" x="{LX + 16}" y="{by + 36}">loads the model when Ollama comes up and drives the status dot on the icon.</text>')

css = """
:root{--fill:#f6f8fa;--stroke:#8c959f;--text:#1f2328;--sub:#59636e;--accent:#0969da;--accentfill:#ddf4ff;--tech:#ffffff}
@media (prefers-color-scheme:dark){:root{--fill:#161b22;--stroke:#6e7681;--text:#e6edf3;--sub:#9198a1;--accent:#58a6ff;--accentfill:#10243e;--tech:#0d1117}}
text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}
.box{fill:var(--fill);stroke:var(--stroke);stroke-width:1.4}
.accent{fill:var(--accentfill);stroke:var(--accent);stroke-width:1.6}
.tech{fill:var(--tech);stroke:var(--stroke);stroke-width:1}
.ghost{fill:none;stroke:var(--stroke);stroke-width:1.2}
.t{font-size:15px;font-weight:600;fill:var(--text)}
.accentt{fill:var(--accent)}
.s{font-size:11.5px;fill:var(--sub)}
.m{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;fill:var(--text)}
.lib{fill:var(--accent);font-weight:700}
.d{fill:var(--sub)}
.hd{font-size:11px;font-weight:700;letter-spacing:1.5px;fill:var(--sub)}
.num{fill:none;stroke:var(--stroke);stroke-width:1.2}
.n{font-size:12px;font-weight:600;fill:var(--sub)}
.ln{stroke:var(--stroke);stroke-width:1.6}
.dot{stroke:var(--stroke);stroke-width:1;stroke-dasharray:2 3}
.head{fill:var(--stroke)}
"""
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
       'aria-label="Technical view of a dictation: which library or API handles each stage">'
       f'<style>{css}</style>\n' + "\n".join(out) + "\n</svg>\n")
open("docs/internals.svg", "w").write(svg)
print("written", len(svg), "height", H)
