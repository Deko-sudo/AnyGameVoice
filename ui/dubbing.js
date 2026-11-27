// Keep saved project choices separate from session-only provider credentials.
function setDubbing(value = {}) {
  $('dub-direction').value = value.translate_to === 'ru' ? 'ru' : '';
  $('dub-provider').value = value.provider || 'ollama';
  $('dub-model').value = value.translation_model || '';
  $('dub-endpoint').value = value.base_url || '';
  $('dub-key').value = '';
  syncDubbing();
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
  return {source_lang: 'en', translate_to, provider: $('dub-provider').value,
    translation_model: $('dub-model').value.trim(), base_url: $('dub-provider').value === 'custom' ? safeDubbingEndpoint($('dub-endpoint').value.trim()) : ''};
}
function syncDubbing() {
  const options = dubbingSettings();
  $('dub-options').hidden = !options.translate_to;
  if (options.provider === 'ollama') $('dub-model').setAttribute('list', 'dub-model-list');
  else $('dub-model').removeAttribute('list');
  $('dub-custom').hidden = options.provider !== 'custom';
  $('dub-auth').hidden = !['custom','openrouter'].includes(options.provider);
  const voice = selectedVoice().split(/[\\/]/).pop() || 'автоподбор';
  $('dub-summary').textContent = options.translate_to
    ? `English → Русский · ${options.provider || 'Выберите провайдера'} / ${options.translation_model || 'Выберите модель'} · Голос: ${voice}`
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
    const host = config.base_url || 'OpenRouter';
    if (!window.confirm(`Отправить до ${count} реплик в ${host} для перевода моделью ${config.translation_model}? Провайдер может списать оплату.`)) {
      throw Error('Облачный перевод отменён.');
    }
  }
  const api_key = config.provider === 'ollama' ? '' : $('dub-key').value.trim() ||
    window.agvModels?.translationToken(config.provider, config.base_url) || '';
  return {...config, trial, api_key};
}
document.addEventListener('DOMContentLoaded', () => {
  for (const id of ['dub-direction','dub-provider','dub-model','dub-endpoint']) {
    $(id).addEventListener('input', () => {
      if (id === 'dub-provider' || id === 'dub-endpoint') $('dub-key').value = '';
      if ($('dub-direction').value) $('voice-language').value = 'ru';
      updateControls();
    });
  }
  $('dub-trial').addEventListener('click', () => {
    if ($('auto-mode').checked) window.agvAuto.start(false, true);
    else generate(true);
  });
  syncDubbing();
});
