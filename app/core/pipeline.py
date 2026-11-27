"""Batch synthesis with verified output, progress and a resumable manifest."""

from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
import wave

from app.studio.core.extractor.dialogue_extractor import extract_dialogue
from app.studio.core.game_detector.detector import detect_engine
from app.studio.core.tts import generator
from app.core.tts.reference import VoiceBlend
from app.utils.atomic import atomic_json
from app.utils.audio_utils import to_srt


def wav_duration(path: str | Path) -> float:
    """Require nonempty readable PCM audio and return its real duration."""
    try:
        with wave.open(str(path), 'rb') as audio:
            frames = audio.getnframes()
            if frames <= 0 or len(audio.readframes(frames)) < frames * audio.getnchannels() * audio.getsampwidth():
                raise ValueError('Synthesis returned empty or truncated WAV audio.')
            return frames / audio.getframerate()
    except (wave.Error, EOFError) as exc:
        raise ValueError('Synthesis did not return valid PCM WAV audio.') from exc


def _digest(path: Path) -> str:
    with path.open('rb') as fh:
        return hashlib.file_digest(fh, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(fh.read()).hexdigest()


def _key(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _check_owned_output(path: Path, expected_hash: str | None) -> None:
    """Never replace a symlink, unknown file, or modified previous output."""
    if path.is_symlink():
        raise ValueError(f'Output conflict: symbolic link at {path.name}. Choose another output folder.')
    if not path.exists():
        return
    if not path.is_file() or not expected_hash or _digest(path) != expected_hash:
        raise ValueError(f'Output conflict: {path.name} is not an unchanged application output. Choose another output folder.')


def _publish_owned(temporary: str, destination: Path, expected_hash: str | None) -> None:
    _check_owned_output(destination, expected_hash)
    if destination.exists():
        os.replace(temporary, destination)
    else:
        # Unlike replace(), link() fails if another file appears at this path.
        os.link(temporary, destination)
        os.unlink(temporary)


def run_batch(folder: str, out: str, voice: str = '', engine: str = 'piper', workers: int = 2,
              emotion: str = 'neutral', translate_to: str = '', provider: str = 'ollama',
              language: str = 'en', character_voices: dict | None = None,
              on_progress=None, cancel_event=None, voice_blend=None, source_lang='auto',
              translation_model='', base_url='', api_key='', trial=False) -> dict:
    """Export audio only. This does not install anything into a game."""
    game = Path(folder).expanduser().resolve()
    output = Path(out).expanduser().resolve()
    if not game.is_dir():
        raise ValueError('Game folder does not exist.')
    if output == game or game in output.parents:
        raise ValueError('Choose an output folder outside the game folder.')
    if not 1 <= workers <= 4:
        raise ValueError('workers must be between 1 and 4.')
    lines = extract_dialogue(str(game))
    if not lines:
        raise ValueError(f'No supported dialogue found (engine: {detect_engine(str(game))}).')
    if len(lines) > 10000:
        raise ValueError('This preview release supports up to 10,000 dialogue lines per project.')
    trial_dir = output / '.agv-trial'
    if trial_dir.is_symlink():
        raise ValueError('Каталог пробного дубляжа не может быть символической ссылкой.')
    if trial:
        lines = lines[:3]
        output = trial_dir
    voices = character_voices or {}
    policy = VoiceBlend.model_validate(voice_blend) if voice_blend is not None else VoiceBlend()
    blends = {}
    for selected in {voices.get(line.speaker) or voice for line in lines}:
        generator.validate_synthesis(engine, selected)
        if translate_to and engine == 'piper' and Path(str(selected) + '.json').is_file():
            config = json.loads(Path(str(selected) + '.json').read_text(encoding='utf-8'))
            voice_lang = config.get('language', {}).get('code', '').replace('-', '_').split('_')[0]
            if voice_lang and voice_lang != translate_to.split('-')[0]:
                raise ValueError(f'Язык голоса Piper ({voice_lang}) отличается от языка перевода ({translate_to}). Выберите подходящий голос.')
        blends[selected] = policy.for_voice(engine, selected)
    translation = [1, source_lang, translate_to, provider, translation_model, base_url] if translate_to else None
    if translate_to:
        language = translate_to
    cancelled = cancel_event or threading.Event()
    output.mkdir(parents=True, exist_ok=True)
    lock = output / '.anygamevoice.lock'
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError('Output folder is in use. After a crash, remove .anygamevoice.lock before retrying.') from exc
    os.close(lock_fd)
    manifest = output / 'anygamevoice.json'
    try:
        old = {}
        if manifest.is_symlink():
            raise ValueError('Output conflict: the project manifest is a symbolic link.')
        if manifest.exists():
            old = json.loads(manifest.read_text(encoding='utf-8'))
            if old.get('schema') != 1 or old.get('game_path') != str(game):
                raise ValueError('Output folder contains a different project. Choose another folder.')
        previous = {item['id']: item for item in old.get('lines', [])}
        trial_rows = {}
        trial_manifest = trial_dir / 'anygamevoice.json'
        if not trial and trial_manifest.is_file() and not trial_manifest.is_symlink():
            sample = json.loads(trial_manifest.read_text(encoding='utf-8'))
            if sample.get('schema') == 1 and sample.get('game_path') == str(game):
                trial_rows = {row['id']: row for row in sample.get('lines', [])}
        owned_audio = dict(old.get('owned_audio_sha256', {}))
        for item in old.get('lines', []):
            if item.get('sha256'):
                owned_audio[item['id']] = item['sha256']
        for ident, pending_hash in old.get('pending_audio_sha256', {}).items():
            # IDs are generated by this pipeline, never accept paths from a manifest.
            if not isinstance(ident, str) or not re.fullmatch(r'[0-9a-f]{20}', ident):
                raise ValueError('Invalid pending audio identifier in project manifest.')
            path = output / f'{ident}.wav'
            if path.is_file() and not path.is_symlink() and _digest(path) == pending_hash:
                owned_audio[ident] = pending_hash
        counts = Counter()
        items = []
        for index, line in enumerate(lines):
            identity = [line.source_file, line.speaker, line.metadata.get('original_text', line.text)]
            occurrence = counts[tuple(identity)]
            counts[tuple(identity)] += 1
            line_id = _key([*identity, occurrence])[:20]
            if translation:
                if cancelled.is_set():
                    raise RuntimeError('Перевод отменён.')
                origin = line.text
                cached = next((r for r in (previous.get(line_id), trial_rows.get(line_id))
                               if r and r.get('translation') == translation
                               and r.get('metadata', {}).get('original_text') == origin and r.get('text')), None)
                if cached:
                    line = replace(line, text=cached['text'], metadata={**line.metadata,
                                   'original_text': origin, 'translated_to': translate_to})
                else:
                    from app.studio.core.translate import translate_lines
                    try:
                        line = translate_lines([line], translate_to, source_lang, provider, api_key,
                                               translation_model, base_url)[0]
                    except Exception:
                        raise RuntimeError(f'Перевод реплики {index + 1} не получен. Проверьте модель, доступ и лимит провайдера.') from None
                lines[index] = line
            selected_voice = voices.get(line.speaker) or voice
            model = Path(selected_voice).expanduser()
            model_state = []
            for fp in (model, Path(str(model) + '.json')):
                if fp.is_file():
                    model_state.append([str(fp.resolve()), fp.stat().st_size, fp.stat().st_mtime_ns])
            recipe = [line.text, selected_voice, model_state, engine, emotion, language]
            if translation:
                recipe.append(translation)
            blend = blends[selected_voice]
            if blend is not None:
                base_path, strength = blend
                stat = Path(base_path).stat()
                recipe.append(['xtts-blend-v1', base_path, strength, stat.st_size, stat.st_mtime_ns])
            fingerprint = _key(recipe)
            items.append({**asdict(line), 'translation': translation, 'id': line_id, 'voice': selected_voice,
                          'filename': f'{line_id}.wav', 'fingerprint': fingerprint,
                          'status': 'pending', 'error': '', 'duration': 0.0})
        result = {'schema': 1, 'game_path': str(game), 'out': str(output),
                  'engine': engine, 'voice': voice, 'character_voices': voices,
                  'emotion': emotion, 'language': language, 'status': 'running',
                  'trial': trial, 'total': len(items), 'succeeded': 0, 'failed': 0, 'cached': 0,
                  'cancelled': 0, 'lines': items, 'owned_audio_sha256': owned_audio,
                  'pending_audio_sha256': {}}

        if policy.protected_voices:
            result['voice_blend'] = policy.model_dump()

        subtitle = output / 'dialogue.srt'
        subtitle_hash = old.get('subtitle_sha256')
        pending_subtitle_hash = old.get('subtitle_pending_sha256')
        if subtitle.is_file() and not subtitle.is_symlink() and pending_subtitle_hash:
            if _digest(subtitle) == pending_subtitle_hash:
                subtitle_hash = pending_subtitle_hash
        if subtitle.exists() and not subtitle_hash and not subtitle.is_symlink():
            raise ValueError('Output conflict: dialogue.srt has no recorded ownership hash (including older projects). Choose a new output folder or move the existing subtitles elsewhere before retrying.')
        _check_owned_output(subtitle, subtitle_hash)
        for item in items:
            _check_owned_output(output / item['filename'], owned_audio.get(item['id']))
        if subtitle_hash:
            result['subtitle_sha256'] = subtitle_hash

        manifest_lock = threading.RLock()
        def publish():
            with manifest_lock:
                result.update(succeeded=sum(i['status'] == 'done' for i in items),
                              failed=sum(i['status'] == 'failed' for i in items),
                              cached=sum(bool(i.get('cached')) for i in items),
                              cancelled=sum(i['status'] == 'cancelled' for i in items))
                atomic_json(manifest, result)
                if on_progress:
                    on_progress({k: v for k, v in result.items() if k != 'lines'})

        def synthesize(item):
            fd, temporary = tempfile.mkstemp(suffix='.wav', prefix='.agv-', dir=output)
            os.close(fd)
            try:
                blend = blends[item['voice']]
                options = {'blend': blend} if blend is not None else {}
                sample = trial_rows.get(item['id'], {})
                sample_file = trial_dir / item['filename']
                reuse = (sample.get('status') == 'done' and sample.get('fingerprint') == item['fingerprint']
                         and sample_file.is_file() and not sample_file.is_symlink())
                if reuse:
                    shutil.copyfile(sample_file, temporary)
                    reuse = _digest(Path(temporary)) == sample.get('sha256')
                if not reuse:
                    generator.generate_voice_to_file(item['text'], temporary, voice=item['voice'], engine=engine,
                                                     emotion=emotion, language=language, **options)
                duration = wav_duration(temporary)
                destination = output / item['filename']
                with manifest_lock:
                    result['pending_audio_sha256'][item['id']] = _digest(Path(temporary))
                    publish()
                _publish_owned(temporary, destination, owned_audio.get(item['id']))
                return {'status': 'done', 'cached': reuse, 'duration': duration, 'sha256': _digest(destination)}
            finally:
                Path(temporary).unlink(missing_ok=True)

        pending = []
        for item in items:
            prev = previous.get(item['id'], {})
            audio = output / item['filename']
            if prev.get('status') == 'done' and prev.get('fingerprint') == item['fingerprint'] and audio.is_file():
                try:
                    duration = wav_duration(audio)
                    if _digest(audio) == prev.get('sha256'):
                        item.update(status='done', duration=duration, sha256=prev['sha256'], cached=True)
                        continue
                except (OSError, ValueError):
                    pass
            pending.append(item)
        publish()
        # Submit only a bounded number of tasks; cancellation does not start queued work.
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='agv-tts') as pool:
            active = {}
            next_index = 0
            while next_index < len(pending) or active:
                while not cancelled.is_set() and len(active) < workers and next_index < len(pending):
                    item = pending[next_index]
                    next_index += 1
                    with manifest_lock:
                        item['status'] = 'running'
                    active[pool.submit(synthesize, item)] = item
                if cancelled.is_set():
                    with manifest_lock:
                        for item in pending[next_index:]:
                            item['status'] = 'cancelled'
                    next_index = len(pending)
                if not active:
                    break
                completed, _ = wait(active, timeout=0.2, return_when=FIRST_COMPLETED)
                for future in completed:
                    item = active.pop(future)
                    with manifest_lock:
                        try:
                            item.update(future.result())
                            owned_audio[item['id']] = item['sha256']
                            result['pending_audio_sha256'].pop(item['id'], None)
                        except Exception as exc:
                            item.update(status='failed', error=str(exc)[:500])
                if completed:
                    publish()
        succeeded = sum(i['status'] == 'done' for i in items)
        result['status'] = ('cancelled' if cancelled.is_set() else 'done' if succeeded == len(items)
                            else 'partial' if succeeded else 'failed')
        publish()
        # These are planning subtitles; actual per-line durations are in the manifest.
        fd, temporary = tempfile.mkstemp(prefix='.agv-subtitles-', dir=output)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                fh.write(to_srt([line for line, item in zip(lines, items) if item['status'] == 'done']))
            # Record the staged hash first: after an interrupted replacement the
            # next run can recognise either the old or the newly written file.
            result['subtitle_pending_sha256'] = _digest(Path(temporary))
            publish()
            _publish_owned(temporary, subtitle, subtitle_hash)
            result['subtitle_sha256'] = _digest(subtitle)
            result.pop('subtitle_pending_sha256', None)
            publish()
        finally:
            Path(temporary).unlink(missing_ok=True)
        return result
    finally:
        lock.unlink(missing_ok=True)
