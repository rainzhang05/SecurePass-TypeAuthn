(function () {
  const startBtn = document.getElementById('startEnrollment');
  const userInput = document.getElementById('userId');
  const promptContainer = document.getElementById('promptContainer');
  const promptText = document.getElementById('promptText');
  const promptChars = document.getElementById('promptChars');
  const typingArea = document.getElementById('typingArea');
  const status = document.getElementById('status');
  const progress = document.getElementById('progress');
  const progressBar = document.getElementById('progressBar');
  const totpSection = document.getElementById('totpSetup');
  const totpQr = document.getElementById('totpQr');
  const totpSecret = document.getElementById('totpSecret');
  const savedList = document.getElementById('savedIdsList');
  const savedEmpty = document.getElementById('savedIdsEmpty');
  const backHome = document.getElementById('backHome');
  const restartBtn = document.getElementById('restartEnrollment');
  const transitions = window.SecurePassTransitions;

  let prompts = [];
  let currentIndex = 0;
  let events = [];
  let trainingActive = false;
  let savedUserIds = [];
  let activeUserId = '';
  let sessionLocked = false;

  startBtn.disabled = true;
  if (restartBtn) {
    restartBtn.disabled = true;
  }

  function showSection(element) {
    if (!element) {
      return;
    }
    if (transitions && typeof transitions.revealSection === 'function') {
      transitions.revealSection(element);
    } else {
      element.classList.remove('hidden');
    }
  }

  function hideSection(element) {
    if (!element) {
      return;
    }
    if (transitions && typeof transitions.hideSection === 'function') {
      transitions.hideSection(element);
    } else {
      element.classList.add('hidden');
    }
  }

  function resetState() {
    currentIndex = 0;
    events = [];
    trainingActive = false;
    progressBar.style.width = '0%';
    status.textContent = '';
    promptChars.innerHTML = '';
    typingArea.value = '';
    typingArea.disabled = false;
    hideSection(promptContainer);
    hideSection(progress);
    hideSection(totpSection);
    if (restartBtn) {
      restartBtn.disabled = true;
    }
  }

  function isPromptActive() {
    return !promptContainer.classList.contains('hidden');
  }

  function updateStartAvailability() {
    const userId = userInput.value.trim();
    const isDuplicate = savedUserIds.includes(userId);
    const shouldDisable = sessionLocked || !userId || isDuplicate;
    startBtn.disabled = shouldDisable;
    startBtn.classList.toggle('is-locked', sessionLocked && Boolean(userId) && !isDuplicate);
  }

  function handleUserIdInput() {
    const userId = userInput.value.trim();
    if (userId !== activeUserId) {
      sessionLocked = false;
    } else if (activeUserId) {
      sessionLocked = true;
    }
    if (!isPromptActive()) {
      if (!userId) {
        status.textContent = '';
      } else if (savedUserIds.includes(userId)) {
        status.textContent = `User ID "${userId}" already exists. Choose a different one.`;
      } else if (!sessionLocked) {
        status.textContent = '';
      }
    }
    updateStartAvailability();
  }

  function sanitizeKey(event) {
    if (event.key === 'Unidentified') {
      return event.code || 'Unknown';
    }
    return event.key;
  }

  function renderPromptCharacters(text) {
    promptChars.innerHTML = '';
    text.split('').forEach((char, index) => {
      const span = document.createElement('span');
      span.dataset.index = String(index);
      if (char === ' ') {
        span.classList.add('space');
        span.textContent = ' ';
      } else {
        span.textContent = char;
      }
      promptChars.appendChild(span);
    });
    if (!text.length) {
      promptChars.classList.add('hidden');
    } else {
      promptChars.classList.remove('hidden');
    }
  }

  function updatePromptHighlights(typed) {
    const expected = prompts[currentIndex] || '';
    const spans = promptChars.querySelectorAll('span');
    spans.forEach((span, index) => {
      span.classList.remove('correct', 'incorrect', 'active');
      if (index < typed.length) {
        if (typed[index] === expected[index]) {
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
    if (promptContainer.classList.contains('hidden')) {
      return;
    }
    const expected = prompts[currentIndex] || '';
    if (typingArea.value.length > expected.length) {
      typingArea.value = typingArea.value.slice(0, expected.length);
    }
    if (!trainingActive && typingArea.value.length > 0) {
      trainingActive = true;
      status.textContent = 'Training sample capture started...';
    }
    updatePromptHighlights(typingArea.value);
  }

  async function refreshSavedIds() {
    if (!savedList || !savedEmpty) {
      return;
    }
    try {
      const payload = await window.SecurePassAPI.get('/users');
      const users = payload.users || [];
      savedUserIds = users.slice();
      savedList.innerHTML = '';
      if (!users.length) {
        savedList.classList.add('hidden');
        savedEmpty.classList.remove('hidden');
        savedEmpty.textContent = 'No trained profiles yet.';
        updateStartAvailability();
        return;
      }
      savedList.classList.remove('hidden');
      savedEmpty.classList.add('hidden');
      users.forEach((userId) => {
        const item = document.createElement('li');
        item.className = 'saved-item';
        const name = document.createElement('span');
        name.textContent = userId;
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'btn btn-danger';
        remove.dataset.deleteId = userId;
        remove.textContent = 'Delete';
        item.appendChild(name);
        item.appendChild(remove);
        savedList.appendChild(item);
      });
      updateStartAvailability();
    } catch (err) {
      savedList.classList.add('hidden');
      savedEmpty.classList.remove('hidden');
      savedEmpty.textContent = `Unable to load saved IDs: ${err.message}`;
      savedUserIds = [];
      updateStartAvailability();
    }
  }

  async function beginEnrollment({ isRestart = false } = {}) {
    const userId = userInput.value.trim();
    if (!userId) {
      status.textContent = 'User ID required.';
      sessionLocked = false;
      updateStartAvailability();
      return;
    }
    if (savedUserIds.includes(userId)) {
      status.textContent = `User ID "${userId}" already exists. Choose a different one.`;
      sessionLocked = false;
      updateStartAvailability();
      return;
    }
    sessionLocked = true;
    activeUserId = userId;
    startBtn.disabled = true;
    updateStartAvailability();
    if (restartBtn) {
      restartBtn.disabled = true;
    }
    userInput.disabled = true;
    resetState();
    status.textContent = isRestart ? 'Restarting enrollment...' : 'Preparing prompts...';
    try {
      const payload = await window.SecurePassAPI.post('/enroll/start', { user_id: userId });
      prompts = payload.prompts || [];
      if (!prompts.length) {
        status.textContent = 'No prompts available.';
        userInput.disabled = false;
        sessionLocked = false;
        updateStartAvailability();
        return;
      }
      showSection(progress);
      showSection(promptContainer);
      preparePrompt();
      status.textContent = 'Type the prompt and press Enter to submit.';
      if (restartBtn) {
        restartBtn.disabled = false;
      }
    } catch (err) {
      status.textContent = err.message;
      sessionLocked = false;
      userInput.disabled = false;
      updateStartAvailability();
    }
  }

  async function deleteUser(userId) {
    try {
      await window.SecurePassAPI.del(`/users/${encodeURIComponent(userId)}`);
      await refreshSavedIds();
      if (userInput.value === userId) {
        status.textContent = 'Profile deleted. Refresh to enroll again if needed.';
      }
    } catch (err) {
      status.textContent = `Delete failed: ${err.message}`;
    }
  }

  async function submitSample() {
    const expected = prompts[currentIndex] || '';
    const typed = typingArea.value;
    if (!typed.length) {
      status.textContent = 'Please type the prompt first.';
      return;
    }
    if (typed !== expected) {
      status.textContent = 'Please match the prompt exactly before submitting.';
      updatePromptHighlights(typed);
      return;
    }
    typingArea.disabled = true;
    try {
      status.textContent = 'Uploading sample...';
      const response = await window.SecurePassAPI.post('/enroll/submit', {
        user_id: userInput.value.trim(),
        events
      });
      trainingActive = false;
      currentIndex += 1;
      const pct = prompts.length ? Math.min(100, Math.round((currentIndex / prompts.length) * 100)) : 0;
      progressBar.style.width = pct + '%';
      if (currentIndex < prompts.length) {
        status.textContent = `Sample ${currentIndex}/${prompts.length} saved. Training paused—start the next prompt.`;
        if (restartBtn) {
          restartBtn.disabled = false;
        }
        preparePrompt();
      } else {
        typingArea.value = '';
        promptChars.innerHTML = '';
        if (response.trained) {
          status.textContent = 'Model training finished! Setting up your TOTP secret...';
          await setupTotp();
          await refreshSavedIds();
          status.textContent = 'Model trained successfully! You can proceed to authentication.';
        } else {
          status.textContent = 'All samples captured.';
        }
        if (restartBtn) {
          restartBtn.disabled = true;
        }
        userInput.disabled = false;
        sessionLocked = true;
        updateStartAvailability();
      }
    } catch (err) {
      status.textContent = err.message;
    } finally {
      events = [];
      if (currentIndex < prompts.length) {
        typingArea.disabled = false;
        typingArea.focus();
      }
    }
  }

  async function setupTotp() {
    try {
      const payload = await window.SecurePassAPI.post('/totp/setup', {
        user_id: userInput.value.trim()
      });
      showSection(totpSection);
      totpQr.src = `data:image/png;base64,${payload.qr}`;
      totpSecret.textContent = `Secret: ${payload.secret}`;
    } catch (err) {
      status.textContent = `TOTP setup failed: ${err.message}`;
      hideSection(totpSection);
    }
  }

  function preparePrompt() {
    typingArea.value = '';
    typingArea.disabled = false;
    typingArea.focus();
    const prompt = prompts[currentIndex] || '';
    promptText.textContent = prompt;
    renderPromptCharacters(prompt);
    updatePromptHighlights('');
    typingArea.setAttribute('maxlength', String(prompt.length));
    trainingActive = false;
  }

  function attachListeners() {
    if (userInput) {
      userInput.addEventListener('input', handleUserIdInput);
    }

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

    typingArea.addEventListener('input', handleTypingInput);
    ['paste', 'copy', 'cut', 'contextmenu'].forEach((type) => {
      typingArea.addEventListener(type, (ev) => ev.preventDefault());
    });

    if (savedList) {
      savedList.addEventListener('click', (event) => {
        const target = event.target;
        if (target instanceof HTMLElement && target.dataset.deleteId) {
          const userId = target.dataset.deleteId;
          const confirmed = window.confirm(`Delete saved profile "${userId}"? This cannot be undone.`);
          if (confirmed) {
            deleteUser(userId);
          }
        }
      });
    }

    if (backHome) {
      backHome.addEventListener('click', (event) => {
        event.preventDefault();
        if (transitions && typeof transitions.navigate === 'function') {
          transitions.navigate('/');
        } else {
          window.location.href = '/';
        }
      });
    }
  }

  startBtn.addEventListener('click', () => {
    if (!sessionLocked) {
      beginEnrollment();
    }
  });

  if (restartBtn) {
    restartBtn.addEventListener('click', () => {
      if (userInput.disabled) {
        beginEnrollment({ isRestart: true });
      }
    });
  }

  refreshSavedIds();
  attachListeners();
})();
