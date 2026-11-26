"""Discover cloud providers and run explicit API-based research requests."""

import json
import os
from pathlib import Path
from queue import Empty, Full, Queue
import re
import shutil
import subprocess
import sys
import tempfile
from threading import Thread
from time import monotonic
from urllib.parse import urlsplit, urlunsplit

import requests


PROVIDERS = {
    'openrouter': ('OpenRouter', None, 'https://openrouter.ai/collections/free-models'),
    'opencode': ('OpenCode', 'opencode', 'https://opencode.ai/console'),
    'codex': ('Codex', 'codex', 'https://learn.chatgpt.com/docs/app-server'),
    'claude': ('Claude Code', 'claude', 'https://claude.ai/settings/usage'),
}
DETECTABLE_AGENTS = {
    'copilot-cli': ('GitHub Copilot CLI', 'copilot'),
    'cursor-agent': ('Cursor Agent', 'cursor-agent'),
    'devin': ('Devin', 'devin'),
    'grok': ('Grok', 'grok'),
    'muse-code': ('Muse Code', 'muse'),
    'kimi-code': ('Kimi Code', 'kimi'),
    'pi': ('Pi', 'pi'),
    'gemini-cli': ('Gemini CLI', 'gemini'),
    'qwen-code': ('Qwen Code', 'qwen'),
    'deepseek-harness': ('DeepSeek Harness', 'dsh'),
    'antigravity': ('Antigravity', 'agy'),
    'amp': ('Amp', 'amp'),
    'crush': ('Crush', 'crush'),
    'aider': ('Aider', 'aider'),
    'goose': ('Goose', 'goose'),
    'droid': ('Droid', 'droid'),
    'zed': ('Zed', 'zeditor' if sys.platform.startswith('linux') else 'zed'),
}
MODEL_ID = re.compile(r'[A-Za-z0-9_.][A-Za-z0-9_./:+@-]{0,199}\Z')
OPENCODE_ID = re.compile(r'[a-z0-9][a-z0-9_.-]{0,79}\Z')
LOCAL_OPENCODE = {'ollama', 'lmstudio', 'vllm', 'localai', 'llamacpp', 'llama.cpp', 'llama-cpp',
                  'mlx', 'ktransformers', 'jan', 'oobabooga', 'koboldcpp', 'opencode-local'}
OPENROUTER_MODELS = (
    ('openrouter/free', 'Free Models Router'),
    ('deepseek/deepseek-v3.2', 'DeepSeek V3.2'),
    ('google/gemini-3-flash-preview', 'Gemini 3 Flash Preview'),
    ('anthropic/claude-sonnet-4', 'Claude Sonnet 4'),
)
OPENROUTER_URL = 'https://openrouter.ai/api/v1'
KNOWN_PLANS = {'free', 'go', 'plus', 'pro', 'max', 'team', 'business', 'enterprise',
               'edu', 'education', 'ultra', 'pro-lite', 'prolite'}


def _executable(command):
    home = Path.home()
    data_home = Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share')
    mise_home = Path(os.environ.get('MISE_DATA_DIR') or data_home / 'mise')
    directories = [*os.get_exec_path(), str(home / '.local/bin'), str(home / '.bun/bin'),
                   str(home / '.opencode/bin'), str(mise_home / 'command-wrappers/bin'), str(mise_home / 'shims')]
    checked_mise = set()
    for directory in dict.fromkeys(directories):
        executable = shutil.which(command, path=directory)
        if not executable:
            continue
        target = Path(executable).resolve()
        if target.stem != 'mise':
            return executable
        if target not in checked_mise:
            checked_mise.add(target)
            resolved = _mise_executable(target, command, home)
            if resolved:
                return resolved
    return None


