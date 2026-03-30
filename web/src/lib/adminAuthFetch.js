const AUTH_REQUIRED_HEADER = 'X-PC1-Auth-Required';

function buildRequest(url, options = {}) {
  return fetch(url, {
    ...options,
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
    throw new Error(data.detail || 'Invalid Device Password');
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
