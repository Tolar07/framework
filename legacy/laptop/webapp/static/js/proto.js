/* proto.js — interaction for the FEED page (render_v2, pitch-night editorial
   pass 2026-08-12, ratified by the Architect). Strict CSP: script-src 'self'
   → NO inline onclick/onkeydown anywhere; every binding is addEventListener.
   Interactions: booking-code copy pills, the live-score badge poll, the
   density switcher (Lean/Trimmed/Full), the sticky-tab scrollspy + scroll
   CTAs, and the dial / market-bar / breakeven fills.
   Motion One (motion.js UMD → window.Motion) is loaded BEFORE this script.
   When available, animate/inView replace the CSS-transition fills with
   eased JS animations (staggered reveals, smooth dial stroke-dashoffset,
   cross-fade density views). When Motion is absent or reduced-motion is
   requested, the vanilla CSS/IO path is the fallback — every number still
   renders, motion is decor, never data-hiding. The `.js` flag on <html>
   gates the CSS entrance states so a no-JS render still shows every number. */

/* Gate the CSS entrance states (reveal/density-view) behind a JS flag — a
   no-JS page renders everything visible instead of stuck at opacity:0. */
document.documentElement.classList.add('js');

/* Motion One availability — UMD bundle loads before proto.js via <script src="/static/js/motion.js"> */
const M = window.Motion;
const hasMotion = typeof M !== 'undefined' && typeof M.animate === 'function' && typeof M.inView === 'function';

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
    if (btn) {
      btn.textContent = code + ' Copied';
      setTimeout(function () { btn.textContent = code + ' Copy'; }, 1600);
    }
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

/* Booking-code copy pills (Acca A / splits / singles / call cards) */
function bindCopyButtons() {
  document.querySelectorAll('.copy-pill[data-code]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      copyCode(btn.getAttribute('data-code'), btn);
    });
  });
}

/* Live-score feed — poll /api/live-scores, update scan rows in place.
   Keys are "home|away|date"; rows carry data-fixture="home|away" so a live
   score slots into the matching row's .f-live badge. */
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

var reduceMotion = window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ---- gauges: wire every dial to a computed circumference ---- */
function setupDials() {
  document.querySelectorAll('.dial, .single-dial').forEach(function (svg) {
    var r = parseFloat(svg.getAttribute('data-radius'));
    var value = parseFloat(svg.getAttribute('data-value'));
    if (!r || Number.isNaN(value)) return;
    var c = 2 * Math.PI * r;
    var fill = svg.querySelector('.dial-fill');
    if (!fill) return;
    fill.style.strokeDasharray = String(c);
    fill.style.strokeDashoffset = String(c);
    fill.setAttribute('data-target', String(c * (1 - value / 100)));
  });
}
function fillDials(scope) {
  scope.querySelectorAll('.dial-fill').forEach(function (fill) {
    if (fill.getAttribute('data-target') !== null) {
      var target = parseFloat(fill.getAttribute('data-target'));
      if (hasMotion && !reduceMotion) {
        // Motion One: smooth eased stroke-dashoffset from full → target
        var c = parseFloat(fill.style.strokeDasharray) || 0;
        M.animate(
          fill,
          { strokeDashoffset: [c, target] },
          { duration: 1.1, easing: [0.16, 1, 0.3, 1] }
        );
      } else {
        fill.style.strokeDashoffset = fill.getAttribute('data-target');
      }
    }
  });
}
function fillBars(scope) {
  scope.querySelectorAll('.mkt-bar-fill, .edge-fill').forEach(function (bar) {
    if (bar.getAttribute('data-value') !== null) {
      var value = parseFloat(bar.getAttribute('data-value'));
      if (hasMotion && !reduceMotion) {
        // Motion One: eased width fill from 0% → value%
        M.animate(
          bar,
          { width: ['0%', value + '%'] },
          { duration: 0.9, easing: [0.16, 1, 0.3, 1] }
        );
      } else {
        bar.style.width = bar.getAttribute('data-value') + '%';
      }
    }
  });
}
setupDials();

/* ---- scroll-triggered reveal (fills gauges/bars the first time each element is seen) ---- */
var revealEls = document.querySelectorAll('.reveal');

