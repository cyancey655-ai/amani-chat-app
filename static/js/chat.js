// Amani Chat room: messaging + browser voice in/out (Web Speech API — no backend needed).
(function () {
  var room = document.querySelector('.chat-room');
  if (!room) return;

  var companionId = room.dataset.companion;
  var conversationId = room.dataset.conversation || null;
  var voicePitch = parseFloat(room.dataset.pitch || '1.1');
  var voiceRate = parseFloat(room.dataset.rate || '1.0');
  var compName = room.dataset.name;
  var greeting = room.dataset.greeting;

  var messagesEl = document.getElementById('messages');
  var input = document.getElementById('msg-input');
  var sendBtn = document.getElementById('send-btn');
  var micBtn = document.getElementById('mic-btn');
  var ttsBtn = document.getElementById('tts-btn');
  var minuteNote = document.getElementById('minute-note');
  var speakReplies = false;
  var sending = false;

  function addMsg(role, text) {
    var div = document.createElement('div');
    div.className = 'msg msg-' + role;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function typing(on) {
    var t = document.getElementById('typing');
    if (on && !t) {
      t = document.createElement('div');
      t.id = 'typing';
      t.className = 'msg msg-assistant typing';
      t.textContent = compName + ' is typing...';
      messagesEl.appendChild(t);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    } else if (!on && t) {
      t.remove();
    }
  }

  function speak(text) {
    if (!speakReplies || !('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.pitch = voicePitch;
    u.rate = voiceRate;
    var voices = window.speechSynthesis.getVoices();
    var en = voices.find(function (v) { return v.lang && v.lang.toLowerCase().indexOf('en') === 0 && v.name.toLowerCase().indexOf('female') !== -1; })
      || voices.find(function (v) { return v.lang && v.lang.toLowerCase().indexOf('en') === 0; });
    if (en) u.voice = en;
    window.speechSynthesis.speak(u);
  }

  function send() {
    var text = input.value.trim();
    if (!text || sending) return;
    sending = true;
    addMsg('user', text);
    input.value = '';
    typing(true);

    fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ companion_id: companionId, conversation_id: conversationId, message: text })
    })
      .then(function (r) { return r.json().then(function (j) { return { status: r.status, body: j }; }); })
      .then(function (res) {
        typing(false);
        sending = false;
        if (res.status === 402) { window.location.href = '/pricing'; return; }
        var j = res.body;
        if (j.error) { addMsg('assistant', 'Oops — try that again?'); return; }
        conversationId = j.conversation_id;
        addMsg('assistant', j.reply);
        speak(j.reply);
        if (j.plan === 'metered' && j.minutes_used != null) {
          minuteNote.textContent = 'Minutes used: ' + j.minutes_used +
            (j.billed_minute ? ' (a new $1.00 started minute was just counted)' : '');
        }
      })
      .catch(function () {
        typing(false);
        sending = false;
        addMsg('assistant', 'Connection hiccup — try again?');
      });
  }

  sendBtn.addEventListener('click', send);
  input.addEventListener('keydown', function (e) { if (e.key === 'Enter') send(); });

  ttsBtn.addEventListener('click', function () {
    speakReplies = !speakReplies;
    ttsBtn.textContent = speakReplies ? '🔊' : '🔇';
    if (!speakReplies && 'speechSynthesis' in window) window.speechSynthesis.cancel();
    if (!('speechSynthesis' in window)) alert('Spoken replies are not supported in this browser.');
  });

  // Voice input via browser speech recognition
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    micBtn.style.opacity = '0.4';
    micBtn.title = 'Voice input not supported in this browser';
  } else {
    var rec = new SR();
    rec.interimResults = false;
    var listening = false;
    rec.onresult = function (e) {
      input.value = e.results[0][0].transcript;
      listening = false;
      micBtn.textContent = '🎤';
      send();
    };
    rec.onend = function () { listening = false; micBtn.textContent = '🎤'; };
    rec.onerror = function () { listening = false; micBtn.textContent = '🎤'; };
    micBtn.addEventListener('click', function () {
      if (listening) { rec.stop(); return; }
      listening = true;
      micBtn.textContent = '⏹';
      rec.start();
    });
  }

  // Opening: load history or show greeting
  if (conversationId) {
    fetch('/api/history/' + conversationId)
      .then(function (r) { return r.json(); })
      .then(function (j) {
        (j.messages || []).forEach(function (m) { addMsg(m.role, m.content); });
        if (!(j.messages || []).length) addMsg('assistant', greeting);
      })
      .catch(function () { addMsg('assistant', greeting); });
  } else {
    addMsg('assistant', greeting);
  }
})();
