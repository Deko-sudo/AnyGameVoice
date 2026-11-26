'use strict';

const $ = id => document.getElementById(id);
const PAGE_SIZE = 6;
const defaultVoiceBlend = () => ({strength: 0.95, base_voice: '', protected_voices: []});
const state = {voiceBlend: defaultVoiceBlend(), lines: [], characters: [], voices: [], engines: {}, game: '', engine: '', assignments: Object.create(null),
  page: 0, view: 'all', tab: 'dialogue', job: null, busy: false, demo: false, audioUrl: null, setupBusy: false, loading: false, resultIndex: new Map()};
const statusNames = {running: 'Идёт генерация', queued: 'В очереди', cancelling: 'Останавливаем запись',
  done: 'Озвучка создана', partial: 'Часть реплик требует внимания', failed: 'Генерация не завершена', cancelled: 'Генерация остановлена'};
const activeStatuses = new Set(['running', 'queued', 'cancelling']);
let pollTimer;
let projectVersion = 0;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `#i-${name}`); svg.append(use); return svg;
}
function notice(text, kind = '') {
  $('notice').textContent = text; $('notice').className = `notice ${kind}`;
  $('notice').hidden = !text; $('notice').setAttribute('role', kind === 'error' ? 'alert' : 'status');
}
function friendlyError(error) {
  const message = error.message || String(error);
  const translations = [
    ['Game folder does not exist.', 'Папка игры не найдена. Проверьте полный путь.'],
    ['Choose a Piper .onnx model before generating audio.', 'Выберите файл модели Piper (.onnx).'],
    ['Piper also needs the matching .onnx.json file beside the model.', 'Рядом с моделью нужен файл с тем же именем и окончанием .onnx.json.'],
    ['Choose an output folder outside the game folder.', 'Укажите папку результата вне каталога игры.'],
    ['A batch is already running. Wait or cancel it first.', 'Уже идёт генерация. Дождитесь завершения или остановите её.'],
    ['Synthesis is busy. Wait for the current job.', 'Сейчас идёт запись. Дождитесь её завершения.']
  ];
  if (message === 'Failed to fetch' || message.includes('NetworkError')) return 'Нет связи с локальной студией. Проверьте, что сервер приложения запущен.';
  if (message.startsWith('No supported dialogue found')) return 'Поддерживаемые диалоги не найдены. Нужны открытые сценарии .rpy, RPG Maker JSON или Godot .dialogue. Архивы .rpa и .rpyc пока не поддерживаются.';
  if (message.startsWith('Output conflict:')) return 'В папке результата уже есть файлы, происхождение или целостность которых не удалось подтвердить. Выберите другую папку результата или переместите существующие файлы, затем повторите запуск.';
  if (message.includes('not installed')) return 'Выбранный движок синтеза не установлен. Выберите доступный движок или установите его зависимости.';
  return translations.find(([source]) => source === message)?.[1] || message;
}
async function responseError(response) {
  let detail;
  try { detail = (await response.json()).detail; } catch { /* Use the HTTP status below. */ }
  if (Array.isArray(detail)) detail = detail.map(issue => {
    const field = issue.loc?.at(-1);
    if (field === 'strength') return 'Сила переноса тембра (strength) должна быть числом от 0 до 1.';
    return `${field || 'Поле'}: ${issue.msg}`;
  }).join('; ');
  const error = new Error(typeof detail === 'string' ? detail : `Ошибка запроса (${response.status}).`);
  error.status = response.status;
  throw error;
}
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  if (!response.ok) await responseError(response);
  return response.json();
}
function running() { return state.job && activeStatuses.has(state.job.status); }
function selectedVoice() { return $('voice-select').value || $('voice-path').value.trim(); }
function speakerName(name) { return name === 'narrator' ? 'Рассказчик' : state.demo ? ({mira: 'Мира', lev: 'Лев'}[name] || name) : name; }
function speakerIndex(name) { return Math.max(0, state.characters.findIndex(c => c.name === name)) % 3; }
function speakerBadge(name) {
  const node = el('span', 'speaker-name');
  node.append(el('span', `speaker-initial tone-${speakerIndex(name)}`, speakerName(name).slice(0, 1).toUpperCase()), el('span', '', speakerName(name)));
  return node;
}
function synthesisParams(voice = selectedVoice()) {
  return {engine: $('tts-engine').value, voice, emotion: $('voice-emotion').value, language: $('voice-language').value};
}
function settings() {
  return {schema: 'anygamevoice-project', version: 1, automatic: !!$('auto-mode')?.checked, renpy_sdk: $('renpy-sdk').value.trim(), path: state.game || $('game-path').value.trim(), out: $('output-path').value.trim(),
    ...synthesisParams(), voice_blend: state.voiceBlend, workers: Number($('worker-count').value), character_voices: {...state.assignments}, demo: state.demo, studio_context: window.agvModels?.snapshot() || {}};
}
function updateControls() {
  const occupied = state.busy || state.setupBusy || state.loading || running();
  const engine = $('tts-engine').value;
  const needsVoice = engine === 'piper' || engine === 'xtts';
  const hasVoice = !!selectedVoice() || (state.characters.length > 0 && state.characters.every(c => !!state.assignments[c.name]));
  $('generate-button-text').textContent = $('auto-mode')?.checked ? 'Создать автоматически' : 'Создать озвучку';
  $('generate-button').disabled = occupied || !state.lines.length || !state.engines[engine] || (needsVoice && !hasVoice) || !$('output-path').value.trim();
  $('auto-selected').hidden = $('auto-mode').checked || !['renpy', 'source_lostcoast'].includes(state.engine);
  $('auto-selected').disabled = $('generate-button').disabled;
  $('preview-button').disabled = occupied || !state.engines[engine] || (needsVoice && !selectedVoice());
  for (const id of ['extract-button', 'browse-game', 'demo-button', 'demo-empty', 'demo-side', 'new-project', 'import-project']) $(id).disabled = occupied;
  for (const id of ['tts-engine', 'voice-select', 'voice-path', 'voice-language', 'voice-emotion', 'output-path', 'worker-count', 'game-path']) $(id).disabled = occupied;
  document.querySelectorAll('.character-model input,.character-model select').forEach(node => { node.disabled = occupied; });
  document.querySelectorAll('.play-button').forEach(node => { node.disabled = occupied || (!state.engines[engine] && node.dataset.hasAudio !== '1'); });
  $('project-json-open').disabled = occupied;
  $('save-project').disabled = !state.game || state.loading;
  document.dispatchEvent(new Event('agv:controls'));
  $('cancel-button').hidden = !running(); $('cancel-button').disabled = state.job?.status === 'cancelling';
  $('generate-label').textContent = running() ? 'Запись выполняется на компьютере' : state.lines.length ? `${state.lines.length} реплик · WAV + манифест` : state.game ? 'Нужны извлечённые реплики' : 'Откройте игру для начала';
}
function setTab(tab) {
  state.tab = tab;
  ['dialogue', 'voices', 'jobs', 'research'].forEach(name => {
    $(`${name}-panel`).hidden = name !== tab;
    const button = document.querySelector(`[data-tab="${name}"]`);
    button.classList.toggle('active', name === tab);
    if (name === tab) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
}
function resultFor(line) {
  return state.resultIndex.get(JSON.stringify([line.source_file, line.line_no, line.speaker, line.text]));
}
function completedLines() { return state.lines.filter(line => resultFor(line)?.status === 'done'); }
function renderLines() {
  const query = $('line-search').value.trim().toLocaleLowerCase();
  const speaker = $('speaker-filter').value;
  const filtered = state.lines.filter(line => (!speaker || line.speaker === speaker) && (!query || `${line.text} ${line.speaker} ${line.source_file}`.toLocaleLowerCase().includes(query)) && (state.view !== 'ready' || resultFor(line)?.status === 'done'));
  state.page = Math.min(state.page, Math.max(0, Math.ceil(filtered.length / PAGE_SIZE) - 1));
  const from = state.page * PAGE_SIZE;
  const body = $('dialogue-body'); body.replaceChildren();
  filtered.slice(from, from + PAGE_SIZE).forEach(line => {
    const result = resultFor(line);
    const row = el('tr'); row.append(el('td', 'line-number', String(state.lines.indexOf(line) + 1).padStart(2, '0')));
    const who = el('td', 'speaker-cell'); who.append(speakerBadge(line.speaker)); row.append(who);
    const text = el('td', 'line-text', line.text); text.append(el('span', 'line-source', `${line.source_file}:${line.line_no || '—'}`)); row.append(text);
    const status = result?.status || 'pending';
    const statusLabel = ({done: 'Готово', failed: 'Ошибка', cancelled: 'Остановлена', pending: 'К генерации', running: 'Запись'})[status] || 'К генерации';
    const badge = el('span', `line-state ${status}`); badge.append(el('i'), document.createTextNode(statusLabel));
    if (result?.error) badge.title = result.error;
    const statusCell = el('td'); statusCell.append(badge); row.append(statusCell);
    const playCell = el('td'); const play = el('button', 'play-button'); play.type = 'button';
    play.dataset.hasAudio = result?.status === 'done' ? '1' : '';
    play.setAttribute('aria-label', `Прослушать реплику ${state.lines.indexOf(line) + 1}`); play.title = result?.status === 'done' ? 'Прослушать готовое аудио' : 'Создать пробную запись'; play.append(icon('play'));
    play.addEventListener('click', () => preview(line)); playCell.append(play); row.append(playCell); body.append(row);
  });
  $('no-matches').hidden = !!filtered.length;
  $('page-label').textContent = filtered.length ? `${from + 1}–${Math.min(from + PAGE_SIZE, filtered.length)} из ${filtered.length} реплик` : '0 реплик';
  $('previous-page').disabled = !state.page; $('next-page').disabled = from + PAGE_SIZE >= filtered.length;
  $('ready-count').textContent = completedLines().length;
  updateControls();
}
function renderVoiceOptions() {
  const selected = selectedVoice(); const engine = $('tts-engine').value;
  $('voice-select').replaceChildren(new Option('Указать путь к модели', ''));
  state.voices.filter(v => v.engine === engine).forEach(v => $('voice-select').add(new Option(`${v.name}${v.language ? ` · ${v.language}` : ''}`, v.path)));
  $('voice-select').value = state.voices.some(v => v.path === selected && v.engine === engine) ? selected : '';
  $('voice-path').value = selected; $('voice-path').hidden = !!$('voice-select').value;
  $('engine-hint').textContent = state.engines[engine] ? 'Движок доступен на этом компьютере; модель проверяется пробной записью.' : ({piper:'Piper не установлен. Установите piper-tts перед генерацией.',xtts:'XTTS не установлен. Назначить образцы можно сейчас; для синтеза нужен движок.',silero:'Silero не установлен.',bark:'Bark не установлен.'})[engine];
  $('voice-hint').textContent = engine === 'piper' ? 'Нужны .onnx и .onnx.json рядом. Модели из папки models/ появятся в списке.' : engine === 'xtts' ? 'Укажите WAV-образец голоса для клонирования.' : engine === 'silero' ? 'Текущий адаптер Silero использует английскую модель. Голос: en_0.' : 'Укажите пресет Bark или оставьте поле пустым.';
  $('voice-path').placeholder = engine === 'piper' ? '/путь/к/голосу.onnx' : engine === 'xtts' ? '/путь/к/образцу.wav' : engine === 'silero' ? 'en_0' : 'v2/en_speaker_6';
  if (engine === 'silero') $('voice-language').value = 'en';
  renderCharacters(); updateControls();
}
function preserveManualChoice() {
  if ($('auto-mode').checked) {
    $('auto-mode').checked = false;
    $('auto-mode').dispatchEvent(new Event('change'));
  }
}
function renderCharacters() {
  const list = $('characters-list'); list.replaceChildren();
  if (!state.characters.length) { list.append(el('p', 'muted', 'Сначала откройте игру с диалогами.')); return; }
  state.characters.forEach(character => {
    const row = el('div', 'character-row');
    const identity = el('div', 'character-identity'); const name = el('div');
    name.append(el('strong', '', speakerName(character.name)), el('small', '', `${character.count} реплик`));
    identity.append(el('span', `speaker-initial tone-${speakerIndex(character.name)}`, speakerName(character.name).slice(0, 1).toUpperCase()), name);
    const model = el('div', 'character-model'); const select = el('select'); select.setAttribute('aria-label', `Голос: ${speakerName(character.name)}`);
    select.add(new Option('Основной голос', ''));
    state.voices.filter(v => v.engine === $('tts-engine').value).forEach(v => select.add(new Option(v.name, v.path)));
    select.add(new Option('Другой путь…', '__custom'));
    const selected = state.assignments[character.name] || '';
    select.value = !selected ? '' : state.voices.some(v => v.path === selected) ? selected : '__custom';
    const input = el('input'); input.type = 'text'; input.value = selected; input.placeholder = '/путь/к/модели'; input.setAttribute('aria-label', `Путь голоса: ${speakerName(character.name)}`); input.hidden = select.value !== '__custom';
    select.addEventListener('change', () => { input.hidden = select.value !== '__custom'; state.assignments[character.name] = select.value === '__custom' ? input.value.trim() : select.value; preserveManualChoice(); updateControls(); });
    input.addEventListener('change', () => { state.assignments[character.name] = input.value.trim(); preserveManualChoice(); updateControls(); });
    model.append(select, input);
    const play = el('button', 'play-button'); play.setAttribute('aria-label', `Прослушать голос: ${speakerName(character.name)}`); play.append(icon('play'));
    play.addEventListener('click', () => preview(state.lines.find(line => line.speaker === character.name), true));
    row.append(identity, model, play); list.append(row);
  });
}
async function refreshVoices() {
  const data = await api('/api/studio/voices'); state.voices = data.voices; state.engines = data.engines;
  renderVoiceOptions();
}
async function loadGame(demo = false, restored = null) {
  if (running() || state.loading || state.busy || state.setupBusy) return;
  const path = $('game-path').value.trim();
  if (!path) { notice('Укажите полный путь к папке игры.', 'error'); $('game-path').focus(); return; }
  if (!restored && state.game && state.game !== path) { resetProject(); $('game-path').value = path; }
  state.loading = true; updateControls(); notice('Читаем сценарии и собираем персонажей…');
  $('extract-button').textContent = 'Читаем…'; const version = ++projectVersion;
  let opened = null; window.agvAuto?.prepare();
  try {
    const data = await api(demo || restored ? '/api/studio/extract' : '/api/studio/prepare', {path, limit: 10000});
    if (version !== projectVersion) return;

    if (data.ready === false) { window.agvAuto?.issue(data); return; }
    $('game-path').value = data.path;
    if (data.language && !restored) $('voice-language').value = data.language;
    state.lines = data.lines; state.characters = data.characters; state.engine = data.engine; state.game = data.path;
    if (restored?.schema) state.voiceBlend = restored.voice_blend || defaultVoiceBlend();
    state.assignments = Object.assign(Object.create(null), restored?.character_voices || {}); state.demo = demo; state.page = 0; state.job = null; state.resultIndex.clear();
    clearTimeout(pollTimer); $('job-indicator').hidden = true; $('mini-progress').hidden = true;
    const name = demo ? 'Ночной сигнал' : data.engine === 'source_lostcoast' ? 'Half-Life 2: Lost Coast' : data.path.split(/[\\/]/).filter(Boolean).at(-1);
    $('project-title').textContent = name; $('crumb').textContent = name;
    $('heading-kicker').textContent = demo ? 'УЧЕБНАЯ СЦЕНА · REN’PY' : 'ПРОЕКТ ОЗВУЧКИ';
    $('project-description').textContent = demo ? 'Небольшая история, чтобы освоиться в студии. Выберите голоса и попробуйте запись.' : $('auto-mode')?.checked ? 'Подготовка, запись и сохранение выполняются автоматически.' : 'Назначьте голоса персонажам и создайте аудио для игровых реплик.';
    $('engine-badge').replaceChildren(icon('folder'), el('span', '', ({renpy: 'Ren’Py', rpgmaker: 'RPG Maker', godot: 'Godot', redengine: 'REDengine', source_lostcoast: 'Source · Lost Coast'})[data.engine] || data.engine));
    $('stat-lines').textContent = data.total; $('nav-lines').textContent = data.total;
    $('stat-characters').textContent = data.characters.length; $('nav-characters').textContent = data.characters.length;
    $('stat-files').textContent = new Set(data.lines.map(line => line.source_file)).size;
    $('project-state').textContent = data.total ? 'Диалоги извлечены' : 'Исследование доступно'; $('dialogue-caption').textContent = 'Выберите реплику, чтобы послушать голос';
    $('output-path').value = restored?.out || data.suggested_out;
    $('speaker-filter').replaceChildren(new Option('Все персонажи', ''));
    data.characters.forEach(c => $('speaker-filter').add(new Option(speakerName(c.name), c.name)));
    $('line-search').value = ''; $('empty-state').hidden = true;
    for (const id of ['table-wrap', 'table-toolbar', 'table-footer']) $(id).hidden = !state.lines.length;
    $('preview-text').value = state.lines.find(line => line.speaker !== 'narrator')?.text || state.lines[0]?.text || 'У каждой истории есть голос.';
    setView('all'); renderCharacters(); renderJob(); setTab('dialogue');
    await window.agvModels?.onGameLoaded({name, demo, restored});
    opened = data;
    notice(!data.total ? 'Игра открыта. Извлечение её диалогов пока не поддерживается; исследование доступно.' : data.truncated ? 'Показана часть реплик. Размер проекта превышает лимит этой версии.' : '');
  } catch (error) { notice(friendlyError(error), 'error'); window.agvAuto?.issue({issue: friendlyError(error)}); }
  finally { state.loading = false; $('extract-button').replaceChildren(document.createTextNode('Открыть игру'), icon('arrow')); updateControls(); }
  if (opened) await window.agvAuto?.loaded({data: opened, restored, demo});
}
async function openDemo() {
  if (running() || state.busy || state.setupBusy || state.loading) return;
  try { const demo = await api(`/api/studio/demo?sdk=${encodeURIComponent($('renpy-sdk').value.trim())}`); $('game-path').value = demo.path; await loadGame(true, {out: demo.out}); }
  catch (error) { notice(friendlyError(error), 'error'); if (friendlyError(error).includes('SDK')) window.agvSetup?.offer('demo'); }
}
async function playAudio(url, label, revoke = false) {
  if (state.audioUrl) URL.revokeObjectURL(state.audioUrl);
  state.audioUrl = revoke ? url : null;
  $('audio').src = url; $('audio-label').textContent = label; $('audio-player').hidden = false;
  try { await $('audio').play(); } catch { notice('Запись готова. Нажмите воспроизведение в аудиоплеере.', 'success'); }
}
async function preview(line = null, forceSynthesis = false) {
  if (state.busy || state.loading || running()) return;
  const output = line && resultFor(line);
  if (output?.status === 'done' && !forceSynthesis) { await playAudio(`/api/studio/mod/${state.job.id}/audio/${output.id}`, speakerName(line.speaker)); return; }
  const text = line ? line.text : $('preview-text').value.trim();
  if (!text) { notice('Добавьте текст пробной записи.', 'error'); return; }
  const voice = line ? state.assignments[line.speaker] || selectedVoice() : selectedVoice();
  state.busy = true; updateControls(); notice('Создаём пробную запись. Первый запуск модели может занять больше времени.');
  try {
    const response = await fetch('/api/studio/preview', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...synthesisParams(voice), voice_blend: state.voiceBlend, text})});
    if (!response.ok) await responseError(response);
    window.agvModels?.markVerified($('tts-engine').value, voice);
    const url = URL.createObjectURL(await response.blob()); notice('Пробная запись готова.', 'success');
    await playAudio(url, line ? speakerName(line.speaker) : 'Пробная запись', true);
  } catch (error) { notice(friendlyError(error), 'error'); }
  finally { state.busy = false; updateControls(); }
}
function downloadJson(data, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'}));
  const anchor = el('a'); anchor.href = url; anchor.download = filename; document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function renderJob() {
  if (state.job) window.agvAuto?.job(state.job);
  const box = $('jobs-content'); box.replaceChildren(); const job = state.job;
  if (!job) { const empty = el('div', 'job-empty'); empty.append(el('h3', '', 'Студия готова к записи'), el('p', '', 'Выберите модель голоса и папку результата. Готовые реплики будут доступны для прослушивания.')); box.append(empty); return; }
  box.append(el('h3', 'job-status-heading', statusNames[job.status] || job.status));
  const processed = (job.succeeded || 0) + (job.failed || 0);
  box.append(el('p', 'job-summary', job.total ? `${job.succeeded} из ${job.total} реплик готовы · Ошибок: ${job.failed || 0}${job.cached ? ` · Из кэша: ${job.cached}` : ''}` : activeStatuses.has(job.status) ? 'Проверяем модель и сценарии…' : 'Запись не началась.'));
  if (running()) {
    const progress = el('progress', 'job-content-progress'); progress.max = job.total || 1;
    if (job.total) progress.value = processed; else progress.removeAttribute('value');
    progress.setAttribute('aria-label', 'Готовность реплик'); box.append(progress);
    box.append(el('p', 'job-help', job.status === 'cancelling' ? 'Остановимся после текущих реплик. Готовое аудио сохранится.' : 'Можно перейти к другим разделам. После остановки повторный запуск использует готовые файлы.'));
  }
  if (job.error) box.append(el('div', 'notice error', friendlyError(new Error(job.error))));
  if (job.result) {
    const location = el('details', 'job-location');
    location.append(el('summary', '', 'Где сохранены файлы'), el('p', 'job-path', job.result.out));
    if (job.result.installation?.path) location.append(el('p', 'job-path', job.result.installation.path));
    box.append(location);
    const failures = job.result.lines.filter(line => line.status === 'failed');
    if (failures.length) {
      const errors = el('ul', 'job-errors'); failures.slice(0, 20).forEach(line => errors.append(el('li', '', `${speakerName(line.speaker)} · ${line.source_file}: ${line.error}`))); box.append(errors);
    }
    const installation = job.result.installation;
    const installedName = installation?.engine === 'renpy' ? 'Ren’Py' : 'Lost Coast';
    box.append(el('p', 'job-help', installation?.status === 'installed' ? installation.verification?.status === 'ok' ? `Озвучка ${installedName} установлена и проверена. Перезапустите игру. Исходные файлы сохранены.` : 'Мод установлен, но проверка не подтверждена. Нажмите «Проверить озвучку».' : installation?.status === 'disabled' ? installation.note : 'WAV-файлы и отчёт сохранены. Для этой игры подключение аудио выполняется отдельно.'));
    if (installation?.error) box.append(el('p', 'notice error', friendlyError(new Error(installation.error))));
    if (installation?.status === 'installed') {
      const playGame = el('button', 'button primary', `Запустить ${installedName}`);
      playGame.addEventListener('click', async () => {
        playGame.disabled = true;
        try { const response = await api(`/api/studio/mod/${job.id}/launch`, {}); notice(response.note, 'success'); }
        catch (error) { notice(friendlyError(error), 'error'); }
        finally { playGame.disabled = false; }
      }); box.append(playGame);
      const verify = el('button', 'button secondary', 'Проверить озвучку');
      verify.disabled = state.busy || running();
      verify.addEventListener('click', async () => {
        if (state.busy || running()) return;
        state.busy = true; updateControls(); verify.disabled = true;
        try {
          const response = await api(`/api/studio/mod/${job.id}/verify`, {});
          job.result.installation = response.installation; job.status = job.result.status = response.status;
          renderJob();
          notice(response.installation.error || 'Проверка мода пройдена. Файлы соответствуют сценарию.', response.installation.error ? 'error' : 'success');
        } catch (error) { notice(friendlyError(error), 'error'); }
        finally { state.busy = false; updateControls(); verify.disabled = false; }
      }); box.append(verify);
      const disable = el('button', 'text-link', 'Отключить озвучку');
      disable.addEventListener('click', async () => {
        if (state.busy || running()) return;
        state.busy = true; updateControls(); disable.disabled = true;
        try {
          job.result.installation = await api(`/api/studio/mod/${job.id}/disable`, {});
          renderJob(); notice(job.result.installation.note, 'success');
        } catch (error) { notice(friendlyError(error), 'error'); }
        finally { state.busy = false; updateControls(); disable.disabled = false; }
      });
      box.append(disable);
    }
    const folder = el('button', 'button secondary', 'Открыть папку результата');
    folder.addEventListener('click', async () => {
      folder.disabled = true;
      try { await api(`/api/studio/mod/${job.id}/open-folder`, {}); }
      catch (error) { notice(friendlyError(error), 'error'); }
      finally { folder.disabled = false; }
    }); box.append(folder);
    const actions = el('div', 'job-result-actions'); const manifest = el('button', 'button secondary', 'Скачать манифест'); manifest.prepend(icon('download'));
    manifest.addEventListener('click', () => downloadJson(job.result, 'anygamevoice.json')); actions.append(manifest);
    if (job.succeeded) { const listen = el('button', 'button secondary', 'К готовым репликам'); listen.addEventListener('click', () => { setView('ready'); setTab('dialogue'); }); actions.append(listen); }
    box.append(actions);
  }
  $('mini-progress').hidden = false;
  $('progress').max = job.total || 1; if (job.total) $('progress').value = processed; else if (activeStatuses.has(job.status)) $('progress').removeAttribute('value'); else $('progress').value = 0;
  $('progress-label').textContent = job.total ? `${job.succeeded}/${job.total} готовы${job.failed ? ` · ${job.failed} ошибок` : ''}` : statusNames[job.status];
  $('project-state').textContent = running() ? 'Идёт запись' : job.status === 'done' ? 'Аудио готово' : 'Диалоги извлечены';
  $('job-indicator').hidden = !running(); updateControls();
}
async function pollJob(id) {
  try {
    const job = await api(`/api/studio/mod/${id}`);
    if (state.job?.id !== id) return;
    state.job = job; state.resultIndex = new Map((job.result?.lines || []).map(item => [JSON.stringify([item.source_file, item.line_no, item.speaker, item.text]), item])); renderJob(); renderLines();
    if (activeStatuses.has(job.status)) pollTimer = setTimeout(() => pollJob(id), 1000);
    else notice(job.status === 'done' ? job.result?.installation?.verification?.status === 'ok' ? 'Озвучка установлена и проверена. Можно запускать игру.' : 'Аудиофайлы созданы. Готовые реплики можно прослушать в таблице.' : job.error ? friendlyError(new Error(job.error)) : statusNames[job.status], job.status === 'done' ? 'success' : job.status === 'failed' || job.status === 'partial' ? 'error' : '');
  } catch (error) {
    if (state.job?.id !== id) return;
    notice(`${friendlyError(error)} Повторим проверку статуса через несколько секунд.`, 'error'); pollTimer = setTimeout(() => pollJob(id), 4000);
  }
}
async function generate() {
  if ($('generate-button').disabled) return;
  state.busy = true; updateControls(); notice('Подготавливаем генерацию…');
  try {
    const data = await api('/api/studio/mod', settings());
    state.job = {id: data.job_id, status: 'running', total: 0, succeeded: 0, failed: 0};
    window.agvAuto?.remember(data.job_id);
    setTab('jobs'); renderJob(); await pollJob(data.job_id);
  } catch (error) { notice(friendlyError(error), 'error'); }
  finally { state.busy = false; updateControls(); }
}
function setView(view) {
  state.view = view; state.page = 0;
  document.querySelectorAll('[data-view]').forEach(button => button.classList.toggle('selected', button.dataset.view === view)); renderLines();
}
function resetProject() {
  if (running() || state.busy || state.setupBusy || state.loading) return;
  window.agvModels?.reset(); window.agvAuto?.reset();
  state.voiceBlend = defaultVoiceBlend();
  projectVersion++; clearTimeout(pollTimer); state.lines = []; state.characters = []; state.assignments = Object.create(null); state.game = ''; state.engine = ''; state.demo = false; state.job = null; state.resultIndex.clear();
  $('project-title').textContent = 'Начните новую историю.'; $('heading-kicker').textContent = 'ВАША ИГРА. ВАШИ ГОЛОСА.';
  $('project-description').textContent = 'Превратите игровые диалоги в озвучку — на своём компьютере.'; $('crumb').textContent = 'Новый проект';
  $('engine-badge').replaceChildren(icon('wave'), el('span', '', 'Аудиостудия'));
  for (const id of ['stat-lines', 'stat-characters', 'stat-files', 'nav-lines', 'nav-characters']) $(id).textContent = '—';
  for (const id of ['game-path', 'output-path', 'line-search']) $(id).value = '';
  $('project-state').textContent = 'Ожидает игру'; $('dialogue-caption').textContent = 'Здесь начинается озвучка';
  for (const id of ['table-wrap', 'table-toolbar', 'table-footer', 'mini-progress', 'job-indicator', 'audio-player']) $(id).hidden = true;
  $('audio').pause(); $('empty-state').hidden = false; notice(''); renderCharacters(); renderJob(); setView('all'); setTab('dialogue'); updateControls(); $('game-path').focus();
}

let folderSelection = null;
let folderPurpose = 'game';
let folderRequest = 0;
async function browseFolders(path = '') {
  const request = ++folderRequest;
  folderSelection = null;
  $('folder-select').disabled = true;
  $('folder-up').disabled = true;
  $('folder-list').replaceChildren(el('p', 'muted', 'Читаем папки…'));
  $('folder-error').hidden = true;
  try {
    const data = await api(`/api/studio/folders?path=${encodeURIComponent(path)}`);
    if (request !== folderRequest || !$('folder-picker').open) return;
    folderSelection = data;
    $('folder-path').value = data.path;
    $('folder-up').disabled = !data.parent;
    $('folder-select').disabled = false;
    $('folder-list').replaceChildren();
    data.folders.forEach(folder => {
      const button = el('button', 'folder-entry', folder.name);
      button.type = 'button'; button.prepend(icon('folder'));
      button.addEventListener('click', () => browseFolders(folder.path));
      $('folder-list').append(button);
    });
    if (!data.folders.length) $('folder-list').append(el('p', 'muted', 'Вложенных папок нет. Можно открыть текущую папку.'));
  } catch (error) {
    if (request !== folderRequest || !$('folder-picker').open) return;
    $('folder-list').replaceChildren();
    $('folder-error').textContent = friendlyError(error);
    $('folder-error').hidden = false;
  }
}
async function chooseGameFolder() {
  if (running() || state.busy || state.setupBusy || state.loading) return;
  folderPurpose = 'game'; $('folder-picker-title').textContent = 'Выберите папку игры'; $('folder-select').textContent = 'Открыть эту папку';
  const shortcuts = $('folder-shortcuts'); shortcuts.replaceChildren(); shortcuts.hidden = true;
  $('folder-picker').showModal();
  const request = ++folderRequest;
  folderSelection = null; $('folder-select').disabled = true; $('folder-up').disabled = true;
  $('folder-error').hidden = true; $('folder-list').replaceChildren(el('p', 'muted', 'Ищем игровые библиотеки…'));
  try {
    const data = await api('/api/studio/games');
    if (request !== folderRequest || !$('folder-picker').open || folderPurpose !== 'game') return;
    for (const library of data.folder_shortcuts || []) {
      const button = el('button', 'text-link', `${library.name} · ${library.path}`);
      button.type = 'button'; button.addEventListener('click', () => browseFolders(library.path));
      shortcuts.append(button);
    }
    shortcuts.hidden = !shortcuts.children.length;
    await browseFolders(data.folder_shortcuts?.[0]?.path || '');
  } catch {
    if (request === folderRequest && $('folder-picker').open && folderPurpose === 'game') await browseFolders();
  }
}
$('source-form').addEventListener('submit', event => {
  event.preventDefault();
  if ($('game-path').value.trim()) loadGame(); else chooseGameFolder();
});
$('browse-game').addEventListener('click', chooseGameFolder);
$('browse-sdk').addEventListener('click', () => {
  if (running() || state.busy || state.setupBusy || state.loading) return;
  $('folder-shortcuts').hidden = true;
  folderPurpose = 'sdk'; $('folder-picker-title').textContent = 'Выберите папку Ren’Py SDK'; $('folder-select').textContent = 'Использовать SDK';
  $('folder-picker').showModal(); browseFolders();
});
$('folder-path-form').addEventListener('submit', event => { event.preventDefault(); browseFolders($('folder-path').value.trim()); });
$('folder-up').addEventListener('click', () => { if (folderSelection?.parent) browseFolders(folderSelection.parent); });
$('folder-select').addEventListener('click', () => {
  if (!folderSelection || $('folder-select').disabled) return;
  const selected = folderSelection.path;
  const purpose = folderPurpose;
  $('folder-picker').close();
  if (purpose === 'sdk') {
    $('renpy-sdk').value = selected; $('renpy-sdk').dispatchEvent(new Event('change'));
    notice('Папка SDK выбрана. Нажмите «Продолжить автоматически», чтобы проверить SDK и установить озвучку.');
  } else { $('game-path').value = selected; loadGame(); }
});
$('folder-picker').addEventListener('close', () => { folderRequest++; folderSelection = null; });
for (const id of ['demo-button', 'demo-empty', 'demo-side']) $(id).addEventListener('click', openDemo);
document.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click', () => setTab(button.dataset.tab)));
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
for (const id of ['line-search', 'speaker-filter']) $(id).addEventListener('input', () => { state.page = 0; renderLines(); });
$('previous-page').addEventListener('click', () => { state.page--; renderLines(); }); $('next-page').addEventListener('click', () => { state.page++; renderLines(); });
$('tts-engine').addEventListener('change', () => { state.assignments = Object.create(null); $('voice-select').value = ''; $('voice-path').value = ''; renderVoiceOptions(); });
$('voice-select').addEventListener('change', () => {
  $('voice-path').hidden = !!$('voice-select').value; if ($('voice-select').value) $('voice-path').value = $('voice-select').value;
  const language = state.voices.find(voice => voice.path === selectedVoice())?.language?.split(/[_-]/)[0];
  if (language && [...$('voice-language').options].some(option => option.value === language)) $('voice-language').value = language;
  updateControls();
});
for (const id of ['voice-path', 'output-path', 'voice-language', 'voice-emotion']) $(id).addEventListener('input', updateControls);
$('preview-button').addEventListener('click', () => preview()); $('generate-button').addEventListener('click', () => { if ($('auto-mode').checked) window.agvAuto?.start(); else generate(); });
$('cancel-button').addEventListener('click', async () => { try { await api(`/api/studio/mod/${state.job.id}/cancel`, {}); state.job.status = 'cancelling'; renderJob(); } catch (error) { notice(friendlyError(error), 'error'); } });
$('new-project').addEventListener('click', resetProject);
$('save-project').addEventListener('click', () => { downloadJson(settings(), 'anygamevoice-project.json'); notice('Настройки проекта сохранены. Их можно открыть кнопкой «Открыть проект».', 'success'); });
$('import-project').addEventListener('click', () => $('project-file').click());
async function validateProjectJson(raw) {
  if (raw.length > 1000000) throw new Error('Файл проекта слишком большой.');
  let data;
  try { data = JSON.parse(raw); }
  catch { throw new Error('Проверьте синтаксис JSON: кавычки, запятые и скобки.'); }
  if (data?.schema !== 'anygamevoice-project' || data.version !== 1 || typeof data.path !== 'string' || !['piper', 'xtts', 'silero', 'bark'].includes(data.engine)) throw new Error('Выберите JSON-файл настроек, сохранённый AnyGameVoice.');
  for (const key of ['out', 'voice', 'emotion', 'language']) if (typeof data[key] !== 'string') throw new Error('В файле проекта отсутствуют обязательные настройки.');
  if (!data.character_voices || typeof data.character_voices !== 'object' || Array.isArray(data.character_voices) || Object.values(data.character_voices).some(v => typeof v !== 'string')) throw new Error('Некорректные назначения голосов.');
  data.voice_blend = await api('/api/studio/project/voice-blend', data.voice_blend ?? defaultVoiceBlend());
  return data;
}

async function applyProjectJson(data) {
  if (typeof data.renpy_sdk === 'string') $('renpy-sdk').value = data.renpy_sdk;
  $('auto-mode').checked = data.automatic === true; $('manual-settings').open = !$('auto-mode').checked;
  $('game-path').value = data.path; $('tts-engine').value = data.engine; $('voice-path').value = data.voice; $('voice-select').value = '';
  $('voice-emotion').value = data.emotion; $('voice-language').value = data.language;
  $('worker-count').value = [1, 2, 4].includes(data.workers) ? data.workers : 2;
  state.voiceBlend = data.voice_blend;
  renderVoiceOptions();
  if (data.path.trim()) await loadGame(Boolean(data.demo), data);
  else updateControls();
}

$('project-file').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  try {
    if (file.size > 1000000) throw new Error('Файл проекта слишком большой.');
    await applyProjectJson(await validateProjectJson(await file.text()));
  } catch (error) { notice(friendlyError(error), 'error'); } finally { event.target.value = ''; }
});

