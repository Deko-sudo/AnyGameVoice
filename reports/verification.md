# AnyGameVoice — проверка восьми утверждений

**Ревизия** `834834ea67c445adf7de42472e4e947549276e2d`. Проверка от 22 ноября 2026 г. Использован уже клонированный [репозиторий](https://github.com/Deko-sudo/AnyGameVoice/tree/834834ea67c445adf7de42472e4e947549276e2d). Команды `git remote get-url origin` и `git rev-parse HEAD` вернули `https://github.com/Deko-sudo/AnyGameVoice.git` и полный SHA выше. В начале проверки `git status --short --branch` вывел только `## main...origin/main`.

**Итог.** Все восемь утверждений подтверждаются чтением кода в описанных ниже условиях. Два первоочередных дефекта — потеря типа на границе перевода и ложный успех пакетной задачи. Они влияют на пользовательский результат даже при правильно выбранных моделях.

**Метод и границы.** Цитаты извлечены из объектов Git командой `git show <SHA>:<путь>`, номера строк — от единицы. Для повторения любой цитаты, например: `git show 834834e:app/core/translate.py | nl -ba | sed -n '40,46p'`. Docker CLI доступен, но Docker daemon отклонил подключение к сокету. Исполнение проекта не началось. Ниже отдельно приведены фактическая диагностика и команда для воспроизведения. Прогон с реальными моделями, измерение производительности и проверка готового бинарника остаются открытыми.

## 1. Переведённая реплика становится словарём и останавливает пакет

**ПОДТВЕРЖДЕНО. Уверенность высокая.** Статический анализ.

[app/core/translate.py:40–46](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/translate.py#L40-L46)

```python
        if isinstance(ln, Dialogue):
            out.append(Dialogue(speaker=speaker, text=tag + trans,
                                source_file=ln.source_file, line_no=ln.line_no,
                                engine=ln.engine, metadata={**ln.metadata, "translated_to": target}))
        else:
            out.append({"speaker": speaker, "text": tag + trans})
    return out
```

[app/main.py:88–90](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/main.py#L88-L90)

```python
    jobs = []
    for i, ln in enumerate(lines):
        fname = f"{i:04d}_{(ln.speaker or 'narrator')}.wav"
```

Ren’Py создаёт `ExtractedLine`, отдельный от `Dialogue` тип. Поэтому `translate_lines` возвращает список словарей именно для фактического ввода пакетной команды. На непустой партии после успешного ответа переводчика первый доступ `ln.speaker` приводит к `AttributeError` ещё до постановки первой задачи TTS. Словарь также лишён `source_file`, `line_no`, `metadata`. Для входа типа `Dialogue` возвращается `Dialogue`, а `translate_text` вообще возвращает строку. [app/core/game_detector/engines/renpy.py:56–63](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/game_detector/engines/renpy.py#L56-L63) · [app/core/extractor/models.py:6–16](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/extractor/models.py#L6-L16) · [app/main.py:77–94](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/main.py#L77-L94)

## 2. XTTS выбирает английский при передаче образца

**ПОДТВЕРЖДЕНО. Уверенность высокая.** Статический анализ.

[app/core/tts/engines/xtts.py:49–53](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/tts/engines/xtts.py#L49-L53)

```python
            kwargs = {"text": text, "file_path": out}
            if voice:
                kwargs["speaker_wav"] = voice
                kwargs["language"] = "en"
            tts.tts_to_file(**kwargs)
```

Любое непустое значение `voice` задаёт и `speaker_wav`, и `language="en"`. При пустом образце сам адаптер не передаёт `language`. Вывод касается аргументов вызова, качество произношения не измерялось.

## 3. Скрипт передаёт PyInstaller явное исключение Torch

**ПОДТВЕРЖДЕНО. Уверенность высокая.** Статический анализ.

[scripts/build_bundle.py:32–36](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/scripts/build_bundle.py#L32-L36)

```python
EXCLUDES = [
    "torch", "torchaudio", "TTS", "transformers", "bark", "scipy",
    "numpy", "soundfile", "UnityPy", "librosa", "numba", "llvmlite",
    "tensorflow", "sklearn", "matplotlib", "PIL",
]
```

[scripts/build_bundle.py:80–83](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/scripts/build_bundle.py#L80-L83)

```python
    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]
    for mod in HIDDEN:
        cmd += ["--hidden-import", mod]
```

И `torch`, и `torchaudio` попадают в аргументы `--exclude-module` в обоих режимах сборки. Утверждение подтверждено для рецепта. Состав конкретного опубликованного бинарника требует ручной проверки его архива и сопутствующих библиотек. [scripts/build_bundle.py:69–86](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/scripts/build_bundle.py#L69-L86)

## 4. Каждый синтез Piper запускает CLI заново

**ПОДТВЕРЖДЕНО. Уверенность высокая.** Статический анализ.

[app/core/tts/engines/piper.py:50–58](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/tts/engines/piper.py#L50-L58)

```python
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out = tmp.name
        try:
            proc = subprocess.run(
                [self.binary, "--model", model, "--output_file", out, *extra.get("cli_flags", [])],
                input=clean.encode("utf-8"),
                capture_output=True,
                timeout=120,
            )
```

В штатном пути одна задача создаёт один WAV и один `subprocess.run` в `PiperEngine.synthesize`. Текст идёт в stdin, результат читается из временного файла. Если бинарник или модель отсутствуют, проверка завершается раньше запуска. Число процессов установлено по коду, время их запуска не измерялось. [app/core/tts/engines/piper.py:38–47](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/tts/engines/piper.py#L38-L47) · [app/main.py:89–96](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/main.py#L89-L96)

## 5. Генератор создаёт новый объект TTS для каждой реплики

**ПОДТВЕРЖДЕНО. Уверенность высокая.** Статический анализ.

[app/core/tts/generator.py:33–35](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/tts/generator.py#L33-L35)

```python
    if cls is PiperEngine:
        return PiperEngine(model_path=voice)
    return cls()
```

[app/core/tts/generator.py:47–51](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/tts/generator.py#L47-L51)

```python
    eng = get_engine(engine, voice)
    try:
        return eng.synthesize(text, voice, emotion=emotion)
    except TypeError:
        return eng.synthesize(text, voice)
```

Каждый `generate_voice_to_file` вызывает `generate_voice`, а тот вызывает фабрику. Поэтому даже кэш `self._tts` в XTTS принадлежит новому экземпляру. Это доказательство создания объекта адаптера, а не утверждение, что любая сторонняя библиотека обязательно загружает все веса с диска на каждом вызове. [app/core/tts/generator.py:54–59](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/tts/generator.py#L54-L59) · [app/core/tts/engines/xtts.py:30–39](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/tts/engines/xtts.py#L30-L39)

## 6. Ren’Py теряет каталог и при некоторых раскладках пропускает сценарии

**ПОДТВЕРЖДЕНО. Уверенность высокая.** Статический анализ.

[app/core/game_detector/engines/renpy.py:58–61](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/game_detector/engines/renpy.py#L58-L61)

```python
                        speaker=speaker or "narrator",
                        text=text,
                        source_file=os.path.basename(path),
                        line_no=no,
```

[app/core/game_detector/engines/renpy.py:69–73](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/game_detector/engines/renpy.py#L69-L73)

```python
def extract_renpy_folder(game_path: str) -> list[ExtractedLine]:
    """Extract dialogue from all .rpy files under game/ (or root)."""
    root = Path(game_path)
    candidates = sorted((root / "game").glob("*.rpy")) or sorted(root.rglob("*.rpy"))
    lines: list[ExtractedLine] = []
```

Это два независимых эффекта. В извлечённой строке остаётся `basename`, поэтому два файла `intro.rpy` в разных каталогах не различимы по `source_file`. Вложенные сценарии пропускаются, когда есть хотя бы один верхнеуровневый `game/*.rpy`: левый список непуст и `or` не вычисляет правый. Если верхний список пуст, сам `extract_renpy_folder` рекурсивно обходит корень. Через общий API дополнительно должен сработать детектор движка. [app/core/extractor/dialogue_extractor.py:29–38](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/extractor/dialogue_extractor.py#L29-L38)

## 7. Длительность субтитров рассчитывается из текста

**ПОДТВЕРЖДЕНО. Уверенность высокая.** Статический анализ.

[app/utils/audio_utils.py:29–33](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/utils/audio_utils.py#L29-L33)

```python
def estimate_duration(text: str, cps: float = CPS) -> float:
    """Estimate spoken seconds for a line."""
    if not text:
        return MIN_LINE_SEC
    return max(MIN_LINE_SEC, len(text) / cps)
```

[app/utils/audio_utils.py:51–54](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/utils/audio_utils.py#L51-L54)

```python
    for i, ln in enumerate(lines, 1):
        dur = estimate_duration(ln.text if hasattr(ln, "text") else str(ln), cps)
        start, end = t, t + dur
        t = end + GAP_SEC
```

Стандартная оценка — 15 символов/с, минимум 1 с, промежуток 0,4 с. `cmd_mod` передаёт в `to_srt` список реплик. Параметры, заголовки и фактическое существование WAV не читаются. В ветвящейся новелле дополнительно нужен порядок реплик конкретной ветки. [app/utils/audio_utils.py:18–21](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/utils/audio_utils.py#L18-L21) · [app/utils/audio_utils.py:60–66](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/utils/audio_utils.py#L60-L66) · [app/main.py:104–106](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/main.py#L104-L106)

## 8. Внешнее задание может стать `done`, когда WAV отсутствуют

**ПОДТВЕРЖДЕНО. Уверенность высокая.** Статический анализ.

[app/main.py:99–103](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/main.py#L99-L103)

```python
    ok = sum(1 for s in snaps if s["status"] == "done")
    print(f"Generated {ok}/{len(snaps)} lines -> {out}")
    for s in snaps:
        if s["status"] == "failed":
            print(f"FAILED {s['name']}: {(s['error'] or '').splitlines()[0]}")
```

[app/ui_server.py:53–55](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/ui_server.py#L53-L55)

```python
        else:
            with _JOBS_LOCK:
                _JOBS[job_id]["status"] = "done"
```

Исключение синтеза превращается в статус `failed` отдельной задачи. `cmd_mod` выводит ошибку, затем пишет SRT и нормально возвращается. Обёртка назначает `done`, если наружу не вышло исключение. При доступном каталоге вывода таким образом возможен даже `done` с 0 WAV. Ошибка записи самого SRT, напротив, дойдёт до обёртки. У `wait_all` также возможен возврат незавершённых задач по тайм-ауту. Значение публичного `done` надо привязать к проверке обязательных артефактов. [app/core/queue/task_queue.py:73–82](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/queue/task_queue.py#L73-L82) · [app/core/queue/task_queue.py:101–111](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/core/queue/task_queue.py#L101-L111) · [app/main.py:97–107](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/main.py#L97-L107) · [app/ui_server.py:38–55](https://github.com/Deko-sudo/AnyGameVoice/blob/834834ea67c445adf7de42472e4e947549276e2d/app/ui_server.py#L38-L55)

## Уточнения к описанию проекта

- Tauri запускает бэкенд с аргументами `ui 8000`. Веб-страница обращается к локальным HTTP-маршрутам FastAPI. Снимок интерфейса для миграции включает `GET /`, `GET /api/health`, `POST /api/scan`, `POST /api/extract`, `GET /api/voices`, `POST /api/mod` и `GET /api/mod/{job_id}`. Текущая форма запуска передаёт `path, out, voice, engine, emotion`, сервер дополнительно принимает `translate_to, provider`. Упакованное окно в этом аудите не запускалось. [Фронтенд](https://github.com/Deko-sudo/AnyGameVoice/blob/834834e/ui/index.html#L56-L90) · [обработчики](https://github.com/Deko-sudo/AnyGameVoice/blob/834834e/app/ui_server.py) · [запуск sidecar](https://github.com/Deko-sudo/AnyGameVoice/blob/834834e/src-tauri/src/main.rs)
- В реестре действительно четыре TTS-адаптера без автоматического выбора уровня. Эмоции задаются ведущим тегом, регулярным выражением и таблицей параметров. Это разбор явной разметки, смысл обычной фразы модуль не оценивает. [Реестр](https://github.com/Deko-sudo/AnyGameVoice/blob/834834e/app/core/tts/generator.py#L15-L25) · [эмоции](https://github.com/Deko-sudo/AnyGameVoice/blob/834834e/app/core/tts/emotions.py#L26-L56)
- В роутере шесть названных LLM-провайдеров. В производстве озвучки LLM используется для перевода. Если считать весь репозиторий, есть второй вызов — составление сводки в `AIAgent.research`. Файл `ai_agent.py` занимает 1951 байт по `git ls-tree -r --long 834834e app/agent`, весь каталог больше. Поиск, загрузка страниц и вызов провайдера реализованы, но `cmd_mod` этот модуль не вызывает. [Роутер](https://github.com/Deko-sudo/AnyGameVoice/blob/834834e/app/providers/router.py) · [research](https://github.com/Deko-sudo/AnyGameVoice/blob/834834e/app/agent/ai_agent.py#L37-L55)

## Как воспроизвести без скачивания моделей

Запускать из корня клона на указанном SHA при отсутствии локальных изменений приложения. Нужен заранее загруженный локальный образ `python:3.11-slim`. Для повторных прогонов сохраните ID образа из `docker image inspect python:3.11-slim --format '{{.Id}}'` и подставьте его вместо тега. Скрипт использует стандартную библиотеку, проходит через действительные экстрактор, перевод списка, генератор, очередь и обработчик фонового задания. Только ответ внешнего переводчика подменён строкой. Отказ TTS вызывается отсутствующим файлом голоса. Временные данные создаются внутри `/reports` и удаляются при штатном выходе.

**Фактический результат этой сессии.** Команда `docker version --format '{{.Server.Version}}'` и попытка `docker run` ниже получили `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`. Для `docker run` код выхода 1, stdout пуст. Разрешение на файловый путь сокета не дало подключения к daemon. Вывода Python из контейнера нет.

```bash
mkdir -p reports
docker run --rm -i --pull=never --network none --read-only \
  --memory 4g --cpus 2 --pids-limit 256 --cap-drop ALL \
  --security-opt no-new-privileges --user "$(id -u):$(id -g)" \
  -v "$PWD:/work:ro" -v "$PWD/reports:/reports:rw" -w /work \
  -e PYTHONDONTWRITEBYTECODE=1 -e TMPDIR=/reports \
  python:3.11-slim python -B - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from unittest.mock import patch

from app.main import cmd_mod
from app.core.extractor.dialogue_extractor import extract_dialogue
from app.core.game_detector.engines.renpy import extract_renpy_folder
from app.ui_server import start_mod_job, mod_job_status

with TemporaryDirectory(dir="/reports") as tmp:
    root = Path(tmp)
    game = root / "game"
    nested = game / "scene"
    nested.mkdir(parents=True)
    (root / "renpy").mkdir()
    main = game / "main.rpy"
    main.write_text('e "Hi."\n', encoding="utf-8")
    (nested / "other.rpy").write_text('a "Hidden."\n', encoding="utf-8")

    rows = extract_dialogue(str(root))
    print("source:", [(type(r).__name__, r.source_file) for r in rows])
    assert [r.text for r in rows] == ["Hi."]

    with patch("app.core.translate.translate_text", return_value="Hola."):
        try:
            cmd_mod(str(root), str(root / "translated"), translate_to="es")
        except AttributeError as err:
            print("translation:", err)
            assert "dict" in str(err) and "speaker" in str(err)
        else:
            raise AssertionError("Expected type mismatch in the audited revision")

    out = root / "broken"
    job = start_mod_job({"path": str(root), "out": str(out),
                         "engine": "piper", "voice": str(root / "missing.onnx")})
    deadline = monotonic() + 10
    status = mod_job_status(job)
    while status["status"] == "running" and monotonic() < deadline:
        sleep(0.05)
        status = mod_job_status(job)
    wavs = list(out.glob("*.wav"))
    srt = (out / "dialogue.srt").read_text(encoding="utf-8")
    print("job:", status["status"], "wavs:", len(wavs), "cue:", srt.splitlines()[1])
    assert status["status"] == "done" and not wavs
    assert srt.splitlines()[1] == "00:00:00,000 --> 00:00:01,000"

    main.unlink()
    rows = extract_renpy_folder(str(root))
    print("nested only:", [r.source_file for r in rows])
    assert [(r.source_file, r.text) for r in rows] == [("other.rpy", "Hidden.")]
PY
```

**Ожидаемые признаки на исходной ревизии, подлежат ручной проверке.** Пункт 1 — исключение `'dict' object has no attribute 'speaker'`. Пункты 7–8 — `job: done wavs: 0 cue: 00:00:00,000 --> 00:00:01,000`. Пункт 6 — при обоих сценариях найдётся только `main.rpy`, после удаления верхнего файла появится `other.rpy` без префикса `scene/`. Проверки выше специально описывают дефекты старой ревизии. Для исправленной реализации ожидаемые результаты должны измениться.

## Первые три дня

| Когда | Что сделать | Приёмка и тесты против регрессий |
|---|---|---|
| **День 1. Правильность партии** | Сначала стабилизировать два узких участка Python на пользовательском пути. Унифицировать реплику на границе экстрактор → перевод → очередь. Довести ошибки дочерних задач и тайм-аут до итогового статуса, сохранив числовой ID и прежние публичные статусы UI. | Тест через `cmd_mod` с настоящим Ren’Py-экстрактором и подменой только перевода/синтеза: непустая партия с `translate_to` даёт WAV, сохраняет говорящего и источник. Через `/api/mod` отдельно проверить успех всех, отказ одного из двух, отказ всех и незавершённую задачу. Ошибка содержит идентификаторы проблемных реплик, повтор не теряет удачные файлы. |
| **День 2. Связь с игрой и временем** | Собственная ветвящаяся сцена, два персонажа, EN→RU и EN→ES. Развести относительный путь, стабильный ID Ren’Py и номер строки для диагностики. Хранить исходную разметку и перевод отдельно. Язык передавать до TTS. Считать длительность готового WAV по числу кадров и частоте. | Верхний и вложенный сценарии видны одновременно. Два одноимённых файла и одинаковый текст в разных ветках не сливаются. Перестановка файлов не меняет привязку WAV. Два корректных тестовых WAV с одним текстом и длительностью 0,5 и 2 с дают соответствующие интервалы. Подменный XTTS получает нужный язык при референсе. Установить и снять тестовый мод на копии игры, проверить исходные хеши. |
| **День 3. Граница Rust и цена загрузки модели** | Зафиксировать контракт UI и форматы результата предыдущих дней как вход для Rust (Axum/Tokio, SQLite, детерминированный DAG). Взять первую операцию для параллельной реализации, например чтение статуса одной партии. В Python измерить холодный и тёплый синтез 1 и 100 реплик с подсчётом созданных адаптеров и процессов. | Один набор контрактных примеров применим к Python и Rust. Отдельно проверить отмену/перезапуск, повторное использование одного рабочего процесса для партии и смену голоса без утечки настроек. Для замены CPU-бэкенда понадобится чистый офлайн-прогон обеих языковых пар с реальными моделями и прослушиванием. |

Существующий тест перевода начинает сразу с `Dialogue`, а пакетный тест подменяет генератор записью `FAKEWAV` и не запрашивает перевод. Поэтому первым вложением времени должен быть сквозной тест на реальном типе экстрактора. Для старта Rust достаточно закрепить исправленное поведение двух критических границ. Переписывать остальные Python-модули перед этим не требуется. [Тест перевода](https://github.com/Deko-sudo/AnyGameVoice/blob/834834e/tests/test_translate.py) · [тест партии](https://github.com/Deko-sudo/AnyGameVoice/blob/834834e/tests/test_batch.py)

## Возражение

Ограниченное декодирование полезно для схемы JSON. При обрыве генерации, ошибке сервера или неверном ID реплики обещание «100% валидных ответов» нельзя использовать как условие перехода DAG. Завершение генерации, парсинг, проверка схемы, совпадение ID и сохранность переменных должны быть отдельными проверяемыми условиями. Корректировки лицензионных обозначений `kokoro-ru` и `whisper-rs` приведены в [манифесте](licenses.md). Выбор движков и архитектуры от этих уточнений не меняется.
