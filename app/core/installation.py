"""Shared installation actions for automatic jobs and the local studio."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading

from app.utils.paths import project_root, user_home

NAMES = {'renpy': 'Ren’Py', 'source_lostcoast': 'Lost Coast'}
_DEMO_LOCK = threading.Lock()


def demo_project(sdk=None):
    """Build a runnable demo in user data, keeping shipped sources read-only."""
    with _DEMO_LOCK:
        return _demo_project(sdk)


def _demo_project(sdk):
    import json
    import tempfile
    from app.utils.paths import resource_path
    launcher = discover_renpy_sdk(sdk)
    parent = user_home() / 'demos'
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / 'night-signal'
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not (target / '.anygamevoice-demo.json').is_file():
            raise ValueError('Папка учебной сцены занята сторонними файлами.')
        return target
    with tempfile.TemporaryDirectory(prefix='.agv-demo-', dir=parent) as temporary:
        stage = Path(temporary) / 'project'
        shutil.copytree(launcher.parent / 'gui/game', stage / 'game',
                        ignore=shutil.ignore_patterns('*.rpyc', 'cache', 'saves', 'script.rpy', 'testcases.rpy'))
        options = stage / 'game/options.rpy'
        text = options.read_text(encoding='utf-8')
        text = re.sub(r'^define config.name.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^define config.save_directory.*$', 'define config.save_directory = "anygamevoice-demo"', text, flags=re.MULTILINE)
        options.write_text(text, encoding='utf-8')
        shutil.copytree(resource_path('examples', 'renpy', 'game'), stage / 'game', dirs_exist_ok=True)
        (stage / '.anygamevoice-demo.json').write_text(json.dumps({'schema': 'anygamevoice-demo', 'version': 1}))
        stage.rename(target)
    return target


def discover_renpy_sdk(value=None):
    """Prefer explicit configuration, then installed application/development tools."""
    from app.core.game_detector.engines.renpy_mod import find_sdk
    if value or os.environ.get('AGV_RENPY_SDK'):
        return find_sdk(value)
    candidates = [user_home() / 'tools/renpy-sdk/renpy.sh', project_root() / 'tools/renpy-sdk/renpy.sh']
    for base in (user_home() / 'tools', project_root().parent / 'tools'):
        if base.is_dir():
            def version(path):
                return tuple(int(n) for n in re.findall(r'\d+', path.parent.name))
            candidates.extend(sorted((*base.glob('renpy-*-sdk/renpy.sh'), *base.glob('renpy-*-sdkarm/renpy.sh')), key=version, reverse=True))
    for path in candidates:
        if path.is_file():
            return find_sdk(path)
    raise ValueError('Ren’Py SDK не найден. В «Настроить вручную» выберите папку SDK и нажмите «Продолжить автоматически».')


def check_target(path, engine, sdk=None):
    """Check requirements and ownership before starting expensive synthesis."""
    if engine == 'renpy':
        from app.core.game_detector.engines import renpy_mod
        root = renpy_mod.check_install_target(path)
        return {'install_engine': engine, 'renpy_sdk': str(discover_renpy_sdk(sdk)), 'path': str(root)}
    if engine == 'source_lostcoast':
        from app.utils.runtime import ffmpeg_command
        from app.core.game_detector.engines.source_lostcoast import game_root, check_owned, MOD_NAME
        root = game_root(path)
        if not ffmpeg_command():
            raise ValueError('Для установки Lost Coast нужен FFmpeg. Установите его и продолжите автоматически.')
        if (root / 'custom').is_symlink():
            raise ValueError('Папка custom не должна быть символической ссылкой.')
        target = root / 'custom' / MOD_NAME
        if target.exists() or target.is_symlink():
            check_owned(target, root)
        return {'install_engine': engine, 'path': str(root)}
    return {'install_engine': None, 'path': str(Path(path).resolve())}


def preflight(params):
    engine = params.get('install_engine') or ('source_lostcoast' if params.get('install_source') else None)
    if engine:
        check_target(params['path'], engine, params.get('renpy_sdk'))
    if engine == 'renpy':
        from app.core.game_detector.engines import renpy_mod
        rows = renpy_mod.export_dialogue_ids(params['path'], params['renpy_sdk'])
        from app.studio.core.extractor.dialogue_extractor import extract_dialogue
        from dataclasses import asdict
        lines = [{**asdict(line), 'id': str(i)} for i, line in enumerate(extract_dialogue(params['path']))]
        plan = renpy_mod.plan_install({'status': 'done', 'lines': lines}, rows)
        if plan['unmatched'] or len(plan['matched']) != plan['engine_total']:
            raise ValueError('Сценарий Ren’Py поддерживается не полностью: ' +
                             f'{len(plan["matched"])} из {plan["engine_total"]} реплик. Автоматическая установка остановлена до записи.')
    return engine


def install(result, params, cancel_event=None):
    engine = params.get('install_engine') or ('source_lostcoast' if params.get('install_source') else None)
    if engine == 'renpy':
        from app.core.game_detector.engines import renpy_mod
        rows = renpy_mod.export_dialogue_ids(result['game_path'], params['renpy_sdk'])
        plan = renpy_mod.plan_install(result, rows)
        if plan['unmatched'] or len(plan['matched']) != plan['engine_total']:
            raise ValueError('Сценарий изменился или озвучен не полностью. Мод не установлен; аудиофайлы сохранены.')
        report = renpy_mod.install_mod(result, rows=rows, cancel_event=cancel_event)
        report['sdk'] = params['renpy_sdk']
        return report
    if engine == 'source_lostcoast':
        from app.core.game_detector.engines.source_lostcoast import install_mod
        return install_mod(result, cancel_event)
    raise ValueError('Для этой игры нет автоматического установщика.')


def verify(result):
    installation = result.get('installation', {})
    engine = installation.get('engine', 'source_lostcoast')
    if engine == 'renpy':
        from app.core.game_detector.engines import renpy_mod
        report = renpy_mod.verify_mod(result['game_path'], sdk=discover_renpy_sdk(installation.get('sdk')))
        if report.get('status') == 'ok' and report.get('engine_total') != report.get('voiced'):
            report['status'] = 'incomplete'
        return report
    if engine == 'source_lostcoast':
        from app.core.game_detector.engines.source_lostcoast import game_root, check_owned, MOD_NAME
        root = game_root(result['game_path'])
        data = check_owned(root / 'custom' / MOD_NAME, root)
        return {'status': 'ok', 'files': len(data['files'])}
    raise ValueError('Неизвестный установщик мода.')


def disable(result):
    installation = result.get('installation', {})
    if installation.get('engine') == 'renpy':
        from app.core.game_detector.engines import renpy_mod
        report = renpy_mod.uninstall_mod(result['game_path'])
        return {**report, 'status': 'disabled', 'engine': 'renpy'}
    if installation.get('engine', 'source_lostcoast') != 'source_lostcoast':
        raise ValueError('Неизвестный установщик мода.')
    from app.core.game_detector.engines.source_lostcoast import disable_mod
    return {**disable_mod(result), 'engine': 'source_lostcoast'}


def launch(result):
    installation = result['installation']
    if verify(result).get('status') != 'ok':
        raise ValueError('Проверка мода не пройдена. Запуск из студии остановлен.')
    if installation.get('engine') == 'renpy':
        sdk = discover_renpy_sdk(installation.get('sdk'))
        command = [str(sdk), result['game_path']]
    else:
        steam = shutil.which('steam')
        if not steam:
            raise ValueError('Steam не найден. Откройте Lost Coast через библиотеку Steam.')
        command = [steam, '-applaunch', '220', '-game', 'lostcoast']
    subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    return {'status': 'requested', 'note': 'Команда запуска отправлена. Если игра уже открыта, перезапустите её для загрузки мода.'}
