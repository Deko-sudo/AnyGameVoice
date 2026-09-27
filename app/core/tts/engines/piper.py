"""Piper engine.

Uses the `piper` CLI binary if installed:
  echo "text" | piper --model voice.onnx --output_file out.wav

No bundled models; user points to a downloaded .onnx voice.
"""

import os
import shutil
import subprocess

from .base import BaseTTSEngine

__all__ = ["PiperEngine"]


class PiperEngine(BaseTTSEngine):
    """Piper TTS adapter."""

    def __init__(self, model_path: str = "", binary: str = "piper") -> None:
        self.model_path = model_path
        self.binary = binary

    def is_available(self) -> bool:
        """True if piper binary is on PATH."""
        return shutil.which(self.binary) is not None

    def synthesize(self, text: str, voice: str = "", emotion: str = "neutral") -> bytes:
        """Synthesize wav bytes. Raises RuntimeError if piper is missing."""
        from app.core.tts.emotions import apply_emotion

        clean, extra = apply_emotion("piper", text)
        if emotion != "neutral" and not extra.get("cli_flags"):
            from app.core.tts.emotions import piper_flags

            extra = {"cli_flags": piper_flags(emotion)}
        model = voice or self.model_path
        if not model or not os.path.isfile(model):
            raise FileNotFoundError(
                "Piper voice model (.onnx) not found. "
                "Download one and pass its path as `voice`."
            )
        if not self.is_available():
            raise RuntimeError(
                "Piper binary not found on PATH. Install piper-tts first."
            )
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out = tmp.name
        try:
            proc = subprocess.run(
                [self.binary, "--model", model, "--output_file", out, *extra.get("cli_flags", [])],
                input=clean.encode("utf-8"),
                capture_output=True,
                timeout=120,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"piper failed: {proc.stderr.decode()[:500]}")
            with open(out, "rb") as fh:
                return fh.read()
        finally:
            try:
                os.unlink(out)
            except OSError:
                pass
