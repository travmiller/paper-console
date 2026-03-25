const TOKEN_STORAGE_KEY = 'pc1_admin_token';
const AUTH_REQUIRED_HEADER = 'X-PC1-Auth-Required';
const TOKEN_HEADER = 'X-PC1-Admin-Token';

export function getAdminToken() {
  return window.localStorage.getItem(TOKEN_STORAGE_KEY) || '';
}

export function setAdminToken(token) {
  const normalized = (token || '').trim();
  if (!normalized) {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(TOKEN_STORAGE_KEY, normalized);
}

export function clearAdminToken() {
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
}

function withToken(headers = {}, token = '') {
  if (!token) return headers;
  return { ...headers, [TOKEN_HEADER]: token };
}

function buildRequest(url, options = {}) {
  const token = getAdminToken();
  return fetch(url, {
    ...options,
    headers: withToken(options.headers || {}, token),
    credentials: options.credentials || 'same-origin',
  });
}

export async function fetchAdminAuthStatus() {
  const response = await buildRequest('/api/system/auth/status');
  if (!response.ok) {
    throw new Error('Failed to load auth status');
  }
  return response.json();
}

export async function loginAdminSession(password, remember = false) {
  const response = await buildRequest('/api/system/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password, remember }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Invalid password');
  }

  const data = await response.json().catch(() => ({}));
  return data.auth || null;
}

export async function logoutAdminSession() {
  await buildRequest('/api/system/auth/logout', { method: 'POST' });
}

export async function adminAuthFetch(url, options = {}) {
  const response = await buildRequest(url, options);
  if (isAuthRequiredResponse(response) && typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('pc1-auth-required'));
  }
  return response;
}

export function isAuthRequiredResponse(response) {
  return response.status === 401 && response.headers.get(AUTH_REQUIRED_HEADER) === 'true';
}
