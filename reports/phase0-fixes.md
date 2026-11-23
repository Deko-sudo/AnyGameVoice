# Фаза 0 — исправления

**Готовность Фазы 0 — да.** На эталонной сцене перевод и генерация завершаются с `done` и 27 WAV. После снятия файла исходный WAV восстановлен побайтно, в каталоге игры осталось ноль `.bak`.

## Три исправления

1. **Эмоции и подстановки.** Разбор начального тега и очистка текста для TTS используют имена из существующего словаря `EMOTIONS` — `neutral`, `happy`, `sad`, `angry`, `whisper` и `shouting`. Неизвестные имена в квадратных скобках сохраняются. Проверены отдельная подстановка, подстановка с последующим текстом и извлечение `{b}[player_name]{/b}` из сценария.
2. **Восстановление.** После успешного `shutil.copy2` функция `restore_file` удаляет использованную копию через `os.unlink`. Если файл уже исчез на этапе удаления, восстановление завершается успешно. При ошибке копирования backup сохраняется. Два пути к одному файлу, в том числе жёсткие ссылки, дают `SameFileError`. Новый вызов после успешного восстановления даёт `FileNotFoundError`.
3. **Снятие одного файла.** Экспортированная `uninstall_audio(target, backup)` проверяет, что копия относится к цели, и вызывает `restore_file(backup)`. Успех возвращает `True`, ошибка возвращает `False` с записью причины в журнал. Проверены корректная пара, отсутствующий backup, чужой backup и сбой копирования. Пример вызова добавлен в README, в раздел «Uninstalling a mod».

## Эталонная сцена

На обоих снимках выполнен одинаковый вызов `cmd_mod(..., translate_to="es")` со штатными `translate_line` и `translate_text`. Ответ `OllamaProvider.complete` и тестовый синтезатор PCM заменяли внешние модели. Сохранённый `report.json` совпал с результатом функции. До исправлений получалось `partial`, 25/27. После исправлений — `done`, 27/27, ошибок 0.

| Строка `game/script.rpy` | До | После | Текст на входе TTS | WAV |
|---|---|---|---|---|
| 18, `s` | `Translation failed: Translation is empty` | `succeeded` | `[player_name]` | `0009_s.wav` |
| 19, `e` | `Translation failed: Translation is empty` | `succeeded` | `[score]` | `0010_e.wav` |

## Полный прогон

Команда на обоих снимках — `python -B -m pytest -q -p no:cacheprovider tests`. Файлы проекта доступны только для чтения, временное хранилище и сеть изолированы.

| Снимок | Результат |
|---|---|
| До исправлений | `71 passed, 1 xfailed, 1 warning` |
| После исправлений | `78 passed, 1 warning` |

Проверка очистки `test_reference_restore_leaves_no_backups` прошла как обычный тест. Единственное предупреждение связано с поддержкой httpx в Starlette TestClient в существующем HTTP-тесте. Снятие целого мода по манифесту относится к Фазе 1. Проверка воспроизведения в Ren’Py SDK остаётся ручной.

## SHA-256 изменённых файлов

База — `862afd9` с наложенным `reports/phase0.patch`. В таблице приведены все существовавшие файлы, чьи байты изменились. В этой сессии созданы этот отчёт и `reports/phase0-fixes.patch`.

| Файл | До | После |
|---|---|---|
| `README.md` | `fff19fda2edb7a896ce2318f17ce43e814ceeb9a91f67e024d88563709479c2e` | `04808e5f68efc4c43241a0fed47dd0714da15fb25c16bc762d72307d33b82f69` |
| `app/core/replacer/audio_replacer.py` | `94ff7c161a88bd905f31c422cebd41caac35b01b85c9df2594dcb5adda86df93` | `7e18bf16a75d56be55a78f4a68d9cb3724e2a1bc6fa9485b0547e082968c4dc3` |
| `app/core/replacer/backup.py` | `be4de2c838f1cacfbd255242896ad0a7a26b1c3a5f60366a085effb5b7338a6a` | `73a4f7dfa739dd5ec4dc900d29a2e1a8e668f2cff1bf3538d33c8b175b422b6b` |
| `app/core/tts/emotions.py` | `cfb88b1d176a10864ee333932e5ee7c9aca8ddd0908e5530078818bacc61e217` | `2f764c0ad7eccd10cdd94f097ce18ab33ffb92e528ad98b63f67920f10189cce` |
| `reports/phase0.md` | `d2a8b598c6b672929314b2878acacb3c5fa75cc2cf24c4b08a269268919970de` | `8d229c3613cb6ca09de8f9e464b11e40d832f20040a2551f0a684f62214bcd37` |
| `tests/test_emotions.py` | `4fad0664ea6972f3287568334b67d7dc14f6a0aa48ca9ef05f9587d73353f867` | `7f6117223fa570c8120073a97fc234e347908f49a269533d7eb852c3cc514e37` |
| `tests/test_renpy_reference.py` | `e8f57dfbd0693358ea8f64e80936953a8e785328b6b7fa88a6751d2b79248a2d` | `bb284d0394658f2b2dbc81b255da531cc157a9613a97dec9810de867db3ad720` |
| `tests/test_replacer.py` | `63f83d51f4886d533e27aa6d59879cb061498f30fe49585274badbecb22ecbc7` | `fc70f920b431184f17937a7d74d76e54d6336272a84ccfcbca50256da64218fb` |

[Статус Фазы 0](phase0.md) · [Дифф поверх эталонного набора](phase0-fixes.patch)