$('project-json-open').addEventListener('click', () => {
  $('project-json-text').value = JSON.stringify(settings(), null, 2);
  $('project-json-error').hidden = true;
  $('project-json-dialog').showModal();
});
async function useProjectEditor(download) {
  const errorText = $('project-json-error');
  errorText.hidden = true;
  $('project-json-apply').disabled = $('project-json-download').disabled = true;
  try {
    const data = await validateProjectJson($('project-json-text').value);
    if (!$('project-json-dialog').open) return;
    if (download) {
      downloadJson(data, 'anygamevoice-project.json');
    } else {
      if (state.game && !data.path.trim()) throw new Error('Оставьте путь к открытой игре или создайте новый проект.');
      $('project-json-dialog').close();
      await applyProjectJson(data);
      if (!data.path.trim() || state.game === data.path) notice('Настройки JSON применены.', 'success');
    }
  } catch (error) {
    errorText.textContent = friendlyError(error); errorText.hidden = false;
  } finally {
    $('project-json-apply').disabled = $('project-json-download').disabled = false;
  }
}
$('project-json-download').addEventListener('click', () => useProjectEditor(true));
$('project-json-apply').addEventListener('click', () => useProjectEditor(false));
$('scan-hardware').addEventListener('click', async () => {
  if (!$('game-path').value.trim()) { notice('Сначала укажите папку игры.', 'error'); return; }
  $('scan-hardware').disabled = true;
  try { const data = await api('/api/studio/scan', {path: $('game-path').value.trim()}); $('hardware-result').textContent = `${data.hardware.ram_gb} ГБ RAM · ${data.hardware.cpu_count} потоков · GPU: ${data.hardware.gpu}. Рекомендован ${data.recommend.engine}.`; }
  catch (error) { notice(friendlyError(error), 'error'); } finally { $('scan-hardware').disabled = false; }
});
async function initialize() {
  try { await api('/api/studio/health'); $('connection-label').textContent = 'Работает на вашем ПК'; await refreshVoices(); await window.agvAuto?.restore(); await window.agvSetup?.restore(); window.agvModels?.welcomeOnStartup(); }
  catch (error) { $('connection-dot').classList.add('offline'); $('connection-label').textContent = 'Нет связи со студией'; notice(friendlyError(error), 'error'); }
  updateControls();
}
initialize();
