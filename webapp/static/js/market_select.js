  function toggleAllMarkets(select) {
    document.querySelectorAll('.market-checkbox input[name="market-col"]').forEach(function(cb) {
      cb.checked = select;
      toggleMarketColumn(cb.value, select);
    });
  }
  function toggleMarketColumn(key, show) {
    var isAdmin = document.querySelector('.phase.mono')?.textContent?.includes('ADMIN') || false;
    var thIndex = -1;
    var headers = document.querySelectorAll('.scan-table th');
    headers.forEach(function(th, i) {
      if (th.textContent.includes(key.replace('/', '')) || th.textContent === key) {
        thIndex = i;
      }
    });
    if (thIndex === -1) return;
    var selector = 'th:nth-child(' + (thIndex + 1) + '), td:nth-child(' + (thIndex + 1) + ')';
    document.querySelectorAll(selector).forEach(function(cell) {
      cell.style.display = show ? '' : 'none';
    });
  }
  function onMarketHeaderKey(e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault();
    toggleMarketPanel();
  }
  function toggleMarketPanel() {
    var panel = document.getElementById('market-select-panel');
    if (!panel) return;
    panel.classList.toggle('collapsed');
    var open = !panel.classList.contains('collapsed');
    var header = panel.querySelector('.market-select-header');
    if (header) header.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.market-checkbox input').forEach(function(cb) {
      cb.addEventListener('change', function() {
        toggleMarketColumn(cb.value, cb.checked);
      });
    });
    // Gear header: click or Enter/Space collapses/expands the body.
    // (CSP-clean: no inline onclick/onkeydown.)
    var header = document.querySelector('.market-select-header');
    if (header) {
      header.addEventListener('click', toggleMarketPanel);
      header.addEventListener('keydown', onMarketHeaderKey);
    }
    // Select All / Clear All dispatch on data-toggle (produce's Clear button
    // shares the class but has no data-toggle, so it is not caught here).
    document.querySelectorAll('.market-select-action[data-toggle]').forEach(function(btn) {
      btn.addEventListener('click', function() {
        toggleAllMarkets(btn.getAttribute('data-toggle') === 'all');
      });
    });
  });
