"""Local studio API: extraction, model discovery, previews and bounded batch jobs."""

from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
import itertools
from pathlib import Path
import threading
from urllib.parse import urlparse

from app.core.tts.reference import VoiceBlend
from app.utils.paths import resource_path, user_home

INDEX = resource_path('ui', 'index.html')
_JOBS = {}
_JOB_SEQ = itertools.count(1)
_JOBS_LOCK = threading.Lock()
_CANCEL = {}
_PREVIEW = threading.Lock()
_RESEARCH = threading.Lock()
_MOD_ACTION = threading.Lock()
ACTIVE = {'queued', 'running', 'cancelling'}
__all__ = ['create_app', 'start_mod_job', 'mod_job_status']


def _setup_busy():
    from app.core.setup_components import is_busy
    return is_busy()


def start_mod_job(params: dict) -> int:
    """Start one batch at a time, with progress and explicit terminal status."""
    from app.core.pipeline import run_batch

    if params.get('base_url'):
        from app.core.cloud_providers import _custom_url
        _custom_url(params['base_url'], '')
    with _JOBS_LOCK:
        if _setup_busy():
            raise ValueError('Дождитесь завершения подготовки компонентов.')
        if any(job['status'] in ACTIVE for job in _JOBS.values()):
            raise ValueError('A batch is already running. Wait or cancel it first.')
        if _RESEARCH.locked():
            raise ValueError('Исследование ещё выполняется. Дождитесь его завершения.')
        if _PREVIEW.locked():
            raise ValueError('A voice preview is running. Wait for it to finish.')
        if _MOD_ACTION.locked():
            raise ValueError('Дождитесь проверки или отключения установленного мода.')
        job_id = next(_JOB_SEQ)
        install_engine = params.get('install_engine') or ('source_lostcoast' if params.get('install_source') else None)
        _JOBS[job_id] = {'id': job_id, 'game_path': str(Path(params['path']).expanduser().resolve()),
                         'trial': bool(params.get('trial')), 'text_only': bool(params.get('text_only')), 'install_engine': install_engine, 'stage': 'preparing' if install_engine else 'synthesis', 'status': 'running', 'total': 0,
                         'succeeded': 0, 'failed': 0, 'cached': 0, 'error': '', 'result': None}
        _CANCEL[job_id] = threading.Event()
        # Keep only a bounded history; audio is still present in the output folder.
        for old in list(_JOBS)[:-20]:
            if _JOBS[old]['status'] not in ACTIVE:
                _JOBS.pop(old)
                _CANCEL.pop(old, None)

    def progress(data):
        with _JOBS_LOCK:
            _JOBS[job_id].update({key: data[key] for key in ('total', 'succeeded', 'failed', 'cached')})

    def run():
        try:
            from app.core import installation
            if install_engine:
                installation.preflight(params)
            if _CANCEL[job_id].is_set():
                with _JOBS_LOCK:
                    _JOBS[job_id].update(status='cancelled', stage='complete')
                return
            with _JOBS_LOCK:
                _JOBS[job_id]['stage'] = 'synthesis'
            result = run_batch(params['path'], params['out'], voice=params.get('voice', ''),
                             engine=params.get('engine', 'piper'), workers=params.get('workers', 2),
                             emotion=params.get('emotion', 'neutral'), translate_to=params.get('translate_to', ''),
                             provider=params.get('provider', 'ollama'), language=params.get('language', 'en'),
                             character_voices=params.get('character_voices', {}),
                             on_progress=progress, cancel_event=_CANCEL[job_id],
                             voice_blend=params.get('voice_blend'), trial=params.get('trial', False),
                             text_only=params.get('text_only', False), language_subdir=params.get('language_subdir', False),
                             api_format=params.get('api_format', 'openai_chat'),
                             source_lang=params.get('source_lang', 'auto'), translation_model=params.get('translation_model', ''),
                             base_url=params.get('base_url', ''), api_key=params.get('api_key', ''))
            if not isinstance(result, dict) or result.get('status') not in {'done', 'partial', 'failed', 'cancelled'}:
                raise RuntimeError('The pipeline did not return a valid batch result.')
            if install_engine and result['status'] == 'done' and not _CANCEL[job_id].is_set():
                from app.utils.atomic import atomic_json
                with _JOBS_LOCK:
                    _JOBS[job_id]['stage'] = 'installing'
                try:
                    result['installation'] = installation.install(result, params, _CANCEL[job_id])
                    with _JOBS_LOCK:
                        _JOBS[job_id]['stage'] = 'verifying'
                    checked = installation.verify(result)
                    result['installation']['verification'] = checked
                    if checked.get('status') != 'ok':
                        raise ValueError('Проверка установленного мода не пройдена. Проверьте файлы или отключите мод.')
                except Exception as exc:
                    report = result.setdefault('installation', {'status': 'failed', 'engine': install_engine})
                    report['error'] = str(exc)[:500]
                    result['status'] = 'cancelled' if _CANCEL[job_id].is_set() else 'partial'
            if install_engine and result['status'] == 'done' and _CANCEL[job_id].is_set() and 'installation' not in result:
                result['status'] = 'cancelled'
            if install_engine:
                from app.utils.atomic import atomic_json
                atomic_json(Path(result['out']) / 'anygamevoice.json', result)
            with _JOBS_LOCK:
                _JOBS[job_id].update(status=result['status'], stage='complete', result=result,
                                      total=result['total'], succeeded=result['succeeded'], failed=result['failed'],
                                      cached=result.get('cached', 0))
        except Exception as exc:
            with _JOBS_LOCK:
                _JOBS[job_id].update(status='cancelled' if _CANCEL[job_id].is_set() else 'failed', stage='complete', error=str(exc)[:500])

    threading.Thread(target=run, daemon=True, name=f'agv-mod-{job_id}').start()
    return job_id


