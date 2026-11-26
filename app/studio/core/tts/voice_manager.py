"""Discover local voice models and copy complete Piper model pairs."""

import json
from pathlib import Path
import shutil

from app.studio.models.voice import Voice
from app.utils.paths import preset_dir, project_root, user_home, user_voices_dir

PRESET_DIR = preset_dir()
USER_DIR = user_voices_dir()
VALID_SUFFIXES = {'.onnx', '.wav', '.pt', '.pth', '.ckpt'}
__all__ = ['VoiceManager', 'PRESET_DIR', 'USER_DIR']


class VoiceManager:
    """Manage models in the bundled, project and user model directories."""

    def __init__(self, user_dir: str | Path | None = None) -> None:
        self.user_dir = Path(user_dir) if user_dir is not None else user_voices_dir()

    def list_voices(self) -> list:
        voices = []
        seen = set()
        for directory in (PRESET_DIR, project_root() / 'models', user_home() / 'models', self.user_dir):
            if not directory.is_dir():
                continue
            for fp in sorted(directory.iterdir()):
                if not fp.is_file() or fp.suffix.lower() not in VALID_SUFFIXES or fp.resolve() in seen:
                    continue
                seen.add(fp.resolve())
                language = ''
                if fp.suffix == '.onnx':
                    try:
                        config = json.loads(Path(str(fp) + '.json').read_text())
                        language = config.get('language', {}).get('code', '')
                    except (OSError, ValueError, AttributeError):
                        pass
                voices.append(Voice(name=fp.stem, path=str(fp.resolve()),
                                    engine='piper' if fp.suffix == '.onnx' else 'xtts' if fp.suffix == '.wav' else 'silero',
                                    language=language))
        return voices

    def add_voice(self, src: str, name: str = '') -> Voice:
        """Copy a sample or a complete Piper pair; never overwrite an existing voice."""
        source = Path(src)
        if not source.is_file():
            raise FileNotFoundError(f'Voice sample not found: {src}')
        filename = name or source.name
        if filename != Path(filename).name or filename in {'.', '..'}:
            raise ValueError('Voice name must be a filename.')
        dest = self.user_dir / filename
        if dest.suffix.lower() not in VALID_SUFFIXES:
            raise ValueError(f'Unsupported voice format: {dest.suffix}')
        pairs = [(source, dest)]
        if source.suffix.lower() == '.onnx':
            config = Path(str(source) + '.json')
            if not config.is_file():
                raise ValueError('Include the matching .onnx.json file beside the model.')
            pairs.append((config, Path(str(dest) + '.json')))
        self.user_dir.mkdir(parents=True, exist_ok=True)
        created = []
        try:
            for origin, target in pairs:
                with target.open('xb') as out, origin.open('rb') as inp:
                    created.append(target)
                    shutil.copyfileobj(inp, out)
        except Exception:
            for target in created:
                target.unlink(missing_ok=True)
            raise
        return Voice(name=dest.stem, path=str(dest), engine='piper' if dest.suffix == '.onnx' else 'xtts')

    def remove_voice(self, name: str) -> bool:
        """Delete an explicitly selected user voice and its configuration."""
        if not self.user_dir.is_dir():
            return False
        for fp in self.user_dir.iterdir():
            if fp.is_file() and fp.suffix in VALID_SUFFIXES and fp.stem == name:
                fp.unlink()
                if fp.suffix == '.onnx':
                    Path(str(fp) + '.json').unlink(missing_ok=True)
                return True
        return False
