"""Automatic installation: preflight, verification, cancellation and studio actions."""
import hashlib
import itertools
from pathlib import Path
import threading
import time
from unittest.mock import Mock

import pytest

from app.studio import ui_server
from app.core import installation
from app.core.game_detector.engines import renpy_mod
from tests.audio_fixture import wav_bytes


@pytest.fixture
def scene(tmp_path):
    root = tmp_path / 'game-root'
    (root / 'game').mkdir(parents=True)
    (root / 'game/script.rpy').write_text('label start:\n    e "Привет."\n', encoding='utf-8')
    out = tmp_path / 'audio'
    out.mkdir()
    audio = wav_bytes()
    (out / 'line.wav').write_bytes(audio)
    result = {'status': 'done', 'game_path': str(root), 'out': str(out), 'total': 1, 'succeeded': 1,
              'failed': 0, 'cached': 0, 'lines': [{'id': 'line', 'source_file': 'script.rpy', 'line_no': 2,
              'text': 'Привет.', 'metadata': {}, 'filename': 'line.wav', 'status': 'done',
              'sha256': hashlib.sha256(audio).hexdigest()}]}
    rows = [{'Identifier': 'start_1234abcd', 'Filename': 'game/script.rpy', 'Line Number': '2', 'Dialogue': 'Привет.'}]
    sdk = tmp_path / 'sdk/renpy.sh'
    sdk.parent.mkdir()
    sdk.write_text('#!/bin/sh\n')
    return root, result, rows, sdk


@pytest.fixture
def registry(monkeypatch):
    monkeypatch.setattr(ui_server, '_JOBS', {})
    monkeypatch.setattr(ui_server, '_CANCEL', {})
    monkeypatch.setattr(ui_server, '_JOB_SEQ', itertools.count(1))
    monkeypatch.setattr(ui_server, '_MOD_ACTION', threading.Lock())
    return ui_server._JOBS


def wait_job(jid):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = ui_server.mod_job_status(jid)
        if job['status'] not in ui_server.ACTIVE:
            return job
        time.sleep(.01)
    pytest.fail('Automatic job did not finish')


def route(path):
    return next(item.endpoint for item in ui_server.create_app().routes if getattr(item, 'path', '') == path)


def test_sdk_discovery_configuration_and_version_order(tmp_path, monkeypatch):
    monkeypatch.delenv('AGV_RENPY_SDK', raising=False)
    monkeypatch.setattr(installation, 'user_home', lambda: tmp_path / 'state')
    monkeypatch.setattr(installation, 'project_root', lambda: tmp_path / 'repo')
    for version in ['8.9.0', '8.10.0']:
        path = tmp_path / 'tools' / f'renpy-{version}-sdk/renpy.sh'
        path.parent.mkdir(parents=True)
        path.write_text('launcher')
    assert installation.discover_renpy_sdk().parent.name == 'renpy-8.10.0-sdk'
    explicit = tmp_path / 'tools/renpy-8.9.0-sdk'
    monkeypatch.setenv('AGV_RENPY_SDK', str(explicit))
    assert installation.discover_renpy_sdk().parent == explicit
    with pytest.raises(ValueError):
        installation.discover_renpy_sdk(tmp_path / 'missing')


def test_arm_sdk_is_discovered_in_user_tools(tmp_path, monkeypatch):
    monkeypatch.delenv('AGV_RENPY_SDK', raising=False)
    monkeypatch.setattr(installation, 'user_home', lambda: tmp_path / 'state')
    monkeypatch.setattr(installation, 'project_root', lambda: tmp_path / 'repo')
    launcher = tmp_path / 'state/tools/renpy-8.5.3-sdkarm/renpy.sh'
    launcher.parent.mkdir(parents=True)
    launcher.write_text('launcher')
    assert installation.discover_renpy_sdk() == launcher


