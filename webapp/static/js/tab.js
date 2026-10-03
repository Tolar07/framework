  // WAI-ARIA tab pattern: roving tabindex (active tab is the only one in the
  // tab order), aria-selected reflects the visible panel, and Left/Right arrow
  // keys move between tabs. The matching section gets role=tabpanel +
  // aria-labelledby on first activation.
  function switchTab(tabId) {
    // Only toggle Call/Scan/Search — flags + verified stay visible always
    var tabSections = ['call-section', 'scan-section', 'search-section'];
    tabSections.forEach(function(id) {
      var el = document.getElementById(id);
      if (el) {
        el.style.display = (id === tabId + '-section') ? 'block' : 'none';
        if (id === tabId + '-section') {
          el.setAttribute('role', 'tabpanel');
          el.setAttribute('aria-labelledby', 'tab-' + tabId);
        }
      }
    });
    // Update tab buttons: selected state + roving tabindex
    document.querySelectorAll('.tab-btn').forEach(function(btn) {
      var isActive = btn.dataset.tab === tabId;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
      btn.setAttribute('tabindex', isActive ? '0' : '-1');
    });
    window.scrollTo(0, 0);
  }
  function onTabKey(e) {
    var tabs = Array.prototype.slice.call(document.querySelectorAll('.tab-btn'));
    var idx = tabs.indexOf(e.currentTarget);
    if (idx === -1) return;
    var to = -1;
    if (e.key === 'ArrowRight') to = (idx + 1) % tabs.length;
    else if (e.key === 'ArrowLeft') to = (idx - 1 + tabs.length) % tabs.length;
    if (to === -1) return;
    e.preventDefault();
    tabs[to].focus();
    switchTab(tabs[to].dataset.tab);
  }
  function navTab(tabId, e) {
    if (e) e.preventDefault();
    switchTab(tabId);
    return false;
  }
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.tab-btn').forEach(function(btn) {
      btn.setAttribute('id', 'tab-' + btn.dataset.tab);
      btn.addEventListener('keydown', onTabKey);
      btn.addEventListener('click', function() { switchTab(btn.dataset.tab); });
    });
    var hash = window.location.hash.slice(1);
    if (hash && ['call', 'scan', 'search'].includes(hash)) {
      switchTab(hash);
    }
  });
  window.addEventListener('hashchange', function() {
    var h = location.hash.slice(1);
    if (['call','scan','search'].includes(h)) switchTab(h);
  });
