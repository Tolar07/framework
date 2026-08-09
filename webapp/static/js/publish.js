  document.addEventListener('DOMContentLoaded', function() {
    var btn = document.querySelector('.publish-btn');
    var stamp = document.querySelector('.published-stamp');
    if (btn) {
      btn.addEventListener('click', function() {
        var d = btn.getAttribute('data-date');
        if (!d) return;
        btn.disabled = true;
        btn.textContent = 'Publishing…';
        fetch('/api/admin/publish', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({date: d})
        }).then(function(r){ return r.json(); })
          .then(function(data) {
            if (data.ok) {
              btn.style.display = 'none';
              if (stamp) stamp.style.display = 'block';
            } else {
              btn.disabled = false;
              btn.textContent = 'Approve → Publish to Client';
              alert('Publish failed: ' + (data.error || 'unknown'));
            }
          }).catch(function(e) {
            btn.disabled = false;
            btn.textContent = 'Approve → Publish to Client';
            alert('Network error: ' + e);
          });
      });
    }
  });
