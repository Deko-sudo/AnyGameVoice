"""Lost Coast: verified caption/soundscript mapping and reversible Source override.

Reads the installed game's own VPKs; never edits Valve archives or gameinfo.
VPK v1/v2 layout: ValvePython/vpk (format reference, independently implemented).
"""
from pathlib import Path, PurePosixPath
import hashlib
import json
import re
import shutil
import struct
import subprocess
import tempfile
import uuid
import wave
import zlib

from app.models.dialogue import Dialogue
from app.utils.atomic import atomic_json

MOD_NAME = 'zz_anygamevoice'


def safe_relative(value):
    value = value.replace('\\', '/')
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(p in {'.', '..'} or ':' in p for p in value.split('/')):
        raise ValueError('Unsafe Source resource path.')
    return path.as_posix()


class VPK:
    """Bounded, read-only VPK index with CRC validation of every requested file."""
    def __init__(self, path):
        self.path = Path(path)
        self.entries = {}
        with self.path.open('rb') as stream:
            header = stream.read(12)
            if len(header) != 12:
                raise ValueError('Truncated VPK header.')
            magic, version, size = struct.unpack('<III', header)
            if magic != 0x55AA1234 or version not in {1, 2} or size > 64 * 1024 ** 2:
                raise ValueError('Unsupported VPK header.')
            self.header = 28 if version == 2 else 12
            stream.seek(self.header)
            tree = stream.read(size)
        if len(tree) != size:
            raise ValueError('Truncated VPK index.')
        self.data_offset = self.header + size
        cursor = 0

        def string():
            nonlocal cursor
            end = tree.find(b'\0', cursor)
            if end < 0:
                raise ValueError('Invalid VPK string.')
            text = tree[cursor:end].decode('utf-8')
            cursor = end + 1
            return text

        while extension := string():
            while directory := string():
                while name := string():
                    if cursor + 18 > len(tree) or len(self.entries) >= 100000:
                        raise ValueError('Invalid VPK entry.')
                    crc, preload, archive, offset, length, terminator = struct.unpack_from('<IHHIIH', tree, cursor)
                    cursor += 18
                    if terminator != 65535 or cursor + preload > len(tree):
                        raise ValueError('Invalid VPK entry terminator.')
                    filename = name + ('.' + extension if extension != ' ' else '')
                    key = safe_relative((directory + '/' if directory != ' ' else '') + filename)
                    if key in self.entries:
                        raise ValueError('Duplicate VPK entry.')
                    self.entries[key] = (crc, archive, offset, length, tree[cursor:cursor + preload])
                    cursor += preload

    def read(self, key, limit=32 * 1024 ** 2):
        crc, archive, offset, length, preload = self.entries[safe_relative(key)]
        if length + len(preload) > limit:
            raise ValueError('Source resource exceeds the supported size.')
        if archive == 0x7FFF:
            origin = self.path
            offset += self.data_offset
        else:
            if not self.path.name.endswith('_dir.vpk'):
                raise ValueError('Expected a VPK directory archive.')
            origin = self.path.with_name(self.path.name[:-8] + f'_{archive:03d}.vpk')
        if length:
            with origin.open('rb') as stream:
                stream.seek(offset)
                payload = stream.read(length)
            if len(payload) != length:
                raise ValueError('Truncated VPK resource.')
        else:
            payload = b''
        data = preload + payload
        if zlib.crc32(data) & 0xFFFFFFFF != crc:
            raise ValueError('VPK resource checksum does not match.')
        return data


def keyvalues(text):
    """Parse Valve KeyValues while preserving duplicate keys and path backslashes."""
    tokens = []
    for match in re.finditer(r'//[^\n]*|"((?:\\.|[^"\\])*)"|([{}])|([^\s{}"]+)', text):
        if match.group(0).startswith('//'):
            continue
        quoted, brace, bare = match.groups()
        tokens.append((re.sub(r'\\(["\\])', r'\1', quoted) if quoted is not None else brace or bare, quoted is not None))
    cursor = 0

    def pairs(depth=0):
        nonlocal cursor
        if depth > 32:
            raise ValueError('KeyValues nesting is too deep.')
        result = []
        while cursor < len(tokens):
            key, quoted = tokens[cursor]
            cursor += 1
            if key == '}' and not quoted:
                if not depth:
                    raise ValueError('Unexpected KeyValues brace.')
                return result
            if cursor == len(tokens):
                raise ValueError('Missing KeyValues value.')
            value, quoted = tokens[cursor]
            cursor += 1
            if value == '{' and not quoted:
                value = pairs(depth + 1)
            result.append((key, value))
        if depth:
            raise ValueError('Missing KeyValues closing brace.')
        return result

    return pairs()


