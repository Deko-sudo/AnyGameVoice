# Фаза 0 — маркеры TTS и очистка резервных копий

**83 теста прошли, xfail — 0.** Эталонная сцена дала `done`, 27/27 WAV. Обе правки вошли во второй из двух локальных коммитов.

## Маркеры и подстановки

В `app/core/tts/emotions.py` набор `STRIP_ALWAYS` объединяет ключи `EMOTIONS` и `BARK_MARKERS`. Очистка удаляет имена из этого набора с учётом исключений в `keep_markers`. Piper извлекает ведущую эмоцию для флагов просодии перед очисткой. XTTS и Silero получают очищенный текст через `app/core/tts/generator.py`, поскольку их адаптеры сами не вызывают `apply_emotion`.

| Движок | Вход | Текст для синтеза |
|---|---|---|
| Piper | `[laughs] Ha ha` | `Ha ha` |
| XTTS | `[sighs] Ha` | `Ha` |
| Silero | `[dragon] Rawr` | `[dragon] Rawr` |
| Bark | `[laughs] Ha ha` | `[laughs] Ha ha` |

**Решение для `[dragon]` — сохранять.** Это имя может быть переменной Ren’Py с тем же синтаксисом, что и `[score]`. Удаление произвольных имён повредило бы игровой текст. Поведение закреплено в docstring и тесте. Регрессия с `{b}[player_name]{/b}`, `[score]` и `[happy]` прошла. Тест через обычный вызов `generate_voice` также показал, что XTTS и Silero получают `hi [score]` при исходном `[laughs] hi [score]`. Ответы моделей в тестах подставные.

## Восстановление

После успешного `shutil.copy2` результат восстановления определён. Если `os.unlink` сообщает `FileNotFoundError`, очистка уже завершена. Прочие `OSError` при удалении пишутся в журнал с уровнем `WARNING`, путями и причиной. При воспроизведённом `PermissionError` функция `restore_file` вернула путь к цели, `uninstall_audio` вернула `True`, а цель и оставшаяся копия содержали исходные байты. Ошибка самого копирования по-прежнему даёт `False` через `uninstall_audio`.

В README обновлены правила для маркеров, значение `True` и описание предупреждения с путём к оставшемуся backup. [Uninstalling a mod](../README.md#uninstalling-a-mod) · [Translation and voice limitations](../README.md#translation-and-voice-limitations)

## Результаты проверок

Команда полного прогона — `python -B -m pytest -q -p no:cacheprovider tests`. Исходники были доступны только для чтения. Тесты использовали приватную временную папку и изолированную сеть.

| Снимок | Результат |
|---|---|
| Рабочее дерево до текущих правок | 78 passed, 1 warning |
| Новые регрессии до реализации, два целевых модуля | 4 failed, 14 passed |
| Исходный эталонный набор в первом коммите | 71 passed, 1 xfailed, 1 warning in 3.10s |
| Итоговое дерево второго коммита | 83 passed, 1 warning in 3.09s |

Первый коммит добавил пять новых файлов. В нём сохранена исходная версия теста из `reports/phase0.patch` с известным xfail очистки. Второй коммит добавил исправления и переключил тест на публичную `uninstall_audio`. Его дерево совпало с протестированным индексом. Единственное предупреждение полного прогона выдал существующий HTTP-тест Starlette о поддержке httpx.

## История и состав

Оба новых коммита созданы в локальной `main` от имени `Codex <codex@localhost>`, как и два предыдущих. Вывод `git log --oneline -4`

```text
9c2727a fix: подстановки Ren'Py, чистый restore, uninstall_audio
b4f1c3a feat: эталонный Ren'Py-набор для регрессионных проверок
862afd9 fix: атомарная публикация WAV, таймаут очереди и UI для partial
8485afc fix: единая модель Line и честный статус задания
```

Вывод `git diff 834834e..HEAD --stat`

```text
 README.md                                          |  60 ++++++++++
 app/core/extractor/dialogue_extractor.py           |   6 +-
 app/core/game_detector/engines/godot.py            |  20 ++--
 app/core/game_detector/engines/renpy.py            |  15 +--
 app/core/game_detector/engines/rpgmaker.py         |  15 +--
 app/core/queue/task_queue.py                       |  69 ++++++++----
 app/core/replacer/audio_replacer.py                |  22 +++-
 app/core/replacer/backup.py                        |  33 ++++--
 app/core/translate.py                              |  56 +++++----
 app/core/tts/emotions.py                           |  38 +++----
 app/core/tts/generator.py                          |  16 ++-
 app/main.py                                        | 125 +++++++++++++++------
 app/models/line.py                                 |  26 +++++
 app/ui_server.py                                   |   4 +-
 tests/fixtures/renpy_reference/.gitignore          |   1 +
 tests/fixtures/renpy_reference/expected.json       |  29 +++++
 tests/fixtures/renpy_reference/game/script.rpy     |  43 +++++++
 .../fixtures/renpy_reference/game/voice/beacon.wav | Bin 0 -> 3244 bytes
 tests/test_batch.py                                |  92 ++++++++++++++-
 tests/test_batch_status.py                         |  94 ++++++++++++++++
 tests/test_emotions.py                             |  38 ++++++-
 tests/test_queue.py                                |  39 +++++++
 tests/test_renpy_reference.py                      | 121 ++++++++++++++++++++
 tests/test_replacer.py                             | 111 ++++++++++++++++--
 tests/test_tauri.py                                |   1 +
 ui/index.html                                      |  16 ++-
 26 files changed, 933 insertions(+), 157 deletions(-)
```

Дифф этой доработки охватывает шесть файлов относительно рабочего дерева с предыдущими фиксами Фазы 0. Применение диффа к копии исходного состояния воспроизвело все шесть файлов побайтно. Отчёты хранятся отдельно от коммитов. [Дифф доработки](phase0-fixes-2.patch)
