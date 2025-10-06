(function () {
  async function post(path, body) {
    const response = await fetch(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    });
    if (!response.ok) {
      let detail = 'Request failed';
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch (err) {
        // Ignore
      }
      throw new Error(detail);
    }
    return response.json();
  }

  window.SecurePassAPI = { post };
})();
