# Два коммита AnyGameVoice

Оба коммита находятся в локальной ветке `main` поверх `834834e`. Выбранные файлы и их содержимое совпали с последовательным применением двух отчётов. Индекс пуст. Каталог `reports/` находится вне обоих коммитов.

## Коммиты и результаты тестов

| Коммит | Изменение | Файлы | Перед коммитом | После коммита |
|---|---|---:|---|---|
| `8485afc1960b763f4dae85c08a5c166fbfca80fe` | Единая модель Line и честный статус задания | 13 | 65 passed in 2.01s | 65 passed in 1.98s |
| `862afd9e2235ab0e9caaff61a8fe60623990ebed` | Атомарная публикация WAV, тайм-аут очереди и UI для partial | 7 | 68 passed, 1 warning in 1.61s | 68 passed, 1 warning in 1.46s |

Команда во всех четырёх прогонах — `python -B -m pytest -q -p no:cacheprovider tests`. Перед каждым коммитом использовался снимок индекса, после — архив созданного коммита. Исходники монтировались только для чтения, временные файлы создавались в приватной папке, сеть была изолирована.

## История

```text
862afd9 fix: атомарная публикация WAV, таймаут очереди и UI для partial
8485afc fix: единая модель Line и честный статус задания
834834e CI: unique bundle names per triple
```

## Изменения относительно базы

Вывод `git diff 834834e..HEAD --stat`

```text
 README.md                                  |  33 ++++++++
 app/core/extractor/dialogue_extractor.py   |   6 +-
 app/core/game_detector/engines/godot.py    |  20 ++---
 app/core/game_detector/engines/renpy.py    |  15 ++--
 app/core/game_detector/engines/rpgmaker.py |  15 ++--
 app/core/queue/task_queue.py               |  69 +++++++++++-----
 app/core/translate.py                      |  56 ++++++++-----
 app/core/tts/generator.py                  |  13 ++-
 app/main.py                                | 125 ++++++++++++++++++++---------
 app/models/line.py                         |  26 ++++++
 app/ui_server.py                           |   4 +-
 tests/test_batch.py                        |  92 ++++++++++++++++++++-
 tests/test_batch_status.py                 |  94 ++++++++++++++++++++++
 tests/test_queue.py                        |  39 +++++++++
 tests/test_tauri.py                        |   1 +
 ui/index.html                              |  16 +++-
 16 files changed, 513 insertions(+), 111 deletions(-)
```

## Изменения второго коммита

Вывод `git diff HEAD~1..HEAD --stat`

```text
 README.md                    | 33 ++++++++++++++++
 app/core/queue/task_queue.py | 68 ++++++++++++++++++++++-----------
 app/main.py                  | 91 ++++++++++++++++++++++++++------------------
 tests/test_batch.py          | 54 ++++++++++++++++++++++++++
 tests/test_batch_status.py   | 60 ++++++++++++++++++++++-------
 tests/test_queue.py          | 39 +++++++++++++++++++
 ui/index.html                | 16 +++++++-
 7 files changed, 286 insertions(+), 75 deletions(-)
```

## Расхождения и примечания

Количество файлов и результаты тестов совпали с ожиданиями. Единственное предупреждение второго набора — StarletteDeprecationWarning о поддержке установленного httpx в TestClient. Сам HTTP-тест прошёл. Проверка `git diff 834834e..HEAD --check` завершилась успешно.

Локальные имя и email Git отсутствовали, поэтому для двух коммитов использован автор и коммитер `Codex <codex@localhost>` через параметры команд. Конфигурация Git сохранена. Публикация в удалённый репозиторий не выполнялась.