def test_missing_sdk_stops_before_model_selection(scene, monkeypatch):
    from app.core.automatic import automatic_settings
    root, _, _, _ = scene
    monkeypatch.delenv('AGV_RENPY_SDK', raising=False)
    monkeypatch.setattr(installation, 'user_home', lambda: root / 'state')
    monkeypatch.setattr(installation, 'project_root', lambda: root / 'repo')
    model_plan = Mock()
    monkeypatch.setattr('app.core.scanner.model_planner.build_plan', model_plan)
    with pytest.raises(ValueError, match='SDK'):
        automatic_settings(root)
    model_plan.assert_not_called()


def test_preflight_rejects_incomplete_dialogue_coverage(scene, monkeypatch):
    root, _, rows, sdk = scene
    monkeypatch.setattr(renpy_mod, 'export_dialogue_ids', lambda *args: rows + [
        {'Identifier': 'other_1234', 'Filename': 'game/script.rpy', 'Line Number': '4', 'Dialogue': 'Другая реплика.'}])
    with pytest.raises(ValueError, match='до записи'):
        installation.preflight({'path': str(root), 'install_engine': 'renpy', 'renpy_sdk': str(sdk)})


def test_preflight_rejects_foreign_mod_before_export(scene, monkeypatch):
    root, _, _, sdk = scene
    target = root / 'game/anygamevoice'
    target.mkdir()
    (target / 'notes.txt').write_text('user data')
    export = Mock()
    monkeypatch.setattr(renpy_mod, 'export_dialogue_ids', export)
    with pytest.raises(ValueError, match='сторонние'):
        installation.preflight({'path': str(root), 'install_engine': 'renpy', 'renpy_sdk': str(sdk)})
    export.assert_not_called()


def test_automatic_job_installs_and_verifies(scene, registry, monkeypatch):
    root, result, rows, sdk = scene
    monkeypatch.setattr(renpy_mod, 'export_dialogue_ids', lambda *args: rows)
    monkeypatch.setattr('app.core.pipeline.run_batch', lambda *args, **kwargs: result)
    stages = []
    original = installation.verify
    def verify(data):
        stages.append(registry[1]['stage'])
        return original(data)
    monkeypatch.setattr(installation, 'verify', verify)
    jid = ui_server.start_mod_job({'path': str(root), 'out': result['out'], 'install_engine': 'renpy', 'renpy_sdk': str(sdk)})
    job = wait_job(jid)
    assert job['status'] == 'done' and stages == ['verifying']
    assert job['result']['installation']['verification']['status'] == 'ok'
    assert (root / 'game/anygamevoice/voice/start_1234abcd.wav').is_file()
    assert (root / 'game/script.rpy').read_text() == 'label start:\n    e "Привет."\n'


def test_preflight_error_never_starts_synthesis(scene, registry, monkeypatch):
    root, result, rows, sdk = scene
    monkeypatch.setattr(renpy_mod, 'export_dialogue_ids', Mock(side_effect=RuntimeError('SDK failed')))
    generate = Mock()
    monkeypatch.setattr('app.core.pipeline.run_batch', generate)
    jid = ui_server.start_mod_job({'path': str(root), 'out': result['out'], 'install_engine': 'renpy', 'renpy_sdk': str(sdk)})
    assert wait_job(jid)['status'] == 'failed'
    generate.assert_not_called()
    assert not (root / 'game/anygamevoice').exists()


def test_verification_failure_keeps_audio_and_disable_action(scene, registry, monkeypatch):
    root, result, rows, sdk = scene
    monkeypatch.setattr(renpy_mod, 'export_dialogue_ids', lambda *args: rows)
    monkeypatch.setattr('app.core.pipeline.run_batch', lambda *args, **kwargs: result)
    monkeypatch.setattr(installation, 'verify', lambda data: {'status': 'stale'})
    jid = ui_server.start_mod_job({'path': str(root), 'out': result['out'], 'install_engine': 'renpy', 'renpy_sdk': str(sdk)})
    job = wait_job(jid)
    assert job['status'] == 'partial'
    assert job['result']['installation']['status'] == 'installed'
    assert 'error' in job['result']['installation']
    assert (Path(result['out']) / 'line.wav').is_file()
    disabled = route('/api/studio/mod/{job_id}/disable')(jid)
    assert disabled['status'] == 'disabled' and not (root / 'game/anygamevoice').exists()


