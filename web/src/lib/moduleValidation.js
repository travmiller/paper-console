export const getModuleValidationErrors = (module) => {
  const errors = {};
  const config = module?.config || {};

  if (!String(module?.name || '').trim()) {
    errors.name = 'Module name is required.';
  }

  if (module?.type === 'email') {
    const email = String(config.email_user || '').trim();
    const password = String(config.email_password || '').trim();
    const provider = String(config.email_service || 'Gmail');
    const host = String(config.email_host || '').trim();
    const port = Number(config.email_port ?? 993);

    if (!email) {
      errors.email_user = 'Email address is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email_user = 'Enter a valid email address.';
    }

    if (!password) {
      errors.email_password = 'App password is required.';
    }

    if (provider === 'Custom') {
      if (!host) {
        errors.email_host = 'IMAP host is required for custom provider.';
      }
      if (!Number.isFinite(port) || port < 1 || port > 65535) {
        errors.email_port = 'Enter a valid IMAP port (1-65535).';
      }
    }
  }

  if (module?.type === 'webhook') {
    const url = String(config.url || '').trim();
    const method = String(config.method || 'GET').toUpperCase();
    const body = String(config.body || '').trim();

    if (!url) {
      errors.url = 'URL is required.';
    } else {
      try {
        const parsed = new URL(url);
        if (!['http:', 'https:'].includes(parsed.protocol)) {
          errors.url = 'URL must start with http:// or https://';
        }
      } catch {
        errors.url = 'Enter a valid URL.';
      }
    }

    if (method === 'POST' && body) {
      try {
        JSON.parse(body);
      } catch {
        errors.body = 'Body must be valid JSON.';
      }
    }
  }

  return errors;
};

export const getModuleValidationIssueCount = (module) => Object.keys(getModuleValidationErrors(module)).length;
