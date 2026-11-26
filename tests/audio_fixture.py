"""Small valid WAV data for exercising audio contracts without a TTS model."""

import io
import struct
import wave


def wav_bytes(value=100, frames=800, rate=8000):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(struct.pack('<h', value) * frames)
    return buffer.getvalue()
