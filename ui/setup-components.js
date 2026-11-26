// Explicit component setup, with resumable UI state and no implicit network work.
(() => {
  let plan = null;
  let params = null;
  let task = null;
  let resume = null;
  let timer;
  let revision = 0;
  const bytes = value => `${(value / 1024 ** 2).toFixed(1)} МБ`;

  function sync() {
    $('setup-button').disabled = state.busy || state.setupBusy || state.loading || running();
    $('setup-language').disabled = !!task;
    $('setup-install').disabled = !!task || !plan?.supported || !plan?.components.some(item => item.needed);
    $('setup-manual').disabled = !!task;
    $('setup-cancel').hidden = !task;
  }
  function renderPlan() {
    $('setup-list').replaceChildren();
    for (const component of plan.components) {
      const row = el('article', 'setup-component');
      row.append(el('strong', '', component.name), el('span', 'setup-state', component.needed ? 'Нужно установить' : 'Уже установлено'));
      if (component.needed) row.append(el('p', '', `${component.estimated ? 'Около ' : ''}${bytes(component.download_bytes)} · ${component.license}`));
      row.append(el('p', 'field-hint', component.note));
      const link = el('a', 'text-link', 'Источник и лицензия'); link.href = component.source; link.target = '_blank'; link.rel = 'noopener noreferrer';
      row.append(link); $('setup-list').append(row);
    }
    $('setup-summary').textContent = plan.reason || (plan.ready ? 'Все необходимые компоненты уже доступны.' : `Потребуется скачать примерно ${bytes(plan.download_bytes)}. Размер Python-зависимостей может отличаться.`);
    $('setup-status').textContent = plan.note;
    sync();
  }
  async function loadPlan() {
    const current = ++revision;
    plan = null; sync();
    $('setup-status').textContent = 'Проверяем установленные компоненты…';
    params = {language: $('setup-language').value, engine: ['renpy','source_lostcoast','rpgmaker','godot'].includes(state.engine) ? state.engine : 'renpy', sdk: $('renpy-sdk').value.trim()};
    try {
      const result = await api('/api/studio/setup/plan', params);
      if (current !== revision) return;
      plan = result; renderPlan();
    } catch (error) { if (current === revision) $('setup-status').textContent = friendlyError(error); }
  }
  async function offer(next = null, manual = false) {
    if (task) { if (!$('setup-dialog').open) $('setup-dialog').showModal(); return; }
    if (next === 'auto' && !['ru','en'].includes($('voice-language').value)) return;
    resume = next;
    $('setup-language').value = ['ru','en'].includes($('voice-language').value) ? $('voice-language').value : 'ru';
    await loadPlan();
    if (manual || (plan?.supported && plan.components.some(item => item.needed))) {
      if (!$('setup-dialog').open) $('setup-dialog').showModal();
    }
  }
  function saveTask(context) {
    try { sessionStorage.setItem('agv-component-setup', JSON.stringify(context)); } catch {}
  }
  function finishTask() {
    task = null; state.setupBusy = false;
    try { sessionStorage.removeItem('agv-component-setup'); } catch {}
  }
  function releaseTask() {
    // loadGame rejects while setupBusy; keep the saved context until it finishes
    // so a page reload during restoration can retry safely.
    task = null; state.setupBusy = false;
  }
  async function poll() {
    if (!task) return;
    try {
      const data = await api(`/api/studio/setup/${task.id}`);
      const labels = {preparing:'Подготавливаем компоненты',runtime:'Устанавливаем изолированное окружение',downloading:'Загружаем голос',sdk:'Подготавливаем SDK',testing:'Проверяем пробной записью'};
      $('setup-status').textContent = data.error || `${labels[data.stage] || 'Подготовка'}${data.component ? ` · ${data.component}` : ''}${data.total ? ` · ${bytes(data.received)} из ${bytes(data.total)}` : ''}`;
      $('setup-progress').hidden = false;
      if (data.total) { $('setup-progress').max = data.total; $('setup-progress').value = data.received; }
      else $('setup-progress').removeAttribute('value');
      $('setup-cancel').disabled = data.status === 'cancelling';
      if (['running','cancelling'].includes(data.status)) { timer = setTimeout(poll, 750); return; }
      const context = task;
      $('setup-progress').hidden = true;
      if (data.status === 'done') {
        if (data.result.sdk) { $('renpy-sdk').value = data.result.sdk; $('renpy-sdk').dispatchEvent(new Event('change')); }
        await refreshVoices();
        await loadPlan();
        $('setup-status').textContent = `Компоненты готовы. Пробная запись ${data.result.preview_duration.toFixed(1)} с выполнена.`;
        notice('Компоненты установлены и проверены пробной записью.', 'success');
        updateControls(); sync();
        if (context.resume) {
          $('setup-dialog').close();
          if (context.resume === 'demo') { finishTask(); updateControls(); sync(); await openDemo(); return; }
          if (state.game && context.project?.path && state.game !== context.project.path) {
            finishTask(); updateControls(); sync();
            notice('Подготовка завершена. Откройте исходный проект и повторите запуск.', 'error');
            return;
          }
          if (!state.game && context.project?.path) {
            const project = context.project;
            $('auto-mode').checked = project.automatic !== false;
            $('tts-engine').value = project.engine;
            $('voice-select').value = ''; $('voice-path').value = project.voice || '';
            $('voice-language').value = project.language || 'ru';
            $('voice-emotion').value = project.emotion || 'neutral';
            $('worker-count').value = project.workers || 1;
            $('game-path').value = context.project.path;
            releaseTask(); updateControls(); sync();
            await loadGame(Boolean(context.project.demo), context.project);
          } else if (context.resume === 'selected' && context.project) {
            const project = context.project;
            $('auto-mode').checked = false;
            $('tts-engine').value = project.engine;
            $('voice-select').value = ''; $('voice-path').value = project.voice || '';
            $('voice-language').value = project.language || 'ru';
            $('voice-emotion').value = project.emotion || 'neutral';
            $('worker-count').value = project.workers || 1;
            $('output-path').value = project.out;
            state.assignments = Object.assign(Object.create(null), project.character_voices || {});
            state.voiceBlend = project.voice_blend || defaultVoiceBlend();
            renderVoiceOptions();
          }
          if (context.project?.path && state.game !== context.project.path) {
            finishTask(); updateControls(); sync();
            notice('Проект не восстановлен. Откройте его и повторите запуск.', 'error');
            return;
          }
          finishTask(); updateControls(); sync();
          if (state.game && context.resume === 'selected') await window.agvAuto.start(true);
          else if (state.game && $('auto-mode').checked) await window.agvAuto.start();
        } else {
          finishTask();
        }
      } else {
        finishTask();
        notice(data.error || 'Подготовка остановлена. Проверенные компоненты сохранены.', data.status === 'failed' ? 'error' : '');
      }
      updateControls(); sync();
    } catch (error) {
      if (error.status === 404 || !task) {
        task = null; state.setupBusy = false;
        try { sessionStorage.removeItem('agv-component-setup'); } catch {}
        updateControls(); sync();
        $('setup-status').textContent = error.status === 404 ? 'Сервер перезапущен. Откройте подготовку повторно: завершённые загрузки сохранены.' : friendlyError(error);
        return;
      }
      $('setup-status').textContent = `${friendlyError(error)} Повторим проверку состояния.`;
      timer = setTimeout(poll, 3000);
    }
  }
  $('setup-button').addEventListener('click', () => offer(null, true));
  $('setup-language').addEventListener('change', loadPlan);
  $('setup-install').addEventListener('click', async () => {
    if (!plan || task || $('setup-install').disabled) return;
    $('setup-install').disabled = true;
    try {
      const response = await api('/api/studio/setup', {...params, components: plan.components.filter(item => item.needed).map(item => item.id), allow_downloads: true});
      task = {id: response.task_id, resume, params: {...params}, plan, project: state.game ? settings() : null};
      saveTask(task); state.setupBusy = true;
      updateControls(); sync(); await poll();
    } catch (error) { $('setup-status').textContent = friendlyError(error); sync(); }
  });
  $('setup-cancel').addEventListener('click', async () => {
    if (!task) return;
    $('setup-cancel').disabled = true;
    try { await api(`/api/studio/setup/${task.id}/cancel`, {}); }
    catch (error) { $('setup-status').textContent = friendlyError(error); $('setup-cancel').disabled = false; }
  });
  $('setup-manual').addEventListener('click', () => { $('setup-dialog').close(); $('manual-settings').open = true; $('renpy-sdk').focus(); });
  document.addEventListener('agv:controls', sync);
  window.agvSetup = {offer, async restore() {
    let context;
    try { context = JSON.parse(sessionStorage.getItem('agv-component-setup') || 'null'); } catch { return; }
    if (!context?.id) return;
    try {
      const data = await api(`/api/studio/setup/${context.id}`);
      $('setup-language').value = context.params?.language || data.result?.language || 'ru';
      if (context.plan) { plan = context.plan; params = context.params; renderPlan(); }
      task = context; state.setupBusy = true; updateControls(); sync();
      $('setup-dialog').showModal(); await poll();
    } catch {
      try { sessionStorage.removeItem('agv-component-setup'); } catch {}
      notice('Сервер перезапущен. Откройте «Подготовить приложение» повторно: завершённые загрузки сохранены.');
    }
  }};
})();
