let preferredDubbingTarget = null;
let dubbingSource = 'auto';

function loadDubbingLanguages(languages) {
  for (const id of ['dub-direction', 'voice-language']) {
    const select = $(id);
    const saved = select.value;
    const options = Object.entries(languages).map(([code, name]) => new Option(name, code));
    if (id === 'dub-direction') options.unshift(new Option('Озвучить исходный текст', ''));
    select.replaceChildren(...options);
    select.value = saved;
  }
}

function setDubbing(value = {}) {
  $('dub-direction').value = value.translate_to || '';
  dubbingSource = value.source_lang || 'auto';
  $('dub-provider').value = value.provider ?? 'ollama';
  $('dub-model').value = value.translation_model || '';
  $('dub-endpoint').value = value.base_url || '';
  $('dub-format').value = value.api_format || 'openai_chat';
  $('dub-key').value = '';
  syncDubbing();
  window.syncMaterialSelects?.();
}
function safeDubbingEndpoint(input) {
  if (!input) return '';
  try {
    const url = new URL(input);
    if (['http:', 'https:'].includes(url.protocol) && !url.username && !url.password && !url.search && !url.hash) return input;
  } catch {}
  return '';
}
function dubbingSettings() {
  const translate_to = $('dub-direction').value;
  if (!translate_to) return {};
  return {source_lang: dubbingSource, translate_to, provider: $('dub-provider').value,
    translation_model: $('dub-model').value.trim(), api_format: $('dub-provider').value === 'custom' ? $('dub-format').value : 'openai_chat', base_url: $('dub-provider').value === 'custom' ? safeDubbingEndpoint($('dub-endpoint').value.trim()) : ''};
}
function syncDubbing() {
  const options = dubbingSettings();
  $('dub-options').hidden = !options.translate_to;
  window.agvModels?.updateDubbingModels(options.provider);
  $('dub-custom').hidden = options.provider !== 'custom';
  $('dub-opencode').hidden = options.provider !== 'opencode';
  $('dub-auth').hidden = ['ollama', 'opencode', ''].includes(options.provider);
  $('dub-text').hidden = !options.translate_to;
  const path = selectedVoice();
  const selected = state.voices.find(item => item.path === path);
  const target = options.translate_to;
  const label = $('dub-direction').selectedOptions[0]?.textContent;
  let voice = path.split(/[\\/]/).pop() || 'автоподбор';
  if (target && $('tts-engine').value === 'piper') {
    const matches = item => item.engine === 'piper' && item.language?.split(/[-_]/)[0].toLowerCase() === target;
    if (selected && !matches(selected)) voice += ' · выберите голос для этого языка';
    else if (!path) voice = state.engines.piper && state.voices.some(matches) ? 'доступен для автоподбора' : 'нужен голос для дубляжа';
  }
  $('dub-summary').textContent = target
    ? `Перевод: ${label} · ${options.provider || 'Выберите провайдера'} / ${options.translation_model || 'Выберите модель'} · Голос: ${voice}`
    : `Без перевода · Голос: ${voice}`;
}
function dubbingRequest(trial) {
  const config = dubbingSettings();
  if (!config.translate_to) return {trial};
  if (!config.provider || !config.translation_model) throw Error('Выберите провайдера и укажите модель перевода.');
  if (config.provider === 'custom') {
    if (!config.base_url) throw Error('Укажите HTTP(S)-адрес API без ключей и параметров.');
  }
  if (config.provider !== 'ollama') {
    const count = trial ? Math.min(3, state.lines.length) : state.lines.length;
    const host = config.base_url || $('dub-provider').selectedOptions[0].textContent;
    if (!window.confirm(`Отправить до ${count} реплик в ${host} для перевода моделью ${config.translation_model}? Провайдер может списать оплату.`)) {
      throw Error('Облачный перевод отменён.');
    }
  }
  const api_key = ['ollama', 'opencode'].includes(config.provider) ? '' : $('dub-key').value.trim() ||
    window.agvModels?.translationToken(config.provider, config.base_url) || '';
  // Existing Russian projects reuse their original manifest and recordings.
  return {...config, trial, api_key, language_subdir: config.translate_to !== 'ru'};
}
document.addEventListener('DOMContentLoaded', () => {
  for (const id of ['dub-direction','dub-provider','dub-model','dub-endpoint','dub-format']) {
    $(id).addEventListener('input', () => {
      if (id === 'dub-provider') {
        $('dub-model').value = '';
        if ($('dub-provider').value === 'opencode') window.agvModels?.loadDubbingOpenCode();
      }
      if (id === 'dub-provider' || id === 'dub-endpoint') $('dub-key').value = '';
      if (id === 'dub-direction') {
        preferredDubbingTarget = $('dub-direction').value;
        if (preferredDubbingTarget) {
          $('voice-language').value = preferredDubbingTarget;
          const voice = state.voices.find(item => item.path === selectedVoice());
          if ($('auto-mode').checked && voice?.engine === 'piper' && voice.language?.split(/[-_]/)[0] !== preferredDubbingTarget) {
            $('voice-path').value = ''; $('voice-select').value = '';
            renderVoiceOptions();
          }
        }
        window.agvModels?.refreshDubbingVoices();
      }
      updateControls();
    });
  }
  $('dub-connect').addEventListener('click', () => window.agvModels?.openConnectionPicker());
  $('dub-text').addEventListener('click', () => generate(false, true));
  $('dub-trial').addEventListener('click', () => {
    if ($('auto-mode').checked) window.agvAuto.start(false, true);
    else generate(true);
  });
  syncDubbing();
});
