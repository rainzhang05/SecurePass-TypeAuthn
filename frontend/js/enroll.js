(() => {
  const { apiPost, disableClipboardInteractions, recordKeystrokes } = window.SecurePassAPI;

  const userInput = document.getElementById('userId');
  const promptText = document.getElementById('prompt');
  const typingArea = document.getElementById('typingArea');
  const startButton = document.getElementById('startEnrollment');
  const submitButton = document.getElementById('submitSample');
  const progressBar = document.getElementById('progressFill');
  const statusBox = document.getElementById('status');
  const samplesCount = document.getElementById('samplesCount');

  let prompts = [];
  let promptIndex = 0;
  let sessionToken = null;
  let recorder = null;
  let userId = '';

  disableClipboardInteractions(typingArea);

  const updatePrompt = () => {
    if (prompts.length === 0) {
      promptText.textContent = 'Press start to retrieve prompts.';
      return;
    }
    promptText.textContent = prompts[promptIndex % prompts.length];
  };

  const updateProgress = (samples = 0) => {
    const percentage = Math.min(100, Math.round((samples / 3) * 100));
    progressBar.style.width = `${percentage}%`;
  };

  const setStatus = (message, type = 'info') => {
    statusBox.textContent = message;
    statusBox.className = type === 'error' ? 'alert-error' : 'alert-success';
  };

  const resetStatus = () => {
    statusBox.textContent = '';
    statusBox.className = '';
  };

  startButton.addEventListener('click', async () => {
    resetStatus();
    userId = userInput.value.trim();
    if (!userId) {
      setStatus('Please enter a user ID to continue.', 'error');
      return;
    }

    try {
      const response = await apiPost('/enroll/start', { user_id: userId });
      sessionToken = response.session_token;
      prompts = response.prompts || [];
      promptIndex = 0;
      updatePrompt();
      typingArea.value = '';
      typingArea.disabled = false;
      typingArea.focus();
      recorder?.destroy?.();
      recorder = recordKeystrokes(typingArea);
      samplesCount.textContent = '0';
      updateProgress(0);
      setStatus('Enrollment session started. Please type the prompt exactly as shown.');
    } catch (error) {
      setStatus(error.message, 'error');
    }
  });

  submitButton.addEventListener('click', async () => {
    resetStatus();
    if (!sessionToken) {
      setStatus('Start enrollment before submitting.', 'error');
      return;
    }
    const typed = typingArea.value.trim();
    if (!typed) {
      setStatus('Type the prompt before submitting.', 'error');
      return;
    }
    const events = recorder?.collect?.() || [];
    if (!events.length) {
      setStatus('No keystroke data captured. Please try again.', 'error');
      return;
    }

    submitButton.disabled = true;

    try {
      const payload = {
        user_id: userId,
        session_token: sessionToken,
        events,
      };
      const response = await apiPost('/enroll/submit', payload);
      samplesCount.textContent = String(response.samples);
      updateProgress(response.samples || 0);
      const trainedMessage = response.trained
        ? 'Model trained successfully. You can proceed to authentication.'
        : 'Sample captured. Provide more samples for training.';
      setStatus(trainedMessage);
      typingArea.value = '';
      recorder?.reset?.();
      promptIndex += 1;
      updatePrompt();
    } catch (error) {
      setStatus(error.message, 'error');
    } finally {
      submitButton.disabled = false;
      typingArea.focus();
    }
  });
})();
