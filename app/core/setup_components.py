"""Explicit, cancellable installation of pinned components in application data.

Sources: PyPI piper-tts 1.8.0 / imageio-ffmpeg 0.6.0; pinned Piper voice
repository revision; Ren'Py's published 8.5.3 SHA-256 checksums.
No system packages, PATH changes, or arbitrary download URLs are accepted.
"""
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import uuid

from app.utils.atomic import atomic_copy, atomic_json
from app.utils.paths import user_home

VOICE_REV = 'cf910fb59f1d79ab3b625a63993a108751c6c25d'
VOICE_BASE = f'https://huggingface.co/rhasspy/piper-voices/resolve/{VOICE_REV}'
VOICES = {
    'ru': {'id': 'ru_RU-denis-medium', 'folder': 'ru/ru_RU/denis/medium', 'name': 'Денис · русский',
           'license': 'CC0 (модель и датасет)', 'size': 63221984,
           'hash': '879bc365cb14d1380e3f5ed6044162ccf54c99f6161871569b7f830aec3ce841',
           'config_size': 5464, 'config_hash': 'e4fb4ab60262d1ab802c8c39301976c4135e545bc834a33c6eedc1f764df3bd6',
           'card_size': 418, 'card_hash': '917110d5056810771fd3daea2644bbadf1341816b7631f2043b33be245903432'},
    'en': {'id': 'en_US-ljspeech-medium', 'folder': 'en/en_US/ljspeech/medium', 'name': 'LJ Speech · английский',
           'license': 'Public domain (датасет); условия модели — MODEL_CARD', 'size': 63531379,
           'hash': '6f52a751e2349abe7a76735eb09dc1875298c77ea2342ffd2fef79ff81b87f22',
           'config_size': 4972, 'config_hash': '141d612cc0a95ed7efc1ca936b845c2364967f2e9217c5dbfcf69fc4d6c65860',
           'card_size': 517, 'card_hash': 'fbee1529c89d36b3fe76d7e9f3f832dce17f44900a52d76a9bda735654766b4d'},
}
SDK = {
    'x86_64': {'name': 'renpy-8.5.3-sdk.tar.bz2', 'size': 153611590,
               'hash': 'eb0a9be7f0fb13632fe25ceade9a8bed5a1b4d6b6e83bd19eeeb29e1a1bb4a45'},
    'aarch64': {'name': 'renpy-8.5.3-sdkarm.tar.bz2', 'size': 166255505,
               'hash': '0579782517f203ba3535dcc2dab54e34bfc318f2f2a7510a5130b6f809f901f6'},
}
PACKAGES = {'piper': 'piper-tts==1.8.0', 'ffmpeg': 'imageio-ffmpeg==0.6.0'}
_LOCK = threading.Lock()
_TASKS_LOCK = threading.Lock()
_TASKS = {}


def is_busy():
    return _LOCK.locked()


def voice_for(language):
    from app.studio.core.tts.voice_manager import VoiceManager
    for voice in VoiceManager().list_voices():
        if voice.engine != 'piper' or voice.language.replace('_', '-').split('-')[0].lower() != language:
            continue
        try:
            config = json.loads(Path(voice.path + '.json').read_text())
            if Path(voice.path).stat().st_size > 0 and config['audio']['sample_rate'] > 0:
                return voice.path
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def sdk_asset():
    machine = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(platform.machine().lower(), platform.machine().lower())
    return SDK.get(machine) if sys.platform.startswith('linux') else None


