/* proto.js — interaction for the FEED page (render_v2, Verge pass 2026-08-12).
   Strict CSP: script-src 'self' → NO inline onclick/onkeydown anywhere; every
   binding is addEventListener.
   Interactions: copy a SportyBet booking code, the live-score badge poll, the
   density switcher (Lean/Trimmed/Full), the sticky-tab scrollspy, and the
   dial / market-bar / breakeven-strip fills (rAF, reduced-motion aware —
   motion is decor, never data-hiding). */

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

/* Feed: live-score feed — poll /api/live-scores, update scan rows in place.
   Keys are "home|away|date"; rows carry data-fixture="home|away" so a live
   score slots into the matching row's .f-live badge (kickoff -> live). */
function bindLiveScores() {
  var rows = Array.prototype.slice.call(
    document.querySelectorAll('.f-scan-row[data-fixture]'));
  if (!rows.length) return;
  function update() {
    fetch('/api/live-scores', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var scores = (data && data.scores) || {};
        rows.forEach(function (row) {
          var key = row.getAttribute('data-fixture');
          var score = null;
          Object.keys(scores).forEach(function (k) {
            if (k.indexOf(key + '|') === 0) score = scores[k];
          });
          var badge = row.querySelector('.f-live');
          if (badge) badge.textContent = score ? ('LIVE ' + score) : '';
        });
      })
      .catch(function () { /* transient — retry next tick */ });
  }
  update();
  setInterval(update, 60000);
}

/* ---- motion helpers (reduced-motion aware) ---- */
function prefersReducedMotion() {
  return window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function easeOut(t) { return 1 - Math.pow(1 - t, 3); }

/* ---- probability dials: rAF stroke-dashoffset animation ----
   The HTML already carries the final offset (no-JS shows the filled dial).
   On activation we reset to the empty offset and animate to the target. */
function dialTarget(circle) {
  var el = circle.closest('.f-dial');
  if (!el) return null;
  var prob = parseFloat(el.getAttribute('data-prob'));
  if (isNaN(prob)) return null;
  prob = Math.max(0, Math.min(1, prob));
  var c = parseFloat(circle.getAttribute('stroke-dasharray'));
  if (!c) c = 2 * Math.PI * parseFloat(circle.getAttribute('r'));
  return c * (1 - prob);
}

function fillDials(scope) {
  var circles = Array.prototype.slice.call(scope.querySelectorAll('.f-dial-fill'));
  if (!circles.length) return;
  var reduced = prefersReducedMotion();
  circles.forEach(function (c) {
    var target = dialTarget(c);
    if (target === null) return;
    var from = parseFloat(c.getAttribute('stroke-dasharray'));
    if (reduced) { c.setAttribute('stroke-dashoffset', String(target)); return; }
    c.setAttribute('stroke-dashoffset', String(from));
    var start = null;
    function step(ts) {
      if (start === null) start = ts;
      var t = Math.min(1, (ts - start) / 650);
      c.setAttribute('stroke-dashoffset', String(from + (target - from) * easeOut(t)));
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
}

/* ---- market bars + breakeven fills: width animations (rAF) ---- */
function fillBars(scope) {
  var reduced = prefersReducedMotion();
  scope.querySelectorAll('.f-mkt-fill, .f-edge-fill').forEach(function (f) {
    var target = parseFloat(f.getAttribute('data-value'));
    if (isNaN(target)) { target = parseFloat((f.getAttribute('style') || '').replace(/[^0-9.]/g, '')) || 0; }
    if (reduced) { f.style.width = target + '%'; return; }
    f.style.width = '0%';
    var start = null;
    function step(ts) {
      if (start === null) start = ts;
      var t = Math.min(1, (ts - start) / 650);
      f.style.width = (target * easeOut(t)).toFixed(2) + '%';
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
}

/* ---- density switcher (Lean / Trimmed / Full) ---- */
function activateDensity(group, view) {
  var bar = document.querySelector('.f-densitybar[data-group="' + group + '"]');
  if (!bar) return;
  bar.querySelectorAll('.f-density-pill').forEach(function (p) {
    p.classList.toggle('active', p.getAttribute('data-for') === view);
  });
  var container = bar.parentNode;
  container.querySelectorAll('.f-density-view[data-view]').forEach(function (v) {
    var on = v.getAttribute('data-view') === view;
    v.classList.toggle('active', on);
    if (on) {
      v.classList.remove('enter');
      fillDials(v);
      fillBars(v);
      void v.offsetWidth;               /* force reflow so the entrance runs */
      v.classList.add('enter');
    }
  });
}

function bindDensitySwitchers() {
  document.querySelectorAll('.f-density-pill').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var bar = btn.closest('.f-densitybar');
      if (!bar) return;
      activateDensity(bar.getAttribute('data-group'), btn.getAttribute('data-for'));
    });
  });
}

/* ---- sticky-tab scrollspy (CALL / SCAN / SINGLES) ---- */
function bindTabSpy() {
  var nav = document.querySelector('.f-tabnav');
  if (!nav || typeof IntersectionObserver === 'undefined') return;
  var pills = Array.prototype.slice.call(nav.querySelectorAll('.f-tabpill'));
  var sections = pills.map(function (p) {
    var id = p.getAttribute('href');
    return id ? document.querySelector(id) : null;
  }).filter(Boolean);
  if (!sections.length) return;
  var spy = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      pills.forEach(function (p) {
        p.classList.toggle('active',
          p.getAttribute('href') === '#' + entry.target.id);
      });
    });
  }, { rootMargin: '-45% 0px -50% 0px', threshold: 0 });
  sections.forEach(function (s) { spy.observe(s); });
}

document.addEventListener('DOMContentLoaded', function () {
  bindCopyButtons();
  bindLiveScores();
  bindDensitySwitchers();
  bindTabSpy();
  /* initial fills for whatever density is active when the page loads */
  document.querySelectorAll('.f-density-view.active').forEach(function (v) {
    fillDials(v);
    fillBars(v);
    v.classList.add('enter');
  });
});
