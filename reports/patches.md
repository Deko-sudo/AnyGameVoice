# AnyGameVoice — два патча к 834834e

База — `834834ea67c445adf7de42472e4e947549276e2d`. Ниже два последовательных unified diff. Второй применяется поверх первого. Оба проверены через `git apply --check` и последовательно применены к временной копии исходных файлов этого коммита. Все 13 полученных файлов приложения и тестов побайтно совпали с рабочим деревом. Фронтенд не затронут. Коммитов не создавалось.

## Поведение после исправления

1. Три текстовых экстрактора возвращают `Line`. Исходный текст, говорящий, расположение в сценарии и язык сохраняются при переводе. `ln.text` возвращает текст для показа, `tts_text` передаётся движку для озвучки. `translate_lines` принимает прежние объекты `Dialogue` и `ExtractedLine` для совместимости и возвращает `list[Line]`. `engine_id` содержит имя движка экстрактора. Алгоритмы поиска и разбора сценариев не менялись.
2. `cmd_mod` записывает `report.json` в выбранную пользователем выходную папку. Числа и результаты по строкам также доступны через существующий `GET /api/mod/{job_id}`. `done` означает, что каждый WAV непустой партии успешно записан. `partial` означает, что часть реплик завершилась ошибкой. При полном отказе или отсутствии реплик возвращается `failed`. Для пропущенной строки указаны `index`, `source_file`, `line_no`, `speaker`, `status` и `skipped_reason`. Субтитры формируются по успешно озвученным строкам. CLI возвращает код 1 для `partial` и `failed`.

При достижении прежнего лимита партии очередь останавливает выбор новых реплик и дожидается уже начатых записей, прежде чем объявить конечный статус. Это может продлить ожидание сверх 600 секунд для работающего синтезатора. Отмена уже выполняющегося стороннего TTS в эти патчи не входит.

## Проверка

- `python -B -m pytest -q -p no:cacheprovider tests` — **65 passed**, без пропусков. Python 3.14.8, pytest 9.2.0. Тесты выполнены локально в Bubblewrap с отдельным сетевым пространством (`--unshare-net`), доступом к исходникам только для чтения и временной папкой для WAV.
- Сквозная регрессия использует настоящий экстрактор Ren’Py, преобразование `Line`, очередь, файловый генератор и чтение стандартного PCM WAV. Ответ переводчика и синтез модели подменены. Тест проверяет `line.speaker`, `line.text`, язык, исходный текст, произносимый текст и количество аудиокадров.
- Дополнительный прогон через FastAPI TestClient использовал существующие `POST /api/mod` и `GET /api/mod/{job_id}`. Из двух реплик первая дала WAV, вторая получила ошибку тестового TTS. Получено `partial`, `succeeded=1`, `failed=1`, `total=2`, `skipped_reason="voice unavailable"`. Причина из HTTP-ответа совпала с записью в `report.json`.
- Производительность и качество речи реальных моделей не измерялись. `git diff --check` прошёл.

## Патч 1. Одна модель реплики от экстракции до WAV

