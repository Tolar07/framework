  document.addEventListener('DOMContentLoaded', function() {
    var input = document.getElementById('admin-search');
    var leagueSel = document.getElementById('admin-filter-league');
    var tierSel = document.getElementById('admin-filter-tier');
    var marketSel = document.getElementById('admin-filter-market');
    var statusSel = document.getElementById('admin-filter-status');
    var allRows = document.querySelectorAll('table.scan-table tbody tr.clickable');
    var allDetail = document.querySelectorAll('table.scan-table tbody tr.detail-row');
    function filter() {
      var q = (input?.value || '').toLowerCase();
      var league = leagueSel?.value || '';
      var tier = tierSel?.value || '';
      var market = marketSel?.value || '';
      var status = statusSel?.value || '';
      allRows.forEach(function(tr, i) {
        var txt = tr.textContent.toLowerCase();
        var bf = tr.dataset;
        var ok = true;
        if (q && !txt.includes(q)) ok = false;
        if (league && bf.league !== league) ok = false;
        if (tier && bf.tier !== tier) ok = false;
        if (market && bf.market !== market) ok = false;
        if (status && bf.status !== status) ok = false;
        tr.style.display = ok ? '' : 'none';
        if (allDetail[i]) allDetail[i].style.display = ok ? '' : 'none';
      });
    }
    // Sprint 4: the free-text field is debounced (150ms) so each keystroke
    // doesn't reflow the whole table; the discrete selects filter immediately.
    function debounce(fn, ms) {
      var t;
      return function() { var args = arguments, self = this; clearTimeout(t); t = setTimeout(function() { fn.apply(self, args); }, ms); };
    }
    if (input) input.addEventListener('input', debounce(filter, 150));
    [leagueSel, tierSel, marketSel, statusSel].forEach(function(el) {
      if (el) el.addEventListener('change', filter);
    });
  });