function initReveals() {
  if (hasMotion && !reduceMotion) {
    // Motion One: staggered inView + animate with custom easing
    revealEls.forEach(function (el, i) {
      M.inView(el, function () {
        M.animate(
          el,
          { opacity: [0, 1], transform: ['translateY(14px)', 'none'] },
          { duration: 0.6, easing: [0.16, 1, 0.3, 1] }
        );
        // Fill gauges/bars inside this revealed element
        fillDials(el);
        fillBars(el);
      }, { once: true, margin: '0px 0px -15%' });
    });
  } else {
    // Vanilla fallback: IntersectionObserver + CSS .show class
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('show');
          fillDials(e.target);
          fillBars(e.target);
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.15 });
    revealEls.forEach(function (el) { io.observe(el); });
  }
}
initReveals();

/* ---- density switcher: cross-fade + animate gauges/bars on entry ---- */
document.querySelectorAll('.densitybar').forEach(function (bar) {
  bar.addEventListener('click', function (e) {
    var btn = e.target.closest('.density-pill');
    if (!btn) return;
    var section = bar.closest('.section');
    var density = btn.getAttribute('data-density');
    section.querySelectorAll('.density-pill').forEach(function (p) {
      p.classList.toggle('on', p === btn);
    });
    section.querySelectorAll('.density-view').forEach(function (v) {
      if (v.getAttribute('data-for') === density) {
        v.classList.add('active');
        if (hasMotion && !reduceMotion) {
          // Motion One cross-fade: animate opacity + transform
          M.animate(
            v,
            { opacity: [0, 1], transform: ['translateY(8px)', 'none'] },
            { duration: 0.35, easing: 'ease-out' }
          );
        } else {
          // Vanilla: double rAF to trigger CSS transition
          v.classList.remove('in');
          requestAnimationFrame(function () {
            requestAnimationFrame(function () {
              v.classList.add('in');
            });
          });
        }
        // Fill gauges/bars in the newly-shown view
        fillDials(v);
        fillBars(v);
        // Animate reveals inside the new view if using Motion One
        if (hasMotion && !reduceMotion) {
          v.querySelectorAll('.reveal').forEach(function (el) {
            M.animate(
              el,
              { opacity: [0, 1], transform: ['translateY(14px)', 'none'] },
              { duration: 0.6, easing: [0.16, 1, 0.3, 1] }
            );
          });
        } else {
          v.querySelectorAll('.reveal').forEach(function (el) { el.classList.add('show'); });
        }
      } else {
        if (hasMotion && !reduceMotion) {
          M.animate(v, { opacity: [1, 0] }, { duration: 0.2, easing: 'ease-in' })
            .finished.then(function () {
              v.classList.remove('active');
              v.classList.remove('in');
            });
        } else {
          v.classList.remove('active');
          v.classList.remove('in');
        }
      }
    });
  });
});

/* the default-active views still need their gauges/bars filled once */
document.querySelectorAll('.density-view.active').forEach(function (v) {
  v.classList.add('in');
  fillDials(v);
  fillBars(v);
});

/* ---- every scroll-nav control (tabnav pills, hero CTAs) is a real button, wired directly ---- */
document.querySelectorAll('[data-scroll-target]').forEach(function (btn) {
  btn.addEventListener('click', function () {
    var target = document.getElementById(btn.getAttribute('data-scroll-target'));
    if (!target) return;
    target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
  });
});

/* ---- tabnav active state: immediate on click, corrected by scroll position afterwards ---- */
var navPills = document.querySelectorAll('.tabnav .pill');
navPills.forEach(function (p) {
  p.addEventListener('click', function () {
    navPills.forEach(function (x) { x.classList.toggle('on', x === p); });
  });
});
var trackedSections = ['top', 'the-call', 'the-scan', 'the-singles']
  .map(function (id) { return document.getElementById(id); })
  .filter(Boolean);
var spy = new IntersectionObserver(function (entries) {
  entries.forEach(function (e) {
    if (e.isIntersecting) {
      var id = e.target.id;
      navPills.forEach(function (p) {
        p.classList.toggle('on', p.getAttribute('data-scroll-target') === id);
      });
    }
  });
}, { rootMargin: '-45% 0px -50% 0px' });
trackedSections.forEach(function (s) { spy.observe(s); });

bindCopyButtons();
bindLiveScores();
