"""Push-to-talk dictation: hold Right Option, speak, release, text is pasted.

Everything runs locally. Hotkey events are only queued by the key listener;
a worker thread does the slow work (mic, sounds) so the listener never blocks
(macOS silently disables an event tap whose callback stalls).
"""

import queue
import re
import subprocess
import threading
import time

import mlx_whisper
import numpy as np
import pyperclip
import sounddevice as sd
from pynput import keyboard
from Quartz import CGEventSourceKeyState, kCGEventSourceStateCombinedSessionState

from . import config, textproc
from .llm import llm_cleanup

kb = keyboard.Controller()
last_paste: tuple[str, float] | None = None  # (text as pasted, time)
frames: list[np.ndarray] = []
stream: sd.InputStream | None = None
recording = False
lock = threading.Lock()
transcribe_lock = threading.Lock()  # MLX isn't safe to run from two threads at once
_events: queue.SimpleQueue = queue.SimpleQueue()


def replace_last(old: str, new: str) -> None:
    """Select the text we pasted last (cursor sits right after it) and paste over it."""
    with kb.pressed(keyboard.Key.shift):
        for _ in range(len(old)):
            kb.tap(keyboard.Key.left)
    paste(new, trailing_space=False)


def paste(text: str, trailing_space: bool = True) -> None:
    """Paste via clipboard, then restore whatever was there before."""
    try:
        old = pyperclip.paste()
    except Exception:
        old = ""
    pyperclip.copy(text + (" " if trailing_space else ""))
    time.sleep(0.05)
    with kb.pressed(keyboard.Key.cmd):
        kb.press("v")
        kb.release("v")
    time.sleep(0.2)
    pyperclip.copy(old)


def transcribe_and_paste(audio: np.ndarray) -> None:
    with transcribe_lock:
        _transcribe_and_paste(audio)


def _transcribe_and_paste(audio: np.ndarray) -> None:
    global last_paste
    if len(audio) / config.SAMPLE_RATE < config.MIN_SECONDS:
        return
    if float(np.sqrt(np.mean(audio**2))) < config.MIN_LOUDNESS:
        return  # silence: don't let Whisper invent text
    t0 = time.time()
    result = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo=config.MODEL,
        initial_prompt=config.WHISPER_PROMPT,
        condition_on_previous_text=False,
    )
    text = textproc.clean(result.get("text", ""))
    if not text or textproc.is_prompt_echo(text):
        return
    if last_paste and time.time() - last_paste[1] < config.EDIT_WINDOW:
        edited = textproc.apply_command(last_paste[0], text)
        if edited is not None:
            replace_last(last_paste[0], edited)
            last_paste = (edited, time.time())
            print(f"[{time.time() - t0:.2f}s] edit -> {edited!r}", flush=True)
            return
    text = llm_cleanup(text)
    paste(text)
    last_paste = (text + " ", time.time())
    print(f"[{time.time() - t0:.2f}s] {text}", flush=True)


def play_sound(name: str) -> None:
    """Short start/stop cue (non-blocking)."""
    subprocess.Popen(
        ["afplay", f"/System/Library/Sounds/{name}.aiff"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _right_option_down() -> bool:
    """Ask macOS directly whether Right Option is physically held."""
    return bool(
        CGEventSourceKeyState(
            kCGEventSourceStateCombinedSessionState, config.RIGHT_OPTION_KEYCODE
        )
    )


def _watchdog() -> None:
    """Safety net: if the key-release event is ever missed, stop recording
    once the key is no longer held (or after MAX_SECONDS)."""
    start = time.time()
    misses = 0
    while recording:
        time.sleep(0.15)
        try:
            misses = 0 if _right_option_down() else misses + 1
        except Exception as e:
            print(f"(watchdog error: {e})", flush=True)
            misses = 0
        if recording and (misses >= 3 or time.time() - start > config.MAX_SECONDS):
            _events.put("release")
            return


def on_audio(indata, frame_count, time_info, status):
    frames.append(indata.copy())


def _do_press():
    global stream, recording
    with lock:
        if recording:
            return
        frames.clear()
        try:
            stream = sd.InputStream(
                samplerate=config.SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=on_audio,
            )
            stream.start()
        except Exception as e:
            # e.g. mic permission denied; don't leave `recording` stuck on
            print(f"(could not start recording: {e})", flush=True)
            stream = None
            return
        recording = True
        play_sound("Pop")
        print("Listening...", flush=True)
        threading.Thread(target=_watchdog, daemon=True).start()


def _do_release():
    global stream, recording
    with lock:
        if not recording:
            return
        recording = False
        try:
            stream.stop()
            stream.close()
        except Exception as e:
            print(f"(error closing mic: {e})", flush=True)
        stream = None
        play_sound("Tink")
        if not frames:
            return
        audio = np.concatenate(frames).flatten()
    threading.Thread(target=transcribe_and_paste, args=(audio,), daemon=True).start()


def _worker() -> None:
    while True:
        ev = _events.get()
        try:
            _do_press() if ev == "press" else _do_release()
        except Exception as e:
            print(f"(recording error: {e})", flush=True)


def on_press(key):
    if key == config.HOTKEY:
        _events.put("press")


def on_release(key):
    if key == config.HOTKEY:
        _events.put("release")


threading.Thread(target=_worker, daemon=True).start()


def warm_up() -> None:
    """Load the models so the first real dictation isn't slow."""
    mlx_whisper.transcribe(
        np.zeros(config.SAMPLE_RATE, dtype=np.float32), path_or_hf_repo=config.MODEL
    )
    if config.USE_LLM:
        llm_cleanup("can we meet on tuesday no wednesday")  # has a cue, so it really loads the model


def main():
    print("Loading model (first run downloads ~1.5 GB)...", flush=True)
    warm_up()
    print("Ready. Hold RIGHT OPTION to dictate. Ctrl+C to quit.", flush=True)
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()
