"""Connections used for dialogue translation."""

import json
import os
from pathlib import Path
import subprocess
import tempfile

import requests

from app.core.cloud_providers import MODEL_ID, _custom_url, _executable


def opencode_translation(model, prompt, system):
    if not MODEL_ID.fullmatch(model) or '/' not in model:
        raise ValueError('Укажите модель OpenCode в формате провайдер/модель.')
    binary = _executable('opencode')
    if not binary:
        raise ValueError('OpenCode не найден. Установите его и подключите провайдера.')
    with tempfile.TemporaryDirectory(prefix='agv-opencode-translation-') as cwd:
        config = {'permissions': [{'action': '*', 'resource': '*', 'effect': 'deny'}],
                  'mcp': {}, 'update': 'disable'}
        Path(cwd, 'opencode.json').write_text(json.dumps(config), encoding='utf-8')
        try:
            result = subprocess.run(
                [binary, 'run', '--standalone', '--archived', '--format', 'json', '--model', model,
                 system + '\n' + prompt],
                cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                timeout=180, check=False, env={**os.environ, 'NO_COLOR': '1'},
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError('OpenCode недоступен или не завершил перевод.') from exc
    if result.returncode != 0:
        raise RuntimeError('OpenCode не выполнил запрос. Проверьте подключение и доступ к модели.')
    texts = []
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        part = event.get('part', {})
        if event.get('type') == 'text' and isinstance(part, dict) and isinstance(part.get('text'), str):
            texts.append(part['text'])
    if not texts:
        raise RuntimeError('OpenCode не вернул перевод. Проверьте модель и подключение.')
    return ''.join(texts)


def custom_translation(model, prompt, system, base_url, api_key, api_format):
    if not MODEL_ID.fullmatch(model):
        raise ValueError('Укажите корректный ID модели.')
    auth = {}
    if api_format == 'openai_responses':
        endpoint = '/responses'
        payload = {'model': model, 'instructions': system, 'input': prompt}
    elif api_format == 'anthropic':
        endpoint = '/messages'
        payload = {'model': model, 'max_tokens': 1024, 'system': system,
                   'messages': [{'role': 'user', 'content': prompt}]}
        auth = {'x-api-key': api_key, 'anthropic-version': '2023-06-01'}
    elif api_format == 'gemini':
        endpoint = '/models/' + model + ':generateContent'
        payload = {'systemInstruction': {'parts': [{'text': system}]},
                   'contents': [{'role': 'user', 'parts': [{'text': prompt}]}]}
        auth = {'x-goog-api-key': api_key}
    elif api_format == 'ollama':
        endpoint = '/api/chat'
        payload = {'model': model, 'stream': False,
                   'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}]}
    else:
        raise ValueError('Выберите поддерживаемый формат API.')
    url = _custom_url(base_url, endpoint)
    if api_key and not auth:
        auth['Authorization'] = 'Bearer ' + api_key
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.post(url, headers=auth, json=payload, timeout=(3, 120), allow_redirects=False)
            if response.status_code != 200:
                raise ValueError(f'Провайдер отклонил запрос (HTTP {response.status_code}).')
            if len(response.content) > 4 * 1024 * 1024:
                raise ValueError('Ответ провайдера слишком большой.')
            data = response.json()
        if api_format == 'openai_responses':
            return ''.join(item.get('text', '') for output in data['output']
                           for item in output.get('content', []) if item.get('type') == 'output_text')
        if api_format == 'anthropic':
            return ''.join(item.get('text', '') for item in data['content'] if item.get('type') == 'text')
        if api_format == 'gemini':
            return ''.join(part.get('text', '') for part in data['candidates'][0]['content']['parts'])
        return data['message']['content']
    except (requests.RequestException, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError('Провайдер недоступен или вернул неподдерживаемый ответ.') from exc
