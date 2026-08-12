/* proto.js — interaction for the FEED page (render_v2, Architect 2026-08-11).
   Strict CSP: script-src 'self' → NO inline onclick/onkeydown anywhere.
   The page is the Telegram board — the only interactions are copying a
   SportyBet booking code and the live-score badge poll. Admin bindings were
   removed with the paused admin tier (2026-08-12). */

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

/* Feed: booking-code copy pills (Acca A / splits / singles) */
function bindCopyButtons() {
  document.querySelectorAll('.f-code-pill[data-code]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      copyCode(btn.getAttribute('data-code'), btn);
    });
  });
}

/* Feed: live-score feed — poll /api/live-scores, update scan cards in place.
   Keys are "home|away|date"; cards carry data-fixture="home|away" so a live
   score slots into the matching card's .f-live badge (kickoff -> live). */
function bindLiveScores() {
  var cards = Array.prototype.slice.call(
    document.querySelectorAll('.f-scan-card[data-fixture]'));
  if (!cards.length) return;
  function update() {
    fetch('/api/live-scores', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var scores = (data && data.scores) || {};
        cards.forEach(function (card) {
          var key = card.getAttribute('data-fixture');
          var score = null;
          Object.keys(scores).forEach(function (k) {
            if (k.indexOf(key + '|') === 0) score = scores[k];
          });
          var badge = card.querySelector('.f-live');
          if (badge) badge.textContent = score ? ('LIVE ' + score) : '';
        });
      })
      .catch(function () { /* transient — retry next tick */ });
  }
  update();
  setInterval(update, 60000);
}

document.addEventListener('DOMContentLoaded', function () {
  bindCopyButtons();
  bindLiveScores();
});
