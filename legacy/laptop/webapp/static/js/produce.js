  var _produceSelected = new Set();

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
  }

  function produceSetDay(date) {
    document.getElementById('produce-date').value = date;
    document.querySelectorAll('.produce-day-chip').forEach(function(ch) {
      ch.classList.toggle('active', ch.getAttribute('data-date') === date);
    });
    produceSearch();
  }

  function produceSearch() {
    var q = document.getElementById('produce-query').value;
    var date = document.getElementById('produce-date').value || '';
    var results = document.getElementById('produce-results');
    results.innerHTML = '<div style="padding:12px;color:var(--ink-faint);">Searching fixtures for ' + escapeHtml(date || 'window') + '…</div>';
    var params = 'days=4';
    if (date) params += '&date=' + encodeURIComponent(date);
    if (q) params += '&q=' + encodeURIComponent(q);
    fetch('/api/admin/fixtures?' + params)
      .then(function(r) {
        return r.json();
      })
      .then(function(data) {
        if (!data || !data.ok) {
          results.innerHTML = '<div style="padding:12px;color:var(--coral);">Error: ' + escapeHtml(data ? data.error : 'failed') + '</div>';
          return;
        }
        var html = '';
        if (!data.leagues.length) {
          html = '<div style="padding:12px;color:var(--ink-faint);">No fixtures found for ' + escapeHtml(date || 'this window') + '</div>';
        } else {
          html += '<div class="produce-results-header">';
          html += '<button type="button" class="btn-secondary produce-select-all">✓ Select All</button>';
          html += '<button type="button" class="btn-secondary produce-clear-all">✗ Clear All</button>';
          html += '<span class="produce-count-display">0 selected</span>';
          html += '</div>';
          data.leagues.forEach(function(lg) {
            html += '<div class="produce-league-group">';
            html += '<div class="produce-league-header">';
            html += '<span class="produce-league-name">' + escapeHtml(lg.name) + ' (' + lg.fixtures.length + ')</span>';
            html += '<button type="button" class="btn-secondary produce-league-select-all" data-league="' + escapeHtml(lg.name) + '">✓ All</button>';
            html += '<button type="button" class="btn-secondary produce-league-clear" data-league="' + escapeHtml(lg.name) + '">✗ None</button>';
            html += '</div>';
            lg.fixtures.forEach(function(f) {
              var key = lg.name + '|' + f.home + '|' + f.away + '|' + f.date;
              var checked = _produceSelected.has(key) ? ' checked' : '';
              html += '<label class="produce-item">';
              html += '<input type="checkbox" data-key="' + escapeHtml(key) + '" data-league="' + escapeHtml(lg.name) + '" data-home="' + escapeHtml(f.home) + '" data-away="' + escapeHtml(f.away) + '" data-date="' + escapeHtml(f.date) + '"' + checked + '>';
              html += '<span class="produce-item-text">' + escapeHtml(f.home) + ' vs ' + escapeHtml(f.away) + '</span>';
              html += '<span class="produce-item-meta">' + escapeHtml(f.date || '') + '</span>';
              html += '</label>';
            });
            html += '</div>';
          });
        }
        results.innerHTML = html;
        results.querySelectorAll('input[type=checkbox]').forEach(function(cb) {
          cb.addEventListener('change', function() {
            if (cb.checked) _produceSelected.add(cb.dataset.key);
            else _produceSelected.delete(cb.dataset.key);
            updateProduceTray();
          });
          if (_produceSelected.has(cb.dataset.key)) cb.checked = true;
        });
        updateProduceTray();
      }).catch(function(e) {
        results.innerHTML = '<div style="padding:12px;color:var(--coral);">Network error: ' + escapeHtml(e) + '</div>';
      });
  }

  function produceSelectAll(select) {
    var results = document.getElementById('produce-results');
    results.querySelectorAll('input[type=checkbox]').forEach(function(cb) {
      cb.checked = select;
      if (select) _produceSelected.add(cb.dataset.key);
      else _produceSelected.delete(cb.dataset.key);
    });
    updateProduceTray();
  }

  function produceSelectLeague(btn, select) {
    var league = btn.dataset.league;
    var results = document.getElementById('produce-results');
    results.querySelectorAll('input[type=checkbox][data-league="' + league + '"]').forEach(function(cb) {
      cb.checked = select;
      if (select) _produceSelected.add(cb.dataset.key);
      else _produceSelected.delete(cb.dataset.key);
    });
    updateProduceTray();
  }

  function updateProduceTray() {
    var tray = document.getElementById('produce-tray');
    var count = document.getElementById('produce-count');
    var go = document.getElementById('produce-go');
    if (!tray) return;
    tray.style.display = _produceSelected.size > 0 ? 'flex' : 'none';
    count.textContent = _produceSelected.size + ' selected';
    go.disabled = _produceSelected.size === 0;
    // Also update the count display in the results header (Sprint 3.4: pop on
    // change — restart the animation by toggling the class off/on).
    var countDisplay = document.querySelector('.produce-count-display');
    if (countDisplay) {
      countDisplay.textContent = _produceSelected.size + ' selected';
      countDisplay.classList.remove('pop');
      void countDisplay.offsetWidth; // reflow so the animation restarts
      countDisplay.classList.add('pop');
    }
  }

  function produceClear() {
    _produceSelected.clear();
    var results = document.getElementById('produce-results');
    if (results) results.querySelectorAll('input[type=checkbox]').forEach(function(cb) { cb.checked = false; });
    updateProduceTray();
  }

  function produceGo() {
    if (_produceSelected.size === 0) return;
    var go = document.getElementById('produce-go');
    var output = document.getElementById('produce-output');
    go.disabled = true;
    go.textContent = 'Producing…';
    output.innerHTML = '<div class="produce-skeleton">'
      + '<div class="skeleton card"><div class="skeleton line" style="width:55%;"></div>'
      + '<div class="skeleton line" style="width:80%;"></div><div class="skeleton line" style="width:40%;"></div></div>'
      + '<div class="skeleton card"><div class="skeleton line" style="width:45%;"></div>'
      + '<div class="skeleton line" style="width:70%;"></div><div class="skeleton line" style="width:60%;"></div></div>'
      + '</div>';
    var groups = {};
    _produceSelected.forEach(function(key) {
      var parts = key.split('|');
      var league = parts[0], home = parts[1], away = parts[2], date = parts[3];
      if (!groups[league]) groups[league] = [];
      groups[league].push({home: home, away: away, date: date});
    });
    var groupsArr = Object.keys(groups).map(function(lg) {
      return {league: lg, fixtures: groups[lg]};
    });
    fetch('/api/admin/produce', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({groups: groupsArr})
    }).then(function(r) {
      if (r.status === 401) { window.location.href = '/admin'; return null; }
      return r.json();
    }).then(function(data) {
      go.disabled = false;
      go.textContent = '\\u26a1 Produce predictions';
      if (!data || !data.ok) {
        output.innerHTML = '<div style="padding:16px;color:var(--coral);">Error: ' + escapeHtml(data ? data.error : 'failed') + '</div>';
        return;
      }
      var html = '<div class="produce-result">';
      html += '<div class="produce-result-header">';
      html += '<span>' + data.n_rated + ' rated \\u00b7 ' + data.n_deploy + ' deploy-eligible \\u00b7 ' + data.elapsed_s + 's</span>';
      html += '<span class="phase mono" style="margin-left:auto;">' + escapeHtml(data.phase || '') + '</span>';
      html += '</div>';
      if (data.flags && data.flags.length) {
        html += '<div class="produce-flags">';
        data.flags.forEach(function(f) { html += '<div class="flag-line"><span class="mk">\\u26a0</span> ' + escapeHtml(f) + '</div>'; });
        html += '</div>';
      }
      html += '<div class="produce-cards">' + data.cards_html + '</div>';
      if (data.summary_html) html += data.summary_html;
      html += '</div>';
      output.innerHTML = html;
      output.querySelectorAll('.call-card').forEach(function(card) {
        card.addEventListener('click', function() { card.classList.toggle('open'); });
      });
    }).catch(function(e) {
      go.disabled = false;
      go.textContent = '\\u26a1 Produce predictions';
      output.innerHTML = '<div style="padding:16px;color:var(--coral);">Network error: ' + escapeHtml(e) + '</div>';
    });
  }

  document.addEventListener('DOMContentLoaded', function() {
    var dateInput = document.getElementById('produce-date');
    if (!dateInput) return;
    // Mark the day chip that matches the default (today)
    document.querySelectorAll('.produce-day-chip').forEach(function(ch) {
      ch.classList.toggle('active', ch.getAttribute('data-date') === dateInput.value);
    });
    // A manual date-picker change triggers the same search
    dateInput.addEventListener('change', function() {
      document.querySelectorAll('.produce-day-chip').forEach(function(ch) {
        ch.classList.toggle('active', ch.getAttribute('data-date') === dateInput.value);
      });
      produceSearch();
    });
    // Static panel buttons (CSP-clean: no inline onclick).
    var searchBtn = document.getElementById('produce-search-btn');
    var go = document.getElementById('produce-go');
    var clear = document.getElementById('produce-clear');
    if (searchBtn) searchBtn.addEventListener('click', produceSearch);
    if (go) go.addEventListener('click', produceGo);
    if (clear) clear.addEventListener('click', produceClear);
    document.querySelectorAll('.produce-day-chip').forEach(function(ch) {
      ch.addEventListener('click', function() { produceSetDay(ch.getAttribute('data-date')); });
    });
    // Delegation for the dynamically-rendered results (Select/Clear All +
    // per-league All/None) — re-created on every search, so bind once on the
    // container and dispatch by class.
    var results = document.getElementById('produce-results');
    if (results) {
      results.addEventListener('click', function(e) {
        var t = e.target;
        if (t.classList && t.classList.contains('produce-select-all')) { produceSelectAll(true); }
        else if (t.classList && t.classList.contains('produce-clear-all')) { produceSelectAll(false); }
        else if (t.classList && t.classList.contains('produce-league-select-all')) { produceSelectLeague(t, true); }
        else if (t.classList && t.classList.contains('produce-league-clear')) { produceSelectLeague(t, false); }
      });
    }
  });
