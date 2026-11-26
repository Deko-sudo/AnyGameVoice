"""Public Arena scores for Russian text with an offline snapshot."""

from datetime import date
import json
import os
import re
from threading import Lock
from time import monotonic, time
from urllib.parse import urlencode

import requests

from app.core.cloud_providers import _request_json
from app.utils.atomic import atomic_json
from app.utils.paths import user_home


ARENA_PAGE = 'https://arena.ai/leaderboard/chat/text/russian'
ARENA_API = 'https://datasets-server.huggingface.co/filter?' + urlencode({
    'dataset': 'lmarena-ai/leaderboard-dataset',
    'config': 'text',
    'split': 'latest',
    'where': '"category"=\'russian\'',
    'orderby': '"rank"',
    'length': 100,
})
CACHE_SECONDS = 6 * 60 * 60
RETRY_SECONDS = 60
_LOCK = Lock()
_last_attempt = float('-inf')
_memory_snapshot = None


def _read_ranking(payload):
    rows = payload.get('rows')
    if not isinstance(rows, list):
        raise ValueError('Expected Arena rows')
    snapshots = {}
    for entry in rows[:100]:
        row = entry.get('row') if isinstance(entry, dict) else None
        if not isinstance(row, dict) or row.get('category') != 'russian':
            continue
        name, rank, score = row.get('model_name'), row.get('rank'), row.get('rating')
        if (
            not isinstance(name, str) or not name.strip() or len(name) > 160
            or type(rank) not in (int, float) or not 1 <= rank <= 100 or int(rank) != rank
            or type(score) not in (int, float) or not 0 < score < 10_000
        ):
            continue
        try:
            published = date.fromisoformat(row.get('leaderboard_publish_date')).isoformat()
        except (TypeError, ValueError):
            continue
        snapshots.setdefault(published, []).append({'name': name.strip(), 'rank': int(rank), 'score': round(score)})
    if not snapshots:
        raise ValueError('No Russian scores in the Arena response')
    published = max(snapshots)
    models = sorted(snapshots[published], key=lambda model: (model['rank'], -model['score']))
    return {'published': published, 'models': models, 'fetched_at': time()}


def _read_cache(path):
    try:
        if path.stat().st_size > 128 * 1024:
            return None
        document = json.loads(path.read_text(encoding='utf-8'))
        fetched_at = document.get('fetched_at')
        published = document.get('published')
        models = document.get('models')
        if (type(fetched_at) in (float, int) and 0 < fetched_at < 4_102_444_800
                and isinstance(models, list) and models and date.fromisoformat(published).isoformat() == published):
            return document
    except (AttributeError, OSError, TypeError, ValueError):
        pass
    return None


def russian_rankings():
    global _last_attempt, _memory_snapshot
    path = user_home() / 'rankings' / 'arena-russian.json'
    metadata = {'url': ARENA_PAGE, 'source': 'Arena · русский текст'}
    with _LOCK:
        snapshot = _memory_snapshot or _read_cache(path)
        if snapshot and 0 <= time() - snapshot['fetched_at'] < CACHE_SECONDS:
            return {**snapshot, **metadata, 'state': 'cached'}
        if monotonic() - _last_attempt >= RETRY_SECONDS:
            _last_attempt = monotonic()
            try:
                status, payload = _request_json('GET', ARENA_API, read_timeout=22)
                if status == 200:
                    fresh = _read_ranking(payload)
                    if snapshot is None or fresh['published'] >= snapshot['published']:
                        _memory_snapshot = fresh
                        try:
                            path.parent.mkdir(parents=True, exist_ok=True)
                            atomic_json(path, fresh)
                        except OSError:
                            pass
                        return {**fresh, **metadata, 'state': 'online'}
            except (requests.RequestException, ValueError):
                pass
        if snapshot:
            return {**snapshot, **metadata, 'state': 'offline'}
        return {**metadata, 'state': 'unavailable', 'models': []}


def local_ifbench(api_key=''):
    """Get current instruction-following scores directly with the user's LLM Stats key."""
    api_key = api_key.strip() or os.getenv('LLM_STATS_API_KEY', '').strip()
    result = {'source': 'LLM Stats', 'benchmark': 'IFBench', 'url': 'https://llm-stats.com/benchmarks/ifbench'}
    if not api_key:
        return {**result, 'state': 'key_required', 'models': []}
    url = 'https://api.zeroeval.com/stats/v1/scores?' + urlencode({'benchmark': 'ifbench', 'limit': 500})
    try:
        status, payload = _request_json('GET', url, api_key, read_timeout=12)
    except (requests.RequestException, ValueError):
        return {**result, 'state': 'unavailable', 'models': []}
    if status in (401, 403):
        return {**result, 'state': 'auth_failed', 'models': []}
    if status != 200 or not isinstance(payload.get('scores'), list):
        return {**result, 'state': 'unavailable', 'models': []}
    models = {}
    for row in payload['scores'][:500]:
        if not isinstance(row, dict) or str(row.get('benchmark_id', '')).lower() != 'ifbench':
            continue
        name, value, maximum, scored = row.get('model_name'), row.get('score'), row.get('max_score'), row.get('scored_at')
        if (not isinstance(name, str) or not 0 < len(name) <= 160
                or type(value) not in (int, float) or type(maximum) not in (int, float)
                or not 0 <= value <= maximum or not 0 < maximum <= 10000):
            continue
        try:
            day = date.fromisoformat(scored[:10]).isoformat()
        except (ValueError, TypeError):
            continue
        entry = {'name': name, 'score': round(value / maximum * 100, 1), 'date': day,
                 'verified': row.get('verified') is True, 'self_reported': row.get('is_self_reported') is True}
        key = re.sub(r'[^a-z0-9]', '', name.lower())
        if key and (key not in models or day > models[key]['date']):
            models[key] = entry
    return {**result, 'state': 'online' if models else 'empty', 'models': list(models.values())}
