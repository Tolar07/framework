/* signoff.js — Phase 3 Architect sign-off / revoke (admin only). External so
   the page keeps a strict CSP (no inline handlers). */
document.addEventListener('DOMContentLoaded', function () {
  'use strict';
  var btn = document.getElementById('phase3-signoff-btn');
  var revoke = document.getElementById('phase3-revoke-btn');

  function flag(msgEl, text, kind) {
    msgEl.innerHTML = '<div class="flag-line ' + (kind || '') + '">' + text + '</div>';
  }

  if (btn) {
    btn.addEventListener('click', function () {
      var name = document.getElementById('architect_name').value;
      var confirm = document.getElementById('signoff-confirm').checked;
      var msgEl = document.getElementById('phase3-signoff-msg');
      if (!name || !confirm) {
        flag(msgEl, 'Please enter your name and confirm the gate requirements.', 'error');
        return;
      }
      fetch('/api/admin/signoff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'sign_off', architect_name: name, confirm: confirm })
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok) {
            flag(msgEl, '✅ Gate signed off — capital deployment authorized. Page will reload...', 'success');
            setTimeout(function () { location.reload(); }, 1500);
          } else {
            flag(msgEl, '❌ Error: ' + (data.error || 'Unknown error'), 'error');
          }
        })
        .catch(function (err) {
          flag(msgEl, '❌ Request failed: ' + err.message, 'error');
        });
    });
  }

  if (revoke) {
    revoke.addEventListener('click', function () {
      if (!confirm('Revoke the Architect sign-off? This closes the capital gate.')) return;
      fetch('/api/admin/signoff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'revoke' })
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok) {
            alert('Sign-off revoked. Page will reload...');
            location.reload();
          } else {
            alert('Error: ' + (data.error || 'Unknown error'));
          }
        })
        .catch(function (err) { alert('Request failed: ' + err.message); });
    });
  }
});
