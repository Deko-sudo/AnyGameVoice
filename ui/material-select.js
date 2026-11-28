/* Enhance studio selects while retaining the native controls as the source of truth. */
(() => {
  const controls = new Map();
  let openControl = null;
  let typed = '';
  let typeTimer;

  function position(control) {
    const rect = control.button.getBoundingClientRect();
    const margin = 12;
    const width = Math.min(Math.max(rect.width, 260), window.innerWidth - margin * 2);
    const below = window.innerHeight - rect.bottom - margin;
    const above = rect.top - margin;
    const openBelow = below >= 336 || below >= above;
    const height = Math.max(0, Math.min(336, (openBelow ? below : above) - 6));
    control.menu.style.width = `${width}px`;
    control.menu.style.maxHeight = `${height}px`;
    control.menu.style.left = `${Math.max(margin, Math.min(rect.left, window.innerWidth - width - margin))}px`;
    control.menu.style.top = `${openBelow ? rect.bottom + 6 : Math.max(margin, rect.top - height - 6)}px`;
  }

  function sync(control) {
    const {select, button, menu} = control;
    button.disabled = select.disabled;
    button.querySelector('.material-select-value').textContent = select.selectedOptions[0]?.textContent || 'Выберите значение';
    menu.replaceChildren(...Array.from(select.options, (option, index) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'material-select-option';
      item.setAttribute('role', 'option');
      item.setAttribute('aria-selected', String(option.selected));
      item.disabled = option.disabled;
      item.tabIndex = -1;
      const text = document.createElement('span');
      text.textContent = option.textContent;
      const check = document.createElement('span');
      check.className = 'material-select-check';
      check.setAttribute('aria-hidden', 'true');
      check.textContent = '✓';
      item.append(text, check);
      item.addEventListener('click', () => {
        select.selectedIndex = index;
        select.dispatchEvent(new Event('input', {bubbles: true}));
        select.dispatchEvent(new Event('change', {bubbles: true}));
        menu.hidePopover();
        button.focus();
      });
      return item;
    }));
  }

  function focusOption(control, direction) {
    const items = Array.from(control.menu.querySelectorAll('[role="option"]:not(:disabled)'));
    if (!items.length) return;
    const focused = items.indexOf(document.activeElement);
    const selected = items.findIndex(item => item.getAttribute('aria-selected') === 'true');
    let index = focused < 0 ? Math.max(0, selected) : focused;
    if (direction === 'first') index = 0;
    else if (direction === 'last') index = items.length - 1;
    else if (focused >= 0) index = (index + direction + items.length) % items.length;
    items[index].focus();
    items[index].scrollIntoView({block: 'nearest'});
  }

  function enhance(select) {
    const button = document.createElement('button');
    const menu = document.createElement('div');
    if (typeof menu.showPopover !== 'function') return;
    button.type = 'button';
    button.className = 'material-select-trigger';
    button.setAttribute('aria-label', select.labels[0]?.textContent.trim() || 'Выберите значение');
    button.setAttribute('aria-haspopup', 'listbox');
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-controls', `${select.id}-menu`);
    const value = document.createElement('span');
    value.className = 'material-select-value';
    const arrow = document.createElement('span');
    arrow.className = 'material-select-arrow';
    arrow.setAttribute('aria-hidden', 'true');
    button.append(value, arrow);
    menu.id = `${select.id}-menu`;
    menu.className = 'material-select-menu';
    menu.setAttribute('popover', 'auto');
    menu.setAttribute('role', 'listbox');
    menu.setAttribute('aria-label', button.getAttribute('aria-label'));
    select.after(button);
    document.body.append(menu);
    const control = {select, button, menu};
    controls.set(select.id, control);
    select.hidden = true;
    sync(control);
    new MutationObserver(() => sync(control)).observe(select, {childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'label']});
    function openMenu() {
      sync(control);
      position(control);
      menu.showPopover();
      position(control);
      focusOption(control, 0);
    }
    button.addEventListener('click', openMenu);
    button.addEventListener('keydown', event => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        openMenu();
      }
    });
    menu.addEventListener('toggle', event => {
      const opened = event.newState === 'open';
      button.setAttribute('aria-expanded', String(opened));
      if (opened) openControl = control;
      else if (openControl === control) openControl = null;
    });
    menu.addEventListener('keydown', event => {
      const directions = {ArrowDown: 1, ArrowUp: -1, Home: 'first', End: 'last'};
      if (event.key in directions) {
        event.preventDefault();
        focusOption(control, directions[event.key]);
      } else if (event.key === 'Escape') {
        event.preventDefault();
        menu.hidePopover();
        button.focus();
      } else if (event.key === 'Tab') {
        menu.hidePopover();
        button.focus();
      } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
        typed += event.key.toLocaleLowerCase();
        clearTimeout(typeTimer);
        typeTimer = setTimeout(() => { typed = ''; }, 700);
        const match = Array.from(menu.querySelectorAll('[role="option"]:not(:disabled)'))
          .find(item => item.textContent.trim().toLocaleLowerCase().startsWith(typed));
        if (match) {
          event.preventDefault();
          match.focus();
          match.scrollIntoView({block: 'nearest'});
        }
      }
    });
  }

  window.syncMaterialSelects = () => controls.forEach(sync);
  function init() {
    for (const id of ['dub-direction', 'dub-provider', 'dub-format']) {
      const select = document.getElementById(id);
      if (!select.hidden) enhance(select);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
  window.addEventListener('resize', () => { if (openControl) position(openControl); });
  document.addEventListener('scroll', event => {
    if (openControl && !openControl.menu.contains(event.target)) position(openControl);
  }, true);
})();
