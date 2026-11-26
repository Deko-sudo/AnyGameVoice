# SPDX-License-Identifier: Apache-2.0
"""Explain model fit separately from installation and measured launch success."""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from app.studio.core.scanner.hardware import scan_hardware

CATALOG = [
    {'id': 'qwen2.5:1.5b', 'name': 'Qwen 2.5 · 1.5B', 'class': '1–2B', 'disk_gb': 1.0, 'memory_gb': 3.0},
    {'id': 'qwen2.5:7b', 'name': 'Qwen 2.5 · 7B', 'class': '7–8B', 'disk_gb': 4.7, 'memory_gb': 7.5},
    {'id': 'qwen2.5:14b', 'name': 'Qwen 2.5 · 14B', 'class': '14B', 'disk_gb': 9.0, 'memory_gb': 13.0},
    {'id': 'qwen3:1.7b', 'name': 'Qwen 3 · 1.7B', 'class': '1–2B', 'disk_gb': 1.4, 'memory_gb': 3.5},
    {'id': 'qwen3:4b', 'name': 'Qwen 3 · 4B', 'class': '4B', 'disk_gb': 2.5, 'memory_gb': 5.5},
    {'id': 'qwen3:8b', 'name': 'Qwen 3 · 8B', 'class': '7–8B', 'disk_gb': 5.2, 'memory_gb': 8.5},
    {'id': 'qwen3:14b', 'name': 'Qwen 3 · 14B', 'class': '14B', 'disk_gb': 9.3, 'memory_gb': 13.5},
    {'id': 'qwen3.5:0.8b', 'name': 'Qwen 3.5 · 0.8B', 'class': '1B', 'disk_gb': 1.3, 'memory_gb': 3.5},
    {'id': 'qwen3.5:2b', 'name': 'Qwen 3.5 · 2B', 'class': '2B', 'disk_gb': 3.1, 'memory_gb': 5.0},
    {'id': 'qwen3.5:4b', 'name': 'Qwen 3.5 · 4B', 'class': '4B', 'disk_gb': 4.0, 'memory_gb': 6.5},
    {'id': 'qwen3.5:9b', 'name': 'Qwen 3.5 · 9B', 'class': '9B', 'disk_gb': 7.6, 'memory_gb': 11.5},
    {'id': 'qwen3.5:27b', 'name': 'Qwen 3.5 · 27B', 'class': '27B', 'disk_gb': 20.0, 'memory_gb': 26.0},
    {'id': 'qwen3.6:27b', 'name': 'Qwen 3.6 · 27B', 'class': '27B', 'disk_gb': 19.0, 'memory_gb': 25.0},
    {'id': 'qwen3.8:27b', 'name': 'Qwen 3.8 · 27B', 'class': '27B', 'disk_gb': 18.0, 'memory_gb': 24.0},
]


def ollama_url():
    url = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment:
        raise ValueError('Для локального исследования OLLAMA_URL должен указывать на localhost.')
    return url


def local_session():
    import requests
    session = requests.Session()
    session.trust_env = False
    return session


def discover_ollama():
    try:
        with local_session() as session:
            response = session.get(ollama_url() + '/api/tags', timeout=(1, 2), allow_redirects=False)
            if response.status_code != 200:
                return {'available': False, 'models': [], 'reason': 'Ollama не отвечает на запрос списка моделей.'}
            data = response.json()
            models = data.get('models', []) if isinstance(data, dict) else []
            valid = [x for x in models[:200] if isinstance(x, dict) and isinstance(x.get('name'), str)]
            def capabilities(model):
                try:
                    with local_session() as client:
                        reply = client.post(ollama_url() + '/api/show', json={'model': model['name']},
                                            timeout=(1, 2), allow_redirects=False)
                        data = reply.json() if reply.status_code == 200 else {}
                        value = data.get('capabilities') if isinstance(data, dict) else None
                        if isinstance(value, list):
                            model = {**model, 'capabilities': value}
                except Exception:
                    pass
                return model
            with ThreadPoolExecutor(max_workers=6) as pool:
                valid = list(pool.map(capabilities, valid))
            return {'available': True, 'models': valid, 'reason': ''}
    except Exception:
        return {'available': False, 'models': [], 'reason': 'Локальный Ollama недоступен. Запустите ollama serve.'}


