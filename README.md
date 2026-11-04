# Talk To Me Man

Free, unlimited, fully local push-to-talk dictation for Apple Silicon Macs.
Hold **Right Option**, speak, release: the text is pasted into the focused app.
No cloud, no subscription, nothing leaves your machine.

- **Transcription:** [mlx-whisper](https://github.com/ml-explore/mlx-examples) (`whisper-large-v3-turbo`), fully on-device.
- **Self-correction cleanup (optional):** a local [Ollama](https://ollama.com) model turns
  "Tuesday, no, Wednesday" into "Wednesday". It only runs when your sentence contains a correction cue.
- **Live feedback:** a frosted-glass pill with a waveform while you speak, three pulsing dots while it
  transcribes, and a check mark when the text is pasted. Start and stop sounds too.
- **Spoken punctuation edits:** after dictating, say "comma", "full stop", "question mark", "quotes"... as a
  separate dictation to fix the previous text.
- **Menu bar app:** an Option-key (⌥) icon that turns bold while recording. The menu has:
  - **Recent dictations:** your last 5, click one to copy it (kept in memory only, cleared when the app quits).
  - **Pause dictation** and **Smart cleanup** toggles (the cleanup choice is remembered).
  - **Microphone:** pick an input device, or use the system default.
  - **Launch at login**, **Edit vocabulary...** (your Whisper word list), **Show log** and **About**.
  - A status line at the top that only appears when something needs attention: loading, an error, or a
    missing Accessibility / Input Monitoring permission (click it to open the right System Settings page).
- **Ollama status light:** a small dot on the icon's top-right corner: green = Ollama ready, orange (pulsing) =
  starting, red = not running (self-correction cleanup is skipped). Hover it for a tooltip. The app loads the
  model for you as soon as Ollama comes up.

## How it works

![Flow of a dictation, from holding the key to the pasted text](docs/flow.svg)

1. **Hold Right Option.** The mic opens, a start sound plays and the waveform pill appears. The key listener only queues the event; a worker thread does the slow work, so the hotkey never freezes.
2. **Release.** The mic closes and the audio stays in memory. It is never written to disk or sent anywhere.
3. **Speech check.** A quick loudness check drops silence and noise, because Whisper invents text for them.
4. **Whisper** (`mlx-whisper`, on-device) turns the audio into text. A short prompt with your word list helps it spell names and jargon.
5. **Quick cleanup** removes "um" and "uh" and tidies spacing.
6. **Spoken punctuation.** If the whole dictation is a command like "comma" or "quotes" and you dictated within the last 2 minutes, the previous text is re-pasted with that fix and nothing else happens.
7. **Correction cue.** If the text contains a cue such as "no", "I mean" or a repeated phrase, a local Ollama model removes the mistaken part. It is told to change nothing else, and a safety check keeps your original text if it rewords too much. If Ollama is off, your text is kept as it is.
8. **Paste.** The text goes in through the clipboard (Cmd+V), the clipboard is restored, a check mark appears and the text is added to Recent dictations.

## Under the hood

The same pipeline from a technical angle: what runs each stage and which library does the work.

![Technical view: which library or API handles each stage of a dictation](docs/internals.svg)

| Library / tool | Used for |
|---|---|
| [`pynput`](https://pynput.readthedocs.io) | global hotkey listener (macOS event tap) and the simulated Cmd+V and Shift+Left key presses |
| [`sounddevice`](https://python-sounddevice.readthedocs.io) | microphone capture through PortAudio / CoreAudio, 16 kHz mono float32 |
| [`numpy`](https://numpy.org) | audio buffers, loudness (RMS) for the speech check and the waveform |
| [`mlx-whisper`](https://github.com/ml-explore/mlx-examples/tree/main/whisper) | speech to text with `whisper-large-v3-turbo`, running on the Apple GPU via MLX |
| [Ollama](https://ollama.com) (`qwen2.5:3b`) | optional local model that fixes spoken self-corrections, called over `localhost` with `urllib` |
| [`pyperclip`](https://github.com/asweigart/pyperclip) | clipboard access (`pbcopy` / `pbpaste`) for pasting |
| [`rumps`](https://github.com/jaredks/rumps) | the menu bar app and its menu |
| PyObjC (`AppKit`, `Quartz`) | the floating waveform pill, SF Symbol menu bar icons, the status dot, permission checks |
| `afplay` | the start and stop sounds |
| Python standard library | `threading` and `queue` (worker thread, locks), `re` (cleanup and cue detection), `collections.deque` (recent dictations), `json` (settings) |

Threads: the key listener only queues events; a worker thread opens and closes the mic; each recording is transcribed on its own thread behind a lock (MLX is not thread-safe); a monitor thread watches Ollama; the UI runs on the main thread.

Regenerate the diagrams with `python scripts/make_flow.py` and `python scripts/make_internals.py`.

## Requirements

macOS on Apple Silicon, Python 3.10+, and (optional) Ollama with `qwen2.5:3b`.

## Install

```bash
git clone https://github.com/praneel-core/talk-to-me-man.git && cd talk-to-me-man
python3 -m venv venv
venv/bin/pip install -r requirements.txt        # or: venv/bin/pip install -r requirements.lock

# optional: smart cleanup
brew install ollama && brew services start ollama
ollama pull qwen2.5:3b
```

The first run downloads the Whisper model (~1.5 GB).

## Run

```bash
venv/bin/python -m talktomeman            # terminal, Ctrl+C to quit
venv/bin/python -m talktomeman.menubar    # menu bar app
scripts/build_app.sh                  # build ~/Applications/Dictate.app (launch from Spotlight)
```

### macOS permissions (one-time)

System Settings → Privacy & Security → add **Dictate.app** (or your terminal) **and** the venv's
`Python.app` (`<brew prefix>/Cellar/python@3.x/.../Resources/Python.app`) under **Accessibility**,
**Input Monitoring** and **Microphone**. Quit and reopen the app afterwards. Rebuilding the app
changes its signature, so you have to re-grant after `build_app.sh`.

Optional: add Dictate.app to Login Items. Ollama started via `brew services` already launches at login.

## Customise

- Settings (hotkey, models, thresholds, cleanup prompt): [talktomeman/config.py](talktomeman/config.py)
- Menu bar look: `MENU_ICON` (`"option"`, `"bubble"` or `"waveform"`) and `OLLAMA_INDICATOR`
  (`"dot"` for the coloured light, `"badge"` for a monochrome corner badge plus a line in the menu)
- Your own names and jargon for Whisper: one per line in `~/.config/talktomeman/words.txt`
- Log of the menu bar app: `/tmp/dictate.log` (or Show log in the menu)
- Choices made in the menu are stored in `~/.config/talktomeman/settings.json`

## Layout

```
talktomeman/
  config.py         settings, prompts, vocabulary
  textproc.py       pure text logic (cleanup, punctuation commands, speech check), unit-tested
  llm.py            Ollama call + safety checks
  ollama_status.py  watches Ollama (off / starting / ready) and loads the model when it comes up
  core.py           hotkey, mic, transcription, paste
  overlay.py        floating waveform pill (listening, thinking, done)
  icons.py          menu bar icons
  menubar.py        rumps menu bar app
  settings.py       saves menu choices (microphone, Smart cleanup) to ~/.config/talktomeman/settings.json
scripts/            build_app.sh, make_icon.py, make_flow.py and make_internals.py (regenerate the diagrams in docs/)
tests/              pytest suite for textproc
dictate_menubar.py  legacy launcher path for an already-built Dictate.app; safe to delete after rebuilding it
```

## Develop

```bash
venv/bin/pip install pytest && venv/bin/python -m pytest
```

## Known limits

- Punctuation commands edit the last pasted text by selecting it with Shift+Left, so they only work while
  the cursor is still right after that text (and within 2 minutes).
- The Ollama status dot has so far only been checked on a dark menu bar.
- Whisper large-v3-turbo takes ~1.5-2 s per short dictation; `whisper-small-mlx` is faster but less accurate.

## License

MIT
