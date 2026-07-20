/* webapp/frontend/js/api.js — tiny fetch wrapper shared by every page. */

const Api = (() => {
  async function request(path, { method = "GET", body } = {}) {
    const res = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      credentials: "same-origin",
      body: body ? JSON.stringify(body) : undefined,
    });

    let data;
    try {
      data = await res.json();
    } catch (_e) {
      data = { ok: false, error: "Unexpected server response." };
    }

    if (!res.ok && !("ok" in data)) {
      data = { ok: false, error: data.error || `Request failed (${res.status}).` };
    }
    return data;
  }

  return {
    get: (path) => request(path),
    post: (path, body) => request(path, { method: "POST", body }),
  };
})();
