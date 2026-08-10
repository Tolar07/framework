// Dark / Light theme toggle — OLP XDV
// Toggles data-theme attribute on <html>, persists to localStorage
// Respects prefers-color-scheme on first load

(function() {
  var toggle = document.getElementById('theme-toggle');
  if (!toggle) return;

  var html = document.documentElement;

  // Get saved preference or detect from system
  function getInitialTheme() {
    var saved = localStorage.getItem('olp-theme');
    if (saved === 'dark' || saved === 'light') {
      return saved;
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  // Apply theme to document
  function applyTheme(theme) {
    html.setAttribute('data-theme', theme);
    toggle.setAttribute('aria-pressed', theme === 'dark');
    localStorage.setItem('olp-theme', theme);
  }

  // Initialize
  var initial = getInitialTheme();
  applyTheme(initial);

  // Toggle handler
  toggle.addEventListener('click', function() {
    var current = html.getAttribute('data-theme') || 'dark';
    var next = current === 'dark' ? 'light' : 'dark';
    applyTheme(next);
  });

  // Listen for system preference changes (if user hasn't manually set)
  var mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  mediaQuery.addEventListener('change', function(e) {
    if (!localStorage.getItem('olp-theme')) {
      applyTheme(e.matches ? 'dark' : 'light');
    }
  });

  // Keyboard support: Space/Enter to toggle
  toggle.addEventListener('keydown', function(e) {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      toggle.click();
    }
  });
})();