// SPDX-License-Identifier: Apache-2.0
// Apply the saved appearance before CSS paints, then attach the native dialog UI.
(() => {
  'use strict';
  const builtins = window.AnyGameVoiceThemes;
  let themes = builtins;
  let custom = [];
  function loadCatalog(rows = []) {
    const seen = new Set();
    custom = (Array.isArray(rows) ? rows : []).filter(row => {
      if (!/^user-[a-f0-9-]{36}$/.test(row?.id) || !/^#[a-f0-9]{6}$/i.test(row.seed) ||
          typeof row.name !== 'string' || !row.name.trim() || row.name.length > 48 || seen.has(row.id)) return false;
      seen.add(row.id);
      return true;
    }).map(({id, name, seed}) => ({id, name, seed}));
    themes = [...builtins, ...custom.map(row => ({
      ...row, description: 'Пользовательская тема', schemes: StudioColor.schemes(row.seed)
    }))];
  }
  function paintCustom(element, theme, mode) {
    const isCustom = theme.id.startsWith('user-');
    for (const [role, value] of Object.entries(theme.schemes[mode])) {
      if (isCustom) element.style.setProperty('--md-' + role, value);
      else element.style.removeProperty('--md-' + role);
    }
  }
  const key = 'anygamevoice.appearance.v1';
  const defaults = { theme: 'iris', mode: 'system' };
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const root = document.documentElement;
  let preferences = { ...defaults };
  let storageAvailable = true;
  function normalize(value) {
    return {
      theme: themes.some(theme => theme.id === value?.theme) ? value.theme : defaults.theme,
      mode: ['system', 'light', 'dark'].includes(value?.mode) ? value.mode : defaults.mode,
    };
  }
  function read() {
    let stored;
    try { stored = localStorage.getItem(key); }
    catch { storageAvailable = false; return { ...defaults }; }
    try {
      const value = JSON.parse(stored);
      loadCatalog(value?.custom);
      return normalize(value);
    }
    catch { return { ...defaults }; }
  }
  function apply() {
    root.dataset.theme = preferences.theme;
    root.dataset.mode = preferences.mode === 'system' ? (media.matches ? 'dark' : 'light') : preferences.mode;
    const theme = themes.find(theme => theme.id === preferences.theme);
    paintCustom(root, theme, root.dataset.mode);
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme.schemes[root.dataset.mode].surface);
  }
  preferences = read();
  apply();
  function save() {
    try { localStorage.setItem(key, JSON.stringify({...preferences, custom})); storageAvailable = true; }
    catch { storageAvailable = false; }
  }
  document.addEventListener('DOMContentLoaded', () => {
    const dialog = document.getElementById('appearance-dialog');
    const grid = document.getElementById('theme-grid');
    const status = document.getElementById('appearance-status');
    const licenses = document.getElementById('licenses-dialog');
    function renderCatalog() {
      grid.replaceChildren();
      document.getElementById('palette-count').textContent = String(themes.length);
      for (const theme of themes) {
        const label = document.createElement('label');
        label.className = 'theme-option';
        label.dataset.palette = theme.id;
        label.title = theme.description;
        const input = document.createElement('input');
        input.type = 'radio'; input.name = 'studio-palette'; input.value = theme.id;
        const preview = document.createElement('span');
        preview.className = 'theme-swatch'; preview.setAttribute('aria-hidden', 'true');
        for (const part of ['swatch-rail', 'swatch-content', 'swatch-action', 'swatch-check']) {
          const span = document.createElement('span'); span.className = part;
          if (part === 'swatch-check') span.textContent = '✓';
          preview.append(span);
        }
        const name = document.createElement('span'); name.className = 'theme-name'; name.textContent = theme.name;
        label.append(input, preview, name); grid.append(label);
      }
    }
    renderCatalog();
    const search = document.getElementById('theme-search');
    function filterCatalog() {
      const query = search.value.trim().toLocaleLowerCase('ru');
      let visible = 0;
      for (const label of grid.children) {
        const theme = themes.find(item => item.id === label.dataset.palette);
        label.hidden = !`${theme.name} ${theme.description} ${theme.id}`.toLocaleLowerCase('ru').includes(query);
        if (!label.hidden) visible++;
      }
      document.getElementById('theme-search-empty').hidden = visible > 0;
    }
    search.addEventListener('input', filterCatalog);
    function sync() {
      for (const input of grid.querySelectorAll('input')) input.checked = input.value === preferences.theme;
      for (const input of document.querySelectorAll('[name="studio-mode"]')) input.checked = input.value === preferences.mode;
      const theme = themes.find(theme => theme.id === preferences.theme);
      for (const label of grid.querySelectorAll('[data-palette^="user-"]')) {
        paintCustom(label, themes.find(item => item.id === label.dataset.palette), root.dataset.mode);
      }
      document.getElementById('custom-theme-remove').hidden = !theme.id.startsWith('user-');
      document.getElementById('appearance-current').textContent = theme.name;
      document.getElementById('appearance-button').setAttribute('aria-label', `Оформление: ${theme.name}`);
      document.getElementById('appearance-summary').textContent = `${theme.name} · ${root.dataset.mode === 'dark' ? 'Тёмная' : 'Светлая'}${preferences.mode === 'system' ? ' · Как в системе' : ''}`;
      status.textContent = storageAvailable ? 'Выбор сохраняется на этом устройстве.' : 'Хранилище браузера недоступно. Выбор действует до закрытия страницы.';
    }
    function update(changes) { preferences = normalize({ ...preferences, ...changes }); apply(); save(); sync(); }
    const nameInput = document.getElementById('custom-theme-name');
    nameInput.addEventListener('input', () => nameInput.setCustomValidity(''));
    document.getElementById('custom-theme-form').addEventListener('submit', event => {
      event.preventDefault();
      const name = nameInput.value.trim();
      if (!name || themes.some(theme => theme.name.toLocaleLowerCase('ru') === name.toLocaleLowerCase('ru'))) {
        nameInput.setCustomValidity('Введите уникальное название темы.');
        nameInput.reportValidity();
        return;
      }
      const row = {id: 'user-' + crypto.randomUUID(), name, seed: document.getElementById('custom-theme-color').value};
      loadCatalog([...custom, row]);
      renderCatalog();
      search.value = '';
      filterCatalog();
      update({theme: row.id});
      event.target.reset();
      event.target.closest('details').open = false;
    });
    document.getElementById('custom-theme-remove').addEventListener('click', () => {
      loadCatalog(custom.filter(row => row.id !== preferences.theme));
      renderCatalog();
      filterCatalog();
      update({theme: defaults.theme});
    });
    grid.addEventListener('change', event => {
      if (event.target.matches('input[type="radio"]')) update({ theme: event.target.value });
    });
    document.getElementById('mode-options').addEventListener('change', event => {
      if (event.target.matches('input[type="radio"]')) update({ mode: event.target.value });
    });
    document.getElementById('appearance-reset').addEventListener('click', () => update(defaults));
    const open = (target, trigger) => {
      trigger.addEventListener('click', () => target.showModal());
      target.addEventListener('close', () => trigger.focus());
      target.addEventListener('click', event => {
        if (event.target !== target) return;
        const bounds = target.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) target.close();
      });
    };
    open(dialog, document.getElementById('appearance-button'));
    open(licenses, document.getElementById('licenses-button'));
    media.addEventListener('change', () => { if (preferences.mode === 'system') { apply(); sync(); } });
    window.addEventListener('storage', event => {
      if (event.key === key || event.key === null) { preferences = read(); renderCatalog(); filterCatalog(); apply(); sync(); }
    });
    sync();
  });
})();
