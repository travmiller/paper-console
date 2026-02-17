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

export async function adminAuthFetch(url, options = {}) {
  const initialToken = getAdminToken();
  const initialHeaders = withToken(options.headers || {}, initialToken);

  let response = await fetch(url, { ...options, headers: initialHeaders });
  const authRequired = response.headers.get(AUTH_REQUIRED_HEADER) === 'true';

  if (response.status !== 401 || !authRequired) {
    return response;
  }

  const prompted = window.prompt('Enter PC-1 admin token');
  if (!prompted) {
    return response;
  }

  const token = prompted.trim();
  if (!token) {
    return response;
  }

  setAdminToken(token);
  const retryHeaders = withToken(options.headers || {}, token);
  response = await fetch(url, { ...options, headers: retryHeaders });

  return response;
}
