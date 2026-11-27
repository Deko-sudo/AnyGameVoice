// Beginner workflow: one folder, diagnosed inputs, background job, actionable result.
(() => {
  const stages = ['folder', 'dialogue', 'voice', 'synthesis', 'install', 'verify', 'result'];
  let steamGames = [];
  let gameLibraries = [];
  let discoveryPromise = null;
  let discoveryState = 'searching';
  let discoveryError = '';
  let pickerOpener = null;
  let startPending = false;
  let retryTrial = false;
  function show(phase, title, detail, error = false) {
    $('auto-title').textContent = title;
    $('auto-detail').textContent = detail;
    $('auto-status').classList.toggle('auto-error', error);
    const index = stages.indexOf(phase);
    document.querySelectorAll('[data-step]').forEach((node, i) => {
      node.hidden = ['install', 'verify'].includes(node.dataset.step) && !['renpy', 'source_lostcoast'].includes(state.engine);
      node.dataset.status = i < index ? 'done' : i === index ? error ? 'error' : 'current' : 'waiting';
      if (i === index) node.setAttribute('aria-current', 'step'); else node.removeAttribute('aria-current');
    });
  }
  function issue(data) {
    show('folder', 'Нужно уточнить папку игры', data.issue, true);
    $('auto-choices').replaceChildren();
    $('auto-choices').hidden = !data.candidates?.length;
    for (const candidate of data.candidates || []) {
      const button = el('button', 'button secondary', candidate.name);
      button.type = 'button';
      button.addEventListener('click', () => { $('game-path').value = candidate.path; loadGame(); });
      $('auto-choices').append(button);
    }
    $('auto-retry').hidden = true;
    notice(data.issue, 'error');
  }
  async function start(useSelection = false, trial = false) {
    if (startPending || state.setupBusy || state.loading || state.busy || running() || !state.lines.length) return;
    retryTrial = trial;
    startPending = true; state.busy = true; updateControls();
    $('auto-retry').hidden = true;
    show('voice', 'Проверяем готовность', useSelection ? 'Проверяем выбранные голоса и возможность установки.' : 'Определяем язык реплик, проверяем модель и свободную память.');
    notice('Подготавливаем автоматическую озвучку…');
    try {
      await refreshVoices();
      const chosen = settings();
      const translation = dubbingRequest(trial);
      const selection = useSelection || (translation.translate_to && chosen.voice) ? {voice: chosen.voice, engine: chosen.engine, emotion: chosen.emotion, language: chosen.language, out: chosen.out, workers: chosen.workers, character_voices: chosen.character_voices, voice_blend: chosen.voice_blend} : null;
      const data = await api('/api/studio/auto', {path: state.game, sdk: $('renpy-sdk').value.trim(), selection, ...translation});
      const params = data.settings;
      $('tts-engine').value = params.engine; $('voice-select').value = ''; $('voice-path').value = params.voice;
      $('voice-language').value = params.language; $('voice-emotion').value = params.emotion;
      $('worker-count').value = params.workers; $('output-path').value = params.out;
      if (params.renpy_sdk) $('renpy-sdk').value = params.renpy_sdk;
      state.assignments = Object.assign(Object.create(null), params.character_voices); renderVoiceOptions();
      remember(data.job_id);
      state.job = {id: data.job_id, status: 'running', install_engine: params.install_engine, stage: 'preparing', total: state.lines.length, succeeded: 0, failed: 0};
      show('synthesis', 'Создаём озвучку автоматически', 'Голос и папка результата выбраны. Можно оставить студию открытой и дождаться окончания.');
      setTab('jobs'); renderJob(); await pollJob(data.job_id);
    } catch (error) {
      const message = friendlyError(error);
      show('voice', 'Автоматический запуск остановлен', message, true);
      if (message.includes('SDK')) { $('manual-settings').open = true; $('renpy-sdk').focus(); }
      $('auto-retry').hidden = false; notice(message, 'error');
      if (useSelection && !/SDK|FFmpeg|renpy.sh/.test(message)) {
        $('manual-settings').open = true;
        notice(`${message} Проверьте выбранный голос и назначения персонажей, затем повторите запуск.`, 'error');
      } else if (/SDK|Piper|голос|FFmpeg|renpy.sh/.test(message)) {
        window.agvSetup?.offer(trial ? null : useSelection ? 'selected' : 'auto');
      }
    } finally { startPending = false; state.busy = false; updateControls(); }
  }
  function job(data) {
    if ('trial' in data) retryTrial = data.trial;
    if (data.result?.trial) {
      show('voice', 'Пробный дубляж', 'Послушайте реплики в разделе «Генерация». Полный запуск доступен в панели озвучки.', data.status !== 'done');
      return;
    }
    if (activeStatuses.has(data.status)) {
      const name = data.install_engine === 'renpy' ? 'Ren’Py' : 'Lost Coast';
      if (data.stage === 'preparing' && data.status !== 'cancelling') show('voice', 'Проверяем совместимость игры', 'До записи проверяем сценарии, идентификаторы реплик и возможность безопасной установки.');
      else if (data.stage === 'installing' && data.status !== 'cancelling') show('install', `Устанавливаем озвучку ${name}`, 'Сопоставляем реплики и устанавливаем мод отдельной папкой.');
      else if (data.stage === 'verifying' && data.status !== 'cancelling') show('verify', 'Проверяем установленную озвучку', 'Проверяем контрольные суммы и соответствие реплик текущему сценарию.');
      else show('synthesis', data.status === 'cancelling' ? 'Останавливаем запись…' : 'Создаём озвучку', `${data.succeeded || 0} из ${data.total || state.lines.length} реплик готовы. Ошибок: ${data.failed || 0}.`);
      return;
    }
    const installation = data.result?.installation;
    if (installation?.status === 'disabled') {
      show('result', 'Мод отключён', installation.note);
    } else if (data.status === 'done') {
      const checked = installation?.verification?.status === 'ok';
      show('result', installation?.status === 'installed' ? checked ? 'Озвучка установлена и проверена' : 'Мод установлен — нужна проверка' : 'Аудиофайлы готовы',
        installation?.status === 'installed' ? checked ? 'Можно запускать игру. Проверка файлов пройдена; звучание можно оценить в игре. Мод можно отключить в результате.' : 'Нажмите «Проверить озвучку», чтобы проверить установленные файлы.' : `Создано ${data.succeeded} реплик. Откройте папку результата или прослушайте их в студии. Для этой игры подключение аудио выполняется отдельно.`);
    } else {
      show(installation ? 'install' : 'synthesis', data.status === 'cancelled' ? 'Задача остановлена' : installation ? 'Аудио создано — установка требует внимания' : 'Нужен повторный запуск',
        installation?.error || data.error ? friendlyError(new Error(installation?.error || data.error)) : `Готово ${data.succeeded || 0} из ${data.total || state.lines.length}. Нажмите «Продолжить автоматически»: проверенные файлы будут использованы повторно.`, data.status !== 'cancelled');
      $('auto-retry').hidden = false;
    }
  }
  function remember(id) {
    try { sessionStorage.setItem('agv-current-job', JSON.stringify({id, project: settings()})); }
    catch { /* Storage can be unavailable in private browser contexts. */ }
  }
  async function restore() {
    let saved;
    try { saved = JSON.parse(sessionStorage.getItem('agv-current-job') || 'null'); } catch { return; }
    if (!saved?.project || saved.project.schema !== 'anygamevoice-project' || typeof saved.project.path !== 'string' || !Number.isInteger(saved.id)) return;
    if (typeof saved.project.renpy_sdk === 'string') $('renpy-sdk').value = saved.project.renpy_sdk;
    $('auto-mode').checked = saved.project.automatic !== false;
    $('manual-settings').open = !$('auto-mode').checked;
    $('game-path').value = saved.project.path;
    $('tts-engine').value = saved.project.engine;
    $('voice-path').value = saved.project.voice || ''; $('voice-select').value = '';
    $('voice-language').value = saved.project.language || 'ru';
    $('voice-emotion').value = saved.project.emotion || 'neutral';
    $('worker-count').value = saved.project.workers || 1;
    renderVoiceOptions();
    await loadGame(Boolean(saved.project.demo), saved.project);
    if (!state.game) return;
    try {
      const snapshot = await api(`/api/studio/mod/${saved.id}`);
      // A restarted backend may reuse numeric IDs for a different project.
      if ((snapshot.game_path && snapshot.game_path !== state.game) || (snapshot.result && snapshot.result.game_path !== state.game)) throw new Error('Сервер перезапущен.');
      state.job = snapshot; setTab('jobs');
      await pollJob(saved.id);
    } catch {
      show('voice', 'Проект восстановлен', 'Сервер перезапущен. Продолжите автоматически: проверенные аудиофайлы сохранены на диске.');
      $('auto-retry').hidden = false;
    }
  }
  function sync() {
    const occupied = state.busy || state.setupBusy || state.loading || running();
    for (const id of ['auto-mode', 'steam-games', 'auto-retry', 'renpy-sdk', 'browse-sdk']) $(id).disabled = occupied;
    $('help-choose').disabled = occupied;
    $('help-demo').disabled = occupied;
    document.querySelectorAll('#auto-choices button').forEach(button => { button.disabled = occupied; });
  }
  function withPeriod(text) { return /[.!?]$/.test(text) ? text : `${text}.`; }
  function pickerMessage(text, error = false) {
    $('steam-list').replaceChildren(el('p', error ? 'notice error' : 'muted', text));
  }
  function gameOrder(a, b) {
    const known = (String(a.appid) === '340' ? 0 : 1) - (String(b.appid) === '340' ? 0 : 1);
    return known || String(a.name || '').localeCompare(String(b.name || ''), 'ru');
  }
  function setChoiceState() {
    const library = $('steam-games');
    const folder = $('browse-game');
    const found = discoveryState === 'found';
    library.classList.toggle('primary', found);
    library.classList.toggle('secondary', !found);
    folder.classList.toggle('primary', !found);
    folder.classList.toggle('secondary', found);
    library.textContent = found ? `Выбрать из библиотеки (${steamGames.length})`
      : discoveryState === 'error' ? 'Повторить поиск'
      : discoveryState === 'empty' ? 'Найти игры' : 'Ищем игры…';
    $('source-hint').textContent = found
      ? `Найдено игр: ${steamGames.length} · библиотек: ${gameLibraries.length}. Выберите игру или укажите папку.`
      : discoveryState === 'error' ? `${withPeriod(discoveryError)} Можно выбрать папку вручную.`
      : discoveryState === 'empty' ? 'Игры автоматически не найдены. Можно выбрать папку вручную.'
      : 'Ищем установленные игры…';
  }
  function filterSteam() {
    if (discoveryState !== 'found') return;
    const query = $('steam-filter').value.trim().toLocaleLowerCase();
    const games = steamGames.filter(game => String(game.name || '').toLocaleLowerCase().includes(query));
    $('steam-list').replaceChildren();
    for (const game of games) {
      const button = el('button', 'steam-game'); button.type = 'button';
      button.append(icon('folder'), el('span', '', game.name));
      button.append(el('small', '', game.source || 'Steam'));
      if (String(game.appid) === '340') button.append(el('small', '', 'Короткая игра · установка мода поддерживается'));
      button.addEventListener('click', () => {
        $('steam-picker').close(); $('game-path').value = game.path; loadGame();
      });
      $('steam-list').append(button);
    }
    if (!games.length) pickerMessage('По этому названию игр нет.');
  }
  async function discoverGames() {
    if (discoveryPromise) return discoveryPromise;
    discoveryState = 'searching';
    setChoiceState();
    discoveryPromise = api('/api/studio/games').then(data => {
      steamGames = [...(data.games || [])].sort(gameOrder);
      gameLibraries = data.libraries || [];
      discoveryState = steamGames.length ? 'found' : 'empty';
      setChoiceState();
      return data;
    }).catch(error => {
      discoveryState = 'error';
      discoveryError = friendlyError(error);
      steamGames = []; gameLibraries = [];
      setChoiceState();
      throw error;
    }).finally(() => { discoveryPromise = null; });
    return discoveryPromise;
  }
  async function openSteam() {
    if ($('steam-picker').open) return;
    pickerOpener = document.activeElement || $('steam-games');
    $('steam-filter').value = ''; $('steam-filter').hidden = true;
    $('game-libraries').textContent = 'Ищем библиотеки…';
    pickerMessage(discoveryState === 'error' ? 'Повторяем поиск…' : 'Ищем установленные игры…');
    $('steam-picker').showModal();
    try {
      await discoverGames();
      if (!$('steam-picker').open) return;
      $('game-libraries').textContent = gameLibraries.length ? `Найденные папки: ${gameLibraries.join(' · ')}` : 'Библиотеки автоматически не найдены.';
      if (discoveryState === 'empty') pickerMessage('Игры не найдены в доступных библиотеках. Выберите папку вручную.');
      else { $('steam-filter').hidden = false; filterSteam(); }
    } catch (error) {
      $('game-libraries').textContent = 'Поиск библиотек завершился ошибкой.';
      pickerMessage(`${withPeriod(friendlyError(error))} Выберите папку вручную.`, true);
    }
  }
  discoverGames().catch(() => {});
  try { $('renpy-sdk').value = localStorage.getItem('agv-renpy-sdk') || ''; } catch {}
  $('renpy-sdk').addEventListener('change', () => { try { localStorage.setItem('agv-renpy-sdk', $('renpy-sdk').value.trim()); } catch {} });
  $('steam-games').addEventListener('click', openSteam);
  $('steam-picker').addEventListener('keydown', event => {
    if (event.key === 'Escape' && !event.isComposing) {
      event.preventDefault();
      $('steam-picker').close();
    }
  });
  $('steam-picker').addEventListener('close', () => {
    const opener = pickerOpener;
    pickerOpener = null;
    if (opener?.isConnected && !opener.disabled) opener.focus();
  });
  $('steam-filter').addEventListener('input', filterSteam);
  $('help-button').addEventListener('click', () => $('help-dialog').showModal());
  $('help-choose').addEventListener('click', () => { $('help-dialog').close(); openSteam(); });
  $('help-demo').addEventListener('click', () => { $('help-dialog').close(); openDemo(); });
  $('auto-retry').addEventListener('click', () => start(!$('auto-mode').checked, retryTrial));
  $('auto-selected').addEventListener('click', () => start(true));
  for (const id of ['tts-engine','voice-select','voice-path','voice-language','voice-emotion','output-path','worker-count']) $(id).addEventListener('change', () => {
    if (state.busy || state.loading || running()) return;
    $('auto-mode').checked = false; updateControls();
    show('voice', 'Ручные настройки', 'Создайте аудио или, для Ren’Py и Lost Coast, создайте и подключите выбранный голос.');
  });
  $('auto-mode').addEventListener('change', () => {
    updateControls();
    $('manual-settings').open = !$('auto-mode').checked;
    show('folder', $('auto-mode').checked ? 'Автоматический режим включён' : 'Ручной режим',
      $('auto-mode').checked ? 'При следующем выборе игры запись запустится сама. Текущие настройки можно сохранить как проект.' : 'Выберите игру, настройте голос и нажмите «Создать озвучку».');
  });
  document.addEventListener('agv:controls', sync);
  window.agvAuto = {
    start, remember, restore,
    prepare() {
      retryTrial = false;
      $('auto-choices').hidden = true; $('auto-retry').hidden = true;
      show('dialogue', 'Проверяем игру и ищем диалоги', 'Если выбрана общая папка, найдём игру внутри или предложим список.');
    },
    issue,
    async loaded({data, restored}) {
      if (!$('auto-mode').checked || restored?.schema) {
        show('voice', 'Игра открыта — настройки доступны', `${data.total} реплик. Выберите голос и нажмите «Создать озвучку», когда будете готовы.`);
        return;
      }
      if ($('dub-direction').value) {
        show('voice', 'Можно послушать пробный дубляж', data.install_supported ? 'Проверьте переводчик и голос. После пробы можно установить полный дубляж.' : 'Проверьте переводчик и голос. Для этой игры будут созданы WAV-файлы для отдельного подключения.');
        return;
      }
      await start();
    },
    job,
    reset() { try { sessionStorage.removeItem('agv-current-job'); } catch {} $('auto-retry').hidden = true; $('auto-choices').hidden = true; show('folder', 'Выберите папку — начнём автоматически', 'Для Ren’Py и Lost Coast установим и проверим мод. Для RPG Maker и Godot подготовим аудиофайлы.'); }
  };
})();