def setup_plan(language='ru', engine='renpy', sdk=''):
    from app.core.installation import discover_renpy_sdk
    from app.studio.core.tts.engines.piper import PiperEngine
    from app.utils.runtime import ffmpeg_command
    try:
        detected_sdk = str(discover_renpy_sdk(sdk or None)) if engine == 'renpy' else ''
    except ValueError:
        detected_sdk = ''
    voice = voice_for(language)
    catalog = VOICES.get(language)
    components = [dict(id='piper', name='Piper 1.8 · синтез речи', needed=not PiperEngine().is_available(),
                       download_bytes=180 * 1024**2, estimated=True, license='GPL-3.0-or-later',
                       source='https://pypi.org/project/piper-tts/1.8.0/',
                       note='Изолированное окружение. Размер зависит от платформы и зависимостей.')]
    if catalog:
        components.append(dict(id='voice', name=catalog['name'], needed=not bool(voice),
                               download_bytes=catalog['size'] + catalog['config_size'] + catalog['card_size'], estimated=False,
                               license=catalog['license'], source=f'https://huggingface.co/rhasspy/piper-voices/blob/{VOICE_REV}/{catalog["folder"]}/MODEL_CARD',
                               note='Проверяются размер и SHA-256 модели, настроек и карточки.'))
    if engine == 'renpy':
        asset = sdk_asset()
        components.append(dict(id='sdk', name='Ren’Py SDK 8.5.3', needed=not bool(detected_sdk),
                               download_bytes=asset['size'] if asset else 0, estimated=False,
                               license='MIT и лицензии включённых библиотек', source='https://www.renpy.org/doc/html/license.html',
                               note='Изолированная копия SDK в данных приложения.'))
    if engine == 'source_lostcoast':
        components.append(dict(id='ffmpeg', name='FFmpeg · подготовка звука', needed=not bool(ffmpeg_command()),
                               download_bytes=35 * 1024**2, estimated=True, license='Лицензия включённого FFmpeg — package binaries / LICENSE',
                               source='https://pypi.org/project/imageio-ffmpeg/0.6.0/', note='Загружается отдельный бинарный пакет из PyPI.'))
    reason = ''
    if not catalog and not voice:
        reason = 'Автозагрузка голоса пока поддерживается для русского и английского. Укажите другую модель вручную.'
    if engine == 'renpy' and not detected_sdk and not sdk_asset():
        reason = 'Автозагрузка SDK поддерживается на Linux x86-64/ARM64. На этой платформе выберите установленный SDK вручную.'
    missing = [c for c in components if c['needed']]
    return dict(language=language, engine=engine, sdk=detected_sdk, components=components,
                ready=not missing and not reason, supported=not bool(reason), reason=reason,
                download_bytes=sum(c['download_bytes'] for c in missing), disk_required_bytes=2 * 1024**3 if missing else 0,
                note='Скачивание начинается только после нажатия «Установить компоненты». Файлы игры не отправляются; системный Python не изменяется.')


def _check_cancel(cancel):
    if cancel.is_set():
        raise InterruptedError('Подготовка остановлена. Уже проверенные компоненты сохранены.')


def _digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


class _HttpsRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise ValueError('Небезопасное перенаправление загрузки.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(asset, cancel, progress):
    """Cache a complete verified asset; never publish partial or mismatched bytes."""
    base = user_home() / 'setup/cache'
    directory = base / asset['hash']
    directory.mkdir(parents=True, exist_ok=True)
    directory.resolve().relative_to(base.resolve())
    target = directory / asset['name']
    if target.is_symlink():
        raise ValueError('Файл кэша не должен быть ссылкой.')
    if target.is_file() and target.stat().st_size == asset['size'] and _digest(target) == asset['hash']:
        progress(asset['size'], asset['size'])
        return target
    _check_cancel(cancel)
    with tempfile.NamedTemporaryFile(prefix='.download-', dir=directory, delete=False) as temporary:
        partial = Path(temporary.name)
        try:
            opener = urllib.request.build_opener(_HttpsRedirect())
            with opener.open(asset['url'], timeout=30) as response:
                length = response.headers.get('Content-Length')
                if length is not None and int(length) != asset['size']:
                    raise ValueError('Размер загрузки отличается от каталога компонентов.')
                received = 0
                while True:
                    _check_cancel(cancel)
                    block = response.read(256 * 1024)
                    if not block:
                        break
                    received += len(block)
                    if received > asset['size']:
                        raise ValueError('Загружаемый файл превышает ожидаемый размер.')
                    temporary.write(block)
                    progress(received, asset['size'])
            temporary.flush()
            if received != asset['size'] or _digest(partial) != asset['hash']:
                raise ValueError('Контрольная сумма или размер загрузки не совпали. Компонент не установлен.')
        except (OSError, urllib.error.URLError) as exc:
            raise RuntimeError('Не удалось скачать компонент. Проверьте сеть и повторите подготовку.') from exc
        finally:
            temporary.close()
            if sys.exc_info()[0]:
                partial.unlink(missing_ok=True)
    os.replace(partial, target)
    return target


def extract_sdk(archive, destination, cancel):
    """Extract files first and links last; reject traversal, devices and bombs."""
    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, 'r:bz2') as tar:
        members = tar.getmembers()
        if len(members) > 100000 or sum(m.size for m in members) > 2 * 1024**3:
            raise ValueError('Архив SDK превышает поддерживаемый размер.')
        links = []
        for member in members:
            _check_cancel(cancel)
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or not name.parts or name.parts[0] not in {'renpy-8.5.3-sdk', 'renpy-8.5.3-sdkarm'}:
                raise ValueError('Небезопасный путь в архиве SDK.')
            path = root.joinpath(*name.parts)
            path.resolve().relative_to(root)
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                path.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as source, path.open('xb') as target:
                    shutil.copyfileobj(source, target)
                path.chmod(0o755 if member.mode & 0o111 else 0o644)
            elif member.issym() or member.islnk():
                links.append((member, path))
            else:
                raise ValueError('Архив SDK содержит неподдерживаемый тип файла.')
        for member, path in sorted(links, key=lambda pair: pair[0].issym()):
            _check_cancel(cancel)
            path.parent.mkdir(parents=True, exist_ok=True)
            target = (path.parent / member.linkname) if member.issym() else root / member.linkname
            target.resolve().relative_to(root / path.relative_to(root).parts[0])
            if member.issym():
                path.symlink_to(member.linkname)
            else:
                os.link(target, path)
        for _, path in links:
            path.resolve().relative_to(root / path.relative_to(root).parts[0])
    candidates = list(root.glob('renpy-*/renpy.sh'))
    if len(candidates) != 1 or not (candidates[0].parent / 'gui/game/options.rpy').is_file():
        raise ValueError('Архив не содержит полный SDK Ren’Py.')
    return candidates[0].parent