def test_cancel_after_preflight_does_not_start_recording(scene, registry, monkeypatch):
    root, result, _, sdk = scene
    def cancel(params):
        ui_server._CANCEL[1].set()
    monkeypatch.setattr(installation, 'preflight', cancel)
    generate = Mock()
    monkeypatch.setattr('app.core.pipeline.run_batch', generate)
    jid = ui_server.start_mod_job({'path': str(root), 'out': result['out'], 'install_engine': 'renpy', 'renpy_sdk': str(sdk)})
    assert wait_job(jid)['status'] == 'cancelled'
    generate.assert_not_called()


def test_verify_route_marks_modified_mod_partial(scene, registry):
    root, result, rows, _ = scene
    result['installation'] = renpy_mod.install_mod(result, rows=rows)
    registry[1] = {'result': result, 'status': 'done'}
    (root / 'game/anygamevoice/voice/start_1234abcd.wav').write_bytes(b'changed')
    response = route('/api/studio/mod/{job_id}/verify')(1)
    assert response['status'] == 'partial' and response['installation']['verification']['status'] == 'failed'
    with pytest.raises(ValueError):
        route('/api/studio/mod/{job_id}/disable')(1)
    assert (root / 'game/anygamevoice').is_dir()


def test_verification_blocks_new_jobs_and_conflicting_actions(scene, registry, monkeypatch):
    root, result, rows, _ = scene
    result['installation'] = renpy_mod.install_mod(result, rows=rows)
    registry[1] = {'result': result, 'status': 'done'}
    def verify(data):
        with pytest.raises(ValueError, match='Дождитесь'):
            ui_server.start_mod_job({'path': str(root), 'out': result['out']})
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            route('/api/studio/mod/{job_id}/disable')(1)
        assert exc.value.status_code == 409
        return {'status': 'ok'}
    monkeypatch.setattr(installation, 'verify', verify)
    assert route('/api/studio/mod/{job_id}/verify')(1)['status'] == 'done'
    assert not ui_server._MOD_ACTION.locked()


def test_renpy_launch_uses_verified_installed_sdk(scene, monkeypatch):
    root, result, rows, sdk = scene
    result['installation'] = {**renpy_mod.install_mod(result, rows=rows), 'sdk': str(sdk)}
    monkeypatch.setattr(renpy_mod, 'export_dialogue_ids', lambda *args: rows)
    popen = Mock()
    monkeypatch.setattr('subprocess.Popen', popen)
    assert installation.launch(result)['status'] == 'requested'
    assert popen.call_args.args[0] == [str(sdk), str(root)]


def test_demo_copy_keeps_shipped_sources_clean(tmp_path, monkeypatch):
    sdk = tmp_path / 'sdk'
    (sdk / 'gui/game').mkdir(parents=True)
    (sdk / 'renpy.sh').write_text('launcher')
    (sdk / 'gui/game/options.rpy').write_text('define config.name = "Template"\ndefine config.save_directory = "gui-7"\n')
    monkeypatch.setattr(installation, 'user_home', lambda: tmp_path / 'state')
    from app.utils.paths import resource_path
    sources = {str(path): path.read_bytes() for path in resource_path('examples', 'renpy').rglob('*') if path.is_file()}
    root = installation.demo_project(sdk)
    assert root == installation.demo_project(sdk)
    assert (root / 'game/chapters/radio.rpy').is_file()
    assert 'anygamevoice-demo' in (root / 'game/options.rpy').read_text()
    assert all(Path(path).read_bytes() == content for path, content in sources.items())
