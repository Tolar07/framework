  function openChatTab() {
    document.getElementById('chat-tab').classList.remove('hidden');
    var fab = document.getElementById('chat-fab');
    if (fab) fab.style.display = 'none';
    document.getElementById('chat-input').focus();
  }
  function closeChatTab() {
    document.getElementById('chat-tab').classList.add('hidden');
    var fab = document.getElementById('chat-fab');
    if (fab) fab.style.display = '';
  }
  function getBoardDate() {
    var tab = document.getElementById('chat-tab');
    return tab ? (tab.getAttribute('data-date') || '') : '';
  }
  function timeNow() {
    var d = new Date();
    var h = d.getHours(), m = d.getMinutes();
    return (h < 10 ? '0' + h : h) + ':' + (m < 10 ? '0' + m : m);
  }
  function sendChatMessage() {
    var input = document.getElementById('chat-input');
    var msg = input.value.trim();
    if (!msg) return;
    appendMessage('user', msg);
    input.value = '';
    document.getElementById('chat-send').disabled = true;
    // Pending bubble — skeleton shimmer replaces the inline "thinking" text.
    var container = document.getElementById('chat-messages');
    var pending = document.createElement('div');
    pending.className = 'chat-message assistant pending';
    pending.innerHTML = '<div class="bubble"><div class="skeleton chat-bubble"></div>'
      + '<span class="msg-time">' + timeNow() + '</span></div>';
    container.appendChild(pending);
    container.scrollTop = container.scrollHeight;
    // Call the AI Analyst API
    fetch('/api/analyst', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: msg, date: getBoardDate()})
    }).then(function(r) { return r.json(); })
      .then(function(data) {
        pending.remove();
        appendMessage('assistant', data.reply || 'Error: no reply');
      }).catch(function(e) {
        pending.remove();
        appendMessage('assistant', 'Network error: ' + e);
      });
  }
  function sendQuickPrompt(prompt) {
    var input = document.getElementById('chat-input');
    input.value = prompt;
    sendChatMessage();
  }
  function appendMessage(role, text) {
    var container = document.getElementById('chat-messages');
    var div = document.createElement('div');
    div.className = 'chat-message ' + role;
    div.innerHTML = '<div class="bubble">' + escapeHtml(text)
      + '<span class="msg-time">' + timeNow() + '</span></div>';
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }
  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  document.addEventListener('DOMContentLoaded', function() {
    // Opener + close button (CSP-clean: no inline onclick).
    var fab = document.getElementById('chat-fab');
    if (fab) fab.addEventListener('click', openChatTab);
    document.querySelectorAll('.chat-close').forEach(function(btn) {
      btn.addEventListener('click', closeChatTab);
    });
    // Quick-prompt chips fill the input and send.
    document.querySelectorAll('.chat-quick-btn[data-prompt]').forEach(function(btn) {
      btn.addEventListener('click', function() {
        sendQuickPrompt(btn.getAttribute('data-prompt'));
      });
    });
    var input = document.getElementById('chat-input');
    var sendBtn = document.getElementById('chat-send');
    if (!input) return;
    input.addEventListener('input', function() {
      sendBtn.disabled = !input.value.trim();
    });
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (input.value.trim()) sendChatMessage();
      }
    });
    if (sendBtn) sendBtn.addEventListener('click', sendChatMessage);
  });