def _mise_executable(mise, command, home):
    try:
        result = subprocess.run([str(mise), 'which', command], cwd=home, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                timeout=2, check=False, env={**os.environ, 'MISE_AUTO_INSTALL': '0'})
    except (OSError, subprocess.SubprocessError):
        return None
    resolved = result.stdout.strip()
    if result.returncode == 0 and Path(resolved).is_absolute() and Path(resolved).resolve() != mise:
        return shutil.which(resolved)
    return None


def provider_inventory():
    supported = [
        {'id': ident, 'name': name, 'installed': bool(_executable(binary)) if binary else None,
         'url': url, 'free_options': ident in {'opencode', 'openrouter'}}
        for ident, (name, binary, url) in PROVIDERS.items()
    ]
    detected = [
        {'id': ident, 'name': name, 'installed': True, 'can_select': False,
         **({'account_probe': True} if ident == 'cursor-agent' else {})}
        for ident, (name, binary) in DETECTABLE_AGENTS.items()
        if _executable(binary)
    ]
    return supported + detected


def _model(ident, name=None, free=False):
    if not isinstance(ident, str) or not MODEL_ID.fullmatch(ident):
        return None
    return {'id': ident, 'name': name[:140] if isinstance(name, str) and name.strip() else ident,
            'free': free}


def _catalog(rows, limit=50):
    models = {}
    for item in rows:
        if item and item['id'] not in models:
            models[item['id']] = item
    return sorted(models.values(), key=lambda item: not item['free'])[:limit]


def _result(status='unknown', plan=None, models=None, limits=None, catalog='unavailable', subscription='unknown'):
    return {'status': status, 'plan': plan, 'models': models or [], 'limits': limits or {},
            'catalog': catalog, 'subscription': subscription}


def _plan(value):
    return value if isinstance(value, str) and value.casefold() in KNOWN_PLANS else None


def _subscription(plan):
    return 'none' if plan and plan.casefold() == 'free' else 'active' if plan else 'unknown'


