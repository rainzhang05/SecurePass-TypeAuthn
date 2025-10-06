(() => {
  const { apiPost, disableClipboardInteractions, recordKeystrokes } = window.SecurePassAPI;

  const userInput = document.getElementById('authUserId');
  const challengeBox = document.getElementById('challenge');
  const typingArea = document.getElementById('authTypingArea');
  const startButton = document.getElementById('startAuth');
  const submitButton = document.getElementById('submitAuth');
  const statusBox = document.getElementById('authStatus');
  const dashboard = document.getElementById('dashboard');
  const welcome = document.getElementById('welcome');
  const totpCode = document.getElementById('totpCode');
  const totpExpiry = document.getElementById('totpExpiry');
  const totpQr = document.getElementById('totpQr');
  const totpSecret = document.getElementById('totpSecret');

  let sessionToken = null;
  let userId = '';
  let recorder = null;
  let totpInterval = null;

  disableClipboardInteractions(typingArea);

  const setStatus = (message, type = 'info') => {
    statusBox.textContent = message;
    statusBox.className = type === 'error' ? 'alert-error' : 'alert-success';
  };

  const resetStatus = () => {
    statusBox.textContent = '';
    statusBox.className = '';
  };

  const resetTotp = () => {
    if (totpInterval) {
      clearInterval(totpInterval);
      totpInterval = null;
    }
    totpCode.textContent = '------';
    totpSecret.textContent = '';
    totpQr.removeAttribute('src');
  };

  const refreshTotpCode = async () => {
    if (!sessionToken) return;
    try {
      const response = await apiPost('/totp/reveal', {
        user_id: userId,
        session_token: sessionToken,
      });
      totpCode.textContent = response.code;
      totpExpiry.textContent = `Valid for ${response.valid_for} seconds`;
    } catch (error) {
      setStatus(error.message, 'error');
    }
  };

  const setupTotp = async () => {
    try {
      const response = await apiPost('/totp/setup', {
        user_id: userId,
        session_token: sessionToken,
      });
      totpSecret.textContent = `Secret: ${response.secret}`;
      totpQr.src = `data:image/png;base64,${response.qr_code}`;
      await refreshTotpCode();
      totpInterval = setInterval(refreshTotpCode, 5000);
    } catch (error) {
      setStatus(error.message, 'error');
    }
  };

  startButton.addEventListener('click', async () => {
    resetStatus();
    resetTotp();
    dashboard.style.display = 'none';
    userId = userInput.value.trim();
    if (!userId) {
      setStatus('Please provide a user ID.', 'error');
      return;
    }
    try {
      const response = await apiPost('/auth/start', { user_id: userId });
      sessionToken = response.session_token;
      challengeBox.textContent = response.challenge;
      typingArea.value = '';
      typingArea.disabled = false;
      typingArea.focus();
      recorder?.destroy?.();
      recorder = recordKeystrokes(typingArea);
      setStatus('Challenge retrieved. Type the phrase and submit to authenticate.');
    } catch (error) {
      setStatus(error.message, 'error');
    }
  });

  submitButton.addEventListener('click', async () => {
    resetStatus();
    if (!sessionToken) {
      setStatus('Start authentication first.', 'error');
      return;
    }
    const events = recorder?.collect?.() || [];
    if (!events.length) {
      setStatus('No keystroke data captured. Type the challenge phrase.', 'error');
      return;
    }
    submitButton.disabled = true;
    try {
      const payload = {
        user_id: userId,
        events,
        session_token: sessionToken,
      };
      const response = await apiPost('/auth/submit', payload, { sessionToken });
      if (response.accepted) {
        setStatus(`Verified ✅ — score ${response.score.toFixed(3)}`, 'success');
        dashboard.style.display = 'block';
        welcome.textContent = `Welcome back, ${userId}. Behavioral signature verified.`;
        await setupTotp();
      } else {
        setStatus(`Denied ❌ — score ${response.score.toFixed(3)} (threshold ${response.threshold.toFixed(3)})`, 'error');
      }
    } catch (error) {
      setStatus(error.message, 'error');
    } finally {
      submitButton.disabled = false;
    }
  });
})();