def game_root(path):
    root = Path(path).expanduser().resolve()
    return root / 'lostcoast' if (root / 'lostcoast/lostcoast_pak_dir.vpk').is_file() else root


def extract_lostcoast(path):
    root = game_root(path)
    archive = VPK(root / 'lostcoast_pak_dir.vpk')
    scripts = keyvalues(archive.read('scripts/level_voices_lostcoast.txt').decode('utf-8-sig'))
    caption = root / 'resource/closecaption_russian.txt'
    if not caption.is_file():
        caption = root / 'resource/closecaption_english.txt'
    raw = caption.read_bytes()
    decoded = raw.decode('utf-16') if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else raw.decode('utf-8-sig')
    lang = dict(keyvalues(decoded)).get('lang', [])
    tokens = {key.casefold(): value for key, value in dict(lang).get('Tokens', []) if isinstance(value, str)}
    lines = []
    for token, values in scripts:
        if not isinstance(values, list):
            continue
        values = dict(values)
        text = tokens.get(token.casefold(), '')
        text = re.sub(r'<[^>]*>', '', text).strip()
        # Effects, coughs and caption-only entries must keep their original sound.
        if not text or re.fullmatch(r'\s*\[[^\]]*\]\s*', text) or values.get('channel') != 'CHAN_VOICE':
            continue
        wave_path = values.get('wave')
        if not isinstance(wave_path, str):
            continue
        wave_path = safe_relative(wave_path.lstrip('*#@><^)}$!?'))
        if not wave_path.lower().endswith('.wav') or not wave_path.startswith('lostcoast/vo/'):
            continue
        lines.append(Dialogue(speaker='Рыбак', text=text, source_file=caption.relative_to(root).as_posix(),
                              engine='source_lostcoast', metadata={'sound_token': token, 'sound_path': wave_path}))
    return lines


