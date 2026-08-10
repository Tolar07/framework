/* proto.js — interaction for the NEW OLP XDV design (render_v2).
   Strict CSP: script-src 'self' → NO inline onclick/onkeydown anywhere.
   Every control is bound here via addEventListener in DOMContentLoaded. */

function showToast(msg, ms) {
  var t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(window._olpToastTimer);
  window._olpToastTimer = setTimeout(function () { t.classList.remove('show'); }, ms || 2800);
}

function copyCode(code, btn) {
  function done() {
    showToast('Copied: ' + code + ' — paste into SportyBet to load selections');
    if (btn) btn.textContent = 'Copied';
  }
  function fallback() {
    var ta = document.createElement('textarea');
    ta.value = code;
    ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); done(); } catch (e) { showToast('Copy failed — code: ' + code); }
    document.body.removeChild(ta);
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(code).then(done, fallback);
  } else { fallback(); }
}

/* Client: bottom tabs */
function bindClientTabs() {
  document.querySelectorAll('.c-tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      var name = tab.getAttribute('data-panel');
      document.querySelectorAll('.c-tab').forEach(function (t) { t.classList.remove('active'); });
      document.querySelectorAll('.c-panel').forEach(function (p) { p.classList.remove('active'); });
      tab.classList.add('active');
      var panel = document.getElementById('panel-' + name);
      if (panel) panel.classList.add('active');
    });
  });
}

/* Client: card detail expand/collapse (Call + Scan rows) */
function bindCardDetail() {
  document.querySelectorAll('.c-card-top').forEach(function (top) {
    top.addEventListener('click', function () {
      var id = top.getAttribute('data-detail');
      var detail = id ? document.getElementById(id) : null;
      if (detail) {
        detail.classList.toggle('open');
        top.setAttribute('aria-expanded', detail.classList.contains('open') ? 'true' : 'false');
      }
    });
    top.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();
      top.click();
    });
  });
}

/* Client: league group collapse */
function bindLeagueGroups() {
  document.querySelectorAll('.c-league-head').forEach(function (head) {
    head.addEventListener('click', function () {
      var body = head.parentElement ? head.parentElement.querySelector('.c-league-body') : null;
      head.classList.toggle('open');
      if (body) body.classList.toggle('open');
      head.setAttribute('aria-expanded', head.classList.contains('open') ? 'true' : 'false');
    });
    head.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();
      head.click();
    });
  });
}

/* Client: scan search filter */
function bindScanSearch() {
  var input = document.getElementById('scan-search');
  if (!input) return;
  var empty = document.getElementById('scan-empty');
  var termEl = document.getElementById('scan-empty-term');
  input.addEventListener('input', function () {
    var term = input.value.toLowerCase();
    var any = false;
    document.querySelectorAll('.scan-row').forEach(function (row) {
      var hay = (row.getAttribute('data-search') || '').toLowerCase();
      var match = hay.indexOf(term) !== -1;
      row.style.display = match ? '' : 'none';
      if (match) any = true;
    });
    if (empty) empty.style.display = (term && !any) ? 'block' : 'none';
    if (termEl) termEl.textContent = input.value;
  });
}

/* Client: booking code copy buttons */
function bindCopyButtons() {
  document.querySelectorAll('.c-bookcode button[data-code]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      copyCode(btn.getAttribute('data-code'), btn);
    });
  });
}

/* Admin: search filter on the dense table */
function bindAdminSearch() {
  var input = document.getElementById('admin-search');
  if (!input) return;
  input.addEventListener('input', function () {
    var term = input.value.toLowerCase();
    document.querySelectorAll('#admin-tbody tr[data-search]').forEach(function (row) {
      var hay = (row.getAttribute('data-search') || '').toLowerCase();
      var hide = term && hay.indexOf(term) === -1;
      row.classList.toggle('hidden', hide);
      if (!hide) {
        /* also reveal any parent detail rows */
        if (row.classList.contains('hidden')) row.classList.remove('hidden');
      }
    });
    /* hide league separators with no visible rows */
    document.querySelectorAll('#admin-tbody .a-league-sep').forEach(function (sep) {
      var league = sep.getAttribute('data-league');
      var any = false;
      document.querySelectorAll('#admin-tbody tr[data-league="' + league + '"]').forEach(function (r) {
        if (!r.classList.contains('hidden')) any = true;
      });
      sep.classList.toggle('hidden', !any);
    });
  });
}

/* Admin: league filter chips */
function bindFilterChips() {
  document.querySelectorAll('.a-chip').forEach(function (chip) {
    chip.addEventListener('click', function () {
      var league = chip.getAttribute('data-league');
      document.querySelectorAll('.a-filterbar .a-chip').forEach(function (c) {
        c.classList.toggle('active', c === chip);
      });
      document.querySelectorAll('#admin-tbody tr').forEach(function (row) {
        if (!row.getAttribute('data-league')) return; /* detail rows follow their parent */
        var show = league === 'all' || row.getAttribute('data-league') === league;
        row.classList.toggle('hidden', !show);
      });
    });
    chip.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();
      chip.click();
    });
  });
}

/* Admin: dense-table row click → expand internals detail row */
function bindAdminRows() {
  document.querySelectorAll('tr.clickable[data-target]').forEach(function (row) {
    row.addEventListener('click', function () {
      var id = row.getAttribute('data-target');
      var detail = id ? document.getElementById(id) : null;
      if (detail) {
        var hidden = detail.classList.contains('hidden');
        detail.classList.toggle('hidden', !hidden);
        row.setAttribute('aria-expanded', hidden ? 'true' : 'false');
      }
    });
    row.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();
      row.click();
    });
  });
}

