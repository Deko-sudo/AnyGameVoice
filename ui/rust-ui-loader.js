import init from './rust-ui/anygamevoice_ui.js';

try {
  await init();
} catch (error) {
  console.error('Rust UI unavailable; loading the standard controls.', error);
  const fallback = document.createElement('script');
  fallback.src = '/assets/material-select.js';
  document.head.append(fallback);
}
