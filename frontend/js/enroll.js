(function () {
  const startBtn = document.getElementById('startEnrollment');
  const userInput = document.getElementById('userId');
  const promptContainer = document.getElementById('promptContainer');
  const promptText = document.getElementById('promptText');
  const typingArea = document.getElementById('typingArea');
  const status = document.getElementById('status');
  const progress = document.getElementById('progress');
  const progressBar = document.getElementById('progressBar');
  const totpSection = document.getElementById('totpSetup');
  const totpQr = document.getElementById('totpQr');
  const totpSecret = document.getElementById('totpSecret');

  let prompts = [];
  let currentIndex = 0;
  let events = [];

  function resetState() {
    currentIndex = 0;
    events = [];
    progressBar.style.width = '0%';
    status.textContent = '';
  }

  function sanitizeKey(event) {
    if (event.key === 'Unidentified') {
      return event.code || 'Unknown';
    }
    return event.key;
  }

  function attachListeners() {
    typingArea.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' && !ev.shiftKey) {
        ev.preventDefault();
        submitSample();
        return;
      }
      events.push({ key: sanitizeKey(ev), event: 'keydown', ts: performance.now() });
    });

    typingArea.addEventListener('keyup', (ev) => {
      events.push({ key: sanitizeKey(ev), event: 'keyup', ts: performance.now() });
    });

    typingArea.addEventListener('paste', (ev) => ev.preventDefault());
    typingArea.addEventListener('copy', (ev) => ev.preventDefault());
    typingArea.addEventListener('cut', (ev) => ev.preventDefault());
    typingArea.addEventListener('contextmenu', (ev) => ev.preventDefault());
  }

  async function submitSample() {
    if (!typingArea.value.trim()) {
      status.textContent = 'Please type the prompt first.';
      return;
    }
    try {
      status.textContent = 'Uploading sample...';
      const response = await window.SecurePassAPI.post('/enroll/submit', {
        user_id: userInput.value.trim(),
        events
      });
      currentIndex += 1;
      const pct = Math.min(100, Math.round((currentIndex / prompts.length) * 100));
      progressBar.style.width = pct + '%';
      status.textContent = response.trained
        ? 'Model trained successfully! You can proceed to authentication.'
        : `Sample ${currentIndex}/${prompts.length} captured.`;
      if (currentIndex < prompts.length) {
        preparePrompt();
      } else {
        typingArea.disabled = true;
        typingArea.value = '';
        if (response.trained) {
          await setupTotp();
        }
      }
    } catch (err) {
      status.textContent = err.message;
    } finally {
      events = [];
    }
  }

  async function setupTotp() {
    try {
      const payload = await window.SecurePassAPI.post('/totp/setup', {
        user_id: userInput.value.trim()
      });
      totpSection.classList.remove('hidden');
      totpQr.src = `data:image/png;base64,${payload.qr}`;
      totpSecret.textContent = `Secret: ${payload.secret}`;
    } catch (err) {
      status.textContent = `TOTP setup failed: ${err.message}`;
    }
  }

  function preparePrompt() {
    typingArea.value = '';
    typingArea.disabled = false;
    typingArea.focus();
    promptText.textContent = prompts[currentIndex];
  }

  startBtn.addEventListener('click', async () => {
    const userId = userInput.value.trim();
    if (!userId) {
      status.textContent = 'User ID required.';
      return;
    }
    startBtn.disabled = true;
    try {
      resetState();
      const payload = await window.SecurePassAPI.post('/enroll/start', { user_id: userId });
      prompts = payload.prompts || [];
      progress.classList.remove('hidden');
      promptContainer.classList.remove('hidden');
      preparePrompt();
      status.textContent = 'Type the prompt and press Enter to submit.';
    } catch (err) {
      status.textContent = err.message;
    } finally {
      startBtn.disabled = false;
    }
  });

  attachListeners();
})();
