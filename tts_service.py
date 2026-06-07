from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from client import OPENAI_MODEL_GPT54_MINI, call_openai_messages


# ---------------------------------------------------------------------------
#  Config (can be overridden by env vars — same pattern as config.py)
# ---------------------------------------------------------------------------

PIPER_EXECUTABLE = os.environ.get("PIPER_EXECUTABLE", "piper")
PIPER_MODEL_DIR = os.environ.get(
    "PIPER_MODEL_DIR", str(Path(__file__).parent / "piper_models")
)
PIPER_DEFAULT_MODEL = os.environ.get("PIPER_DEFAULT_MODEL", "pl_PL-darkman-medium")

_TTS_PREPROCESS_SYSTEM = """\
Jesteś preprocesorem tekstu do syntezatora mowy (TTS). Przekształć podany tekst na czysty, płynnie brzmiący tekst mówiony w języku, w którym jest napisany.

ZASADY:
- Usuń wszelkie formatowanie markdown: nagłówki #, pogrubienia **, kursywy *, listy -, tabele |
- Tabele zamień na zdania opisowe: wymień kolumny i opisz każdy wiersz naturalnym zdaniem
- Bloki kodu zamień na słowo „kod" lub krótki opis co kod robi (jeśli wiadomo)
- Linki zamień na sam tekst linku, URL-e pomiń
- Zachowaj pełną treść merytoryczną — nic nie skracaj, nie streszczaj
- Nie dodawaj żadnych wstępów ani komentarzy od siebie
- Zwróć TYLKO czysty tekst do odczytania, nic więcej"""


# ---------------------------------------------------------------------------
#  Text preprocessing — markdown → speakable plain text via LLM
# ---------------------------------------------------------------------------


def preprocess_for_tts(text: str) -> str:
    """Convert markdown-rich text to clean, speakable plain text using gpt-5.4-mini."""
    text = text.strip()
    if not text:
        return ""
    return call_openai_messages(
        _TTS_PREPROCESS_SYSTEM,
        [{"role": "user", "content": text}],
        model=OPENAI_MODEL_GPT54_MINI,
    ).strip()


# ---------------------------------------------------------------------------
#  Piper runner
# ---------------------------------------------------------------------------


def _resolve_model_path(model_name: str) -> Path:
    model_dir = Path(PIPER_MODEL_DIR)
    for candidate in [
        model_dir / f"{model_name}.onnx",
        model_dir / model_name,
        Path(model_name),  # absolute path passed directly
    ]:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Piper model '{model_name}' not found in {model_dir}. "
        f"Download it and place the .onnx (+ .onnx.json) file there."
    )


def run_piper_tts(text: str, model_name: str | None = None) -> bytes:
    """
    Synthesize *text* with Piper TTS. Returns raw WAV bytes.

    Raises FileNotFoundError if the model file is missing.
    Raises RuntimeError if Piper exits with a non-zero code.
    """
    model_name = model_name or PIPER_DEFAULT_MODEL
    model_path = _resolve_model_path(model_name)
    clean = preprocess_for_tts(text)
    if not clean:
        return b""

    # Piper writes WAV to --output_file; we use a temp file so we get a
    # proper WAV container (headers included) without needing to build one.
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            [PIPER_EXECUTABLE, "--model", str(model_path), "--output_file", str(tmp_path)],
            input=clean.encode("utf-8"),
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"Piper exited {result.returncode}: {stderr[:400]}")
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