def run_command(command, cancel, timeout=600):
    with tempfile.TemporaryFile() as log:
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + timeout
        try:
            while proc.poll() is None:
                _check_cancel(cancel)
                if time.monotonic() > deadline:
                    raise RuntimeError('Подготовка компонента превысила время ожидания.')
                time.sleep(.15)
            if proc.returncode:
                log.seek(0)
                detail = log.read()[-1000:].decode(errors='replace')
                raise RuntimeError('Не удалось подготовить компонент: ' + detail)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()


def install_runtime(components, cancel):
    from app.utils.runtime import managed_runtime
    runtime = managed_runtime()
    packages = set(runtime['packages'] if runtime else [])
    packages.update(PACKAGES[key].split('==')[0] for key in components)
    versions = {value.split('==')[0]: value for value in PACKAGES.values()}
    if not packages <= versions.keys():
        raise ValueError('Неизвестные пакеты в управляемом окружении.')
    python = sys.executable if not getattr(sys, 'frozen', False) else shutil.which('python3') or shutil.which('python')
    if not python:
        raise ValueError('Для подготовки окружения нужен установленный Python 3.10 или новее.')
    base = user_home() / 'runtime'
    directory = base / 'versions'
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.env-', dir=directory) as temporary:
        stage = Path(temporary) / 'venv'
        run_command([python, '-I', '-m', 'venv', '--copies', str(stage)], cancel)
        interpreter = stage / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
        run_command([str(interpreter), '-I', '-m', 'pip', '--isolated', 'install', '--no-input', '--no-cache-dir',
                     '--disable-pip-version-check', '--only-binary=:all:', '--index-url', 'https://pypi.org/simple',
                     *[versions[p] for p in sorted(packages)]], cancel)
        _check_cancel(cancel)
        version = uuid.uuid4().hex
        target = directory / version
        stage.rename(target)
        try:
            installed_python = target / interpreter.relative_to(stage)
            if 'piper-tts' in packages:
                run_command([str(installed_python), '-I', '-m', 'piper', '--help'], cancel, timeout=60)
            if 'imageio-ffmpeg' in packages:
                run_command([str(installed_python), '-I', '-c', 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_version())'], cancel, timeout=60)
            _check_cancel(cancel)
            atomic_json(base / 'active.json', {'schema': 'anygamevoice-runtime', 'version': version, 'packages': sorted(packages)})
        except Exception:
            shutil.rmtree(target)
            raise


def install_voice(language, cancel, progress):
    voice = VOICES[language]
    assets = [(voice['id'] + '.onnx', voice['size'], voice['hash']),
              (voice['id'] + '.onnx.json', voice['config_size'], voice['config_hash']),
              ('MODEL_CARD', voice['card_size'], voice['card_hash'])]
    downloaded = []
    for name, size, digest in assets:
        asset = {'name': name, 'size': size, 'hash': digest, 'url': f'{VOICE_BASE}/{voice["folder"]}/{name}'}
        downloaded.append(download(asset, cancel, progress))
    config = json.loads(downloaded[1].read_text())
    if config.get('language', {}).get('code', '').split('_')[0] != language or not config.get('audio', {}).get('sample_rate'):
        raise ValueError('Настройки голоса не соответствуют выбранному языку.')
    directory = user_home() / 'models'
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink():
        raise ValueError('Папка установки моделей не должна быть ссылкой.')
    targets = [directory / (voice['id'] + suffix) for suffix in ['.onnx', '.onnx.json', '.MODEL_CARD']]
    for source, target in zip(downloaded, targets):
        if target.is_symlink() or (target.exists() and _digest(target) != _digest(source)):
            raise ValueError('Файл голоса уже существует и отличается от каталога. Он сохранён без изменений.')
    _check_cancel(cancel)
    for source, target in zip(downloaded, targets):
        if not target.exists():
            atomic_copy(source, target)
    return str(targets[0])


def install_sdk(cancel, progress):
    asset = dict(sdk_asset() or {})
    if not asset:
        raise ValueError('Автозагрузка SDK не поддерживается на этой платформе.')
    asset['url'] = 'https://www.renpy.org/dl/8.5.3/' + asset['name']
    archive = download(asset, cancel, progress)
    tools = user_home() / 'tools'
    tools.mkdir(parents=True, exist_ok=True)
    if tools.is_symlink():
        raise ValueError('Папка установки SDK не должна быть ссылкой.')
    with tempfile.TemporaryDirectory(prefix='.sdk-', dir=tools) as temporary:
        root = extract_sdk(archive, Path(temporary), cancel)
        run_command([str(root / 'renpy.sh'), '--version'], cancel, timeout=60)
        _check_cancel(cancel)
        target = tools / root.name
        if target.exists() or target.is_symlink():
            raise ValueError('Папка SDK уже существует. Она сохранена без изменений; выберите её вручную.')
        root.rename(target)
    return str(target / 'renpy.sh')


def task_status(task_id):
    with _TASKS_LOCK:
        return copy.deepcopy(_TASKS[task_id]['status'])


def cancel_task(task_id):
    with _TASKS_LOCK:
        item = _TASKS[task_id]
        item['cancel'].set()
        if item['status']['status'] == 'running':
            item['status']['status'] = 'cancelling'


def start_setup(language, engine, sdk, components, allow_downloads=False):
    if not allow_downloads:
        raise ValueError('Нажмите «Установить компоненты», чтобы разрешить загрузку.')
    if not _LOCK.acquire(blocking=False):
        raise ValueError('Подготовка компонентов уже выполняется.')
    try:
        plan = setup_plan(language, engine, sdk)
        if not plan['supported']:
            raise ValueError(plan['reason'])
        needed = {item['id'] for item in plan['components'] if item['needed']}
        if not needed <= set(components) or set(components) - {item['id'] for item in plan['components']}:
            raise ValueError('Список компонентов изменился. Откройте подготовку заново.')
        home = user_home()
        home.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(home).free < plan['disk_required_bytes']:
            raise ValueError('Для подготовки компонентов нужно не менее 2 ГБ свободного места.')
        task_id = uuid.uuid4().hex
        cancel = threading.Event()
        with _TASKS_LOCK:
            _TASKS[task_id] = {'cancel': cancel, 'status': {'id': task_id, 'status': 'running', 'stage': 'preparing', 'component': '', 'received': 0, 'total': 0, 'error': '', 'result': None}}
            for old in list(_TASKS)[:-10]:
                if _TASKS[old]['status']['status'] not in {'running', 'cancelling'}:
                    _TASKS.pop(old)
    except Exception:
        _LOCK.release()
        raise

    def update(**changes):
        with _TASKS_LOCK:
            _TASKS[task_id]['status'].update(changes)

    def progress(received, total):
        update(received=received, total=total)

    def run():
        try:
            managed = needed & {'piper', 'ffmpeg'}
            if managed:
                update(stage='runtime', component='Piper / FFmpeg')
                install_runtime(managed, cancel)
            if 'voice' in needed:
                update(stage='downloading', component=VOICES[language]['name'])
                install_voice(language, cancel, progress)
            selected_sdk = plan['sdk']
            if 'sdk' in needed:
                update(stage='sdk', component='Ren’Py SDK 8.5.3', received=0, total=0)
                selected_sdk = install_sdk(cancel, progress)
            _check_cancel(cancel)
            update(stage='testing', component='Пробная запись', received=0, total=0)
            from app.studio.core.tts.generator import generate_voice
            from app.core.pipeline import wav_duration
            voice = voice_for(language)
            if not voice:
                raise ValueError('Подходящий голос не найден после подготовки.')
            audio = generate_voice('Проверка голоса.' if language == 'ru' else 'Voice setup is complete.', voice=voice, engine='piper', language=language)
            with tempfile.TemporaryDirectory(prefix='agv-setup-probe-') as temporary:
                sample = Path(temporary) / 'probe.wav'
                sample.write_bytes(audio)
                duration = wav_duration(sample)
            final = setup_plan(language, engine, selected_sdk)
            if not final['ready']:
                raise ValueError('Подготовка не завершена. Проверьте недостающие компоненты.')
            _check_cancel(cancel)
            update(status='done', stage='complete', result={'language': language, 'engine': engine, 'sdk': selected_sdk, 'voice': voice, 'preview_duration': duration})
        except Exception as exc:
            update(status='cancelled' if cancel.is_set() else 'failed', stage='complete', error=str(exc)[:1000])
        finally:
            _LOCK.release()
    threading.Thread(target=run, daemon=True, name='agv-setup').start()
    return task_id
