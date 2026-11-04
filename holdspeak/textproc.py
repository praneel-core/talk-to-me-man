"""Pure text helpers (no audio, no models) so they can be unit-tested."""

import re

import numpy as np

from . import config

FILLERS = re.compile(r"\b(?:um+|uh+|er+|ah+|hmm+|mm+)\b[,.]?\s*", re.IGNORECASE)

# Only call the LLM when the text looks like it contains a self-correction or a
# stutter; otherwise the regex cleanup is enough and we skip ~2s of latency.
CORRECTION_CUES = re.compile(
    r"\b(?:no|nope|sorry|actually|wait|rather|scratch that|i mean|make that|"
    r"or rather|correction|not)\b|\b(\w+(?: \w+)?),? \1\b",
    re.IGNORECASE,
)

PUNCT_COMMANDS = {
    "full stop": ".", "period": ".", "dot": ".",
    "comma": ",",
    "question mark": "?",
    "exclamation mark": "!", "exclamation point": "!",
    "colon": ":", "semicolon": ";", "semi colon": ";",
    "ellipsis": "...", "three dots": "...",
}
QUOTE_COMMANDS = {"quotes", "quote", "in quotes", "put in quotes", "quotation marks"}


def clean(text: str) -> str:
    """Light cleanup: remove filler words, tidy spaces, capitalise."""
    text = FILLERS.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text:
        text = text[0].upper() + text[1:]
    return text


def needs_llm(text: str) -> bool:
    return len(text.split()) >= 3 and bool(CORRECTION_CUES.search(text))


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def too_different(source: str, edited: str, limit: float = 0.15) -> bool:
    """True if `edited` contains too many words that weren't in `source`
    (i.e. the LLM reworded instead of just editing)."""
    src = set(_words(source))
    new = _words(edited)
    return bool(new) and sum(w not in src for w in new) / len(new) > limit


def is_prompt_echo(text: str) -> bool:
    """Whisper sometimes echoes its prompt back on near-silence."""
    pattern = "|".join(
        re.escape(w) for w in [config.PROMPT_PREFIX.strip(), *config.CUSTOM_WORDS]
    )
    leftover = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return not re.search(r"[a-z0-9]", leftover, re.IGNORECASE)


def apply_command(prev: str, spoken: str) -> str | None:
    """If `spoken` is a punctuation command, return `prev` edited accordingly."""
    cmd = re.sub(r"[^a-z ]", "", spoken.lower()).strip()
    if cmd not in PUNCT_COMMANDS and cmd not in QUOTE_COMMANDS:
        return None
    body = prev.strip()
    m = re.search(r"[.,;:!?]+$", body)
    tail = m.group(0) if m else ""
    body = body[: len(body) - len(tail)]
    if cmd in QUOTE_COMMANDS:
        return f'"{body}{tail}" '
    return body + PUNCT_COMMANDS[cmd] + " "


def has_speech(audio: np.ndarray, sample_rate: int) -> bool:
    """Cheap voice-activity check. Whisper invents text ("Thank you.") for
    silence/noise, so only transcribe audio with enough loud 30 ms frames.
    The first 0.3 s is ignored because the start sound plays into the mic."""
    skip = int(config.CUE_SKIP_SECONDS * sample_rate)
    audio = audio[skip:]
    n = int(0.03 * sample_rate)
    if len(audio) < n:
        return False
    frames = audio[: len(audio) // n * n].reshape(-1, n)
    rms = np.sqrt((frames**2).mean(axis=1))
    return int((rms > config.SPEECH_FRAME_RMS).sum()) >= config.MIN_SPEECH_FRAMES
