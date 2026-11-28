// SPDX-License-Identifier: Apache-2.0
// Hardware-aware planning, source-grounded research and actor reference assignment.
(() => {
  let plan = null;
  let epoch = 0;
  let report = null;
  let references = Object.create(null);
  let pending = false;
  let welcomePreferences = null;
  let welcomeSeen = false;
  let welcomeStep = 'mode';
  let welcomeDraft;
  let catalogFromWelcome = false;
  let providerList = [];
  let providerScan;
  let customProbe;
  let opencodeLogin;
  let routerConnection;
  let routerSessionKey = '';
  let customSessionKey;
  let rankings;
  let rankingPending = false;
  let scoresByModel = new Map();
  let localScores;
  let localScoresPending = false;
  const providerResults = new Map();
  const cloudModels = [
    {id: 'openrouter/free', label: 'Бесплатный · Free Models Router'},
    {id: 'deepseek/deepseek-v3.2', label: 'Экономичный · DeepSeek V3.2'},
    {id: 'google/gemini-3-flash-preview', label: 'Средний · Gemini 3 Flash Preview'},
    {id: 'anthropic/claude-sonnet-4', label: 'Дорогой · Claude Sonnet 4'},
  ];
  const cloudURL = model => `https://openrouter.ai/${model.id}`;
  try {
    const saved = JSON.parse(localStorage.getItem('agv-start-models-v1'));
    if (typeof saved?.voice === 'string' && typeof saved?.research === 'string') welcomePreferences = saved;
    welcomeSeen = localStorage.getItem('agv-welcome-seen-v3') === '1';
  } catch { /* Settings stay in this tab if storage is unavailable. */ }
  const verifiedVoices = new Set();
  const fits = {recommended: 'С запасом', tight: 'На пределе', unsupported: 'Не подходит', unknown: 'Нужна проверка'};
  const occupied = () => state.busy || state.setupBusy || state.loading || running();
  const selectedResearch = () => plan?.research.find(item => item.id === $('research-model').value);
  const savedCloudResearch = () => welcomePreferences?.mode === 'cloud' && welcomePreferences.cloudResearch &&
    ['openrouter', 'custom'].includes(welcomePreferences.cloudProvider) ? welcomePreferences : null;
  const activeCloudResearch = () => $('research-model').value === 'agv:cloud' ? savedCloudResearch() : null;
  const cloudResearchName = config => config.cloudProvider === 'openrouter' ? 'OpenRouter' : config.custom?.name || 'Свой провайдер';
  const readiness = item => item.launch_verified ? 'Пробная запись выполнена' : item.installed && item.engine==='xtts' ? 'Движок установлен · веса требуют проверки' : item.installed ? 'Установлена · запуск не проверен' : 'Нужно установить';
  function syncControls() {
    const selected = selectedResearch();
    for (const id of ['research-model','research-title-input','research-search','research-source-url','research-source-text','research-key','reference-character','reference-actor','reference-path','reference-protected']) $(id).disabled = occupied() || pending || !state.game;
    $('choose-models').disabled = occupied() || pending || !plan;
    $('refresh-model-plan').disabled = occupied() || pending;
    $('models-setup').disabled = occupied() || pending;
    $('welcome-open').disabled = occupied();
    $('welcome-catalog').disabled = !plan || pending;
    const ready = activeCloudResearch() || (selected?.installed && selected.fit === 'recommended' && !selected.manual_only);
    $('run-research').disabled = occupied() || pending || !state.game || !ready;
    $('apply-reference').disabled = occupied() || pending || !state.characters.length;
    document.querySelectorAll('.research-sample,.cast-finding button').forEach(button=>{button.disabled=occupied();});
    document.querySelectorAll('#model-picker input').forEach(input => { input.disabled = occupied() || pending || input.dataset.unavailable === '1'; });
  }
  function researchDescription() {
    const configured = activeCloudResearch();
    $('research-key-field').hidden = !configured;
    if (configured) {
      $('recommended-research').textContent = configured.cloudModelName || configured.cloudResearch;
      $('recommended-research-note').textContent = cloudResearchName(configured);
      $('research-model-help').textContent = `При запуске ${cloudResearchName(configured)} получит название игры, выдержки из источников и несколько текстовых реплик.`;
      $('research-state').textContent = 'Проверьте название игры и источники.';
      syncControls();
      return;
    }
    const item = selectedResearch();
    if (!item) {
      const cloud = welcomePreferences?.mode === 'cloud';
      const cloudModel = cloudModels.find(model => model.id === welcomePreferences?.cloudResearch);
      const suggested = plan?.research.find(model => model.id === plan.suggested_research);
      $('recommended-research').textContent = cloud
        ? welcomePreferences?.cloudModelName || cloudModel?.label || 'Облачная LLM'
        : suggested?.name || 'Нет подходящей локальной модели';
      $('recommended-research-note').textContent = cloud
        ? 'Провайдер сохранён · облачный запуск ещё не подключён'
        : suggested ? `Рекомендация · ${readiness(suggested)}` : '';
      $('research-model-help').textContent = cloud
        ? 'Облачный выбор сохранён в «Первый запуск». Здесь можно вручную выбрать локальную модель.'
        : 'Выберите модель, когда понадобится исследование.';
      $('research-state').textContent = cloud ? 'Облачное исследование ещё не подключено.' : 'Модель исследования пока не выбрана.';
      syncControls();
      return;
    }
    $('recommended-research').textContent = item.name;
    $('recommended-research-note').textContent = `${fits[item.fit]} · ${readiness(item)}`;
    $('research-model-help').textContent = `${item.reason} ${item.installed ? 'Модель хранится локально.' : `Для установки: ${item.install_command || 'см. карту модели'}.`} Лицензия: ${item.license}`;
    $('research-state').textContent = item.installed && item.fit === 'recommended' && !item.manual_only ? 'Готово к исследованию. Сначала проверьте название игры и источники.' : !item.installed ? 'Для исследования нужно установить выбранную модель в Ollama, затем нажать «Обновить подбор».' : 'Выбранная модель требует проверки. Автоматический запуск отключён.';
    syncControls();
  }
  function applyTTS(item, allowUninstalled = false) {
    if (item.fit !== 'recommended' || (!item.installed && !allowUninstalled)) return;
    const previousEngine = $('tts-engine').value;
    if (previousEngine !== item.engine) state.assignments = Object.create(null);
    $('tts-engine').value = item.engine; $('voice-select').value = ''; $('voice-path').value = item.voice;
    $('worker-count').value = '1'; renderVoiceOptions();
    $('recommended-voice').textContent = item.name;
    $('recommended-voice-note').textContent = item.cloning ? item.installed ? 'Нужен образец актёра для каждого персонажа' : 'Сначала установите XTTS и назначьте образец актёра' : 'Обычный голос, без клонирования';
  }
  function voiceOption(item) {
    return item?.fit === 'recommended' && (item.installed || item.cloning);
  }
  function researchOption(item) {
    return item?.fit === 'recommended' && !item.manual_only;
  }
  function chooseWelcomeVoice(id) {
    const item = plan?.tts.find(model => model.id === id);
    if (id && !voiceOption(item)) return;
    if (id) {
      preserveManualChoice();
      const sameVoice = $('tts-engine').value === item.engine &&
        (item.cloning || selectedVoice() === item.voice);
      if (!sameVoice) applyTTS(item, item.cloning);
    } else if (!$('auto-mode').checked) {
      $('auto-mode').checked = true;
      $('auto-mode').dispatchEvent(new Event('change'));
    }
  }
  function machineSummary(hw) {
    const memory = hw.available_ram_gb == null
      ? `RAM ${hw.ram_gb} ГБ`
      : `RAM ${hw.ram_gb} ГБ, свободно ${hw.available_ram_gb} ГБ`;
    return `${hw.cpu_count} потоков · ${memory} · ${hw.gpu}${hw.vram_gb ? ` · VRAM ${hw.vram_gb} ГБ` : ''}`;
  }
  function retainOption(select, value) {
    select.value = [...select.options].some(option => option.value === value && !option.disabled) ? value : '';
  }

  const providerStatus = {
    connected: 'Подключение найдено', subscription: 'Вход через аккаунт подтверждён', api_key: 'API-ключ принят',
    key_required: 'Нужен API-ключ', auth_failed: 'API-ключ отклонён', not_signed_in: 'Вход не найден',
    not_installed: 'Клиент не установлен', unknown: 'Статус входа неизвестен',
  };
  function providerName(id) {
    return id === 'custom' ? welcomeDraft.custom?.name || 'Свой провайдер'
      : providerList.find(provider => provider.id === id)?.name || id;
  }
  const fromOpenCode = id => id?.startsWith('oc:');
  const needsOpenCodeLogin = provider => provider?.source === 'opencode' && provider.status !== 'connected';
  const subscriptionSummary = (result, id) => {
    if (result?.subscription === 'active') {
      const plan = result.plan;
      return `Подписка ${plan ? plan[0].toUpperCase() + plan.slice(1) : 'активна'}`;
    }
    if (id === 'opencode' && result?.subscription === 'none') return 'Без подписки Go';
    if (result?.subscription === 'none') return 'Бесплатный тариф';
    return '';
  };
  function limitSummary(limits) {
    if (Number.isFinite(limits?.remaining_usd)) return `Остаток по лимиту ключа: $${limits.remaining_usd.toFixed(2)}`;
    const windows = (limits?.windows || []).map(window => {
      const duration = window.window === 'monthly' ? 'Месяц · ' : window.minutes === 10080 ? 'Неделя · '
        : window.minutes === 300 ? '5 часов · ' : window.minutes ? `${window.minutes} мин · ` : '';
      const reset = window.resets_at
        ? `, сброс ${new Date(window.resets_at * 1000).toLocaleString('ru-RU', {dateStyle: 'short', timeStyle: 'short'})}`
        : '';
      return `${duration}осталось ${Math.round(100 - window.used_percent)}%${reset}`;
    });
    if (Number.isFinite(limits?.remaining_budget_usd)) windows.push(`Остаток бюджета OpenCode: $${limits.remaining_budget_usd.toFixed(2)}`);
    return windows.join(' / ');
  }

  const scoreKey = name => name.toLowerCase().replace(/[^a-z0-9]/g, '');
  const localScore = item => localScores?.models?.find(model =>
    scoreKey(model.name) === scoreKey(item.name) || scoreKey(model.name) === scoreKey(item.id));
  function localSuggestion() {
    if (!plan) return null;
    const installed = plan.research.find(item => item.id === plan.selected_research);
    if (installed) return installed;
    const ranked = plan.research.filter(item => researchOption(item) && localScore(item));
    if (ranked.length >= 2) return ranked.reduce((best, item) =>
      localScore(item).score > localScore(best).score ? item : best);
    return plan.research.find(item => item.id === plan.suggested_research);
  }
  function modelScore(model) {
    const name = model.name.replace(/^[^:]+:\s+/, '').replace(/\s+\(free\)$/i, '');
    const id = model.id.split('/').at(-1).replace(/:free$/, '');
    return scoresByModel.get(scoreKey(name)) || scoresByModel.get(scoreKey(id));
  }
  function cloudModelOrder(models) {
    return [...models].sort((a, b) =>
      (modelScore(a)?.rank ?? Infinity) - (modelScore(b)?.rank ?? Infinity));
  }
  function accessDescription(id, result, model) {
    const appliesToModel = ['codex', 'claude'].includes(id) || model.id.startsWith('opencode-go/');
    const access = id === 'openrouter' ? providerStatus[result.status] :
      appliesToModel ? subscriptionSummary(result, id) || providerStatus[result.status] :
      model.id.startsWith('opencode/') && !model.free ? 'Оплата по использованию' :
      result.status === 'connected' ? 'Найдена в подключённом клиенте' : '';
    const price = model.free ? 'Бесплатная модель' : Number.isFinite(model.input_price_usd) && Number.isFinite(model.output_price_usd)
      ? `$${model.input_price_usd.toLocaleString('ru-RU', {maximumFractionDigits: 4})} / $${model.output_price_usd.toLocaleString('ru-RU', {maximumFractionDigits: 4})}` : '';
    return [access, price].filter(Boolean).join(' · ');
  }
  function renderComparison() {
    const box = $('welcome-comparison');
    const visible = welcomeDraft.mode === 'cloud' && ['provider', 'llm'].includes(welcomeStep);
    box.hidden = !visible;
    if (!visible) return;
    const status = $('welcome-ranking-status');
    const list = $('welcome-ranking-models');
    list.replaceChildren();
    if (!rankings?.models?.length) {
      status.textContent = rankingPending ? 'Загружаем рейтинг русского текста…' : 'Рейтинг сейчас недоступен. Выбор модели работает по каталогу провайдера.';
      return;
    }
    const date = rankings.published.split('-').reverse().join('.');
    const source = rankings.state === 'offline' ? 'Последний сохранённый рейтинг' : 'Рейтинг Arena';
    const options = [...providerResults].flatMap(([id, result]) => {
      if (welcomeStep === 'llm' && id !== welcomeDraft.cloudProvider) return [];
      if (id === 'custom' && welcomeDraft.cloudProvider !== 'custom') return [];
      return result.models.map(model => ({id, result, model, rank: modelScore(model)})).filter(item => item.rank);
    }).sort((a, b) => a.rank.rank - b.rank.rank);
    const best = options[0];
    const bestConnected = options.find(item => ['connected', 'subscription', 'api_key'].includes(item.result.status));
    const bestFree = options.find(item => item.model.free);
    const shortlist = new Map();
    for (const [item, label] of [[best, 'По рейтингу'], [bestConnected, 'В подключённых каталогах'], [bestFree, 'Из бесплатных']]) {
      if (!item) continue;
      const key = `${item.id}:${item.model.id}`;
      if (!shortlist.has(key)) shortlist.set(key, {...item, labels: []});
      shortlist.get(key).labels.push(label);
    }
    status.textContent = `${source} от ${date}. Лидер — ${rankings.models[0].name}.` +
      (providerScan ? ' Сверяем модели провайдеров…' : !best ? ' Совпадений с каталогом пока нет.' :
        welcomeStep === 'provider' && !bestConnected ? ' Среди подключённых моделей совпадений пока нет.' : '');
    for (const item of shortlist.values()) {
      const row = el('li');
      const text = el('span');
      const label = accessDescription(item.id, item.result, item.model);
      text.append(el('strong', '', item.model.name),
        el('small', '', [...item.labels, providerName(item.id), label].filter(Boolean).join(' · ')));
      const rank = el('span');
      rank.append(el('small', '', `№${item.rank.rank} · ${item.rank.score}`));
      if (welcomeStep === 'llm') {
        const select = el('button', 'text-link', 'Выбрать');
        select.type = 'button';
        select.setAttribute('aria-label', `Выбрать ${item.model.name}`);
        select.addEventListener('click', () => {
          welcomeDraft.cloudResearch = item.model.id;
          $('welcome-model-search').value = '';
          renderWelcome();
          $('welcome-research').focus();
        });
        rank.append(select);
      }
      row.append(text, rank);
      list.append(row);
    }
  }
  async function loadComparison() {
    if (rankingPending) return;
    rankingPending = true;
    renderComparison();
    try {
      rankings = await api('/api/studio/cloud/rankings/russian');
      scoresByModel = new Map(rankings.models.map(model => [scoreKey(model.name), model]));
    } catch {
      rankings ??= {models: []};
    } finally {
      rankingPending = false;
      if ($('welcome-dialog').open) renderWelcome();
    }
  }

  function providerCard(provider) {
    const result = providerResults.get(provider.id);
    const label = el('label', 'welcome-provider');
    const radio = el('input');
    radio.type = 'radio';
    radio.name = 'welcome-provider';
    radio.value = provider.id;
    radio.disabled = provider.installed === false;
    radio.checked = welcomeDraft.cloudProvider === provider.id;
    const content = el('span');
    content.append(el('strong', '', provider.name));
    const hints = [];
    if (provider.id === 'custom') hints.push('OpenAI-совместимый API · укажите адрес');
    if (provider.source === 'opencode') {
      if (provider.status === 'connected') hints.push('Подключён в OpenCode');
      else if (provider.methods.includes('oauth')) hints.push('Вход через аккаунт в OpenCode');
      else if (provider.methods.includes('key')) hints.push('API-ключ в OpenCode');
      else hints.push('Настройка через OpenCode');
    }
    if (provider.free_options && provider.installed !== false) hints.push('Есть бесплатные модели');
    if (provider.installed === false) hints.push('Клиент не установлен');
    else if (result?.status && !provider.source) hints.push(providerStatus[result.status] || providerStatus.unknown);
    else if (providerScan && !provider.source && provider.id !== 'custom') hints.push('Проверяем доступ…');
    else if (provider.installed) hints.push('Клиент найден');
    const subscription = subscriptionSummary(result, provider.id);
    if (subscription) hints.push(subscription);
    else if (result?.plan) hints.push(`Тариф ${result.plan.toUpperCase()}`);
    content.append(el('small', '', hints.join(' · ')));
    label.append(radio, content);
    return label;
  }

  function renderProviders() {
    const box = $('welcome-provider-list');
    const focus = document.activeElement?.name === 'welcome-provider' ? document.activeElement.value : null;
    const scroll = box.scrollTop;
    const clients = providerList.filter(provider => typeof provider.installed === 'boolean' && provider.can_select !== false);
    const detected = providerList.filter(provider => provider.can_select === false && provider.installed);
    const catalog = providerList.filter(provider => typeof provider.installed !== 'boolean');
    const filter = $('welcome-provider-search').value.trim().toLowerCase();
    const connectedOnly = $('welcome-providers-connected').checked;
    const freeOnly = $('welcome-providers-free').checked;
    const matching = catalog.filter(provider => {
      const status = provider.status || providerResults.get(provider.id)?.status;
      return `${provider.name} ${provider.id}`.toLowerCase().includes(filter) &&
        (!connectedOnly || ['connected', 'subscription', 'api_key'].includes(status)) &&
        (!freeOnly || provider.free_options);
    });
    $('welcome-client-list').replaceChildren(...clients.map(providerCard));
    $('welcome-detected').hidden = !detected.length;
    $('welcome-detected-list').replaceChildren(...detected.map(provider => {
      const status = providerResults.get(provider.id)?.status;
      return el('li', '', status && status !== 'unknown' ? `${provider.name} · ${providerStatus[status]}` : provider.name);
    }));
    $('welcome-custom-provider').replaceChildren(providerCard({id: 'custom', name: 'Свой провайдер'}));
    box.replaceChildren(...matching.map(providerCard));
    $('welcome-provider-count').textContent = matching.length ? String(matching.length) : '';
    if (!matching.length) box.append(el('p', 'field-hint', providerScan ? 'Загружаем провайдеров…' : 'По этим фильтрам ничего не найдено.'));
    box.scrollTop = scroll;
    const choices = [...$('welcome-provider-panel').querySelectorAll('input[name="welcome-provider"]')];
    if (focus) choices.find(input => input.value === focus)?.focus({preventScroll: true});
    const active = choices.find(input => input.checked && !input.disabled);
    $('welcome-custom-fields').hidden = active?.value !== 'custom';
    $('welcome-openrouter-fields').hidden = active?.value !== 'openrouter';
    const site = $('welcome-provider-site');
    const selected = providerList.find(item => item.id === active?.value);
    site.hidden = !selected?.url;
    if (selected?.url) site.href = selected.url;
    const login = $('welcome-provider-login');
    login.hidden = !active || selected?.source !== 'opencode';
    login.disabled = !!opencodeLogin;
    login.textContent = needsOpenCodeLogin(selected) ? 'Подключить через OpenCode' : 'Сменить вход в OpenCode';
    const result = providerResults.get(selected?.id) || (['oc:opencode', 'oc:opencode-go'].includes(selected?.id) ? providerResults.get('opencode') : null);
    const detail = $('welcome-provider-detail');
    detail.hidden = !active || active.value === 'custom';
    if (!detail.hidden) {
      const subscription = subscriptionSummary(result, active.value.startsWith('oc:opencode') ? 'opencode' : active.value);
      const unknown = active.value === 'openrouter' ? 'Подключение по ключу API' : 'Подписка пока не подтверждена';
      detail.textContent = [subscription || unknown, limitSummary(result?.limits)].filter(Boolean).join(' · ');
    }
    $('welcome-continue').disabled = !!customProbe || !active || !!opencodeLogin || !!routerConnection ||
      (needsOpenCodeLogin(selected) && !selected.free_options);
  }

  async function scanCloudProviders() {
    if (providerScan) return;
    $('welcome-provider-status').textContent = 'Ищем установленные клиенты и проверяем доступ…';
    $('welcome-provider-refresh').disabled = true;
    providerScan = true;
    try {
      const installed = await api('/api/studio/cloud/providers');
      const launchers = installed.filter(item => item.installed !== false && (item.can_select !== false || item.account_probe));
      const hasOpenCode = installed.some(item => item.id === 'opencode' && item.installed);
      providerList = [...installed, ...providerList.filter(item => hasOpenCode && item.source === 'opencode')];
      const catalog = hasOpenCode && api('/api/studio/cloud/opencode/catalog').then(rows => {
        if (!rows.length) return false;
        const top = ['oc:opencode', 'oc:openai', 'oc:anthropic', 'oc:google', 'oc:github-copilot', 'oc:openrouter', 'oc:opencode-go'];
        const tagged = rows.map(item => item.id === 'oc:openrouter' ? {...item, name: 'OpenRouter · OpenCode'} : item);
        providerList = [
          ...installed,
          ...top.map(id => tagged.find(item => item.id === id)).filter(Boolean),
          ...tagged.filter(item => !top.includes(item.id)),
        ];
        if ($('welcome-dialog').open && welcomeStep === 'provider') renderProviders();
        return true;
      }).catch(() => false);
      if (welcomeStep === 'provider') renderProviders();
      const probes = launchers.map(async provider => {
        try {
          const result = provider.id === 'openrouter' && routerSessionKey
            ? await api('/api/studio/cloud/openrouter/connect', {api_key: routerSessionKey})
            : await api(`/api/studio/cloud/providers/${provider.id}/inspect`, {});
          providerResults.set(provider.id, result);
        } catch {
          providerResults.set(provider.id, {status: 'unknown', models: []});
        }
        if ($('welcome-dialog').open && ['provider', 'llm'].includes(welcomeStep)) renderWelcome();
      });
      const [catalogLoaded] = await Promise.all([catalog, ...probes]);
      $('welcome-provider-status').textContent = !hasOpenCode
        ? 'Для каталога интеграций установите OpenCode. OpenRouter и свой API доступны здесь.'
        : !catalogLoaded
          ? 'OpenCode не отдал каталог интеграций. Можно обновить список или подключить свой API.' : '';
    } catch {
      $('welcome-provider-status').textContent = 'Проверка провайдеров недоступна. Повторите её или укажите свой API.';
    } finally {
      providerScan = false;
      $('welcome-provider-refresh').disabled = false;
      if ($('welcome-dialog').open && ['provider', 'llm'].includes(welcomeStep)) renderWelcome();
    }
  }
  async function loginWithOpenCode() {
    const id = welcomeDraft.cloudProvider;
    if (!fromOpenCode(id) || opencodeLogin) return;
    const note = $('welcome-provider-status');
    opencodeLogin = true;
    renderProviders();
    try {
      await api(`/api/studio/cloud/opencode/${encodeURIComponent(id.slice(3))}/login`, {});
      note.textContent = 'Завершите вход в окне OpenCode, затем нажмите «Обновить статусы».';
    } catch (error) {
      note.textContent = friendlyError(error);
    } finally {
      opencodeLogin = false;
      if ($('welcome-dialog').open && welcomeStep === 'provider') renderProviders();
    }
  }
  async function loadOpenCodeModels(id) {
    providerResults.delete(id);
    try {
      providerResults.set(id, await api(`/api/studio/cloud/opencode/${encodeURIComponent(id.slice(3))}/models`));
    } catch {
      providerResults.set(id, {models: [], status: 'unknown'});
    }
    if ($('welcome-dialog').open && welcomeStep === 'llm' && welcomeDraft.cloudProvider === id) renderWelcome();
  }
  async function openRouterModels() {
    const key = $('welcome-openrouter-key');
    const token = key.value.trim();
    if (!token) { showWelcomeStep('llm'); return; }
    const draft = welcomeDraft;
    const note = $('welcome-provider-status');
    routerConnection = true;
    note.textContent = 'Проверяем ключ OpenRouter…';
    renderProviders();
    try {
      const provider = await api('/api/studio/cloud/openrouter/connect', {api_key: token});
      if (draft !== welcomeDraft || !$('welcome-dialog').open || welcomeStep !== 'provider' || draft.cloudProvider !== 'openrouter') return;
      providerResults.set('openrouter', provider);
      if (provider.status !== 'api_key') {
        note.textContent = provider.status === 'auth_failed' ? 'OpenRouter отклонил ключ. Проверьте его или откройте каталог без ключа.' : 'Не удалось проверить ключ. Можно повторить попытку или открыть каталог без ключа.';
        return;
      }
      routerSessionKey = token;
      note.textContent = '';
      showWelcomeStep('llm');
    } catch (error) {
      note.textContent = friendlyError(error);
    } finally {
      key.value = '';
      routerConnection = false;
      if ($('welcome-dialog').open && welcomeStep === 'provider') renderProviders();
    }
  }
  function localCustomURL(value) {
    let url;
    try { url = new URL(value); } catch { throw new Error('Укажите корректный базовый URL.'); }
    const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
    if ((url.protocol !== 'https:' && !(url.protocol === 'http:' && loopback)) ||
      url.username || url.password || url.search || url.hash) {
      throw new Error('Нужен HTTPS или HTTP на localhost. Укажите URL без пароля и параметров.');
    }
    return url.href.replace(/\/+$/, '');
  }
  async function openCustomModels(manual = false) {
    if (customProbe) return;
    const note = $('welcome-provider-status');
    const key = $('welcome-custom-key');
    const draft = welcomeDraft;
    const token = key.value.trim();
    note.textContent = '';
    try {
      const baseUrl = localCustomURL($('welcome-custom-url').value.trim());
      const name = $('welcome-custom-name').value.trim() || 'Свой провайдер';
      customProbe = true;
      $('welcome-continue').disabled = true;
      $('welcome-custom-manual').disabled = true;
      if (!manual) note.textContent = 'Проверяем каталог моделей…';
      const result = manual
        ? {status: 'unknown', models: [], catalog: 'manual'}
        : await api('/api/studio/cloud/custom/models', {base_url: baseUrl, api_key: token});
      if (draft !== welcomeDraft || !$('welcome-dialog').open || welcomeStep !== 'provider' || draft.cloudProvider !== 'custom') return;
      if (welcomeDraft.custom?.baseUrl !== baseUrl) welcomeDraft.cloudResearch = '';
      welcomeDraft.custom = {name, baseUrl};
      if (token || customSessionKey?.baseUrl !== baseUrl) customSessionKey = {baseUrl, token};
      providerResults.set('custom', result);
      note.textContent = '';
      showWelcomeStep('llm');
    } catch (error) {
      note.textContent = friendlyError(error);
    } finally {
      key.value = '';
      customProbe = false;
      $('welcome-custom-manual').disabled = false;
      if ($('welcome-dialog').open && welcomeStep === 'provider') renderProviders();
    }
  }
  $('welcome-provider-panel').addEventListener('change', event => {
    if (event.target.name !== 'welcome-provider') return;
    if (event.target.value !== welcomeDraft.cloudProvider) welcomeDraft.cloudResearch = '';
    welcomeDraft.cloudProvider = event.target.value;
    $('welcome-provider-status').textContent = '';
    renderProviders();
  });
  $('welcome-provider-refresh').addEventListener('click', scanCloudProviders);
  $('welcome-provider-login').addEventListener('click', loginWithOpenCode);
  for (const id of ['welcome-provider-search', 'welcome-providers-connected', 'welcome-providers-free']) {
    $(id).addEventListener('input', () => {
      $('welcome-provider-list').scrollTop = 0;
      renderProviders();
    });
  }
  $('welcome-model-search').addEventListener('input', renderWelcome);
  $('welcome-local-search').addEventListener('input', renderWelcome);
  async function loadLocalScores(apiKey = '') {
    if (localScoresPending) return;
    localScoresPending = true;
    $('local-ratings-connect').disabled = true;
    $('local-ratings-status').textContent = 'Загружаем оценки LLM Stats…';
    try {
      localScores = await api('/api/studio/models/local-ranking', {api_key: apiKey});
      const messages = {
        key_required: 'Для онлайн-оценок нужен бесплатный ключ LLM Stats.',
        auth_failed: 'Ключ не принят. Проверьте его и попробуйте снова.',
        unavailable: 'Не удалось получить оценки. Попробуйте позже.',
        empty: 'Оценки IFBench пока не найдены.',
        online: 'Оценки IFBench загружены. Data by LLM Stats.',
      };
      $('local-ratings-status').textContent = messages[localScores.state] || messages.unavailable;
    } catch {
      $('local-ratings-status').textContent = 'Не удалось получить оценки. Попробуйте позже.';
    } finally {
      $('local-ratings-key').value = '';
      $('local-ratings-connect').disabled = false;
      localScoresPending = false;
      if ($('welcome-dialog').open && welcomeStep === 'llm' && welcomeDraft.mode === 'local') renderWelcome();
    }
  }
  $('local-ratings-connect').addEventListener('click', () => loadLocalScores($('local-ratings-key').value.trim()));
  $('welcome-local-list').addEventListener('change', event => {
    if (event.target.name !== 'welcome-local-model') return;
    welcomeDraft.research = event.target.value;
    $('welcome-research').value = event.target.value;
    explainWelcomeResearch();
  });
  $('welcome-custom-manual').addEventListener('click', () => openCustomModels(true));

  function explainWelcomeResearch() {
    const select = $('welcome-research');
    const link = $('welcome-cloud-card');
    const note = $('welcome-research-note');
    if (welcomeDraft.mode === 'cloud') {
      const id = welcomeDraft.cloudProvider;
      const result = providerResults.get(id);
      link.hidden = id !== 'openrouter' || !select.value;
      if (!link.hidden) link.href = cloudURL({id: select.value});
      note.textContent = !result && (providerScan || fromOpenCode(id)) ? 'Получаем список моделей…'
        : result?.catalog === 'default_only'
          ? 'Для этого аккаунта доступна настройка по умолчанию в Claude Code. Точный список смотрите через /model.'
          : result?.catalog === 'fallback'
            ? 'Каталог не ответил. Показаны варианты OpenRouter для справки.'
            : !result?.models?.length && id !== 'custom'
              ? 'Модели не получены. Можно вернуться к выбору провайдера.'
              : ['openrouter', 'custom'].includes(id)
                ? 'Эту модель можно использовать в разделе «Исследование игры».'
                : 'Модель сохранится в настройках. Исследование через этот клиент ещё не подключено.';
      return;
    }
    link.hidden = true;
    const item = plan?.research.find(model => model.id === select.value);
    const suggested = localSuggestion();
    if (item) {
      note.textContent = item.installed ? 'Модель обнаружена в Ollama. Запуск ещё не проверен.' : `Для запуска установите модель командой ${item.install_command}.`;
    } else if (pending) {
      note.textContent = 'Проверяем установленные модели…';
    } else {
      note.textContent = suggested
        ? `Рекомендуем ${suggested.name}. Модель можно выбрать позже.`
        : 'Подходящая локальная LLM пока не найдена. Можно выбрать облако или продолжить без LLM.';
    }
  }

  function explainWelcomeVoice() {
    const voice = plan?.tts.find(model => model.id === $('welcome-voice').value);
    const note = $('welcome-voice-note');
    if (voice?.cloning) {
      note.textContent = voice.installed
        ? 'После открытия игры назначьте образец голоса персонажу.'
        : 'Для клонирования установите XTTS и назначьте образец голоса персонажу.';
    } else if (voice?.installed) {
      note.textContent = 'Голос обнаружен на компьютере. Проверьте язык перед записью.';
    } else {
      note.textContent = 'Голос можно настроить после открытия игры.';
    }
  }

  function renderWelcome() {
    const cloud = welcomeDraft.mode === 'cloud';
    for (const phase of ['mode', 'provider', 'llm', 'voice']) $(`welcome-${phase}-panel`).hidden = welcomeStep !== phase;
    $('welcome-later').hidden = welcomeStep !== 'mode';
    $('welcome-back').hidden = welcomeStep === 'mode';
    $('welcome-continue').hidden = welcomeStep === 'mode';
    $('welcome-continue').disabled = false;
    $('welcome-continue').textContent = welcomeStep === 'voice' ? 'Перейти в студию' : 'Далее';

    const [title, description] = {
      mode: ['Добро пожаловать в AnyGameVoice', 'Где будут работать ваши модели?'],
      provider: ['Выберите провайдера', 'Используйте установленный клиент, бесплатные модели или свой API.'],
      llm: ['Выберите LLM', cloud ? `Провайдер: ${providerName(welcomeDraft.cloudProvider)}` : 'Выберите локальную модель для работы с текстом и исследования игры.'],
      voice: ['Выберите модель озвучки', cloud
        ? 'На этом шаге можно выбрать локальный голос. Облачная озвучка ещё не подключена.'
        : 'Выберите обычный голос Piper или клонирование по образцу с XTTS.'],
    }[welcomeStep];
    $('welcome-title').textContent = title;
    $('welcome-description').textContent = description;

    renderComparison();
    if (welcomeStep === 'provider') renderProviders();
    if (welcomeStep === 'llm') {
      const research = $('welcome-research');
      $('welcome-model-search-field').hidden = !cloud;
      $('welcome-local-models').hidden = cloud;
      research.hidden = !cloud;
      $('welcome-research-label').hidden = !cloud;
      $('welcome-research-label').textContent = cloud ? 'Облачная LLM' : 'Локальная LLM';
      research.replaceChildren(new Option('Выбрать позже', ''));
      if (cloud) {
        const filter = $('welcome-model-search').value.trim().toLowerCase();
        for (const model of cloudModelOrder(providerResults.get(welcomeDraft.cloudProvider)?.models || [])) {
          if (!`${model.name} ${model.id}`.toLowerCase().includes(filter) && model.id !== welcomeDraft.cloudResearch) continue;
          const rank = modelScore(model);
          const label = [model.name, rank && `Arena №${rank.rank}`, model.free && 'бесплатно'].filter(Boolean).join(' · ');
          research.add(new Option(label, model.id));
        }
      } else {
        for (const item of plan?.research || []) {
          const status = item.fit !== 'recommended' ? fits[item.fit] : item.installed ? 'установлена' : 'нужно установить';
          const option = new Option(`${item.name} · ${status}`, item.id);
          option.disabled = !researchOption(item);
          research.add(option);
        }
      }
      retainOption(research, cloud ? welcomeDraft.cloudResearch : welcomeDraft.research);
      if (!cloud) renderLocalModels();
      const custom = cloud && welcomeDraft.cloudProvider === 'custom';
      $('welcome-custom-model-field').hidden = !custom;
      $('welcome-custom-model').value = custom ? welcomeDraft.cloudResearch || '' : '';
      $('welcome-refresh').hidden = cloud || !!plan || pending;
      explainWelcomeResearch();
    }
    if (welcomeStep === 'voice') {
      const voice = $('welcome-voice');
      voice.replaceChildren(new Option('Настроить позже · автоподбор Piper', ''));
      for (const item of plan?.tts || []) {
        if (item.engine === 'piper' && item.fit === 'unsupported') continue;
        const status = item.fit !== 'recommended' ? fits[item.fit] : item.installed ? 'установлена' : 'нужно установить';
        const option = new Option(`${item.name} · ${status}`, item.id);
        option.disabled = !voiceOption(item);
        voice.add(option);
      }
      retainOption(voice, welcomeDraft.voice);
      $('welcome-install').hidden = !plan?.tts.some(item =>
        item.engine === 'piper' && item.fit === 'recommended' && !item.installed);
      explainWelcomeVoice();
    }
  }

  function renderLocalModels() {
    const list = $('welcome-local-list');
    const query = $('welcome-local-search').value.trim().toLowerCase();
    const items = (plan?.research || []).filter(item => `${item.name} ${item.id}`.toLowerCase().includes(query));
    const suggested = localSuggestion();
    const recommendation = $('welcome-local-recommendation');
    recommendation.replaceChildren();
    if (suggested) {
      const measured = localScore(suggested);
      const rankedCount = plan.research.filter(item => researchOption(item) && localScore(item)).length;
      const basis = suggested.installed ? 'Уже установлена и проходит оценку памяти.'
        : measured && rankedCount >= 2 ? 'Лучший результат IFBench среди подходящих моделей с оценками.'
          : 'Подходит по оценке свободной памяти. Выбрана наиболее новая доступная серия.';
      recommendation.append(el('strong', '', `Рекомендуем ${suggested.name}`),
        el('small', '', `${basis} ${suggested.reason}`),
        el('small', '', 'Оценка приблизительная. Скорость и ускорение GPU нужно проверить запуском.'));
    } else if (!pending && plan) {
      recommendation.append(el('strong', '', 'Подходящая модель не найдена'),
        el('small', '', 'Проверьте свободную память и место на диске или выберите облачный режим.'));
    }
    items.sort((a, b) => Number(b.installed) - Number(a.installed)
      || Number(b.id === suggested?.id) - Number(a.id === suggested?.id));
    $('welcome-local-status').textContent = pending ? 'Проверяем Ollama и установленные модели…'
      : !plan?.ollama.available ? plan?.ollama.reason || 'Проверка Ollama недоступна.'
        : `Найдено установленных моделей: ${plan.research.filter(item => item.installed).length}.`;
    list.replaceChildren();
    if (!items.length && !pending) list.append(el('p', 'field-hint', 'Модели не найдены.'));
    for (const item of items) {
      const label = el('label', 'local-model-card');
      const radio = el('input');
      radio.type = 'radio'; radio.name = 'welcome-local-model'; radio.value = item.id;
      radio.checked = welcomeDraft.research === item.id;
      radio.disabled = !researchOption(item);
      const info = el('span');
      const status = item.installed ? 'Установлена' : 'Доступна для установки';
      const memory = item.memory_gb == null ? '' : ` · ≈ ${item.memory_gb} ГБ RAM`;
      info.append(el('strong', '', item.name), el('small', '', `${status} · ${fits[item.fit]}${memory}`));
      const measured = localScore(item);
      if (measured) {
        const verified = measured.verified ? 'проверено' : measured.self_reported ? 'данные автора' : 'источник не подтверждён';
        info.append(el('small', '', `IFBench · ${measured.score}% · ${measured.date} · ${verified} · LLM Stats`));
      } else {
        const arena = modelScore(item);
        if (arena) info.append(el('small', '', `Arena · русский текст №${arena.rank} · ${rankings.published}`));
      }
      if (item.manual_only || item.fit !== 'recommended') info.append(el('small', '', item.reason));
      label.append(radio, info); list.append(label);
    }
  }

  function showWelcomeStep(step) {
    welcomeStep = step;
    renderWelcome();
    $('welcome-title').focus();
  }

  function openWelcome() {
    if (occupied() || document.querySelector('dialog[open]')) return;
    $('welcome-comparison').open = !window.matchMedia('(max-width: 440px), (max-height: 500px)').matches;
    const currentVoice = !$('auto-mode').checked && plan?.tts.find(item =>
      item.engine === $('tts-engine').value && (item.cloning || item.voice === selectedVoice()));
    welcomeDraft = {
      mode: 'local',
      research: '',
      cloudResearch: '',
      cloudProvider: welcomePreferences?.cloudResearch ? 'openrouter' : '',
      ...welcomePreferences,
      voice: currentVoice?.id || welcomePreferences?.voice || '',
    };
    $('welcome-custom-name').value = welcomeDraft.custom?.name || '';
    $('welcome-custom-url').value = welcomeDraft.custom?.baseUrl || '';
    $('welcome-custom-key').value = '';
    $('welcome-provider-search').value = '';
    $('welcome-providers-connected').checked = false;
    $('welcome-providers-free').checked = false;
    $('welcome-provider-list').scrollTop = 0;
    welcomeStep = 'mode';
    renderWelcome();
    $('welcome-dialog').returnValue = '';
    $('welcome-dialog').showModal();
  }
  $('welcome-open').addEventListener('click', openWelcome);
  document.querySelectorAll('[data-welcome-mode]').forEach(card => {
    card.addEventListener('click', () => {
      welcomeDraft.mode = card.dataset.welcomeMode;
      if (welcomeDraft.mode === 'cloud') {
        showWelcomeStep('provider');
        scanCloudProviders();
        loadComparison();
      } else {
        if (!welcomeDraft.research && plan?.selected_research) welcomeDraft.research = plan.selected_research;
        showWelcomeStep('llm');
        if (!localScores) loadLocalScores();
        if (!rankings) loadComparison();
      }
    });
  });
  $('welcome-back').addEventListener('click', () => {
    if (welcomeStep === 'voice') showWelcomeStep('llm');
    else if (welcomeStep === 'llm' && welcomeDraft.mode === 'cloud') showWelcomeStep('provider');
    else showWelcomeStep('mode');
  });
  $('welcome-research').addEventListener('change', () => {
    const key = welcomeDraft.mode === 'cloud' ? 'cloudResearch' : 'research';
    welcomeDraft[key] = $('welcome-research').value;
    if (!$('welcome-custom-model-field').hidden) $('welcome-custom-model').value = welcomeDraft[key];
    explainWelcomeResearch();
  });
  $('welcome-custom-model').addEventListener('input', () => {
    welcomeDraft.cloudResearch = $('welcome-custom-model').value.trim();
  });
  $('welcome-voice').addEventListener('change', () => {
    welcomeDraft.voice = $('welcome-voice').value;
    explainWelcomeVoice();
  });
  $('welcome-refresh').addEventListener('click', () => refresh(false));
  $('welcome-catalog').addEventListener('click', () => {
    catalogFromWelcome = true;
    $('welcome-dialog').close('detour');
    $('choose-models').click();
  });
  $('welcome-install').addEventListener('click', () => {
    $('welcome-dialog').close('detour');
    window.agvSetup?.offer(null, true);
  });
  $('welcome-continue').addEventListener('click', () => {
    if (welcomeStep === 'provider') {
      $('welcome-model-search').value = '';
      if (welcomeDraft.cloudProvider === 'custom') openCustomModels();
      else if (welcomeDraft.cloudProvider === 'openrouter') openRouterModels();
      else if (welcomeDraft.cloudProvider) {
        showWelcomeStep('llm');
        if (fromOpenCode(welcomeDraft.cloudProvider)) loadOpenCodeModels(welcomeDraft.cloudProvider);
      }
      return;
    }
    if (welcomeStep === 'llm') {
      const id = welcomeDraft.cloudProvider;
      const model = providerResults.get(id)?.models?.find(item => item.id === welcomeDraft.cloudResearch);
      welcomeDraft.cloudModelName = model?.name || welcomeDraft.cloudResearch;
      showWelcomeStep('voice');
      return;
    }
    welcomeDraft.voice = $('welcome-voice').value;
    if (welcomePreferences?.cloudProvider !== welcomeDraft.cloudProvider ||
      welcomePreferences?.custom?.baseUrl !== welcomeDraft.custom?.baseUrl) $('research-key').value = '';
    welcomePreferences = {...welcomeDraft};
    setDubbing({translate_to:$('dub-direction').value, ...translationDefaults()});
    try { localStorage.setItem('agv-start-models-v1', JSON.stringify(welcomePreferences)); } catch {}
    chooseWelcomeVoice(welcomePreferences.voice);
    renderResearchOptions(true);
    researchDescription();
    $('welcome-dialog').close();
  });
  $('welcome-dialog').addEventListener('close', () => {
    $('welcome-custom-key').value = '';
    $('welcome-openrouter-key').value = '';
    if ($('welcome-dialog').returnValue === 'detour') return;
    welcomeSeen = true;
    try { localStorage.setItem('agv-welcome-seen-v3', '1'); } catch {}
  });
  const cloudLinks = $('cloud-model-links');
  for (const model of cloudModels) {
    const link = el('a', '', model.label);
    link.href = cloudURL(model);
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    if (cloudLinks.childNodes.length) cloudLinks.append(document.createTextNode(' · '));
    cloudLinks.append(link);
  }
  function candidate(item, role) {
    const label = el('label', `model-candidate fit-${item.fit}`);
    const radio = el('input'); radio.type = 'radio'; radio.name = `model-${role}`; radio.value = item.id;
    radio.dataset.unavailable = role === 'tts' ? (!item.installed || item.fit !== 'recommended' ? '1' : '0') : item.manual_only || item.fit !== 'recommended' ? '1' : '0';
    radio.checked = catalogFromWelcome
      ? (role === 'tts' ? welcomeDraft.voice : welcomeDraft.research) === item.id
      : role === 'tts'
        ? $('tts-engine').value === item.engine && (item.voice ? selectedVoice() === item.voice : item.engine === 'xtts')
        : $('research-model').value === item.id;
    const text = el('span', 'model-candidate-body');
    text.append(el('strong', '', item.name), el('span', 'model-fit-label', `${fits[item.fit]} · ${readiness(item)}`), el('small', '', `${item.class}${item.memory_gb == null ? '' : ` · ≈ ${item.memory_gb} ГБ RAM`}`), el('small', '', item.reason), el('small', '', `Лицензия: ${item.license}`));
    if (!item.installed && item.install_command) text.append(el('code', 'model-install-command', item.install_command));
    if (item.source?.startsWith('https://huggingface.co/')) {
      const link = el('a', 'text-link', 'Официальная карточка на Hugging Face');
      link.href = item.source; link.target = '_blank'; link.rel = 'noopener noreferrer';
      link.addEventListener('click', event => event.stopPropagation()); text.append(link);
    }
    radio.addEventListener('change', () => {
      if (catalogFromWelcome) {
        welcomeDraft[role === 'tts' ? 'voice' : 'research'] = item.id;
        return;
      }
      if (role === 'tts') {
        if ($('auto-mode').checked) { $('auto-mode').checked = false; $('auto-mode').dispatchEvent(new Event('change')); }
        applyTTS(item);
      }
      else { $('research-model').value = item.id; researchDescription(); }
    });
    label.append(radio, text); return label;
  }
  function renderPlan(autoselect) {
    $('machine-summary').textContent = machineSummary(plan.hardware);
    $('model-class').textContent = `Рекомендуемый класс: ${plan.research_class}`;
    $('model-upper').textContent = `Предел по общему объёму RAM: ${plan.upper_class}; свободной памяти может не хватить.${plan.gpu_research_class ? ` Потенциал GPU: ${plan.gpu_research_class}; ускорение не проверено.` : ' GPU-ускорение не проверено.'}`;
    $('model-estimate-note').textContent = plan.note;
    renderResearchOptions();
    if (autoselect && plan.selected_tts) applyTTS(plan.selected_tts);
    else {
      const name = state.voices.find(voice => voice.path === selectedVoice())?.name || selectedVoice() || $('tts-engine').selectedOptions[0].textContent;
      const xtts = !$('auto-mode').checked && $('tts-engine').value === 'xtts';
      $('recommended-voice').textContent = selectedVoice() || xtts ? name : plan.selected_tts?.name || 'Голос не установлен';
      $('recommended-voice-note').textContent = selectedVoice()
        ? 'Текущий выбор сохранён · проверьте пробной записью'
        : xtts
          ? state.engines.xtts ? 'Назначьте WAV-образец персонажу' : 'Сначала установите XTTS и назначьте образец актёра'
          : plan.selected_tts ? 'Доступный обычный голос · без клонирования' : 'Откройте подготовку компонентов';
    }
    const oldSearch = $('research-search').value;
    $('research-search').replaceChildren(new Option('Мой источник · без интернет-поиска', 'none'));
    for (const item of plan.searches) {
      const option = new Option(`${item.name}${item.available ? '' : ' · нужен API-ключ'}`, item.id);
      option.disabled = !item.available; $('research-search').add(option);
    }
    $('research-search').value = plan.searches.some(item => item.id === oldSearch && item.available) ? oldSearch : plan.searches.find(item => item.available)?.id || 'none';
    $('provided-source').open = $('research-search').value === 'none';
    $('tts-model-candidates').replaceChildren(...plan.tts.map(item => candidate(item, 'tts')));
    $('research-model-candidates').replaceChildren(...plan.research.map(item => candidate(item, 'research')));
    researchDescription();
  }
  function renderResearchOptions(usePreferences = false) {
    updateDubbingModels($('dub-provider').value);
    const oldResearch = usePreferences ? '' : $('research-model').value;
    const configured = savedCloudResearch();
    $('research-model').replaceChildren(new Option('Выберите модель исследования', ''));
    if (configured) $('research-model').add(new Option(`${configured.cloudModelName || configured.cloudResearch} · ${cloudResearchName(configured)}`, 'agv:cloud'));
    for (const item of plan?.research || []) {
      const option = new Option(`${item.name} · ${fits[item.fit]} · ${item.installed ? 'установлена' : 'нужно установить'}`, item.id);
      option.disabled = item.fit !== 'recommended' || !!item.manual_only;
      $('research-model').add(option);
    }
    const requested = oldResearch || (configured ? 'agv:cloud' : welcomePreferences?.mode === 'local' ? welcomePreferences.research : '');
    const preferred = plan?.research.find(item => item.id === requested);
    $('research-model').value = (configured && requested === 'agv:cloud') || researchOption(preferred)
      ? requested : welcomePreferences ? '' : plan?.selected_research || plan?.suggested_research || '';
  }
  async function refresh(autoselect = false) {
    const current = ++epoch; const game = state.game;
    pending = true; $('model-overview').hidden = false; $('machine-summary').textContent = 'Проверяем свободную память, локальные голоса и Ollama…'; syncControls();
    try {
      const data = await api('/api/studio/models/plan', {language: $('voice-language').value});
      if (current !== epoch || game !== state.game) return;
      plan = data;
      if (!game && !occupied() && welcomePreferences?.voice && !selectedVoice()) chooseWelcomeVoice(welcomePreferences.voice);
      for (const item of plan.tts) item.launch_verified=verifiedVoices.has(JSON.stringify([item.engine,item.voice]));
      renderPlan(autoselect);
    } catch (error) {
      if (current !== epoch) return;
      $('machine-summary').textContent = `Подбор не завершён: ${friendlyError(error)}`;
    } finally {
      if (current === epoch) {
        pending = false;
        if ($('welcome-dialog').open) {
          if (welcomeDraft.mode === 'local' && !welcomeDraft.research && plan?.selected_research) {
            welcomeDraft.research = plan.selected_research;
          }
          renderWelcome();
        }
        syncControls();
      }
    }
  }
  function renderReport() {
    const box = $('research-results'); box.replaceChildren(); box.hidden = !report;
    if (!report) return;
    box.append(el('h3', '', 'Предварительный отчёт'), el('p', 'research-summary', report.summary), el('p', 'field-hint', report.note));
    const sources = new Map(report.sources.map(source => [source.id, source]));
    if (!report.cast.length) box.append(el('p', '', 'Подтверждённые выдержкой соответствия актёров не найдены. Добавьте другой источник.'));
    for (const finding of report.cast) {
      const row = el('article', 'cast-finding');
      row.append(el('strong', '', `${finding.character} → ${finding.actor}`), el('span', 'model-fit-label', 'Кандидат · проверьте роль и издание'), el('blockquote', '', finding.evidence));
      for (const sourceId of finding.source_ids) {
        const source = sources.get(sourceId); if (!source) continue;
        const link = el('a', 'research-source-link', source.title); link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; row.append(link);
      }
      const use = el('button', 'text-link', 'Добавить образец этого актёра');
      use.addEventListener('click', () => {
        $('reference-actor').value = finding.actor;
        const character = state.characters.find(item => item.name.toLowerCase() === finding.character.toLowerCase() || speakerName(item.name).toLowerCase() === finding.character.toLowerCase());
        if (character) $('reference-character').value = character.name;
        $('reference-path').focus();
      });
      row.append(use); box.append(row);
    }
    if (report.samples.length) {
      box.append(el('h3', '', 'Реплики для сравнения'));
      for (const sample of report.samples) {
        const button = el('button', 'research-sample');
        button.append(el('strong', '', speakerName(sample.speaker)), el('span', '', sample.text));
        button.addEventListener('click', () => preview(sample, true)); box.append(button);
      }
    }
    const links = el('details', 'research-all-sources'); links.append(el('summary', '', `Источники · ${report.sources.length}`));
    for (const source of report.sources) { const link = el('a', 'research-source-link', source.title); link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; links.append(link); }
    box.append(links);
  }
  $('research-form').addEventListener('submit', async event => {
    event.preventDefault(); if ($('run-research').disabled) return;
    const sources = [];
    if ($('research-source-url').value.trim() || $('research-source-text').value.trim()) {
      if (!$('research-source-url').value.trim() || !$('research-source-text').value.trim()) { $('research-state').textContent = 'Для своего источника нужны и ссылка, и выдержка.'; return; }
      sources.push({title:'Источник пользователя',url:$('research-source-url').value.trim(),snippet:$('research-source-text').value.trim()});
    }
    if ($('research-search').value === 'none' && !sources.length) { $('research-state').textContent = 'Добавьте ссылку и выдержку или выберите настроенный интернет-поиск.'; return; }
    const cloud = activeCloudResearch();
    const request = {path:state.game,title:$('research-title-input').value.trim(),model:$('research-model').value,search:$('research-search').value,sources};
    if (cloud) {
      request.model = cloud.cloudResearch;
      request.provider = cloud.cloudProvider;
      request.base_url = cloud.cloudProvider === 'custom' ? cloud.custom?.baseUrl || '' : '';
      request.api_key = $('research-key').value.trim() ||
        (cloud.cloudProvider === 'openrouter' ? routerSessionKey :
          request.base_url && request.base_url === customSessionKey?.baseUrl ? customSessionKey.token : '');
    }
    state.busy = true; updateControls(); $('research-state').textContent = 'Исследуем источники. Это может занять несколько минут…';
    try {
      report = await api('/api/studio/research', request);
      renderReport(); $('research-state').textContent = `Отчёт готов. Кандидатов: ${report.cast.length}. Реплик для сравнения: ${report.samples.length}.`;
    } catch (error) { $('research-state').textContent = friendlyError(error); }
    finally { state.busy = false; updateControls(); }
  });
  $('reference-form').addEventListener('submit', async event => {
    event.preventDefault(); if ($('apply-reference').disabled) return;
    const character = $('reference-character').value;
    if (!state.characters.some(item => item.name === character)) return;
    const path = $('reference-path').value.trim();
    const protectedReference = $('reference-protected').checked;
    state.busy = true; updateControls();
    try {
      const data = await api('/api/studio/reference/validate', {path});
      if ($('tts-engine').value !== 'xtts') state.assignments = Object.create(null);
      $('tts-engine').value = 'xtts'; $('voice-select').value = ''; $('voice-path').value = '';
      state.assignments[character] = data.path;
      if (protectedReference && !state.voiceBlend.protected_voices.includes(data.path)) {
        state.voiceBlend.protected_voices.push(data.path);
      }
      preserveManualChoice();
      references[character] = {actor:$('reference-actor').value.trim(),path:data.path,duration:data.duration};
      renderVoiceOptions();
      $('reference-state').textContent = `${speakerName(character)}: образец ${data.duration} с назначен. ${state.engines.xtts ? 'Сравните пробную запись с оригиналом.' : 'Для синтеза ещё нужен установленный XTTS; готовность не подтверждена.'}`;
      if (protectedReference && state.voiceBlend.strength < 1 && !state.voiceBlend.base_voice) $('reference-state').textContent += ' Укажите WAV с другим голосом в «Настройки JSON» (base_voice).';
      $('recommended-voice').textContent = 'XTTS v2 · образцы актёров'; $('recommended-voice-note').textContent = 'Назначен образец персонажу; остальные голоса задаются отдельно';
    } catch (error) { $('reference-state').textContent = friendlyError(error); }
    finally { state.busy = false; updateControls(); }
  });
  $('models-setup').addEventListener('click', () => { $('model-picker').close('setup'); window.agvSetup?.offer(null, true); });
  $('choose-models').addEventListener('click', () => {
    if (!plan) return;
    renderPlan(false);
    $('model-picker').returnValue = '';
    $('model-picker').showModal();
  });
  $('model-picker').addEventListener('close', () => {
    const resumeWelcome = catalogFromWelcome && $('model-picker').returnValue !== 'setup';
    catalogFromWelcome = false;
    if (resumeWelcome) {
      $('welcome-dialog').returnValue = '';
      renderWelcome();
      $('welcome-dialog').showModal();
      $('welcome-title').focus();
    } else {
      $('choose-models').focus();
    }
  });
  $('refresh-model-plan').addEventListener('click', () => refresh(false));
  $('research-model').addEventListener('change', researchDescription);
  $('research-search').addEventListener('change', () => { $('provided-source').open = $('research-search').value === 'none'; });
  for (const id of ['tts-engine','voice-select','voice-path']) $(id).addEventListener('change',()=>{
    if (!state.game) return;
    $('recommended-voice').textContent=state.voices.find(voice=>voice.path===selectedVoice())?.name || selectedVoice() || $('tts-engine').selectedOptions[0].textContent;
    $('recommended-voice-note').textContent='Ваш выбор · фактический запуск проверяется пробной записью';
  });
  $('voice-language').addEventListener('change', () => { if (state.game) refresh(false); });
  document.addEventListener('agv:controls', syncControls);
  function updateDubbingModels(provider) {
    const models = provider === 'ollama'
      ? (plan?.research || []).filter(item => item.installed && !item.manual_only)
      : providerResults.get(provider)?.models || [];
    $('dub-model-list').replaceChildren(...models.map(item => new Option(item.name || item.id, item.id)));
  }
  function translationDefaults() {
    if (welcomePreferences?.mode !== 'cloud') return {provider:'ollama', translation_model:welcomePreferences?.research || ''};
    if (!savedCloudResearch()) return {provider:'', translation_model:''};
    return {provider:welcomePreferences.cloudProvider, translation_model:welcomePreferences.cloudResearch || '',
      base_url:welcomePreferences.cloudProvider === 'custom' ? welcomePreferences.custom?.baseUrl || '' : ''};
  }
  window.agvModels = {
    translationDefaults,
    updateDubbingModels,
    refreshDubbingVoices() {
      if (state.game) refresh($('auto-mode').checked && $('tts-engine').value === 'piper' && !selectedVoice());
    },
    translationToken(provider, endpoint) {
      if (provider === 'openrouter') return routerSessionKey;
      return provider === 'custom' && endpoint === customSessionKey?.baseUrl ? customSessionKey.token : '';
    },
    welcomeOnStartup() {
      const preview = new URLSearchParams(location.search).get('welcome') === '1';
      if (preview || (!welcomeSeen && !state.game)) openWelcome();
    },
    async onGameLoaded({name, restored}) {
      plan = null; report = null; references = Object.create(null); renderReport();
      for (const id of ['recommended-voice','recommended-research','model-class','model-upper','recommended-voice-note','recommended-research-note','model-estimate-note']) $(id).textContent='';
      $('research-model').replaceChildren(new Option('Подбираем модель…',''));
      const savedReferences=restored?.studio_context?.references;
      if (savedReferences && typeof savedReferences==='object') for (const character of state.characters) {
        const entry=savedReferences[character.name];
        if (entry && typeof entry.actor==='string' && typeof entry.path==='string' && state.assignments[character.name]===entry.path) references[character.name]={actor:entry.actor.slice(0,120),path:entry.path,duration:Number(entry.duration)||0};
      }
      for(const id of ['research-source-url','research-source-text']) $(id).value='';
      $('research-title-input').value = typeof restored?.studio_context?.title === 'string' ? restored.studio_context.title.slice(0,200) : name;
      $('reference-character').replaceChildren(...state.characters.map(item => new Option(speakerName(item.name),item.name)));
      $('reference-state').textContent = state.characters.length ? 'Образец хранится локально. Назначение выбирает XTTS.' : 'Сначала нужен адаптер извлечения диалогов этой игры.';
      $('reference-path').value = ''; $('reference-actor').value = ''; $('reference-protected').checked = false;
      $('empty-state').hidden = !!state.lines.length;
      $('empty-state').querySelector('h3').textContent = state.lines.length ? 'У каждой истории есть голос' : 'Для этой игры нужен адаптер диалогов';
      $('empty-state').querySelector('p').textContent = state.lines.length ? 'Откройте папку игры. Мы найдём диалоги и соберём персонажей в одном месте.' : 'Модели подобраны. Исследование дубляжа доступно в разделе «Исследование»; озвучка начнётся после извлечения реплик.';
      $('demo-empty').hidden = !state.lines.length;
      await refresh(!restored?.schema && $('auto-mode').checked);
      const savedModel = restored?.studio_context?.model;
      if (typeof savedModel === 'string' && plan?.research.some(item=>item.id===savedModel && item.fit==='recommended' && !item.manual_only)) { $('research-model').value=savedModel; researchDescription(); }
    },
    markVerified(engine,voice) {
      verifiedVoices.add(JSON.stringify([engine,voice]));
      const candidate=plan?.tts.find(item=>item.engine===engine && item.voice===voice); if(candidate) candidate.launch_verified=true;
      if(engine===$('tts-engine').value && voice===selectedVoice()) $('recommended-voice-note').textContent='Пробная запись выполнена на этом компьютере';
    },
    snapshot: () => ({title:$('research-title-input').value,model:$('research-model').value,references:{...references}}),
    reset() { epoch++; pending=false; report=null; references=Object.create(null); renderReport(); for(const id of ['research-title-input','research-source-url','research-source-text','reference-actor','reference-path']) $(id).value=''; $('reference-character').replaceChildren(new Option('Нужны извлечённые персонажи','')); $('research-model').replaceChildren(new Option('Сначала откройте игру','')); $('reference-state').textContent=''; $('research-state').textContent='Откройте игру, чтобы подобрать модель.'; $('empty-state').querySelector('h3').textContent='У каждой истории есть голос'; $('empty-state').querySelector('p').textContent='Откройте папку игры. Мы найдём диалоги и соберём персонажей в одном месте.'; $('demo-empty').hidden=false; }
  };
  setDubbing({translate_to:$('dub-direction').value, ...translationDefaults()});
  syncControls();
  refresh(false);
})();