/* Admin: Trigger Production → POST /api/trigger-board?date= (real run) */
function bindTrigger() {
  var btn = document.getElementById('trigger-btn');
  if (!btn) return;
  var label = document.getElementById('trigger-label');
  var dateInput = document.getElementById('trigger-date');
  btn.addEventListener('click', function () {
    var dateStr = dateInput ? dateInput.value : '';
    btn.disabled = true;
    btn.classList.add('loading');
    if (label) label.textContent = 'Running…';
    showToast('Running the real production pipeline — this can take a few minutes…', 6000);
    var q = dateStr ? ('?date=' + encodeURIComponent(dateStr)) : '';
    fetch('/api/trigger-board' + q, { method: 'POST' })
      .then(function (r) { return r.json().catch(function () { return {}; }); })
      .then(function (data) {
        if (data && data.ok) {
          showToast(data.message || 'Board produced');
          setTimeout(function () { window.location.reload(); }, 900);
        } else {
          showToast((data && data.error) || 'Production failed — see server log', 5000);
        }
        btn.disabled = false;
        btn.classList.remove('loading');
        if (label) label.textContent = '▶ Trigger Production';
      })
      .catch(function (err) {
        showToast('Production failed: ' + err, 5000);
        btn.disabled = false;
        btn.classList.remove('loading');
        if (label) label.textContent = '▶ Trigger Production';
      });
  });
}

/* Admin: Approve → Publish (hard-gated server-side; show the real reason) */
function bindApprove() {
  var btn = document.getElementById('approve-btn');
  if (!btn) return;
  var status = document.getElementById('publish-status');
  var dateInput = document.getElementById('trigger-date');
  btn.addEventListener('click', function () {
    btn.disabled = true;
    btn.textContent = 'Publishing…';
    if (status) { status.textContent = ''; status.className = ''; }
    var payload = { approved_by: 'admin' };
    if (dateInput && dateInput.value) payload.date = dateInput.value;
    fetch('/api/admin/publish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        btn.disabled = false;
        if (data && data.ok) {
          btn.textContent = '✓ Published to Client';
          btn.classList.add('published');
          if (status) {
            status.textContent = 'Published ' + new Date().toLocaleTimeString() + ' — visible on client dashboard now';
            status.className = '';
          }
          showToast('Board published to client dashboard');
        } else {
          btn.textContent = 'Approve → Publish to Client';
          var msg = (data && data.error) || 'Publish blocked';
          if (status) { status.textContent = 'Blocked: ' + msg; status.className = 'err'; }
          showToast(msg, 6000);
        }
      })
      .catch(function (err) {
        btn.disabled = false;
        btn.textContent = 'Approve → Publish to Client';
        if (status) { status.textContent = 'Publish failed: ' + err; status.className = 'err'; }
      });
  });
}

/* Admin: date selector navigates to the chosen board */
function bindAdminDate() {
  var input = document.getElementById('trigger-date');
  if (!input) return;
  input.addEventListener('change', function () {
    if (input.value) window.location.href = '/admin/' + input.value;
  });
}

/* Admin: AI Analyst full chat → POST /api/analyst (REAL backend, same as the bot) */
function bindAdminChat() {
  var input = document.getElementById('admin-chat-input');
  var send = document.getElementById('admin-chat-send');
  var log = document.getElementById('admin-chatlog');
  var dateInput = document.getElementById('trigger-date');
  if (!input || !send || !log) return;
  function ask() {
    var text = input.value.trim();
    if (!text) return;
    var q = document.createElement('div');
    q.className = 'q';
    q.textContent = text;
    log.appendChild(q);
    input.value = '';
    log.scrollTop = log.scrollHeight;
    send.disabled = true;
    var waiting = document.createElement('div');
    waiting.className = 'a';
    waiting.textContent = '…';
    log.appendChild(waiting);
    log.scrollTop = log.scrollHeight;
    var payload = { message: text };
    if (dateInput && dateInput.value) payload.date = dateInput.value;
    fetch('/api/analyst', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        waiting.textContent = (data && data.reply) || (data && data.error) || 'No response.';
        send.disabled = false;
        log.scrollTop = log.scrollHeight;
      })
      .catch(function (err) {
        waiting.textContent = 'Analyst error: ' + err;
        send.disabled = false;
      });
  }
  send.addEventListener('click', ask);
  input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); ask(); } });
}

/* Admin: clickable stat pills */
function bindStatPills() {
  document.querySelectorAll('.a-stat[data-chip]').forEach(function (pill) {
    pill.addEventListener('click', function () {
      var league = pill.getAttribute('data-chip');
      var chip = document.querySelector('.a-chip[data-league="' + league + '"]');
      if (chip) chip.click();
      else showToast('No filter for that group', 2000);
    });
  });
}

/* Admin: error/rejection log expand/collapse */
function bindLogToggle() {
  var head = document.getElementById('log-toggle');
  var body = document.getElementById('log-body');
  if (!head || !body) return;
  head.addEventListener('click', function () {
    body.classList.toggle('hidden');
    head.setAttribute('aria-expanded', !body.classList.contains('hidden') ? 'true' : 'false');
  });
}

document.addEventListener('DOMContentLoaded', function () {
  bindClientTabs();
  bindCardDetail();
  bindLeagueGroups();
  bindScanSearch();
  bindCopyButtons();
  bindAdminSearch();
  bindFilterChips();
  bindAdminRows();
  bindTrigger();
  bindApprove();
  bindAdminDate();
  bindAdminChat();
  bindStatPills();
  bindLogToggle();
});