```diff
diff --git i/app/core/extractor/dialogue_extractor.py w/app/core/extractor/dialogue_extractor.py
index 23a752d..ab45f35 100644
--- i/app/core/extractor/dialogue_extractor.py
+++ w/app/core/extractor/dialogue_extractor.py
@@ -8,7 +8,7 @@ Unity/Unreal: compiled assets, text extraction not supported yet
 
 import os
 
-from app.core.extractor.models import ExtractedLine
+from app.models.line import Line
 
 __all__ = ["extract_dialogue", "supported_engines"]
 
@@ -20,8 +20,8 @@ def supported_engines() -> tuple:
     return SUPPORTED
 
 
-def extract_dialogue(game_path: str) -> list:
-    """Extract dialogue lines (list of ExtractedLine). Empty if unsupported."""
+def extract_dialogue(game_path: str) -> list[Line]:
+    """Extract dialogue lines (list of Line). Empty if unsupported."""
     if not game_path or not os.path.isdir(game_path):
         return []
     try:
diff --git i/app/core/game_detector/engines/godot.py w/app/core/game_detector/engines/godot.py
index c826832..d885010 100644
--- i/app/core/game_detector/engines/godot.py
+++ w/app/core/game_detector/engines/godot.py
@@ -13,16 +13,16 @@ Also lists audio assets for the replacer.
 import os
 from pathlib import Path
 
-from app.core.extractor.models import ExtractedLine
+from app.models.line import Line
 
 __all__ = ["extract_godot_folder", "extract_godot_file", "list_audio_assets"]
 
 AUDIO_SUFFIXES = {".wav", ".ogg", ".mp3"}
 
 
-def extract_godot_file(path: str) -> list[ExtractedLine]:
+def extract_godot_file(path: str) -> list[Line]:
     """Extract dialogue from a single .dialogue file."""
-    out: list[ExtractedLine] = []
+    out: list[Line] = []
     try:
         with open(path, encoding="utf-8", errors="replace") as fh:
             for no, raw in enumerate(fh, 1):
@@ -36,8 +36,9 @@ def extract_godot_file(path: str) -> list[ExtractedLine]:
                     speaker, text = speaker.strip(), text.strip()
                     if speaker and text and " " not in speaker and len(speaker) <= 32:
                         out.append(
-                            ExtractedLine(
-                                speaker=speaker, text=text,
+                            Line(
+                                engine_id="godot",
+                                speaker=speaker, source_text=text,
                                 source_file=os.path.basename(path), line_no=no,
                             )
                         )
@@ -45,8 +46,9 @@ def extract_godot_file(path: str) -> list[ExtractedLine]:
                 # bare narration line
                 if len(line) > 1:
                     out.append(
-                        ExtractedLine(
-                            speaker="narrator", text=line,
+                        Line(
+                            engine_id="godot",
+                            speaker="narrator", source_text=line,
                             source_file=os.path.basename(path), line_no=no,
                         )
                     )
@@ -55,9 +57,9 @@ def extract_godot_file(path: str) -> list[ExtractedLine]:
     return out
 
 
-def extract_godot_folder(game_path: str) -> list[ExtractedLine]:
+def extract_godot_folder(game_path: str) -> list[Line]:
     """Extract dialogue from all .dialogue files under game_path."""
-    lines: list[ExtractedLine] = []
+    lines: list[Line] = []
     for fp in sorted(Path(game_path).rglob("*.dialogue")):
         if fp.is_file():
             lines.extend(extract_godot_file(str(fp)))
diff --git i/app/core/game_detector/engines/renpy.py w/app/core/game_detector/engines/renpy.py
index c4a4a65..22f40f8 100644
--- i/app/core/game_detector/engines/renpy.py
+++ w/app/core/game_detector/engines/renpy.py
@@ -11,7 +11,7 @@ import os
 import re
 from pathlib import Path
 
-from app.core.extractor.models import ExtractedLine
+from app.models.line import Line
 
 __all__ = ["extract_renpy_file", "extract_renpy_folder"]
 
@@ -33,9 +33,9 @@ def _clean(text: str) -> str:
     return text.strip()
 
 
-def extract_renpy_file(path: str) -> list[ExtractedLine]:
+def extract_renpy_file(path: str) -> list[Line]:
     """Extract dialogue lines from a single .rpy file."""
-    out: list[ExtractedLine] = []
+    out: list[Line] = []
     try:
         with open(path, encoding="utf-8", errors="replace") as fh:
             for no, raw in enumerate(fh, 1):
@@ -54,9 +54,10 @@ def extract_renpy_file(path: str) -> list[ExtractedLine]:
                 if speaker and " " in speaker:
                     continue
                 out.append(
-                    ExtractedLine(
+                    Line(
+                        engine_id="renpy",
                         speaker=speaker or "narrator",
-                        text=text,
+                        source_text=text,
                         source_file=os.path.basename(path),
                         line_no=no,
                     )
@@ -66,11 +67,11 @@ def extract_renpy_file(path: str) -> list[ExtractedLine]:
     return out
 
 
-def extract_renpy_folder(game_path: str) -> list[ExtractedLine]:
+def extract_renpy_folder(game_path: str) -> list[Line]:
     """Extract dialogue from all .rpy files under game/ (or root)."""
     root = Path(game_path)
     candidates = sorted((root / "game").glob("*.rpy")) or sorted(root.rglob("*.rpy"))
-    lines: list[ExtractedLine] = []
+    lines: list[Line] = []
     for fp in candidates:
         if fp.is_file():
             lines.extend(extract_renpy_file(str(fp)))
diff --git i/app/core/game_detector/engines/rpgmaker.py w/app/core/game_detector/engines/rpgmaker.py
index 18d9bcf..838ff7d 100644
--- i/app/core/game_detector/engines/rpgmaker.py
+++ w/app/core/game_detector/engines/rpgmaker.py
@@ -12,7 +12,7 @@ import json
 import os
 from pathlib import Path
 
-from app.core.extractor.models import ExtractedLine
+from app.models.line import Line
 
 __all__ = ["extract_rpgmaker_folder", "extract_rpgmaker_file"]
 
@@ -36,9 +36,9 @@ def _iter_event_lists(data) -> list:
     return lists
 
 
-def extract_rpgmaker_file(path: str) -> list[ExtractedLine]:
+def extract_rpgmaker_file(path: str) -> list[Line]:
     """Extract dialogue from a single RPG Maker JSON file."""
-    out: list[ExtractedLine] = []
+    out: list[Line] = []
     try:
         with open(path, encoding="utf-8", errors="replace") as fh:
             data = json.load(fh)
@@ -59,9 +59,10 @@ def extract_rpgmaker_file(path: str) -> list[ExtractedLine]:
                 text = " ".join(str(p) for p in params if isinstance(p, str)).strip()
                 if text:
                     out.append(
-                        ExtractedLine(
+                        Line(
+                            engine_id="rpgmaker",
                             speaker=speaker or "narrator",
-                            text=text,
+                            source_text=text,
                             source_file=os.path.basename(path),
                             line_no=0,
                         )
@@ -69,7 +70,7 @@ def extract_rpgmaker_file(path: str) -> list[ExtractedLine]:
     return out
 
 
-def extract_rpgmaker_folder(game_path: str) -> list[ExtractedLine]:
+def extract_rpgmaker_folder(game_path: str) -> list[Line]:
     """Extract dialogue from data/*.json (Map files + CommonEvents)."""
     root = Path(game_path)
     data_dir = root / "data" if (root / "data").is_dir() else root
@@ -79,7 +80,7 @@ def extract_rpgmaker_folder(game_path: str) -> list[ExtractedLine]:
         files.append(common)
     if not files:  # nested layout (e.g. www/ folder)
         files = sorted(root.rglob("Map001.json"))
-    lines: list[ExtractedLine] = []
+    lines: list[Line] = []
     for fp in files:
         if fp.is_file():
             lines.extend(extract_rpgmaker_file(str(fp)))
diff --git i/app/core/translate.py w/app/core/translate.py
index 7e19409..d4bb155 100644
--- i/app/core/translate.py
+++ w/app/core/translate.py
@@ -5,9 +5,14 @@ Game dialogue is translated line by line to keep speaker timing;
 tags like [happy] are preserved by translating only the clean text.
 """
 
-from app.models.dialogue import Dialogue
+from dataclasses import replace
 
-__all__ = ["translate_text", "translate_lines", "SUPPORTED_HINT"]
+from app.core.extractor.models import ExtractedLine
+from app.core.tts.emotions import parse_emotion
+from app.models.dialogue import Dialogue
+from app.models.line import Line
+
+__all__ = ["translate_text", "translate_line", "translate_lines", "SUPPORTED_HINT"]
 
 
 def translate_text(text: str, target: str = "en", source: str = "auto",
@@ -26,24 +31,37 @@ def translate_text(text: str, target: str = "en", source: str = "auto",
     return out.strip().strip("\"'")
 
 
-def translate_lines(lines: list, target: str, source: str = "auto",
-                    provider: str = "ollama", api_key: str = "", model: str = "") -> list:
-    """Translate dialogue texts, preserving speakers and metadata."""
-    from app.core.tts.emotions import parse_emotion
+def translate_line(line: Line, target: str, source: str = "auto",
+                   provider: str = "ollama", api_key: str = "", model: str = "") -> Line:
+    if line.manual_override and line.target_lang == target and line.translated_text:
+        return line
+    source_lang = line.source_lang if source == "auto" else source
+    emotion, clean = parse_emotion(line.source_text)
+    translated = translate_text(clean, target, source_lang, provider, api_key, model)
+    if not translated.strip():
+        raise ValueError("Translation is empty")
+    tag = "" if emotion == "neutral" else f"[{emotion}] "
+    return replace(
+        line, source_lang=source_lang, target_lang=target,
+        translated_text=tag + translated, tts_text=translated,
+        emotion=line.emotion if emotion == "neutral" else emotion,
+        metadata={**line.metadata, "translated_to": target},
+    )
 
-    out: list = []
-    for ln in lines:
-        emotion, clean = parse_emotion(ln.text)
-        tag = "" if emotion == "neutral" else f"[{emotion}] "
-        trans = translate_text(clean, target, source, provider, api_key, model)
-        speaker = getattr(ln, "speaker", "")
-        if isinstance(ln, Dialogue):
-            out.append(Dialogue(speaker=speaker, text=tag + trans,
-                                source_file=ln.source_file, line_no=ln.line_no,
-                                engine=ln.engine, metadata={**ln.metadata, "translated_to": target}))
-        else:
-            out.append({"speaker": speaker, "text": tag + trans})
-    return out
+
+def translate_lines(lines: list[Line | Dialogue | ExtractedLine], target: str, source: str = "auto",
+                    provider: str = "ollama", api_key: str = "", model: str = "") -> list[Line]:
+    """Accept earlier extractor/CLI models at the boundary; always return Lines."""
+    result = []
+    for line in lines:
+        if not isinstance(line, Line):
+            line = Line(
+                engine_id=getattr(line, "engine", ""), source_file=line.source_file,
+                line_no=line.line_no, speaker=line.speaker, source_text=line.text,
+                metadata=line.metadata,
+            )
+        result.append(translate_line(line, target, source, provider, api_key, model))
+    return result
 
 
 SUPPORTED_HINT = "Any target language the provider supports (e.g. en, ru, ja, de, fr)."
diff --git i/app/core/tts/generator.py w/app/core/tts/generator.py
index fc2ad5a..06bd54f 100644
--- i/app/core/tts/generator.py
+++ w/app/core/tts/generator.py
@@ -5,6 +5,8 @@ Only piper works out of the box; xtts/bark/silero need optional
 packages and raise a clear RuntimeError otherwise.
 """
 
+from app.models.line import Line
+
 from .engines.bark import BarkEngine
 from .engines.piper import PiperEngine
 from .engines.silero import SileroEngine
@@ -35,8 +37,13 @@ def get_engine(name: str, voice: str = ""):
     return cls()
 
 
-def generate_voice(text: str, voice: str = "default", engine: str = "piper", emotion: str = "neutral") -> bytes:
+def generate_voice(text: str | Line, voice: str = "default", engine: str = "piper", emotion: str = "neutral") -> bytes:
     """Generate voice audio bytes for text (emotion tag or param)."""
+    if isinstance(text, Line):
+        voice = text.voice_id or voice
+        if text.emotion != "neutral":
+            emotion = text.emotion
+        text = text.tts_text or text.text
     if not text or not text.strip():
         raise ValueError("text must not be empty")
     if engine == "piper" and (not voice or voice == "default"):
@@ -51,9 +58,11 @@ def generate_voice(text: str, voice: str = "default", engine: str = "piper", emo
         return eng.synthesize(text, voice)
 
 
-def generate_voice_to_file(text: str, out_path: str, voice: str = "", engine: str = "piper", emotion: str = "neutral") -> str:
+def generate_voice_to_file(text: str | Line, out_path: str, voice: str = "", engine: str = "piper", emotion: str = "neutral") -> str:
     """Generate audio and write to out_path. Returns out_path."""
     data = generate_voice(text, voice=voice, engine=engine, emotion=emotion)
+    if not data:
+        raise ValueError("TTS returned no audio")
     with open(out_path, "wb") as fh:
         fh.write(data)
     return out_path
diff --git i/app/main.py w/app/main.py
index 2dcf2df..b82e203 100644
--- i/app/main.py
+++ w/app/main.py
@@ -90,7 +90,7 @@ def cmd_mod(folder: str, out: str, voice: str = "", engine: str = "piper", worke
         fname = f"{i:04d}_{(ln.speaker or 'narrator')}.wav"
         dest = os.path.join(out, fname)
         tid = q.submit(
-            generate_voice_to_file, ln.text, dest, voice=voice, engine=engine, emotion=emotion,
+            generate_voice_to_file, ln, dest, voice=voice, engine=engine, emotion=emotion,
             priority=Priority.NORMAL, name=fname,
         )
         jobs.append((tid, dest, ln))
diff --git i/tests/test_batch.py w/tests/test_batch.py
index 515e6e2..f8045d2 100644
--- i/tests/test_batch.py
+++ w/tests/test_batch.py
@@ -1,5 +1,7 @@
 """Subtitle + batch pipeline tests."""
 
+import io
+import wave
 from unittest.mock import patch
 
 
@@ -32,9 +34,9 @@ def test_batch_mod(tmp_path):
     (game / "game" / "script.rpy").write_text('e "Hello there!"\n"Wind."\n', encoding="utf-8")
     out = tmp_path / "out"
 
-    def fake_gen(text, out_path, voice="", engine="piper", emotion="neutral"):
+    def fake_gen(line, out_path, voice="", engine="piper", emotion="neutral"):
         with open(out_path, "wb") as fh:
-            fh.write(b"FAKEWAV" + text.encode())
+            fh.write(b"FAKEWAV" + line.text.encode())
         return out_path
 
     # cmd_mod imports generate_voice_to_file lazily, so patch the source.
@@ -43,3 +45,35 @@ def test_batch_mod(tmp_path):
     wavs = sorted(out.glob("*.wav"))
     assert len(wavs) == 2
     assert (out / "dialogue.srt").is_file()
+
+
+def test_translated_line_reaches_wav(tmp_path):
+    from app.core.tts import generator
+    from app.main import cmd_mod
+    from app.models.line import Line
+
+    game = tmp_path / "game"
+    game.mkdir()
+    (game / "script.rpy").write_text('e "Hi!"\n', encoding="utf-8")
+    output = tmp_path / "out"
+    audio = io.BytesIO()
+    with wave.open(audio, "wb") as wav:
+        wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
+        wav.writeframes(b"\0\0" * 80)
+
+    with (
+        patch("app.core.translate.translate_text", return_value="¡Hola!"),
+        patch.object(generator, "get_engine") as engine,
+        patch.object(generator, "generate_voice_to_file", wraps=generator.generate_voice_to_file) as write,
+    ):
+        engine.return_value.synthesize.return_value = audio.getvalue()
+        cmd_mod(str(tmp_path), str(output), voice="sample", translate_to="es")
+
+    line = write.call_args.args[0]
+    assert isinstance(line, Line)
+    assert (line.speaker, line.text, line.tts_text) == ("e", "¡Hola!", "¡Hola!")
+    assert (line.engine_id, line.source_file, line.line_no) == ("renpy", "script.rpy", 1)
+    assert (line.source_text, line.target_lang) == ("Hi!", "es")
+    engine.return_value.synthesize.assert_called_once_with("¡Hola!", "sample", emotion="neutral")
+    with wave.open(str(output / "0000_e.wav"), "rb") as wav:
+        assert wav.getnframes() == 80
diff --git 1/app/models/line.py 2/app/models/line.py
new file mode 100644
index 0000000..0ed13e7
--- /dev/null
+++ 2/app/models/line.py
@@ -0,0 +1,26 @@
+"""A dialogue line throughout extraction, translation and speech generation."""
+
+from dataclasses import dataclass, field
+
+
+@dataclass
+class Line:
+    engine_id: str = ""
+    source_file: str = ""
+    line_no: int = 0
+    speaker: str = ""
+    source_text: str = ""
+    source_lang: str = "auto"
+    target_lang: str = ""
+    translated_text: str = ""
+    tts_text: str = ""
+    voice_id: str = ""
+    emotion: str = "neutral"
+    duration_target: float | None = None
+    manual_override: bool = False
+    metadata: dict = field(default_factory=dict)
+
+    @property
+    def text(self) -> str:
+        """Display text for the existing UI and subtitle writers."""
+        return self.translated_text or self.source_text
```

