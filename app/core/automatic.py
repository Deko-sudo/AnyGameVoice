"""Local folder diagnosis and deterministic automatic synthesis configuration."""
from collections import Counter
from dataclasses import asdict
import hashlib
from pathlib import Path
import re

from app.studio.core.game_detector.detector import ENGINE_MARKERS, is_dispatch
from app.studio.core.extractor.dialogue_extractor import extract_dialogue
from app.utils.paths import user_home

LANGUAGES = {'ru': 'русский', 'en': 'английский', 'ja': 'японский'}


def direct_engine(root):
    if is_dispatch(root):
        return 'unreal'
    scores = {engine: sum(any(root.glob(pattern)) for pattern in patterns) for engine, patterns in ENGINE_MARKERS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else 'unknown'


def language_for(lines):
    text = ' '.join(line.text for line in lines)[:100000]
    cyrillic = len(re.findall(r'[А-Яа-яЁё]', text))
    latin = len(re.findall(r'[A-Za-z]', text))
    kana = len(re.findall(r'[\u3040-\u30ff]', text))
    if kana > 10:
        return 'ja'
    return 'ru' if cyrillic > latin else 'en'


def prepare_game(path):
    selected = Path(path).expanduser().resolve()
    if not selected.is_dir():
        raise ValueError('Game folder does not exist.')
    root = selected
    # Accept the script/data directory too, and recover the containing game.
    if root.name == 'game' and any(root.glob('*.rpy')):
        root = root.parent
    elif root.name == 'data' and (root / 'System.json').is_file():
        root = root.parent
    engine = direct_engine(root)
    candidates = []
    if engine == 'unknown':
        for child in sorted(root.iterdir(), key=lambda p: p.name.casefold())[:200]:
            if child.is_dir() and not child.name.startswith('.'):
                found = direct_engine(child)
                if found != 'unknown':
                    candidates.append({'name': child.name, 'path': str(child.resolve()), 'engine': found})
        if len(candidates) == 1:
            root = Path(candidates[0]['path'])
            engine = candidates[0]['engine']
        elif len(candidates) > 1:
            return {'ready': False, 'path': str(root), 'engine': 'unknown', 'total': 0, 'lines': [], 'characters': [],
                    'candidates': candidates, 'issue': 'В этой папке несколько игр. Выберите одну из списка ниже.'}
    lines = extract_dialogue(str(root)) if engine != 'unknown' else []
    language = language_for(lines)
    base = user_home() / 'exports'
    if base.resolve() == root or root in base.resolve().parents:
        base = Path.home() / 'AnyGameVoice-exports'
    digest = hashlib.sha256(str(root).encode()).hexdigest()[:8]
    out = base / f'{root.name}-{digest}'
    result = {'ready': bool(lines), 'path': str(root), 'engine': engine, 'total': len(lines),
              'lines': [asdict(line) for line in lines[:10000]], 'truncated': len(lines) > 10000,
              'characters': [{'name': name, 'count': count} for name, count in Counter(x.speaker for x in lines).items()],
              'suggested_out': str(out), 'language': language, 'language_name': LANGUAGES.get(language, language),
              'language_note': 'Язык определён по тексту; для латиницы по умолчанию выбран английский. Можно изменить вручную.',
              'install_supported': engine in {'source_lostcoast', 'renpy'}, 'candidates': [], 'issue': ''}
    if not lines:
        if is_dispatch(root):
            result['issue'] = 'Dispatch найдена. Для её банков FMOD ещё нужен адаптер, который подключит русский дубляж и переключение с English в игре.'
        elif engine == 'renpy':
            result['issue'] = 'Это Ren’Py, но открытые диалоги .rpy не найдены. Архивы .rpa и .rpyc пока не поддерживаются.'
        elif engine in {'unity', 'unreal', 'redengine'}:
            result['issue'] = 'Игра найдена, но для её упакованных диалогов ещё нет адаптера. Автоматическая озвучка этой игры пока недоступна.'
        else:
            result['issue'] = 'Диалоги не найдены. Выберите папку самой игры: с файлом запуска, папкой game или data. Папка сохранений не подходит.'
    elif len(lines) > 10000:
        result.update(ready=False, issue='Найдено больше 10 000 реплик — текущий лимит превышен. Автоматический запуск остановлен.')
    return result


def automatic_settings(path, sdk=None, selection=None, target_lang='', trial=False):
    from app.core.scanner.model_planner import build_plan
    from app.studio.core.tts.generator import validate_synthesis
    data = prepare_game(path)
    if not data['ready']:
        raise ValueError(data['issue'])
    from app.core.installation import check_target
    target = {'install_engine': None} if trial else check_target(data['path'], data['engine'], sdk)
    if selection is not None:
        blend_settings = selection.get('voice_blend')
        selection = {key: selection[key] for key in ('voice', 'engine', 'emotion', 'language', 'out', 'workers', 'character_voices')}
        if target_lang:
            selection['language'] = target_lang
        output = Path(selection['out']).expanduser().resolve()
        root = Path(data['path']).resolve()
        if output == root or root in output.parents:
            raise ValueError('Choose an output folder outside the game folder.')
        voices = selection['character_voices']
        for selected in {voices.get(line['speaker']) or selection['voice'] for line in data['lines']}:
            validate_synthesis(selection['engine'], selected)
        if blend_settings is not None:
            from app.core.tts.reference import VoiceBlend
            policy = VoiceBlend.model_validate(blend_settings)
            for selected in {voices.get(line['speaker']) or selection['voice'] for line in data['lines']}:
                policy.for_voice(selection['engine'], selected)
            selection['voice_blend'] = policy.model_dump()
        return {'path': data['path'], **selection,
                'install_source': not trial and data['engine'] == 'source_lostcoast',
                'install_engine': target['install_engine'],
                **({'renpy_sdk': target['renpy_sdk']} if 'renpy_sdk' in target else {})}
    language = target_lang or data['language']
    plan = build_plan(language)
    voice = plan['selected_tts']
    if not voice:
        installed = [item for item in plan['tts'] if item['installed'] and item['engine'] == 'piper']
        if installed:
            reason = next((item['reason'] for item in installed if item['fit'] != 'unsupported'), installed[0]['reason'])
            raise ValueError(f'Автоматический запуск остановлен: подходящий голос не найден ({language}). {reason} Откройте «Настроить вручную» или инструкцию «Как пользоваться».')
        raise ValueError(f'Для автоматической озвучки нужен установленный Piper и голос: {language}. Откройте «Как пользоваться» → «Если голос не найден».')
    validate_synthesis(voice['engine'], voice['voice'])
    return {'path': data['path'], 'out': data['suggested_out'], 'voice': voice['voice'], 'engine': voice['engine'],
            'language': language, 'emotion': 'neutral', 'workers': 1, 'character_voices': {},
            'install_source': not trial and data['engine'] == 'source_lostcoast',
            'install_engine': target['install_engine'], **({'renpy_sdk': target['renpy_sdk']} if 'renpy_sdk' in target else {})}
