const THEME_STORAGE_KEY = 'spriteforgeTheme';

function preferredTheme() {
  const saved = localStorage.getItem(THEME_STORAGE_KEY);
  if (saved === 'light' || saved === 'dark') return saved;
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
    return 'light';
  }
  return 'dark';
}

function applyTheme(theme) {
  const isLight = theme === 'light';
  document.body.classList.toggle('theme-light', isLight);
  const button = $('#themeToggle');
  if (button) {
    button.setAttribute('aria-pressed', isLight ? 'true' : 'false');
    button.textContent = isLight ? 'Light' : 'Dark';
    button.title = isLight ? 'Switch to dark theme' : 'Switch to light theme';
  }
}

function setTheme(theme) {
  localStorage.setItem(THEME_STORAGE_KEY, theme);
  applyTheme(theme);
}

function toggleTheme() {
  const next = document.body.classList.contains('theme-light') ? 'dark' : 'light';
  setTheme(next);
  toast(next === 'light' ? 'Light theme enabled.' : 'Dark theme enabled.');
}

function installThemeToggle() {
  applyTheme(preferredTheme());
  $('#themeToggle')?.addEventListener('click', toggleTheme);
}

installThemeToggle();
