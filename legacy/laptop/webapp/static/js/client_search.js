  // Client Search tab — live filter over the scan table in #search-section.
  // Works on the trimmed payload only (team/league text already on the page),
  // so the data-leak boundary (no model internals) is untouched.
  document.addEventListener('DOMContentLoaded', function() {
    var input = document.getElementById('client-search');
    if (!input) return;
    var leagueSel = document.getElementById('client-filter-league');
    var groups = document.querySelectorAll('#search-section table.scan-table tbody.league-group');
    var summary = document.getElementById('client-search-summary');
    function filter() {
      var q = (input.value || '').toLowerCase();
      var league = leagueSel.value || '';
      var shown = 0;
      groups.forEach(function(tb) {
        var any = false;
        var lastOk = true;
        tb.querySelectorAll('tr').forEach(function(tr) {
          if (tr.classList.contains('league-row')) {
            var txt = tr.textContent.toLowerCase();
            var ok = true;
            if (q && !txt.includes(q)) ok = false;
            if (league && tr.dataset.league !== league) ok = false;
            tr.style.display = ok ? '' : 'none';
            if (ok) any = true;
            lastOk = ok;
          } else if (tr.classList.contains('detail-row')) {
            // A detail row always immediately follows its fixture row
            tr.style.display = lastOk ? '' : 'none';
          }
        });
        tb.style.display = any ? '' : 'none';
        if (any) shown++;
      });
      if (summary) {
        summary.innerHTML = shown
          ? '<div class="flag-line">' + shown + ' league' + (shown === 1 ? '' : 's') + ' match your search.</div>'
          : '<div class="flag-line">No fixtures match — try another team or league.</div>';
      }
    }
    // Sprint 4: debounce keystrokes (150ms) so a fast typist doesn't run the
    // filter for every char — reflow cost is O(board), the page stays responsive.
    function debounce(fn, ms) {
      var t;
      return function() { var args = arguments, self = this; clearTimeout(t); t = setTimeout(function() { fn.apply(self, args); }, ms); };
    }
    input.addEventListener('input', debounce(filter, 150));
    if (leagueSel) leagueSel.addEventListener('change', filter);

    // Live scores polling for produced bet block
    function fetchLiveScores() {
      var scoreEls = document.querySelectorAll('.live-score[data-fixture]');
      if (!scoreEls.length) return;
      // Collect unique leagues from the fixture elements
      var leagues = new Set();
      scoreEls.forEach(function(el) {
        var text = el.closest('.graded-row').textContent;
        var match = text.match(/\\(([^)]+)\\)$/);
        if (match) leagues.add(match[1]);
      });
      if (!leagues.size) return;
      fetch('/api/live-scores', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({leagues: Array.from(leagues)})
      }).then(function(r) { return r.json(); })
        .then(function(data) {
          if (!data.ok) return;
          scoreEls.forEach(function(el) {
            var fixture = el.dataset.fixture;
            var date = el.dataset.date;
            // Try multiple key formats
            var keys = [
              fixture + '|' + date,
              fixture.replace(' vs ', '|') + '|' + date,
            ];
            var score = null;
            for (var k of keys) {
              if (data.scores[k]) { score = data.scores[k]; break; }
            }
            if (score) {
              el.textContent = 'LIVE — ' + score;
              el.classList.add('has-score');
            }
          });
        }).catch(function() {});
    }
    // Poll every 30 seconds
    setInterval(fetchLiveScores, 30000);
    fetchLiveScores();
  });
