/**
 * olp-xdv-home-blended — Motion One enhancement layer
 *
 * Augments the existing CSS/IntersectionObserver animations in the blended
 * landing page with Motion One (`motion` package, vanilla DOM — no React):
 *   1. Staggered scroll reveals (replaces flat IO → class toggle)
 *   2. Smooth dial fill with easing (replaces CSS stroke-dashoffset transition)
 *   3. Cross-fade density-view transitions (replaces display:none + opacity CSS)
 *   4. Tab scroll spy with smooth motion (extends existing scrollIntoView)
 *
 * DESIGN PRINCIPLE: motion is decor, never data-hiding (honest-edge).
 * Every animation here is a visual flourish on content that is ALREADY visible
 * — no data is revealed, hidden, or transformed by these animations. The
 * `prefers-reduced-motion` check at the top bails out entirely if the user
 * has motion sensitivity enabled, falling back to the page's native CSS.
 *
 * Pitch-night tokens are untouched — this layer only animates them.
 */

import { animate, inView, scroll } from 'motion';

// ---------- gate: reduced-motion users get the vanilla page as-is ----------
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
if (reduceMotion) {
  // Still fill gauges/bars once (the vanilla JS already does this, but
  // if this module replaces the inline script, we must not skip the data
  // fill — only skip the *animation* of it).
  document.addEventListener('DOMContentLoaded', () => {
    fillAllGauges(document);
  });
} else {
  document.addEventListener('DOMContentLoaded', () => {
    initReveals();
    initDialFills();
    initBarFills();
    initDensitySwitcher();
    initTabScroll();
  });
}

// ---------- gauge data-fill (no animation, pure state) ----------
function fillAllGauges(scope) {
  scope.querySelectorAll('.dial-fill').forEach((fill) => {
    if (fill.dataset.target !== undefined) {
      fill.style.strokeDashoffset = fill.dataset.target;
    }
  });
  scope.querySelectorAll('.mkt-bar-fill, .edge-fill').forEach((bar) => {
    if (bar.dataset.value !== undefined) {
      bar.style.width = bar.dataset.value + '%';
    }
  });
}

// ---------- 1. staggered scroll reveals ----------
function initReveals() {
  const reveals = document.querySelectorAll('.reveal');
  reveals.forEach((el, i) => {
    inView(el, () => {
      animate(
        el,
        { opacity: [0, 1], transform: ['translateY(14px)', 'none'] },
        { duration: 0.6, easing: [0.16, 1, 0.3, 1] }
      );
    });
  });
}

// ---------- 2. dial fill animation ----------
// Each SVG dial has data-value (0-100) and data-radius.
// circumference = 2πr; we animate strokeDashoffset from full (c)
// down to the target (c * (1 - value/100)).
function initDialFills() {
  document.querySelectorAll('.dial, .single-dial').forEach((svg) => {
    const r = parseFloat(svg.dataset.radius);
    const value = parseFloat(svg.dataset.value);
    if (!r || Number.isNaN(value)) return;
    const c = 2 * Math.PI * r;
    const fill = svg.querySelector('.dial-fill');
    if (!fill) return;

    const target = c * (1 - value / 100);

    inView(svg, () => {
      animate(
        fill,
        { strokeDasharray: c, strokeDashoffset: [c, target] },
        { duration: 1.1, easing: [0.16, 1, 0.3, 1] }
      );
    });
  });
}

// ---------- 3. market bar + edge strip fill animation ----------
function initBarFills() {
  document.querySelectorAll('.mkt-bar-fill, .edge-fill').forEach((bar) => {
    const value = parseFloat(bar.dataset.value);
    if (Number.isNaN(value)) return;

    inView(bar, () => {
      animate(
        bar,
        { width: ['0%', value + '%'] },
        { duration: 0.9, easing: [0.16, 1, 0.3, 1] }
      );
    });
  });
}

// ---------- 4. density-view cross-fade transitions ----------
function initDensitySwitcher() {
  document.querySelectorAll('.densitybar').forEach((bar) => {
    bar.addEventListener('click', (e) => {
      const btn = e.target.closest('.density-pill');
      if (!btn) return;
      const section = bar.closest('.section');
      const density = btn.dataset.density;

      // toggle pill active state
      section.querySelectorAll('.density-pill').forEach((p) =>
        p.classList.toggle('on', p === btn)
      );

      // cross-fade views
      section.querySelectorAll('.density-view').forEach((v) => {
        if (v.dataset.for === density) {
          v.classList.add('active');
          // animate in: fade + slight rise
          animate(
            v,
            { opacity: [0, 1], transform: ['translateY(8px)', 'none'] },
            { duration: 0.35, easing: 'ease-out' }
          );
          // fill gauges/bars in the newly-shown view
          requestAnimationFrame(() => {
            fillAllGauges(v);
            // animate the dials/bars that just appeared
            v.querySelectorAll('.dial-fill').forEach((fill) => {
              if (fill.dataset.target !== undefined) {
                const c = parseFloat(fill.style.strokeDasharray) || 0;
                animate(
                  fill,
                  { strokeDashoffset: [c, parseFloat(fill.dataset.target)] },
                  { duration: 1.1, easing: [0.16, 1, 0.3, 1] }
                );
              }
            });
            v.querySelectorAll('.mkt-bar-fill, .edge-fill').forEach((bar) => {
              const value = parseFloat(bar.dataset.value);
              if (!Number.isNaN(value)) {
                animate(
                  bar,
                  { width: ['0%', value + '%'] },
                  { duration: 0.9, easing: [0.16, 1, 0.3, 1] }
                );
              }
            });
            v.querySelectorAll('.reveal').forEach((el) => {
              animate(
                el,
                { opacity: [0, 1], transform: ['translateY(14px)', 'none'] },
                { duration: 0.6, easing: [0.16, 1, 0.3, 1] }
              );
            });
          });
        } else {
          // fade out then hide
          animate(
            v,
            { opacity: [1, 0] },
            { duration: 0.2, easing: 'ease-in' }
          ).finished.then(() => {
            v.classList.remove('active');
            v.classList.remove('in');
          });
        }
      });
    });
  });

  // the default-active view on load still needs its gauges/bars filled
  document.querySelectorAll('.density-view.active').forEach((v) => {
    v.classList.add('in');
    fillAllGauges(v);
  });
}

// ---------- 5. tab scroll: smooth motion + active-state spy ----------
function initTabScroll() {
  const scrollButtons = document.querySelectorAll('[data-scroll-target]');
  scrollButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = document.getElementById(btn.dataset.scrollTarget);
      if (!target) return;
      // Motion One doesn't have a scrollIntoView equivalent, so we use
      // a custom smooth scroll with scroll() — but the native smooth
      // scroll is already good. We keep native scrollIntoView and let
      // the scroll spy observer handle the active state.
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  // tabnav active state: immediate on click, corrected by scroll position
  const navPills = document.querySelectorAll('.tabnav .pill');
  navPills.forEach((p) => {
    p.addEventListener('click', () =>
      navPills.forEach((x) => x.classList.toggle('on', x === p))
    );
  });

  const trackedSections = ['top', 'the-call', 'the-scan', 'the-singles']
    .map((id) => document.getElementById(id))
    .filter(Boolean);

  const spy = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          const id = e.target.id;
          navPills.forEach((p) =>
            p.classList.toggle('on', p.dataset.scrollTarget === id)
          );
        }
      });
    },
    { rootMargin: '-45% 0px -50% 0px' }
  );
  trackedSections.forEach((s) => spy.observe(s));
}
