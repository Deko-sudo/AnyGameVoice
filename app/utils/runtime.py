"""Locate app-managed command environments without changing the process PATH."""
import json
from pathlib import Path
import re
import shutil
import sys

from app.utils.paths import user_home


def managed_runtime():
    base = user_home() / 'runtime'
    try:
        data = json.loads((base / 'active.json').read_text())
        version = data['version']
        if not re.fullmatch(r'[a-f0-9]{32}', version):
            return None
        root = (base / 'versions' / version).resolve()
        root.relative_to((base / 'versions').resolve())
        python = root / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
        if not python.is_file():
            return None
        return {'root': root, 'python': python, 'packages': data.get('packages', [])}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def external_piper_command():
    sibling = Path(sys.executable).with_name('piper.exe' if sys.platform == 'win32' else 'piper')
    binary = str(sibling) if sibling.is_file() else shutil.which('piper')
    return [binary] if binary else []


def piper_command():
    runtime = managed_runtime()
    if runtime and 'piper-tts' in runtime['packages']:
        return [str(runtime['python']), '-m', 'piper']
    return external_piper_command()


def ffmpeg_command():
    binary = shutil.which('ffmpeg')
    if binary:
        return binary
    runtime = managed_runtime()
    if runtime and 'imageio-ffmpeg' in runtime['packages']:
        matches = sorted(runtime['root'].glob('**/imageio_ffmpeg/binaries/ffmpeg*'))
        return next((str(path) for path in matches if path.is_file() and not path.name.endswith('.py')), None)
    return None
