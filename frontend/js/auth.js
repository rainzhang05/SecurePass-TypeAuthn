(function () {
  const startBtn = document.getElementById('startAuth');
  const dropdown = document.getElementById('authUserDropdown');
  const dropdownToggle = document.getElementById('authDropdownToggle');
  const dropdownMenu = document.getElementById('authDropdownMenu');
  const dropdownLabel = document.getElementById('authDropdownLabel');
  const container = document.getElementById('challengeContainer');
  const challengeText = document.getElementById('challengeText');
  const challengeChars = document.getElementById('challengeChars');
  const textarea = document.getElementById('authArea');
  const status = document.getElementById('authStatus');
  const totpSection = document.getElementById('totp');
  const totpCode = document.getElementById('totpCode');
  const backHome = document.getElementById('authBackHome');
  const restartBtn = document.getElementById('restartAuth');
  const transitions = window.SecurePassTransitions;

  if (!startBtn || !dropdown || !dropdownToggle || !dropdownMenu || !dropdownLabel || !textarea || !status) {
    return;
  }

  let events = [];
  let challengePhrase = '';
  let captureActive = false;
  let sessionActive = false;
  let dropdownDisabled = true;
  let availableUsers = [];
  let selectedUser = '';
  let lockedUserId = '';
  let sessionLocked = false;

  textarea.disabled = true;
  setDropdownDisabled(true);
  startBtn.disabled = true;
  if (restartBtn) {
    restartBtn.disabled = true;
  }
  resetChallengeDisplay();

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
      if (char === ' ') {
        span.classList.add('space');
        span.textContent = ' ';
      } else {
        span.textContent = char;
      }
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

  function resetChallengeDisplay() {
    challengePhrase = '';
    challengeText.textContent = '';
    challengeChars.innerHTML = '';
    challengeChars.classList.add('hidden');
    textarea.value = '';
    textarea.disabled = true;
    updateChallengeHighlights('');
    hideSection(container);
    hideSection(totpSection);
    events = [];
    captureActive = false;
    sessionActive = false;
    if (restartBtn) {
      restartBtn.disabled = true;
    }
  }

  function updateStartButtonState() {
    if (!selectedUser) {
      startBtn.disabled = true;
      startBtn.classList.remove('is-locked');
      return;
    }
    startBtn.disabled = sessionLocked;
    startBtn.classList.toggle('is-locked', sessionLocked);
  }

  function handleTypingInput() {
    if (textarea.disabled) {
      return;
    }
    if (textarea.value.length > challengePhrase.length) {
      textarea.value = textarea.value.slice(0, challengePhrase.length);
    }
    if (!captureActive && textarea.value.length > 0) {
      captureActive = true;
      status.textContent = 'Authentication capture started...';
      sessionActive = true;
    }
    updateChallengeHighlights(textarea.value);
  }

  function closeDropdown() {
    dropdown.classList.remove('open');
    dropdownToggle.setAttribute('aria-expanded', 'false');
  }

  function openDropdown() {
    if (dropdownDisabled) {
      return;
    }
    dropdown.classList.add('open');
    dropdownToggle.setAttribute('aria-expanded', 'true');
  }

  function setDropdownDisabled(disabled) {
    dropdownDisabled = disabled;
    if (disabled) {
      dropdown.classList.add('disabled');
      closeDropdown();
    } else {
      dropdown.classList.remove('disabled');
    }
    dropdownToggle.setAttribute('aria-disabled', disabled ? 'true' : 'false');
  }

  function updateDropdownLabel(text) {
    dropdownLabel.textContent = text;
  }

  function selectUser(userId, { silent } = { silent: false }) {
    const previousUser = selectedUser;
    selectedUser = userId;
    const options = dropdownMenu.querySelectorAll('.dropdown-option');
    options.forEach((opt) => {
      if (!(opt instanceof HTMLElement)) return;
      const isActive = opt.dataset.value === userId;
      opt.classList.toggle('is-active', isActive);
      opt.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });
    if (userId) {
      updateDropdownLabel(userId);
      sessionLocked = Boolean(lockedUserId) && userId === lockedUserId;
      if (!silent && userId !== previousUser) {
        status.textContent = '';
      }
    } else {
      updateDropdownLabel('Select a saved ID');
      sessionLocked = false;
      if (!silent) {
        status.textContent = 'Select a saved ID to begin.';
      }
    }
    if (!silent && userId !== previousUser) {
      resetChallengeDisplay();
    }
    updateStartButtonState();
  }

  function toggleDropdown() {
    if (dropdownDisabled) {
      return;
    }
    if (dropdown.classList.contains('open')) {
      closeDropdown();
    } else {
      openDropdown();
    }
  }

  async function loadUsers() {
    try {
      const payload = await window.SecurePassAPI.get('/users');
      availableUsers = payload.users || [];
      dropdownMenu.innerHTML = '';
      if (!availableUsers.length) {
        const emptyState = document.createElement('div');
        emptyState.className = 'dropdown-empty';
        emptyState.textContent = 'No saved profiles';
        dropdownMenu.appendChild(emptyState);
        setDropdownDisabled(true);
        selectUser('', { silent: true });
        lockedUserId = '';
        sessionLocked = false;
        resetChallengeDisplay();
        updateStartButtonState();
        status.textContent = 'Enroll a profile to begin authentication.';
        return;
      }
      availableUsers.forEach((userId) => {
        const option = document.createElement('button');
        option.type = 'button';
        option.className = 'dropdown-option';
        option.dataset.value = userId;
        option.setAttribute('role', 'option');
        option.textContent = userId;
        dropdownMenu.appendChild(option);
      });
      setDropdownDisabled(false);
      if (selectedUser && availableUsers.includes(selectedUser)) {
        selectUser(selectedUser, { silent: true });
      } else {
        selectUser('', { silent: true });
      }
      updateStartButtonState();
      status.textContent = '';
    } catch (err) {
      dropdownMenu.innerHTML = '';
      const errorState = document.createElement('div');
      errorState.className = 'dropdown-empty';
      errorState.textContent = 'Unable to load IDs';
      dropdownMenu.appendChild(errorState);
      setDropdownDisabled(true);
      selectUser('', { silent: true });
      lockedUserId = '';
      sessionLocked = false;
      resetChallengeDisplay();
      updateStartButtonState();
      status.textContent = `Unable to load saved IDs: ${err.message}`;
    }
  }

  function formatScore(result) {
    if (!result || typeof result.score !== 'number' || Number.isNaN(result.score)) {
      return 'N/A';
    }
    return result.score.toFixed(3);
  }

  async function beginAuthSession({ isRestart = false } = {}) {
    const userId = selectedUser;
    if (!userId) {
      status.textContent = 'Select a saved ID first.';
      return;
    }
    sessionLocked = true;
    updateStartButtonState();
    setDropdownDisabled(true);
    if (restartBtn) {
      restartBtn.disabled = true;
    }
    resetChallengeDisplay();
    status.textContent = isRestart ? 'Restarting challenge...' : 'Preparing challenge...';
    try {
      const payload = await window.SecurePassAPI.post('/auth/start', { user_id: userId });
      challengePhrase = payload.challenge || '';
      challengeText.textContent = challengePhrase;
      renderChallengeCharacters(challengePhrase);
      updateChallengeHighlights('');
      textarea.value = '';
      textarea.disabled = false;
      textarea.focus();
      showSection(container);
      hideSection(totpSection);
      status.textContent = 'Type the phrase and press Enter.';
      lockedUserId = userId;
      events = [];
      captureActive = false;
      sessionActive = true;
      if (restartBtn) {
        restartBtn.disabled = false;
      }
    } catch (err) {
      status.textContent = err.message;
      sessionLocked = false;
      resetChallengeDisplay();
      if (availableUsers.length) {
        setDropdownDisabled(false);
      }
      updateStartButtonState();
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
        user_id: selectedUser,
        events
      });
      const scoreLabel = formatScore(response.result);
      if (response.result && response.result.accepted) {
        status.textContent = `Verified ✅ (score ${scoreLabel})`;
        await revealTotp(response.auth_token);
      } else {
        status.textContent = `Denied ❌ (score ${scoreLabel})`;
        hideSection(totpSection);
      }
    } catch (err) {
      status.textContent = err.message;
      hideSection(totpSection);
    } finally {
      events = [];
      textarea.value = '';
      updateChallengeHighlights('');
      textarea.disabled = false;
      textarea.focus();
      captureActive = false;
      sessionActive = false;
      if (availableUsers.length) {
        setDropdownDisabled(false);
      }
      if (restartBtn && selectedUser) {
        restartBtn.disabled = false;
      }
      updateStartButtonState();
    }
  }

  async function revealTotp(token) {
    if (!token) {
      return;
    }
    try {
      const payload = await window.SecurePassAPI.post('/totp/reveal', {
        user_id: selectedUser,
        auth_token: token
      });
      showSection(totpSection);
      totpCode.textContent = payload.code;
    } catch (err) {
      status.textContent = `2FA retrieval failed: ${err.message}`;
      hideSection(totpSection);
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
      backHome.addEventListener('click', (event) => {
        event.preventDefault();
        if (transitions && typeof transitions.navigate === 'function') {
          transitions.navigate('/');
        } else {
          window.location.href = '/';
        }
      });
    }

    if (restartBtn) {
      restartBtn.addEventListener('click', () => {
        if (!selectedUser) {
          status.textContent = 'Select a saved ID first.';
          return;
        }
        beginAuthSession({ isRestart: true });
      });
    }

    dropdownToggle.addEventListener('click', (event) => {
      event.stopPropagation();
      toggleDropdown();
    });

    dropdownMenu.addEventListener('click', (event) => {
      const target = event.target instanceof Element ? event.target.closest('.dropdown-option') : null;
      const option = target;
      if (!option) {
        return;
      }
      event.stopPropagation();
      selectUser(option.dataset.value || '');
      closeDropdown();
    });

    document.addEventListener('click', (event) => {
      if (!dropdown.contains(event.target)) {
        closeDropdown();
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        closeDropdown();
      }
    });
  }

  startBtn.addEventListener('click', () => {
    if (!sessionLocked) {
      beginAuthSession();
    }
  });

  loadUsers();
  attachListeners();
})();
