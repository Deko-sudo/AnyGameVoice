# SPDX-License-Identifier: Apache-2.0
"""Validate a bounded PCM reference without uploading or copying the recording."""
from hashlib import sha256
from pathlib import Path
from typing import Annotated
import wave

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


def validate_reference(path):
    source = Path(path).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != '.wav':
        raise ValueError('Укажите существующий WAV-образец голоса актёра.')
    if source.stat().st_size > 50 * 1024 ** 2:
        raise ValueError('WAV-образец должен быть меньше 50 МБ.')
    try:
        with wave.open(str(source), 'rb') as wav:
            duration = wav.getnframes() / wav.getframerate()
            if wav.getcomptype() != 'NONE' or wav.getsampwidth() not in {1, 2, 3, 4}:
                raise ValueError('Для образца нужен несжатый PCM WAV.')
            if not 6 <= duration <= 120:
                raise ValueError('Нужен образец длительностью от 6 до 120 секунд.')
            if wav.getnchannels() not in {1, 2} or wav.getframerate() < 16000:
                raise ValueError('Нужен моно/стерео WAV с частотой не ниже 16 кГц.')
            expected = wav.getnframes() * wav.getnchannels() * wav.getsampwidth()
            if len(wav.readframes(wav.getnframes())) != expected:
                raise ValueError('WAV-образец обрезан или повреждён.')
            return {'path': str(source), 'duration': round(duration, 2), 'sample_rate': wav.getframerate(),
                    'channels': wav.getnchannels(), 'note': 'Формат проверен. Чистоту речи и сходство оценивайте прослушиванием.'}
    except (wave.Error, EOFError, ZeroDivisionError) as exc:
        raise ValueError('Не удалось прочитать PCM WAV-образец.') from exc


class VoiceBlend(BaseModel):
    """Set the reference weight for WAVs marked as originating from a Russian dub."""

    model_config = ConfigDict(extra='forbid')
    strength: float = Field(default=0.95, ge=0, le=1, strict=True)
    base_voice: str = Field(default='', max_length=4096)
    protected_voices: list[Annotated[str, StringConstraints(min_length=1, max_length=4096)]] = Field(
        default_factory=list, max_length=200
    )

    def for_voice(self, engine: str, voice: str) -> tuple[str, float] | None:
        if not self.protected_voices or not voice:
            return None
        chosen = Path(voice).expanduser().resolve()
        if not any(chosen == Path(path).expanduser().resolve() for path in self.protected_voices):
            return None
        if engine != 'xtts':
            raise ValueError('Для переноса тембра с ограничением выберите XTTS.')
        if self.strength == 1:
            return None
        if not self.base_voice.strip():
            raise ValueError('В «Настройки JSON» укажите base_voice — WAV с другим голосом для смешивания.')
        source = Path(validate_reference(voice)['path'])
        base = Path(validate_reference(self.base_voice)['path'])
        if source == base or (source.stat().st_size == base.stat().st_size
                              and sha256(source.read_bytes()).digest() == sha256(base.read_bytes()).digest()):
            raise ValueError('Для смешивания нужен WAV с другим голосом.')
        return str(base), self.strength
