(function () {
  async function handleResponse(response) {
    if (!response.ok) {
      let detail = 'Request failed';
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch (err) {
        // Ignore parsing issues
      }
      throw new Error(detail);
    }
    if (response.status === 204) {
      return {};
    }
    return response.json();
  }

  async function post(path, body) {
    const response = await fetch(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    });
    return handleResponse(response);
  }

  async function get(path) {
    const response = await fetch(path, {
      method: 'GET',
      headers: {
        'Accept': 'application/json'
      }
    });
    return handleResponse(response);
  }

  async function del(path) {
    const response = await fetch(path, {
      method: 'DELETE',
      headers: {
        'Accept': 'application/json'
      }
    });
    return handleResponse(response);
  }

  window.SecurePassAPI = { post, get, del };
})();
