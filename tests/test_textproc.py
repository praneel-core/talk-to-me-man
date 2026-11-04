import pytest

from holdspeak import textproc


@pytest.mark.parametrize(
    "prev,spoken,expected",
    [
        ("Hello there. ", "Comma.", "Hello there, "),
        ("Are you coming ", "Question mark", "Are you coming? "),
        ("Hello there, ", "Period", "Hello there. "),
        ("Hello there. ", "Quotes.", '"Hello there." '),
        ("Send it today ", "Hello", None),
        ("Send it today ", "comma separated values", None),
    ],
)
def test_apply_command(prev, spoken, expected):
    assert textproc.apply_command(prev, spoken) == expected


def test_clean_removes_fillers_and_capitalises():
    assert textproc.clean("um so uh we should go") == "So we should go"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("can we meet on tuesday no wednesday", True),
        ("i think we should we should launch", True),
        ("the report is ready for review", False),
        ("no", False),  # too short to bother the LLM
    ],
)
def test_needs_llm(text, expected):
    assert textproc.needs_llm(text) is expected


def test_too_different_flags_rewording():
    src = "can we meet on tuesday no wednesday"
    assert not textproc.too_different(src, "Can we meet on Wednesday?")
    assert textproc.too_different(src, "Would you be available for a catch-up midweek?")


def test_prompt_echo_detected():
    assert textproc.is_prompt_echo("ChatGPT, Claude, Anthropic.")
    assert not textproc.is_prompt_echo("Ask Claude about the API.")


def test_has_speech_rejects_silence_and_noise():
    import numpy as np

    rng = np.random.default_rng(0)
    assert not textproc.has_speech(np.zeros(32000, dtype=np.float32), 16000)
    assert not textproc.has_speech(rng.normal(0, 0.004, 32000).astype(np.float32), 16000)


def test_has_speech_accepts_loud_audio():
    import numpy as np

    t = np.arange(32000) / 16000
    tone = (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    assert textproc.has_speech(tone, 16000)
