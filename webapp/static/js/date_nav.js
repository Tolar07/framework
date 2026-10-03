/* date_nav.js — the board-date picker: jumping to a chosen date. The base URL
   (dashboard vs admin) is carried on the input as data-base, so no inline JS
   is needed. Loaded on every page (html_shell); a no-op if no picker exists. */
document.addEventListener('DOMContentLoaded', function () {
  'use strict';
  var input = document.querySelector('.date-nav-input');
  if (!input) return;
  input.addEventListener('change', function () {
    if (input.value) {
      window.location.href = input.getAttribute('data-base') + '/' + input.value;
    }
  });
});