def install_mod(result, cancel_event=None):
    """Install a complete verified batch as one isolated, reversible custom mod."""
    root = game_root(result['game_path'])
    gameinfo = (root / 'gameinfo.txt').read_text()
    from app.utils.runtime import ffmpeg_command
    ffmpeg = ffmpeg_command()
    if 'lostcoast/custom/*' not in gameinfo or not ffmpeg:
        raise ValueError('Для установки Lost Coast нужны custom в gameinfo и установленный FFmpeg.')
    expected = {line.metadata['sound_token']: line for line in extract_lostcoast(root)}
    if result['status'] != 'done' or len(result['lines']) != len(expected):
        raise ValueError('Устанавливается только полностью готовая озвучка.')
    output = Path(result['out']).resolve()
    custom = root / 'custom'
    if custom.is_symlink():
        raise ValueError('Папка custom не должна быть символической ссылкой.')
    target = custom / MOD_NAME
    if target.exists():
        check_owned(target, root)
    voice_archive = next((VPK(root / f'lostcoast_sound_vo_{language}_dir.vpk') for language in ('russian', 'english')
                          if (root / f'lostcoast_sound_vo_{language}_dir.vpk').is_file()), None)
    if voice_archive is None:
        raise ValueError('Не найден исходный звуковой архив Lost Coast.')
    with tempfile.TemporaryDirectory(prefix='.agv-stage-', dir=root) as temporary:
        stage = Path(temporary) / MOD_NAME
        stage.mkdir()
        installed = []
        seen = set()
        for item in result['lines']:
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError('Установка остановлена. Игра не изменена.')
            token = item.get('metadata', {}).get('sound_token')
            line = expected.get(token)
            if token in seen or not line or item['text'] != line.text or item.get('status') != 'done':
                raise ValueError('Сценарии изменились. Создайте озвучку повторно.')
            seen.add(token)
            filename = safe_relative(item['filename'])
            source = (output / filename).resolve()
            if source.parent != output or hashlib.sha256(source.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('Файл озвучки изменён. Создайте озвучку повторно.')
            relative = 'sound/' + line.metadata['sound_path']
            raw = voice_archive.read(relative)
            reference = Path(temporary) / 'reference.wav'
            reference.write_bytes(raw)
            with wave.open(str(reference), 'rb') as audio:
                rate, channels, frames = audio.getframerate(), audio.getnchannels(), audio.getnframes()
                duration = frames / rate
            with wave.open(str(source), 'rb') as audio:
                generated_duration = audio.getnframes() / audio.getframerate()
            if not duration or not generated_duration:
                raise ValueError('Пустая звуковая реплика.')
            ratio = max(1.0, generated_duration / duration)
            filters = []
            while ratio > 2:
                filters.append('atempo=2')
                ratio /= 2
            filters.extend([f'atempo={ratio:.8f}', 'apad'])
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            proc = subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-y', '-i', str(source), '-af', ','.join(filters),
                                   '-t', str(duration), '-ar', str(rate), '-ac', str(channels), '-c:a', 'pcm_s16le', str(destination)],
                                  capture_output=True, timeout=120)
            if proc.returncode:
                raise RuntimeError('Не удалось подготовить WAV для Source: ' + proc.stderr.decode(errors='replace')[:300])
            with wave.open(str(destination), 'rb') as audio:
                if audio.getsampwidth() != 2 or audio.getframerate() != rate or audio.getnchannels() != channels or abs(audio.getnframes() - frames) > 2:
                    raise ValueError('Не удалось сохранить длительность и формат исходного звука.')
            installed.append({'path': relative, 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()})
        ownership = {'schema': 'anygamevoice-source-mod', 'game_path': str(root), 'files': installed}
        atomic_json(stage / 'anygamevoice-mod.json', ownership)
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError('Установка остановлена. Игра не изменена.')
        custom.mkdir(exist_ok=True)
        backup = None
        if target.exists():
            check_owned(target, root)
            backups = root / '.anygamevoice-backups'
            backups.mkdir(exist_ok=True)
            if backups.is_symlink():
                raise ValueError('Папка резервных копий не должна быть ссылкой.')
            backup = backups / uuid.uuid4().hex
            target.rename(backup)
        try:
            stage.rename(target)
        except Exception:
            if backup:
                backup.rename(target)
            raise
    return {'status': 'installed', 'path': str(target), 'files': len(installed), 'engine': 'source_lostcoast',
            'note': 'Мод установлен. Перезапустите Lost Coast. Синхронизацию губ и звучание проверьте в игре.'}


def check_owned(target, root):
    if target.is_symlink():
        raise ValueError('Папка мода не должна быть ссылкой.')
    try:
        data = json.loads((target / 'anygamevoice-mod.json').read_text())
    except (OSError, ValueError) as exc:
        raise ValueError('В папке мода есть сторонние файлы. Выберите другое место установки.') from exc
    if data.get('schema') != 'anygamevoice-source-mod' or data.get('game_path') != str(root):
        raise ValueError('Папка мода принадлежит другому проекту.')
    for item in data['files']:
        path = target / safe_relative(item['path'])
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Установленный мод изменён вручную. Сохраните изменения перед повторной установкой.')
    if any(p.is_symlink() for p in target.rglob('*')):
        raise ValueError('В папке мода обнаружена символическая ссылка.')
    actual = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
    if actual != {item['path'] for item in data['files']} | {'anygamevoice-mod.json'}:
        raise ValueError('В папке мода появились сторонние файлы.')


def disable_mod(result):
    root = game_root(result['game_path'])
    target = root / 'custom' / MOD_NAME
    check_owned(target, root)
    backups = root / '.anygamevoice-backups'
    if backups.is_symlink():
        raise ValueError('Папка резервных копий не должна быть ссылкой.')
    backups.mkdir(exist_ok=True)
    destination = backups / ('disabled-' + uuid.uuid4().hex)
    target.rename(destination)
    return {'status': 'disabled', 'path': str(destination), 'note': 'Мод отключён. Перезапустите игру, чтобы вернуть исходную озвучку.'}
