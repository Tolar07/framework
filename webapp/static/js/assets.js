/* assets.js — Sprint 4: async-load the full stylesheet + preload the
   self-hosted fonts. The URL base is read from <html data-asset-base>, set by
   html_shell ('/static' on the server, './static' in the static export).
   Keeping this in external JS (rather than an inline onload= handler) means
   the page stays CSP-clean (script-src 'self', zero inline handlers). */
(function () {
  'use strict';
  var base = document.documentElement.getAttribute('data-asset-base') || './static';
  function inject(href, isFont) {
    var link = document.createElement('link');
    link.href = base + href;
    if (isFont) {
      link.rel = 'preload';
      link.as = 'font';
      link.type = 'font/woff2';
      link.crossOrigin = 'anonymous';
    } else {
      link.rel = 'stylesheet';
    }
    document.head.appendChild(link);
  }
  inject('/css/app.css', false);
  inject('/fonts/IBM-Plex-Mono-normal-600.woff2', true);
  inject('/fonts/Inter-normal-400.woff2', true);
  inject('/fonts/Barlow-Condensed-normal-600.woff2', true);
})();