def memory_fit(required, hardware):
    total = hardware.get('ram_gb') or 0
    available = hardware.get('available_ram_gb')
    if not total or available is None:
        return 'unknown', 'Недостаточно данных о свободной RAM.'
    if required + 1 > total:
        return 'unsupported', f'Нужно около {required:g} ГБ RAM плюс запас для системы.'
    if required + 1 > available:
        return 'tight', f'Сейчас свободно {available:g} ГБ RAM; нужно около {required:g} ГБ и запас 1 ГБ.'
    return 'recommended', f'Оценка {required:g} ГБ RAM; сейчас свободно {available:g} ГБ.'


def build_plan(language='ru', hardware=None, voices=None, engines=None, ollama=None):
    from dataclasses import asdict
    from app.studio.core.tts.voice_manager import VoiceManager
    from app.studio.core.tts.generator import list_engines
    hw = scan_hardware() if hardware is None else hardware
    voices = [asdict(v) for v in VoiceManager().list_voices()] if voices is None else voices
    engines = list_engines() if engines is None else engines
    ollama = discover_ollama() if ollama is None else ollama
    lang = language.lower().replace('_', '-').split('-')[0]
    tts = []
    for voice in voices:
        if voice.get('engine') != 'piper':
            continue
        path = Path(voice['path'])
        config_ok = False
        try:
            config = json.loads(Path(str(path) + '.json').read_text(encoding='utf-8'))
            config_ok = isinstance(config, dict) and bool(config.get('audio', {}).get('sample_rate')) and path.is_file()
        except (OSError, ValueError, AttributeError):
            pass
        matches = voice.get('language', '').lower().replace('_', '-').split('-')[0] == lang
        required = max(1.0, round(path.stat().st_size / 1024 ** 3 * 2 + .5, 1)) if path.is_file() else 1.0
        fit, reason = memory_fit(required, hw)
        if not matches:
            fit, reason = 'unsupported', 'Язык модели не совпадает с выбранным языком речи или не указан.'
        installed = bool(engines.get('piper') and config_ok)
        tts.append({'id': voice['path'], 'name': voice['name'], 'engine': 'piper', 'voice': voice['path'],
                    'class': 'Быстрый CPU-синтез', 'fit': fit, 'reason': reason,
                    'installed': installed, 'launch_verified': False, 'memory_gb': required,
                    'cloning': False, 'license': 'Движок GPL-3.0-or-later; лицензия голоса — в model card.'})
    if not any(v.get('engine') == 'piper' and v.get('language', '').lower().replace('_', '-').split('-')[0] == lang for v in voices):
        fit, reason = memory_fit(1.0, hw)
        tts.append({'id': 'piper-install', 'name': 'Piper · голос для ' + language, 'engine': 'piper', 'voice': '',
                    'class': 'Быстрый CPU-синтез', 'fit': fit, 'reason': reason, 'installed': False,
                    'launch_verified': False, 'memory_gb': 1.0, 'cloning': False,
                    'license': 'Движок GPL-3.0-or-later; голос — отдельная лицензия.'})
    fit, reason = memory_fit(5.0, hw)
    tts.append({'id': 'xtts', 'name': 'XTTS v2 · образец актёра', 'engine': 'xtts', 'voice': '',
                'class': 'Клонирование по WAV', 'fit': fit, 'reason': reason,
                'installed': bool(engines.get('xtts')), 'launch_verified': False, 'memory_gb': 5.0,
                'cloning': True, 'source': 'https://huggingface.co/coqui/XTTS-v2', 'license': 'Веса: Coqui Public Model License; отдельно от Apache-2.0 приложения.'})
    research = []
    installed = {model['name']: model for model in ollama['models']}
    for candidate in CATALOG:
        item = dict(candidate)
        item['fit'], item['reason'] = memory_fit(item['memory_gb'], hw)
        item['installed'] = ollama['available'] and item['id'] in installed
        if not item['installed'] and hw.get('free_disk_gb') is not None and item['disk_gb'] + 2 > hw['free_disk_gb']:
            item.update(fit='unsupported', reason='Недостаточно свободного места для весов и временных файлов.')
        family, size = item['id'].split(':')
        source = ('https://huggingface.co/Qwen/Qwen2.5-' + size.upper() + '-Instruct-GGUF' if family == 'qwen2.5'
                  else 'https://huggingface.co/Qwen/Qwen' + family[4:] + '-' + size.upper())
        item.update(launch_verified=False, license='Проверьте лицензию на странице модели.', source=source,
                    install_command='ollama pull ' + item['id'])
        research.append(item)
    for name, data in installed.items():
        if name in {x['id'] for x in research}:
            continue
        try:
            size = max(0, float(data.get('size', 0))) / 1024 ** 3
        except (TypeError, ValueError):
            size = 0
        required = round(size * 1.25 + 2, 1) if size else None
        fit, reason = memory_fit(required, hw) if required else ('unknown', 'Размер модели неизвестен.')
        capabilities = data.get('capabilities')
        image_model = bool(re.search(r'(?:^|[-_/])(?:image|embedding|embed)(?:[-_/:.]|$)', name, re.I))
        usable = isinstance(capabilities, list) and 'completion' in capabilities and not image_model
        details = data.get('details') if isinstance(data.get('details'), dict) else {}
        research.append({'id': name, 'name': name, 'class': details.get('parameter_size') or 'Класс неизвестен',
                         'memory_gb': required, 'disk_gb': round(size, 1), 'fit': fit if usable else 'unknown',
                         'reason': ('Модель предназначена для изображений или эмбеддингов.' if image_model else
                                    'Текстовый режим не подтверждён.' if not usable else 'Текстовый режим подтверждён Ollama. ' + reason),
                         'installed': True, 'launch_verified': False, 'license': 'Проверьте карту этой модели.',
                         'manual_only': not usable})
    research.sort(key=lambda x: (not x['installed'], x.get('manual_only', False), x.get('memory_gb') or float('inf')))
    ready = next((x for x in tts if x['installed'] and x['fit'] == 'recommended' and x['engine'] == 'piper'), None)
    ready_research = max((x for x in research if x['installed'] and x['fit'] == 'recommended' and not x.get('manual_only')), key=lambda x: x['memory_gb'], default=None)
    def recommendation_key(item):
        version = re.match(r'^qwen(\d+(?:\.\d+)?):', item['id'])
        return (float(version.group(1)) if version else 0, item['memory_gb'])
    suggested = ready_research or max((x for x in research if x['fit'] == 'recommended' and not x.get('manual_only')),
                                      key=recommendation_key, default=None)
    upper = max((x for x in research if x['fit'] in {'recommended', 'tight'} and not x.get('manual_only')), key=lambda x: x['memory_gb'], default=None)
    searches = [{'id': 'brave', 'name': 'Brave Search', 'available': bool(os.getenv('BRAVE_SEARCH_API_KEY'))},
                {'id': 'tavily', 'name': 'Tavily', 'available': bool(os.getenv('TAVILY_API_KEY'))}]
    gpu_memory = hw.get('free_vram_gb')
    gpu_item = max((x for x in CATALOG if gpu_memory is not None and x['memory_gb'] + 1 <= gpu_memory), key=lambda x: x['memory_gb'], default=None)
    gpu_class = gpu_item['class'] if gpu_item else None
    return {'gpu_research_class': gpu_class, 'hardware': hw, 'tts': tts, 'research': research, 'selected_tts': ready,
            'selected_research': ready_research['id'] if ready_research else None,
            'suggested_research': suggested['id'] if suggested else None,
            'research_class': suggested['class'] if suggested else 'Нет подходящей оценки',
            'upper_class': upper['class'] if upper else 'Недостаточно RAM',
            'ollama': {'available': ollama['available'], 'reason': ollama.get('reason', '')}, 'searches': searches,
            'note': 'Оценка памяти — ориентир при коротком контексте. Установленная модель ещё не означает проверенный запуск. '
                    'GPU учитывается в инвентаризации; ускорение конкретного движка нужно подтвердить пробной записью. '
                    'Исследование и синтез запускаются последовательно.'}
