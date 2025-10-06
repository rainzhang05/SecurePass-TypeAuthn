(function () {
  const startBtn = document.getElementById('startAuth');
  const userSelect = document.getElementById('authUserId');
  const container = document.getElementById('challengeContainer');
  const challengeText = document.getElementById('challengeText');
  const challengeChars = document.getElementById('challengeChars');
  const textarea = document.getElementById('authArea');
  const status = document.getElementById('authStatus');
  const totpSection = document.getElementById('totp');
  const totpCode = document.getElementById('totpCode');
  const backHome = document.getElementById('authBackHome');

  let events = [];
  let challengePhrase = '';
  let captureActive = false;
  let sessionActive = false;

  textarea.disabled = true;

  function sanitizeKey(event) {
    if (event.key === 'Unidentified') {
      return event.code || 'Unknown';
    }
    return event.key;
  }

  function renderChallengeCharacters(text) {
    challengeChars.innerHTML = '';
    text.split('').forEach((char, index) => {
      const span = document.createElement('span');
      span.dataset.index = String(index);
      span.textContent = char === ' ' ? '␣' : char;
      challengeChars.appendChild(span);
    });
    if (!text.length) {
      challengeChars.classList.add('hidden');
    } else {
      challengeChars.classList.remove('hidden');
    }
  }

  function updateChallengeHighlights(typed) {
    const spans = challengeChars.querySelectorAll('span');
    spans.forEach((span, index) => {
      span.classList.remove('correct', 'incorrect', 'active');
      if (index < typed.length) {
        if (typed[index] === challengePhrase[index]) {
          span.classList.add('correct');
        } else {
          span.classList.add('incorrect');
        }
      } else if (index === typed.length) {
        span.classList.add('active');
      }
    });
  }

  function handleTypingInput() {
    if (!sessionActive) {
      return;
    }
    if (textarea.value.length > challengePhrase.length) {
      textarea.value = textarea.value.slice(0, challengePhrase.length);
    }
    if (!captureActive && textarea.value.length > 0) {
      captureActive = true;
      status.textContent = 'Authentication capture started...';
    }
    updateChallengeHighlights(textarea.value);
  }

  async function loadUsers() {
    try {
      const payload = await window.SecurePassAPI.get('/users');
      const users = payload.users || [];
      userSelect.innerHTML = '';
      if (!users.length) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No saved profiles';
        userSelect.appendChild(option);
        userSelect.disabled = true;
        startBtn.disabled = true;
        status.textContent = 'Enroll a profile to begin authentication.';
        return;
      }
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = 'Select a saved ID';
      placeholder.disabled = true;
      placeholder.selected = true;
      userSelect.appendChild(placeholder);
      users.forEach((userId) => {
        const option = document.createElement('option');
        option.value = userId;
        option.textContent = userId;
        userSelect.appendChild(option);
      });
      userSelect.disabled = false;
      startBtn.disabled = false;
      status.textContent = '';
    } catch (err) {
      status.textContent = `Unable to load saved IDs: ${err.message}`;
      userSelect.disabled = true;
      startBtn.disabled = true;
    }
  }

  async function submitAttempt() {
    if (!textarea.value.length) {
      status.textContent = 'Type the challenge phrase.';
      return;
    }
    if (textarea.value !== challengePhrase) {
      status.textContent = 'Please match the challenge exactly before submitting.';
      updateChallengeHighlights(textarea.value);
      return;
    }
    textarea.disabled = true;
    try {
      status.textContent = 'Authenticating...';
      const response = await window.SecurePassAPI.post('/auth/submit', {
        user_id: userSelect.value,
        events
      });
      if (response.result.accepted) {
        status.textContent = `Verified ✅ (score ${response.result.score.toFixed(3)})`;
        await revealTotp(response.auth_token);
      } else {
        status.textContent = `Denied ❌ (score ${response.result.score.toFixed(3)})`;
        totpSection.classList.add('hidden');
      }
    } catch (err) {
      status.textContent = err.message;
      totpSection.classList.add('hidden');
    } finally {
      events = [];
      textarea.value = '';
      updateChallengeHighlights('');
      textarea.disabled = false;
      textarea.focus();
      captureActive = false;
      sessionActive = false;
      userSelect.disabled = false;
      startBtn.disabled = false;
    }
  }

  async function revealTotp(token) {
    if (!token) {
      return;
    }
    try {
      const payload = await window.SecurePassAPI.post('/totp/reveal', {
        user_id: userSelect.value,
        auth_token: token
      });
      totpSection.classList.remove('hidden');
      totpCode.textContent = payload.code;
    } catch (err) {
      status.textContent = `2FA retrieval failed: ${err.message}`;
    }
  }

  function attachListeners() {
    textarea.addEventListener('keydown', async (ev) => {
      if (ev.key === 'Enter' && !ev.shiftKey) {
        ev.preventDefault();
        await submitAttempt();
        return;
      }
      events.push({ key: sanitizeKey(ev), event: 'keydown', ts: performance.now() });
    });

    textarea.addEventListener('keyup', (ev) => {
      events.push({ key: sanitizeKey(ev), event: 'keyup', ts: performance.now() });
    });

    textarea.addEventListener('input', handleTypingInput);
    ['paste', 'copy', 'cut', 'contextmenu'].forEach((type) => {
      textarea.addEventListener(type, (ev) => ev.preventDefault());
    });

    if (backHome) {
      backHome.addEventListener('click', () => {
        window.location.href = '/';
      });
    }
  }

  startBtn.addEventListener('click', async () => {
    const userId = userSelect.value;
    if (!userId) {
      status.textContent = 'Select a saved ID first.';
      return;
    }
    startBtn.disabled = true;
    userSelect.disabled = true;
    try {
      const payload = await window.SecurePassAPI.post('/auth/start', { user_id: userId });
      challengePhrase = payload.challenge;
      challengeText.textContent = challengePhrase;
      renderChallengeCharacters(challengePhrase);
      updateChallengeHighlights('');
      textarea.value = '';
      textarea.disabled = false;
      textarea.focus();
      container.classList.remove('hidden');
      totpSection.classList.add('hidden');
      status.textContent = 'Type the phrase and press Enter.';
      events = [];
      captureActive = false;
      sessionActive = true;
    } catch (err) {
      status.textContent = err.message;
      userSelect.disabled = false;
      startBtn.disabled = false;
    }
  });

  loadUsers();
  attachListeners();
})();
