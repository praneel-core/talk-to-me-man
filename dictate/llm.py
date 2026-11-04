"""Optional self-correction cleanup via a local Ollama model."""

import json
import urllib.request

from . import config, textproc


def llm_cleanup(text: str) -> str:
    """Resolve self-corrections with a local LLM (Ollama).
    Falls back to the input text if Ollama isn't running or misbehaves."""
    if not config.USE_LLM or not textproc.needs_llm(text):
        return text
    payload = {
        "model": config.OLLAMA_MODEL,
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": 0, "num_predict": 400},
        "messages": [
            {"role": "system", "content": config.LLM_PROMPT},
            {"role": "user", "content": text},
        ],
    }
    try:
        req = urllib.request.Request(
            config.OLLAMA_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT) as resp:
            out = json.loads(resp.read())["message"]["content"].strip()
    except Exception as e:
        print(f"(LLM cleanup skipped: {e})", flush=True)
        return text
    if len(out) > 1 and out.startswith('"') and out.endswith('"'):
        out = out[1:-1].strip()
    # Sanity checks: if the model rambled, returned nothing or reworded, keep the original.
    if not out or len(out) > len(text) * 1.3 + 20:
        return text
    if textproc.too_different(text, out):
        print(f"(LLM cleanup rejected, too different: {out})", flush=True)
        return text
    return out