def _run(binary, args, cwd, timeout=7, stderr=subprocess.DEVNULL):
    with tempfile.TemporaryFile() as output:
        subprocess.run([binary, *args], cwd=cwd, stdin=subprocess.DEVNULL, stdout=output,
                       stderr=stderr, timeout=timeout, check=False,
                       env={**os.environ, 'NO_COLOR': '1', 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1'})
        output.seek(0)
        return output.read(1024 * 1024).decode('utf-8', errors='replace')


def _json_result(binary, args, cwd, **kwargs):
    try:
        return json.loads(_run(binary, args, cwd, **kwargs))
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _opencode_rows(binary, path, cwd):
    result = _json_result(binary, ['api', 'GET', path], cwd)
    data = result.get('data') if isinstance(result, dict) else None
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _cloud_integration(ident):
    return isinstance(ident, str) and OPENCODE_ID.fullmatch(ident) and ident not in LOCAL_OPENCODE


def opencode_catalog():
    binary = _executable('opencode')
    if not binary:
        return []
    with tempfile.TemporaryDirectory(prefix='agv-opencode-') as cwd:
        rows = _opencode_rows(binary, '/api/integration', cwd)
    return [
        {'id': 'oc:' + ident, 'name': row['name'][:140], 'source': 'opencode',
         'status': 'connected' if row.get('connections') else 'not_signed_in',
         'methods': sorted({method['type'] for method in row.get('methods', [])
                            if isinstance(method, dict) and method.get('type') in {'key', 'oauth', 'env', 'command', 'external'}}),
         'free_options': ident == 'opencode'}
        for row in rows
        if _cloud_integration(ident := row.get('id')) and isinstance(row.get('name'), str)
    ]


def opencode_models(ident):
    if not _cloud_integration(ident):
        raise ValueError('Выберите облачного провайдера.')
    binary = _executable('opencode')
    if not binary:
        return _result(status='not_installed')
    with tempfile.TemporaryDirectory(prefix='agv-opencode-') as cwd:
        providers = _opencode_rows(binary, '/api/provider', cwd)
        ids = {ident} | {row.get('id') for row in providers if row.get('integrationID') == ident}
        rows = _opencode_rows(binary, '/api/model', cwd)
    models = _opencode_chat_models(rows, ids)
    return _result(status='connected' if models else 'not_signed_in', models=models,
                   catalog='client' if models else 'unavailable')


def _opencode_chat_models(rows, providers=None):
    return _catalog((
        _model(f"{row['providerID']}/{row['id']}", row.get('name'),
               free=row['providerID'] == 'opencode' and (row['id'].endswith('-free') or row['id'] == 'big-pickle'))
        for row in rows if _cloud_integration(row.get('providerID'))
        and (providers is None or row['providerID'] in providers)
        and isinstance(row.get('id'), str) and row.get('type') == 'chat' and row.get('enabled') is True
    ), limit=400)


def open_opencode_login(ident):
    if not _cloud_integration(ident) or not any(row['id'] == 'oc:' + ident for row in opencode_catalog()):
        raise ValueError('Провайдер не найден в облачном каталоге OpenCode. Обновите список.')
    binary = _executable('opencode')
    if not binary:
        raise ValueError('Установите OpenCode для входа в аккаунт.')
    if sys.platform == 'win32':
        launcher = shutil.which('wt')
        prefix = ['new-tab']
    else:
        launcher = shutil.which('xdg-terminal-exec')
        prefix = []
    if not launcher:
        raise ValueError('Откройте OpenCode и подключите этого провайдера через /connect, затем обновите список.')
    try:
        subprocess.Popen([launcher, *prefix, binary, 'auth', 'login', ident], cwd=Path.home(),
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise ValueError('Не удалось открыть OpenCode. Войдите через /connect и обновите список.') from exc


def _inspect_opencode(binary, cwd):
    accounts = _json_result(binary, ['auth', 'list', '--format', 'json'], cwd)
    status = 'unknown'
    if isinstance(accounts, list):
        connected = any(isinstance(account, dict) and _cloud_integration(account.get('id'))
                        and account.get('connections') for account in accounts)
        status = 'connected' if connected else 'not_signed_in'
    models = _opencode_chat_models(_opencode_rows(binary, '/api/model', cwd))
    if not models:
        try:
            output = _run(binary, ['models'], cwd)
        except (OSError, subprocess.SubprocessError):
            output = ''
        models = _catalog((
            _model(ident, free=ident.startswith('opencode/') and
                   (ident.endswith('-free') or ident == 'opencode/big-pickle'))
            for ident in (line.strip() for line in output.splitlines())
            if '/' in ident and _cloud_integration(ident.split('/', 1)[0])
        ), limit=400)
    usage = _json_result(binary, ['api', 'GET', '/api/experimental/usage/limits'], cwd, timeout=18)
    result = _result(status=status, models=models, catalog='client' if models else 'unavailable')
    result.update(_opencode_subscription(usage))
    return result


def _opencode_subscription(usage):
    data = usage.get('data') if isinstance(usage, dict) else None
    if not isinstance(data, dict) or not isinstance(data.get('workspace'), dict):
        return {}
    go = data.get('go')
    if go is not None and not isinstance(go, dict):
        return {}
    limits = {}
    if go is not None:
        windows = []
        for key, minutes in (('rolling', 300), ('weekly', 10080), ('monthly', None)):
            meter = go.get(key)
            if not isinstance(meter, dict):
                continue
            percent, reset = meter.get('percent'), meter.get('resetsAt')
            if type(percent) not in (int, float) or not 0 <= percent <= 100:
                continue
            reset_at = int(reset / 1000) if type(reset) in (int, float) and 0 < reset < 4102444800000 else None
            windows.append({'window': key, 'minutes': minutes, 'used_percent': percent, 'resets_at': reset_at,
                            'limited': meter.get('limited') is True})
        if not windows:
            return {}
        limits['windows'] = windows
    budgets = data.get('budgets')
    if isinstance(budgets, list):
        remaining = []
        for budget in budgets:
            if not isinstance(budget, dict) or budget.get('coverage') != 'all' or budget.get('per') != 'set':
                continue
            limit, spent = budget.get('limit'), budget.get('spent')
            if all(type(amount) in (int, float) and 0 <= amount < float('inf') for amount in (limit, spent)):
                remaining.append(max(0, limit - spent))
        if remaining:
            limits['remaining_budget_usd'] = min(remaining)
    return {'status': 'connected', 'plan': 'Go' if go is not None else None,
            'subscription': 'active' if go is not None else 'none', 'limits': limits}


def _inspect_claude(binary, cwd):
    account = _json_result(binary, ['auth', 'status'], cwd)
    if not isinstance(account, dict) or not isinstance(account.get('loggedIn'), bool):
        return _result()
    if not account['loggedIn']:
        return _result(status='not_signed_in')
    mode = account.get('authMethod')
    status = 'subscription' if mode == 'claude.ai' else 'api_key' if mode == 'api_key' else 'connected'
    models = [_model('default', 'По умолчанию в Claude Code')]
    plan = _plan(account.get('subscriptionType'))
    return _result(status=status, plan=plan, subscription=_subscription(plan),
                   models=models, catalog='default_only')


def _inspect_cursor(binary, cwd):
    try:
        output = _run(binary, ['status'], cwd, stderr=subprocess.STDOUT)
    except (OSError, subprocess.SubprocessError):
        return _result()
    if re.search(r'\bnot logged in\b', output, re.IGNORECASE):
        return _result(status='not_signed_in')
    if re.search(r'\blogged in as\b', output, re.IGNORECASE):
        return _result(status='connected')
    return _result()


class _CodexReader:
    def __init__(self, process):
        self.process = process
        self.lines = Queue(maxsize=64)
        self.deadline = monotonic() + 12
        Thread(target=self._read_lines, daemon=True).start()

    def _read_lines(self):
        try:
            for _ in range(128):
                line = self.process.stdout.readline(512 * 1024 + 1)
                if not line or len(line) > 512 * 1024:
                    break
                self.lines.put_nowait(line)
            self.lines.put_nowait(None)
        except (OSError, ValueError, Full):
            pass

    def call(self, ident, method, params=None):
        message = {'method': method}
        if ident is not None:
            message['id'] = ident
        if params is not None:
            message['params'] = params
        self.process.stdin.write((json.dumps(message) + '\n').encode())
        self.process.stdin.flush()
        if ident is None:
            return {}
        while monotonic() < self.deadline:
            try:
                line = self.lines.get(timeout=max(0, self.deadline - monotonic()))
            except Empty:
                break
            if line is None:
                break
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if isinstance(data, dict) and data.get('id') == ident:
                result = data.get('result')
                return result if isinstance(result, dict) else {}
        raise TimeoutError('Codex app server did not respond')


def _codex_limits(result):
    limits = result.get('rateLimits')
    if not isinstance(limits, dict):
        return {}
    windows = []
    for key in ('primary', 'secondary'):
        item = limits.get(key)
        if not isinstance(item, dict):
            continue
        used = item.get('usedPercent')
        if type(used) not in (int, float) or not 0 <= used <= 100:
            continue
        duration, reset = item.get('windowDurationMins'), item.get('resetsAt')
        windows.append({'used_percent': used, 'minutes': duration if type(duration) is int and duration > 0 else None,
                        'resets_at': reset if type(reset) is int and 0 < reset < 4102444800 else None})
    return {'windows': windows} if windows else {}


def _inspect_codex(binary, cwd):
    result = _result()
    with subprocess.Popen([binary, 'app-server', '--listen', 'stdio://'], cwd=cwd,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        try:
            rpc = _CodexReader(process)
            rpc.call(0, 'initialize', {'clientInfo': {'name': 'anygamevoice', 'title': 'AnyGameVoice', 'version': '0.1.1'}})
            rpc.call(None, 'initialized')
            response = rpc.call(1, 'account/read', {'refreshToken': False})
            account = response.get('account')
            if isinstance(account, dict):
                mode = account.get('type')
                plan = _plan(account.get('planType'))
                result.update(status='subscription' if mode == 'chatgpt' else 'api_key' if mode == 'apiKey' else 'connected',
                              plan=plan, subscription=_subscription(plan))
            elif response.get('requiresOpenaiAuth') is True:
                result['status'] = 'not_signed_in'
            if result['status'] in {'subscription', 'api_key', 'connected'}:
                reply = rpc.call(2, 'model/list', {'limit': 30, 'includeHidden': False})
                result['models'] = _catalog(_model(item.get('model'), item.get('displayName'))
                                            for item in reply.get('data', []) if isinstance(item, dict) and not item.get('hidden'))
                if result['models']:
                    result['catalog'] = 'client'
            if result['status'] == 'subscription':
                result['limits'] = _codex_limits(rpc.call(3, 'account/rateLimits/read'))
        except (OSError, ValueError, TypeError):
            pass
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    return result


def _request_json(method, url, token=None, payload=None, read_timeout=5):
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    with requests.Session() as session:
        session.trust_env = False
        with session.request(method, url, headers=headers, json=payload, timeout=(3, read_timeout),
                             allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                return response.status_code, {}
            body = bytearray()
            deadline = monotonic() + read_timeout + 3
            for part in response.iter_content(65536):
                body.extend(part)
                if len(body) > 4 * 1024 * 1024 or monotonic() > deadline:
                    raise ValueError('Ответ провайдера слишком большой или загружается слишком долго.')
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError('Провайдер вернул ответ в неподдерживаемом формате.')
            return 200, data


def _get_json(url, token=None):
    return _request_json('GET', url, token)


def _router_model(ident, row):
    model = _model(ident, row.get('name'), ident == 'openrouter/free' or ident.endswith(':free'))
    prices = row.get('pricing')
    if model is None or not isinstance(prices, dict):
        return model
    try:
        prompt, completion = (float(prices[key]) * 1_000_000 for key in ('prompt', 'completion'))
    except (KeyError, TypeError, ValueError):
        return model
    if 0 <= prompt < float('inf') and 0 <= completion < float('inf'):
        model.update(input_price_usd=prompt, output_price_usd=completion)
        model['free'] = model['free'] or prompt == completion == 0
    return model


def _inspect_openrouter(api_key=''):
    root = OPENROUTER_URL
    fallback = [_model(ident, name, ident == 'openrouter/free') for ident, name in OPENROUTER_MODELS]
    token = api_key or os.getenv('OPENROUTER_API_KEY')
    result = _result(status='unknown' if token else 'key_required', models=fallback, catalog='fallback')
    try:
        status, data = _get_json(root + '/models')
        if status == 200:
            listed = {}
            for row in data.get('data', []):
                if not isinstance(row, dict):
                    continue
                ident = row.get('id')
                if isinstance(ident, str):
                    listed[ident] = row
            models = _catalog((_router_model(ident, row) for ident, row in listed.items()), limit=500)
            if models:
                result.update(models=models, catalog='provider')
    except (requests.RequestException, ValueError, TypeError):
        pass
    if token:
        try:
            status, data = _get_json(root + '/key', token)
            key = data.get('data')
            if status == 200 and isinstance(key, dict):
                result['status'] = 'api_key'
                remaining = key.get('limit_remaining')
                if type(remaining) in (float, int) and 0 <= remaining < float('inf'):
                    result['limits']['remaining_usd'] = remaining
            elif status in (401, 403):
                result['status'] = 'auth_failed'
        except (requests.RequestException, ValueError):
            pass
    return result


def inspect_provider(ident):
    if ident == 'openrouter':
        return _inspect_openrouter()
    command = DETECTABLE_AGENTS[ident][1] if ident == 'cursor-agent' else PROVIDERS[ident][1]
    binary = _executable(command)
    if not binary:
        return _result(status='not_installed')
    probe = {'opencode': _inspect_opencode, 'claude': _inspect_claude, 'codex': _inspect_codex,
             'cursor-agent': _inspect_cursor}[ident]
    try:
        with tempfile.TemporaryDirectory(prefix='agv-provider-') as cwd:
            return probe(binary, cwd)
    except OSError:
        return _result()


def _custom_url(base_url, endpoint):
    try:
        url = urlsplit(base_url.strip())
        _port = url.port
    except ValueError as error:
        raise ValueError('Укажите корректный базовый URL провайдера.') from error
    if (url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password
            or url.query or url.fragment):
        raise ValueError('Укажите базовый HTTP(S) URL без имени, пароля и параметров.')
    if url.scheme == 'http' and url.hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise ValueError('Для удалённого провайдера нужен HTTPS. HTTP доступен на localhost.')
    path = url.path.rstrip('/') + endpoint
    return urlunsplit((url.scheme, url.netloc, path, '', ''))


def custom_models(base_url, token):
    url = _custom_url(base_url, '/models')
    try:
        status, data = _get_json(url, token)
    except (requests.RequestException, ValueError) as error:
        raise ValueError('Провайдер недоступен или вернул неподдерживаемый каталог.') from error
    if status in (401, 403):
        raise ValueError('Провайдер отклонил вход. Проверьте API-ключ.')
    if status != 200 or not isinstance(data.get('data'), list):
        raise ValueError('Сервер не отдал список моделей. Проверьте базовый URL или укажите ID вручную.')
    models = _catalog(_model(row.get('id'), row.get('name')) for row in data['data'] if isinstance(row, dict))
    return _result(status='api_key' if token else 'connected', models=models, catalog='provider')


def research_completion(provider, model, prompt, system, schema, base_url='', api_key=''):
    if not MODEL_ID.fullmatch(model):
        raise ValueError('Укажите корректный ID облачной модели.')
    if provider == 'openrouter':
        url = OPENROUTER_URL + '/chat/completions'
        api_key = api_key or os.getenv('OPENROUTER_API_KEY', '')
        if not api_key:
            raise ValueError('Для исследования через OpenRouter укажите API-ключ.')
    elif provider == 'custom':
        url = _custom_url(base_url, '/chat/completions')
    else:
        raise ValueError('Этот провайдер ещё не подключён к исследованию игры.')
    try:
        status, data = _request_json('POST', url, api_key, {
            'model': model, 'stream': False,
            'messages': [
                {'role': 'system', 'content': f'{system} Верни только JSON этой схемы: {json.dumps(schema, ensure_ascii=False)}'},
                {'role': 'user', 'content': prompt},
            ],
        }, read_timeout=120)
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError('Облачный провайдер недоступен или вернул неподдерживаемый ответ.') from exc
    if status in (401, 403):
        raise ValueError('Провайдер отклонил вход. Проверьте API-ключ и доступ к модели.')
    if status == 429:
        raise ValueError('Провайдер сообщил об исчерпании лимита. Проверьте квоту или повторите позже.')
    if status != 200:
        raise RuntimeError(f'Облачный провайдер не выполнил запрос (HTTP {status}). Проверьте модель и тариф.')
    try:
        content = data['choices'][0]['message']['content'].strip()
    except (IndexError, KeyError, TypeError, AttributeError) as exc:
        raise RuntimeError('Облачная модель не вернула текст исследования.') from exc
    fenced = re.fullmatch(r'```(?:json)?\s*(.+?)\s*```', content, flags=re.DOTALL | re.IGNORECASE)
    return fenced[1] if fenced else content
