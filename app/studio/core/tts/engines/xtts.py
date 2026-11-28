"""XTTS engine (optional backend).

Needs the `TTS` package (coqui): pip install TTS
Voice cloning from a short reference sample.
"""

from app.core.tts.engines.base import BaseTTSEngine

__all__ = ["XTTSEngine"]


class XTTSEngine(BaseTTSEngine):
    """XTTS v2 adapter (lazy import, GPU recommended)."""

    name = "xtts"

    def __init__(self, model: str = "tts_models/multilingual/multi-dataset/xtts_v2") -> None:
        self.model = model
        self._tts = None

    def is_available(self) -> bool:
        """True if the TTS package is importable."""
        try:
            import TTS  # noqa: F401

            return True
        except ImportError:
            return False

    def _load(self):
        if self._tts is None:
            try:
                from TTS.api import TTS
            except ImportError as exc:
                raise RuntimeError(
                    "XTTS needs the 'TTS' package. Run: pip install TTS"
                ) from exc
            self._tts = TTS(self.model)
        return self._tts

    def synthesize(self, text: str, voice: str = "", language: str = "en",
                   blend: tuple[str, float] | None = None) -> bytes:
        """Synthesize with voice cloning (voice = reference wav path)."""
        import tempfile, os

        tts = self._load()
        if language == 'zh':
            language = 'zh-cn'
        if blend is not None:
            return self._synthesize_blended(tts.synthesizer, text, voice, language, blend)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out = tmp.name
        try:
            kwargs = {"text": text, "file_path": out}
            if voice:
                kwargs["speaker_wav"] = voice
                kwargs["language"] = language
            tts.tts_to_file(**kwargs)
            with open(out, "rb") as fh:
                return fh.read()
        finally:
            try:
                os.unlink(out)
            except OSError:
                pass

    @staticmethod
    def _synthesize_blended(synthesizer, text, voice, language, blend):
        """Blend XTTS conditioning vectors. The weight is not a similarity score."""
        from array import array
        from io import BytesIO
        import sys
        import wave

        base, strength = blend
        if not 0 <= strength <= 1:
            raise ValueError('Сила переноса тембра должна быть от 0 до 1.')
        model = synthesizer.tts_model
        get_latents = getattr(model, 'get_conditioning_latents', None)
        infer = getattr(model, 'inference', None)
        if not callable(get_latents) or not callable(infer):
            raise RuntimeError('Эта версия XTTS не поддерживает смешивание тембра.')
        base_style, base_speaker = get_latents(audio_path=[base])
        style, speaker = get_latents(audio_path=[voice])
        result = infer(
            text, language,
            base_style * (1 - strength) + style * strength,
            base_speaker * (1 - strength) + speaker * strength,
            enable_text_splitting=True,
        )
        pcm = array('h', (round(max(-1.0, min(1.0, sample)) * 32767) for sample in result['wav']))
        if not pcm:
            raise RuntimeError('XTTS вернул пустую запись.')
        if sys.byteorder == 'big':
            pcm.byteswap()
        output = BytesIO()
        with wave.open(output, 'wb') as stream:
            stream.setparams((1, 2, synthesizer.output_sample_rate, 0, 'NONE', 'not compressed'))
            stream.writeframes(pcm.tobytes())
        return output.getvalue()
