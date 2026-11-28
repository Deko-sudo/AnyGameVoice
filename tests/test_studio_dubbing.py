"""Exercise the public dubbing routes with deterministic translation and audio."""

import json
import time
from pathlib import Path

import pytest

from app.core import cloud_providers
from app.studio.core.tts import generator
from tests.audio_fixture import wav_bytes


@pytest.fixture
def client():
    pytest.importorskip('httpx')
    from fastapi.testclient import TestClient
    from app.ui_server import create_app

    with TestClient(create_app()) as session:
        yield session


def finish_job(client, route, settings, *, status_route=None):
    response = client.post(route, json=settings)
    response.raise_for_status()
    started = response.json()
    assert 'temporary-key' not in response.text
    url = f'{status_route or route}/{started["job_id"]}'
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        response = client.get(url)
        response.raise_for_status()
        assert 'temporary-key' not in response.text
        job = response.json()
        if job['status'] not in ('running', 'queued'):
            return job
        time.sleep(.02)
    pytest.fail(f'Job did not finish at {url}')


@pytest.fixture
def project(tmp_path):
    game = tmp_path / 'sample' / 'game'
    game.mkdir(parents=True)
    (game / 'script.rpy').write_text(
        'label start:\n' + ''.join(f'    e "Line {i}."\n' for i in range(4)), encoding='utf-8',
    )
    return dict(path=str(game.parent), out=str(tmp_path / 'out'), translate_to='ru', source_lang='en',
                provider='custom', translation_model='text-one', base_url='http://localhost/v1',
                api_key='temporary-key')


@pytest.fixture
def translations(monkeypatch):
    calls = []

    def translate(provider, model, prompt, system, base_url, api_key):
        assert (provider, base_url, api_key) == ('custom', 'http://localhost/v1', 'temporary-key')
        original = prompt.splitlines()[-1]
        calls.append((model, original))
        if model == 'broken':
            raise RuntimeError(api_key)
        return 'Реплика ' + original[-2]

    monkeypatch.setattr(cloud_providers, 'chat_completion', translate)
    return calls


@pytest.mark.parametrize('automatic_trial', [False, True])
def test_trial_then_full_dub(tmp_path, monkeypatch, client, project, translations, automatic_trial):
    spoken = []

    def speak(text, dest, **options):
        assert text.startswith('Реплика') and options['language'] == 'ru'
        spoken.append(text)
        Path(dest).write_bytes(wav_bytes())

    monkeypatch.setattr(generator, 'validate_synthesis', lambda *_: None)
    monkeypatch.setattr(generator, 'generate_voice_to_file', speak)
    route = '/api/studio/mod'
    if automatic_trial:
        selection = dict(out=project['out'], language='en')
        job = finish_job(client, '/api/studio/auto', {**project, 'selection': selection, 'trial': True},
                         status_route=route)
    else:
        job = finish_job(client, route, {**project, 'trial': True})
    sample = job['result']
    assert sample['succeeded'] == 3 and 'installation' not in sample
    assert not (Path(project['path']) / 'game' / 'anygamevoice').exists()
    assert finish_job(client, route, project)['result']['cached'] == 3
    assert translations == [('text-one', f'Line {i}.') for i in range(4)]
    assert len(spoken) == 4
    assert finish_job(client, route, {**project, 'translation_model': 'text-two'})['result']['cached'] == 0
    assert finish_job(client, route, {**project, 'translation_model': 'broken'})['status'] == 'failed'
    assert len(spoken) == 8
    assert all('temporary-key' not in f.read_text() for f in tmp_path.rglob('*.json'))


def test_legacy_mod_translation(client, project, translations, monkeypatch):
    from app.core.tts import generator as legacy_generator

    def speak(line, dest, **options):
        assert line.tts_text == 'Реплика ' + line.source_text[-2]
        assert line.target_lang == 'ru'
        Path(dest).write_bytes(wav_bytes())

    monkeypatch.setattr(legacy_generator, 'generate_voice_to_file', speak)
    job = finish_job(client, '/api/mod', project)
    assert job['succeeded'] == 4
    assert translations == [('text-one', f'Line {i}.') for i in range(4)]
    failed = finish_job(client, '/api/mod', {**project, 'translation_model': 'broken'})
    assert failed['failed'] == 4
    assert 'temporary-key' not in json.dumps(failed)
    assert 'temporary-key' not in (Path(project['out']) / 'report.json').read_text()


@pytest.mark.parametrize('target', 'en zh hi es ar fr bn pt id ur ru de ja pcm arz mr vi te sw ha'.split())
def test_translation_target_then_dub(client, project, monkeypatch, target):
    from app.core.dubbing_languages import LANGUAGES

    display_name, prompt_name = LANGUAGES[target]
    assert client.get('/api/studio/voices').json()['translation_languages'][target] == display_name
    originals = []

    def translate(provider, model, prompt, system, base_url, api_key):
        assert (prompt_name if target != 'ru' else 'русский') in prompt
        original = prompt.splitlines()[-1]
        originals.append(original)
        return f'{target} {original}'

    monkeypatch.setattr(cloud_providers, 'chat_completion', translate)
    # The text action must work on a machine with no TTS backend or voice.
    monkeypatch.setattr(generator, 'validate_synthesis', lambda *_: pytest.fail('Text mode loaded TTS'))
    route = '/api/studio/mod'
    settings = {**project, 'translate_to': target, 'language_subdir': target != 'ru'}
    job = finish_job(client, route, {**settings, 'text_only': True})
    result = job['result']
    assert result['text_only'] and result['status'] == 'done' and result['succeeded'] == 4
    assert not list(Path(result['out']).glob('*.wav'))
    assert Path(result['out']).name == f'translations-{target}'
    assert [row['text'] for row in result['lines']] == [f'{target} Line {i}.' for i in range(4)]
    assert client.get(f"/api/studio/mod/{job['id']}/audio/{result['lines'][0]['id']}").status_code == 404
    assert 'temporary-key' not in (Path(result['out']) / 'anygamevoice.json').read_text()

    def speak(text, dest, **settings):
        assert text.startswith(target + ' ') and settings['language'] == target
        Path(dest).write_bytes(wav_bytes())

    monkeypatch.setattr(generator, 'validate_synthesis', lambda *_: None)
    monkeypatch.setattr(generator, 'generate_voice_to_file', speak)
    dubbed = finish_job(client, route, {**settings, 'trial': True})['result']
    assert dubbed['succeeded'] == 3
    expected_dir = Path(project['out']) if target == 'ru' else Path(project['out']) / f'dub-{target}'
    assert Path(dubbed['out']) == expected_dir / '.agv-trial'
    assert originals == [f'Line {i}.' for i in range(4)]