def mod_job_status(job_id: int) -> dict:
    """Return a snapshot. Only completed results contain per-line output metadata."""
    with _JOBS_LOCK:
        return dict(_JOBS[job_id])


def create_app():
    """Build the local API and serve offline frontend assets."""
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse, JSONResponse, Response
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
    from typing import Literal

    class FolderRequest(BaseModel):
        path: str = Field(min_length=1, max_length=4096)
        limit: int = Field(default=1000, ge=1, le=10000)

    class ModelRequest(BaseModel):
        language: str = Field(default='ru', min_length=2, max_length=12)

    class TranslationSettings(BaseModel):
        source_lang: str = Field(default='auto', max_length=12)
        translate_to: str = Field(default='', max_length=12)
        provider: Literal['ollama', 'openai', 'anthropic', 'groq', 'mistral', 'deepseek', 'openrouter', 'custom', 'opencode'] = 'ollama'
        translation_model: str = Field(default='', max_length=200)
        base_url: str = Field(default='', max_length=2048)
        api_key: str = Field(default='', max_length=4096, repr=False)
        api_format: Literal['openai_chat', 'openai_responses', 'anthropic', 'gemini', 'ollama'] = 'openai_chat'
        trial: bool = False
        language_subdir: bool = False

    class SelectedAutoSettings(BaseModel):
        voice: str = Field(default='', max_length=4096)
        engine: Literal['piper', 'xtts', 'bark', 'silero'] = 'piper'
        emotion: Literal['neutral', 'happy', 'sad', 'angry', 'whisper', 'shouting'] = 'neutral'
        language: str = Field(default='en', min_length=2, max_length=12)
        out: str = Field(min_length=1, max_length=4096)
        workers: int = Field(default=2, ge=1, le=4)
        character_voices: dict[str, str] = Field(default_factory=dict, max_length=200)
        voice_blend: VoiceBlend | None = None

    class AutoRequest(FolderRequest, TranslationSettings):
        sdk: str = Field(default='', max_length=4096)
        selection: SelectedAutoSettings | None = None

    class SetupRequest(BaseModel):
        language: str = Field(default='ru', min_length=2, max_length=12)
        engine: Literal['renpy', 'source_lostcoast', 'rpgmaker', 'godot'] = 'renpy'
        sdk: str = Field(default='', max_length=4096)
        components: list[Literal['piper', 'voice', 'sdk', 'ffmpeg']] = Field(default_factory=list, max_length=4)
        allow_downloads: bool = False

    class ResearchSource(BaseModel):
        title: str = Field(default='Мой источник', max_length=200)
        url: str = Field(min_length=1, max_length=2000)
        snippet: str = Field(min_length=1, max_length=4000)

    class ResearchRequest(BaseModel):
        path: str = Field(min_length=1, max_length=4096)
        title: str = Field(min_length=1, max_length=200)
        model: str = Field(min_length=1, max_length=200)
        search: Literal['none', 'brave', 'tavily'] = 'none'
        sources: list[ResearchSource] = Field(default_factory=list, max_length=8)
        provider: Literal['local', 'openrouter', 'custom'] = 'local'
        base_url: str = Field(default='', max_length=2048)
        api_key: str = Field(default='', max_length=4096, repr=False)

    class ReferenceRequest(BaseModel):
        path: str = Field(min_length=1, max_length=4096)

    class SynthesisRequest(BaseModel):
        voice: str = Field(default='', max_length=4096)
        engine: Literal['piper', 'xtts', 'bark', 'silero'] = 'piper'
        emotion: Literal['neutral', 'happy', 'sad', 'angry', 'whisper', 'shouting'] = 'neutral'
        language: str = Field(default='en', min_length=2, max_length=12)
        voice_blend: VoiceBlend | None = None

    class ModRequest(SynthesisRequest, TranslationSettings):
        text_only: bool = False
        path: str = Field(min_length=1, max_length=4096)
        out: str = Field(min_length=1, max_length=4096)
        workers: int = Field(default=2, ge=1, le=4)
        character_voices: dict[str, str] = Field(default_factory=dict, max_length=200)

    class PreviewRequest(SynthesisRequest):
        text: str = Field(min_length=1, max_length=2000)

    app = FastAPI(title='AnyGameVoice', version='0.1.1')

    @app.middleware('http')
    async def local_requests(request: Request, call_next):
        # The UI and API share one origin. Reject browser requests originating elsewhere.
        origin = request.headers.get('origin')
        expected = urlparse(str(request.base_url))
        host = request.url.hostname
        if host not in {'127.0.0.1', 'localhost', '[::1]', '::1', 'testserver'}:
            return JSONResponse({'detail': 'Local access only.'}, status_code=403)
        if origin and origin != f'{expected.scheme}://{expected.netloc}':
            return JSONResponse({'detail': 'Cross-origin requests are not allowed.'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "font-src 'self'; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        )
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=400)

    @app.exception_handler(FileNotFoundError)
    async def missing_file(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=400)

    @app.exception_handler(PermissionError)
    async def permission_error(request, exc):
        return JSONResponse({'detail': 'Нет доступа к выбранной папке. Проверьте права доступа и выберите папку игры.'}, status_code=403)

    @app.exception_handler(RuntimeError)
    async def runtime_error(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=400)

    @app.get('/')
    def index():
        return FileResponse(INDEX)

    @app.get('/api/studio/health')
    def health():
        return {'status': 'ok', 'app': 'AnyGameVoice', 'version': '0.1.1'}

    @app.get('/api/studio/demo')
    def demo(sdk: str = ''):
        from app.core.installation import demo_project
        return {'path': str(demo_project(sdk or None)),
                'out': str(user_home() / 'exports' / 'night-signal')}

    @app.get('/api/studio/folders')
    def folders(path: str = ''):
        """Browse local directories without uploading game files to the browser."""
        if len(path) > 4096:
            raise HTTPException(400, 'Путь слишком длинный.')
        try:
            folder = Path(path).expanduser().resolve() if path.strip() else Path.home()
            if not folder.is_dir():
                raise HTTPException(400, 'Папка не найдена. Проверьте полный путь.')
            entries = []
            for child in folder.iterdir():
                if child.name.startswith('.'):
                    continue
                try:
                    if child.is_dir():
                        entries.append({'name': child.name, 'path': str(child)})
                except OSError:
                    continue
        except (OSError, ValueError, RuntimeError) as exc:
            raise HTTPException(400, 'Не удалось прочитать папку. Проверьте путь и права доступа.') from exc
        entries.sort(key=lambda item: item['name'].casefold())
        return {'path': str(folder), 'parent': str(folder.parent) if folder.parent != folder else None,
                'folders': entries}

    @app.post('/api/studio/scan')
    def scan(payload: FolderRequest):
        from app.studio.core.game_detector.detector import scan_game_folder
        from app.studio.core.scanner.hardware import recommend_settings, scan_hardware
        from app.core.scanner.permissions import check_path_access
        hw = scan_hardware()
        folder = scan_game_folder(str(Path(payload.path).expanduser()))
        return {'hardware': hw, 'recommend': recommend_settings(hw),
                'access': check_path_access(payload.path), 'folder': folder}

    @app.post('/api/studio/extract')
    def extract(payload: FolderRequest):
        from app.studio.core.extractor.dialogue_extractor import extract_dialogue
        from app.studio.core.game_detector.detector import detect_engine
        path = Path(payload.path).expanduser().resolve()
        if not path.is_dir():
            raise ValueError('Game folder does not exist.')
        lines = extract_dialogue(str(path))
        engine = detect_engine(str(path))
        return {'total': len(lines), 'engine': engine, 'path': str(path),
                'truncated': len(lines) > payload.limit,
                'characters': [{'name': name, 'count': count} for name, count in Counter(x.speaker for x in lines).items()],
                'lines': [asdict(line) for line in lines[:payload.limit]],
                'suggested_out': str(user_home() / 'exports' / path.name)}

    @app.post('/api/studio/prepare')
    def prepare(payload: FolderRequest):
        from app.core.automatic import prepare_game
        return prepare_game(payload.path)

    @app.post('/api/studio/auto')
    def automatic(payload: AutoRequest):
        if _setup_busy():
            raise HTTPException(409, 'Дождитесь завершения подготовки компонентов.')
        from app.core.automatic import automatic_settings
        params = automatic_settings(payload.path, sdk=payload.sdk or None, target_lang=payload.translate_to, trial=payload.trial,
                                    selection=payload.selection.model_dump() if payload.selection is not None else None)
        params.update(payload.model_dump(include=set(TranslationSettings.model_fields)))
        job_id = start_mod_job(params)
        return {'job_id': job_id, 'settings': {k: v for k, v in params.items() if k != 'api_key'}}

    @app.post('/api/studio/setup/plan')
    def component_plan(payload: SetupRequest):
        from app.core.setup_components import setup_plan
        return setup_plan(payload.language, payload.engine, payload.sdk)

    @app.post('/api/studio/setup')
    def setup_components(payload: SetupRequest):
        from app.core.setup_components import start_setup
        with _JOBS_LOCK:
            if any(job['status'] in ACTIVE for job in _JOBS.values()) or _PREVIEW.locked() or _RESEARCH.locked() or _MOD_ACTION.locked():
                raise HTTPException(409, 'Дождитесь завершения текущей задачи перед подготовкой компонентов.')
            task_id = start_setup(payload.language, payload.engine, payload.sdk, payload.components, payload.allow_downloads)
        return {'task_id': task_id}

    @app.get('/api/studio/setup/{task_id}')
    def setup_status(task_id: str):
        from app.core.setup_components import task_status
        try:
            return task_status(task_id)
        except KeyError:
            raise HTTPException(404, 'Подготовка компонентов не найдена.')

    @app.post('/api/studio/setup/{task_id}/cancel')
    def setup_cancel(task_id: str):
        from app.core.setup_components import cancel_task, task_status
        try:
            cancel_task(task_id)
            return task_status(task_id)
        except KeyError:
            raise HTTPException(404, 'Подготовка компонентов не найдена.')

    @contextmanager
    def installed_job(job_id):
        with _JOBS_LOCK:
            if any(job['status'] in ACTIVE for job in _JOBS.values()) or _MOD_ACTION.locked() or _setup_busy():
                raise HTTPException(409, 'Дождитесь завершения текущей задачи.')
            job = _JOBS.get(job_id)
            if not job or not job.get('result') or job['result'].get('installation', {}).get('status') != 'installed':
                raise HTTPException(400, 'Установленный мод не найден.')
            _MOD_ACTION.acquire()
        try:
            yield job
        finally:
            _MOD_ACTION.release()

    @app.post('/api/studio/mod/{job_id}/disable')
    def disable(job_id: int):
        from app.core.installation import disable as disable_mod
        from app.utils.atomic import atomic_json
        with installed_job(job_id) as job:
            installation = disable_mod(job['result'])
            job['result']['installation'] = installation
            atomic_json(Path(job['result']['out']) / 'anygamevoice.json', job['result'])
        return installation

    @app.post('/api/studio/mod/{job_id}/launch')
    def launch_game(job_id: int):
        from app.core.installation import launch
        with installed_job(job_id) as job:
            return launch(job['result'])

    @app.post('/api/studio/mod/{job_id}/verify')
    def verify_job(job_id: int):
        from app.core.installation import verify
        from app.utils.atomic import atomic_json
        with installed_job(job_id) as job:
            report = job['result']['installation']
            try:
                report['verification'] = verify(job['result'])
                if report['verification'].get('status') != 'ok':
                    raise ValueError('Проверка установленного мода не пройдена.')
                report.pop('error', None)
                if job['result'].get('succeeded') == job['result'].get('total'):
                    job['status'] = job['result']['status'] = 'done'
            except (ValueError, OSError, RuntimeError) as exc:
                report['verification'] = {'status': 'failed'}
                report['error'] = str(exc)[:500]
                job['status'] = job['result']['status'] = 'partial'
            atomic_json(Path(job['result']['out']) / 'anygamevoice.json', job['result'])
            return {'status': job['status'], 'installation': report}

    @app.post('/api/studio/mod/{job_id}/open-folder')
    def open_folder(job_id: int):
        import os
        import subprocess
        import sys
        with _JOBS_LOCK:
            result = _JOBS.get(job_id, {}).get('result')
            if not result or not Path(result['out']).is_dir():
                raise HTTPException(400, 'Папка результата пока не создана.')
            path = str(Path(result['out']).resolve())
        if sys.platform == 'win32':
            os.startfile(path)
        else:
            try:
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', path],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError as exc:
                raise HTTPException(400, 'Не удалось открыть проводник. Путь к файлам показан в результате.') from exc
        return {'path': path}

    @app.get('/api/studio/games')
    @app.get('/api/studio/steam/games')
    def installed_games():
        from app.core.game_libraries import discover_games
        return discover_games()

    class CustomProviderRequest(BaseModel):
        base_url: str = Field(min_length=1, max_length=2048)
        api_key: str = Field(default='', max_length=4096)

    @app.get('/api/studio/cloud/providers')
    def cloud_providers():
        from app.core.cloud_providers import provider_inventory
        return provider_inventory()

    @app.get('/api/studio/cloud/rankings/russian')
    def cloud_russian_rankings():
        from app.core.model_rankings import russian_rankings
        return russian_rankings()

    class LocalRankingRequest(BaseModel):
        api_key: str = Field(default='', max_length=4096, repr=False)

    @app.post('/api/studio/models/local-ranking')
    def local_model_ranking(payload: LocalRankingRequest):
        from app.core.model_rankings import local_ifbench
        return local_ifbench(payload.api_key)

    @app.post('/api/studio/cloud/providers/{provider}/inspect')
    def inspect_cloud_provider(provider: Literal['openrouter', 'opencode', 'codex', 'claude', 'cursor-agent']):
        from app.core.cloud_providers import inspect_provider
        return inspect_provider(provider)

    @app.post('/api/studio/cloud/custom/models')
    def inspect_custom_provider(payload: CustomProviderRequest):
        from app.core.cloud_providers import custom_models
        return custom_models(payload.base_url, payload.api_key)

    class OpenRouterConnection(BaseModel):
        api_key: str = Field(min_length=1, max_length=4096, repr=False)

    @app.post('/api/studio/cloud/openrouter/connect')
    def connect_openrouter(payload: OpenRouterConnection):
        from app.core.cloud_providers import _inspect_openrouter
        return _inspect_openrouter(payload.api_key)

    @app.get('/api/studio/cloud/opencode/catalog')
    def cloud_opencode_catalog():
        from app.core.cloud_providers import opencode_catalog
        return opencode_catalog()

    @app.get('/api/studio/cloud/opencode/{provider}/models')
    def cloud_opencode_models(provider: str):
        from app.core.cloud_providers import opencode_models
        return opencode_models(provider)

    @app.post('/api/studio/cloud/opencode/{provider}/login')
    def cloud_opencode_login(provider: str):
        from app.core.cloud_providers import open_opencode_login
        open_opencode_login(provider)
        return {'opened': True}

    @app.post('/api/studio/models/plan')
    def models_plan(payload: ModelRequest):
        from app.core.scanner.model_planner import build_plan
        return build_plan(payload.language)

    @app.post('/api/studio/reference/validate')
    def reference(payload: ReferenceRequest):
        from app.core.tts.reference import validate_reference
        return validate_reference(payload.path)

    @app.post('/api/studio/research')
    def research(payload: ResearchRequest):
        from app.agent.game_research import research_game
        with _JOBS_LOCK:
            if _setup_busy() or any(job['status'] in ACTIVE for job in _JOBS.values()) or _PREVIEW.locked() or not _RESEARCH.acquire(blocking=False):
                raise HTTPException(409, 'Исследование и синтез выполняются по очереди. Дождитесь текущей задачи.')
        try:
            return research_game(payload.path, payload.title, payload.model, payload.search,
                                 [item.model_dump() for item in payload.sources],
                                 provider=payload.provider, base_url=payload.base_url, api_key=payload.api_key)
        finally:
            _RESEARCH.release()

    @app.get('/api/studio/voices')
    def voices():
        from app.studio.core.tts.generator import list_engines
        from app.studio.core.tts.voice_manager import VoiceManager
        from app.core.dubbing_languages import LANGUAGES
        return {'voices': [asdict(v) for v in VoiceManager().list_voices()], 'engines': list_engines(),
                'translation_languages': {code: names[0] for code, names in LANGUAGES.items()}}

    @app.post('/api/studio/project/voice-blend')
    def project_voice_blend(payload: VoiceBlend):
        return payload.model_dump()

    @app.post('/api/studio/preview')
    def preview(payload: PreviewRequest):
        from app.studio.core.tts.generator import generate_voice, validate_synthesis
        with _JOBS_LOCK:
            if _setup_busy() or _RESEARCH.locked() or any(job['status'] in ACTIVE for job in _JOBS.values()) or not _PREVIEW.acquire(blocking=False):
                raise HTTPException(409, 'Synthesis is busy. Wait for the current job.')
        try:
            validate_synthesis(payload.engine, payload.voice)
            blend = payload.voice_blend.for_voice(payload.engine, payload.voice) if payload.voice_blend else None
            options = {'blend': blend} if blend is not None else {}
            audio = generate_voice(payload.text, voice=payload.voice, engine=payload.engine,
                                   emotion=payload.emotion, language=payload.language, **options)
            return Response(audio, media_type='audio/wav')
        finally:
            _PREVIEW.release()

    @app.post('/api/studio/mod')
    def mod(payload: ModRequest):
        return {'job_id': start_mod_job(payload.model_dump())}

    @app.get('/api/studio/mod/{job_id}')
    def job(job_id: int):
        try:
            return mod_job_status(job_id)
        except KeyError as exc:
            raise HTTPException(404, 'Unknown job.') from exc

    @app.post('/api/studio/mod/{job_id}/cancel')
    def cancel(job_id: int):
        with _JOBS_LOCK:
            if job_id not in _JOBS:
                raise HTTPException(404, 'Unknown job.')
            if _JOBS[job_id]['status'] in ACTIVE:
                _CANCEL[job_id].set()
                _JOBS[job_id]['status'] = 'cancelling'
        return {'status': mod_job_status(job_id)['status']}

    @app.get('/api/studio/mod/{job_id}/audio/{line_id}')
    def audio(job_id: int, line_id: str):
        try:
            result = mod_job_status(job_id)['result'] or {}
        except KeyError as exc:
            raise HTTPException(404, 'Unknown job.') from exc
        item = next((x for x in result.get('lines', []) if x['id'] == line_id and x['status'] == 'done'), None)
        if not item:
            raise HTTPException(404, 'Audio is not available.')
        base = Path(result['out']).resolve()
        target = (base / item['filename']).resolve()
        if target.parent != base or not target.is_file():
            raise HTTPException(404, 'Audio is not available.')
        return FileResponse(target, media_type='audio/wav')

    app.mount('/assets', StaticFiles(directory=INDEX.parent), name='assets')
    return app


def run(host: str = '127.0.0.1', port: int = 8000) -> None:
    """Serve the local UI and API on the same origin."""
    import uvicorn
    uvicorn.run(create_app(), host=host, port=port)
