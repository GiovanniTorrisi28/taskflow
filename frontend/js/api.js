const API_BASE = "/api";

function getToken() {
  return localStorage.getItem("taskflow_token");
}

function setSession(token, user) {
  localStorage.setItem("taskflow_token", token);
  localStorage.setItem("taskflow_user", JSON.stringify(user));
}

function getCurrentUser() {
  const raw = localStorage.getItem("taskflow_user");
  return raw ? JSON.parse(raw) : null;
}

function clearSession() {
  localStorage.removeItem("taskflow_token");
  localStorage.removeItem("taskflow_user");
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = "/index.html";
  }
}

async function apiFetch(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearSession();
    window.location.href = "/index.html";
    throw new Error("Sessione scaduta, effettua di nuovo il login");
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Errore ${res.status}`);
  }
  return data;
}
