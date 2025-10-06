(function () {
  const startBtn = document.getElementById('startAuth');
  const userInput = document.getElementById('authUserId');
  const container = document.getElementById('challengeContainer');
  const challengeText = document.getElementById('challengeText');
  const textarea = document.getElementById('authArea');
  const status = document.getElementById('authStatus');
  const totpSection = document.getElementById('totp');
  const totpCode = document.getElementById('totpCode');

  let events = [];
  let challengePhrase = '';

  function sanitizeKey(event) {
    if (event.key === 'Unidentified') {
      return event.code || 'Unknown';
    }
    return event.key;
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

    ['paste', 'copy', 'cut', 'contextmenu'].forEach((type) => {
      textarea.addEventListener(type, (ev) => ev.preventDefault());
    });
  }

  async function submitAttempt() {
    if (!textarea.value.trim()) {
      status.textContent = 'Type the challenge phrase.';
      return;
    }
    try {
      status.textContent = 'Authenticating...';
      const response = await window.SecurePassAPI.post('/auth/submit', {
        user_id: userInput.value.trim(),
        events
      });
      if (response.result.accepted) {
        status.textContent = `Verified ✅ (score ${response.result.score.toFixed(3)})`;
        await revealTotp(response.auth_token);
      } else {
        status.textContent = `Denied ❌ (score ${response.result.score.toFixed(3)})`;
      }
    } catch (err) {
      status.textContent = err.message;
    } finally {
      events = [];
      textarea.value = '';
    }
  }

  async function revealTotp(token) {
    if (!token) {
      return;
    }
    try {
      const payload = await window.SecurePassAPI.post('/totp/reveal', {
        user_id: userInput.value.trim(),
        auth_token: token
      });
      totpSection.classList.remove('hidden');
      totpCode.textContent = payload.code;
    } catch (err) {
      status.textContent = `2FA retrieval failed: ${err.message}`;
    }
  }

  startBtn.addEventListener('click', async () => {
    const userId = userInput.value.trim();
    if (!userId) {
      status.textContent = 'User ID required.';
      return;
    }
    startBtn.disabled = true;
    try {
      const payload = await window.SecurePassAPI.post('/auth/start', { user_id: userId });
      challengePhrase = payload.challenge;
      challengeText.textContent = challengePhrase;
      textarea.value = '';
      textarea.focus();
      container.classList.remove('hidden');
      status.textContent = 'Type the phrase and press Enter.';
      totpSection.classList.add('hidden');
    } catch (err) {
      status.textContent = err.message;
    } finally {
      startBtn.disabled = false;
    }
  });

  attachListeners();
})();