## Патч 2. Итог задания и причины пропуска

```diff
diff --git a/app/main.py b/app/main.py
--- a/app/main.py
+++ b/app/main.py
@@ -64,47 +64,79 @@
 
 
 def cmd_mod(folder: str, out: str, voice: str = "", engine: str = "piper", workers: int = 2, emotion: str = "neutral",
-            translate_to: str = "", provider: str = "ollama"):
-    """Batch pipeline: extract -> synthesize via queue -> wavs + SRT sidecar."""
-    import os
-
+            translate_to: str = "", provider: str = "ollama") -> dict:
+    """Generate audio and return the same per-line report exposed by the UI."""
     from app.core.extractor.dialogue_extractor import extract_dialogue
-    from app.core.queue.priority import Priority
-    from app.core.queue.task_queue import TaskQueue
+    from app.core.queue.task_queue import TaskQueue, TaskStatus
+    from app.core.translate import translate_line
     from app.core.tts.generator import generate_voice_to_file
     from app.utils.audio_utils import to_srt
 
     lines = extract_dialogue(folder)
-    if not lines:
-        print(f"No dialogue extracted from {folder}.")
-        return
-    if translate_to:
-        from app.core.translate import translate_lines
-
-        lines = translate_lines(lines, translate_to, provider=provider)
-        print(f"Translated {len(lines)} lines -> {translate_to} ({provider}).")
-    os.makedirs(out, exist_ok=True)
+    output = Path(out)
+    output.mkdir(parents=True, exist_ok=True)
+    results = []
     q = TaskQueue(workers=workers)
     jobs = []
-    for i, ln in enumerate(lines):
-        fname = f"{i:04d}_{(ln.speaker or 'narrator')}.wav"
-        dest = os.path.join(out, fname)
-        tid = q.submit(
-            generate_voice_to_file, ln, dest, voice=voice, engine=engine, emotion=emotion,
-            priority=Priority.NORMAL, name=fname,
-        )
-        jobs.append((tid, dest, ln))
-    snaps = q.wait_all(timeout=600)
-    q.shutdown()
-    ok = sum(1 for s in snaps if s["status"] == "done")
-    print(f"Generated {ok}/{len(snaps)} lines -> {out}")
-    for s in snaps:
-        if s["status"] == "failed":
-            print(f"FAILED {s['name']}: {(s['error'] or '').splitlines()[0]}")
-    srt_path = os.path.join(out, "dialogue.srt")
-    with open(srt_path, "w", encoding="utf-8") as fh:
-        fh.write(to_srt(lines))
-    print(f"Subtitles: {srt_path}")
+    try:
+        for i, line in enumerate(lines):
+            result = {
+                "index": i, "source_file": line.source_file, "line_no": line.line_no,
+                "speaker": line.speaker, "status": "failed", "skipped_reason": None,
+            }
+            results.append(result)
+            if translate_to:
+                try:
+                    line = translate_line(line, translate_to, provider=provider)
+                except Exception as exc:
+                    result["skipped_reason"] = f"Translation failed: {str(exc) or type(exc).__name__}"
+                    continue
+            line.voice_id = line.voice_id or voice
+            if line.emotion == "neutral":
+                line.emotion = emotion
+            name = f"{i:04d}_{line.speaker or 'narrator'}.wav"
+            tid = q.submit(generate_voice_to_file, line, str(output / name),
+                           engine=engine, name=name)
+            jobs.append((tid, line, result))
+        q.wait_all(timeout=600)
+    finally:
+        # After the deadline, stop taking new lines. A running writer must
+        # finish before its outcome can be included in the terminal report.
+        q.shutdown(wait=True)
+
+    completed = []
+    for tid, line, result in jobs:
+        task = q.status(tid)
+        if task["status"] == TaskStatus.DONE:
+            result.update(status="succeeded", wav=task["name"])
+            completed.append(line)
+        elif task["status"] == TaskStatus.FAILED:
+            result["skipped_reason"] = task["error"].splitlines()[0] or "TTS failed"
+        else:
+            result["skipped_reason"] = "Batch timed out before synthesis started"
+
+    total, succeeded = len(lines), len(completed)
+    failed = total - succeeded
+    if not succeeded:
+        status = "failed"
+    elif failed:
+        status = "partial"
+    else:
+        status = "done"
+    error = f"{failed} of {total} lines failed" if failed else ""
+    if not total:
+        error = "No dialogue extracted"
+    report = {
+        "status": status, "total": total, "succeeded": succeeded, "failed": failed,
+        "error": error, "lines": results,
+    }
+    (output / "dialogue.srt").write_text(to_srt(completed), encoding="utf-8")
+    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
+    print(f"Generated {succeeded}/{total} lines -> {out} ({status})")
+    for result in results:
+        if result["skipped_reason"]:
+            print(f"SKIPPED {result['source_file']}:{result['line_no']}: {result['skipped_reason']}")
+    return report
 
 
 def cmd_unpack(target: str, out: str, engine: str = "auto", unrealpak: str = "", aes_key: str = ""):
@@ -215,8 +247,10 @@
         p.add_argument("--provider", default="ollama")
         p.add_argument("--workers", type=int, default=2)
         a = p.parse_args(rest)
-        cmd_mod(a.folder, a.out, voice=a.voice, engine=a.engine, workers=a.workers, emotion=a.emotion,
-                translate_to=a.translate_to, provider=a.provider)
+        report = cmd_mod(a.folder, a.out, voice=a.voice, engine=a.engine, workers=a.workers,
+                         emotion=a.emotion, translate_to=a.translate_to, provider=a.provider)
+        if report["status"] != "done":
+            raise SystemExit(1)
     elif cmd == "unpack" and rest:
         import argparse
 
diff --git a/app/core/queue/task_queue.py b/app/core/queue/task_queue.py
--- a/app/core/queue/task_queue.py
+++ b/app/core/queue/task_queue.py
@@ -110,6 +110,9 @@
         with self._lock:
             return [dict(self._tasks[k]) for k in sorted(self._tasks)]
 
-    def shutdown(self) -> None:
-        """Stop workers (daemon threads also die with the process)."""
+    def shutdown(self, wait: bool = False) -> None:
+        """Stop accepting queued work and optionally wait for active writers."""
         self._stop.set()
+        if wait:
+            for thread in self._threads:
+                thread.join()
diff --git a/app/ui_server.py b/app/ui_server.py
--- a/app/ui_server.py
+++ b/app/ui_server.py
@@ -37,7 +37,7 @@
         _JOBS[job_id] = {"id": job_id, "status": "running", "params": params, "error": ""}
     def _run():
         try:
-            cmd_mod(
+            report = cmd_mod(
                 params.get("path", ""),
                 params.get("out", "./out"),
                 voice=params.get("voice", ""),
@@ -52,7 +52,7 @@
                 _JOBS[job_id].update(status="failed", error=str(exc)[:500])
         else:
             with _JOBS_LOCK:
-                _JOBS[job_id]["status"] = "done"
+                _JOBS[job_id].update(report)
 
     threading.Thread(target=_run, daemon=True, name=f"agv-mod-{job_id}").start()
     return job_id
diff --git a/tests/test_tauri.py b/tests/test_tauri.py
--- a/tests/test_tauri.py
+++ b/tests/test_tauri.py
@@ -33,6 +33,7 @@
         calls.append((path, out, kwargs))
         with open(os.path.join(tmp_path, "ok.txt"), "w") as fh:
             fh.write("done")
+        return {"status": "done", "total": 1, "succeeded": 1, "failed": 0, "error": "", "lines": []}
 
     import app.main as mainmod
 
diff --git a/tests/test_batch_status.py b/tests/test_batch_status.py
new file mode 100644
--- /dev/null
+++ b/tests/test_batch_status.py
@@ -0,0 +1,62 @@
+"""Terminal API status and the report on disk describe the same batch."""
+
+import json
+import time
+import wave
+
+import pytest
+
+from app import ui_server
+from app.core.tts import generator
+
+
+@pytest.mark.parametrize(
+    ("texts", "broken", "expected"),
+    [
+        (["First.", "Second."], {"Second."}, "partial"),
+        (["Only."], {"Only."}, "failed"),
+        ([], set(), "failed"),
+        (["Only."], set(), "done"),
+    ],
+)
+def test_mod_job_reports_every_line(tmp_path, monkeypatch, texts, broken, expected):
+    game = tmp_path / "game"
+    game.mkdir()
+    (game / "script.rpy").write_text(
+        "".join(f'e "{text}"\n' for text in texts), encoding="utf-8",
+    )
+    out = tmp_path / "out"
+
+    def synthesize(line, out_path, **kwargs):
+        if line.text in broken:
+            raise RuntimeError("test voice unavailable")
+        with wave.open(out_path, "wb") as wav:
+            wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
+            wav.writeframes(b"\0\0")
+        return out_path
+
+    monkeypatch.setattr(generator, "generate_voice_to_file", synthesize)
+    job = ui_server.start_mod_job({"path": str(tmp_path), "out": str(out)})
+    deadline = time.monotonic() + 5
+    snapshot = ui_server.mod_job_status(job)
+    while snapshot["status"] == "running" and time.monotonic() < deadline:
+        time.sleep(0.01)
+        snapshot = ui_server.mod_job_status(job)
+
+    assert snapshot["status"] == expected
+    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
+    assert {key: snapshot[key] for key in report} == report
+    assert (report["succeeded"], report["failed"], report["total"]) == (
+        len(texts) - len(broken), len(broken), len(texts),
+    )
+    assert len(report["lines"]) == len(texts)
+    subtitles = (out / "dialogue.srt").read_text(encoding="utf-8")
+    for i, (row, text) in enumerate(zip(report["lines"], texts)):
+        assert (row["index"], row["source_file"], row["line_no"]) == (i, "script.rpy", i + 1)
+        if text in broken:
+            assert row["status"] == "failed"
+            assert row["skipped_reason"] == "test voice unavailable"
+            assert text not in subtitles
+        else:
+            assert row["status"] == "succeeded" and row["skipped_reason"] is None
+            assert (out / row["wav"]).is_file() and text in subtitles
```
