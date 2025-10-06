const API_BASE = window.location.origin;

async function apiPost(endpoint, body = {}, options = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (options.sessionToken) {
    headers['X-Session-Token'] = options.sessionToken;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const details = await response.json().catch(() => ({}));
    throw new Error(details.detail || `Request failed with status ${response.status}`);
  }

  return response.json();
}

function disableClipboardInteractions(element) {
  element.addEventListener('paste', (event) => event.preventDefault());
  element.addEventListener('copy', (event) => event.preventDefault());
  element.addEventListener('cut', (event) => event.preventDefault());
  element.addEventListener('contextmenu', (event) => event.preventDefault());
}

function recordKeystrokes(target, callbacks) {
  const events = [];
  const start = performance.now();

  const handler = (event) => {
    const timestamp = performance.now() - start;
    events.push({ key: event.key, event: event.type, timestamp });
    if (callbacks?.onEvent) {
      callbacks.onEvent(event, events);
    }
  };

  target.addEventListener('keydown', handler);
  target.addEventListener('keyup', handler);

  return {
    collect: () => events.slice(),
    reset: () => {
      events.length = 0;
    },
    destroy: () => {
      target.removeEventListener('keydown', handler);
      target.removeEventListener('keyup', handler);
    },
  };
}

window.SecurePassAPI = {
  apiPost,
  disableClipboardInteractions,
  recordKeystrokes,
};
