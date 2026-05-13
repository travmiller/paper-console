export const formatTimeForDisplay = (time24, timeFormat = '12h') => {
  if (!time24) return '';
  if (timeFormat === '24h') return time24;

  const [hours, minutes] = time24.split(':');
  const h = parseInt(hours, 10);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const h12 = h % 12 || 12;
  return `${h12}:${minutes} ${ampm}`;
};

export const normalizePrintWebhookEndpointPath = (value) => {
  const slug = String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '');

  return slug;
};

export const generatePrintWebhookToken = () => {
  const bytes = new Uint8Array(18);

  if (globalThis.crypto?.getRandomValues) {
    globalThis.crypto.getRandomValues(bytes);
    let binary = '';
    bytes.forEach((byte) => {
      binary += String.fromCharCode(byte);
    });
    return btoa(binary)
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/g, '');
  }
  return `pc1_${Math.random().toString(36).slice(2)}${Math.random().toString(36).slice(2)}`;
};

export const validateHHMM = (timeValue) => /^([01]\d|2[0-3]):([0-5]\d)$/.test(String(timeValue || '').trim());

export const validateCronExpression = (expression) => {
  const parts = stripCronTimezonePrefix(expression).split(/\s+/).filter(Boolean);
  return parts.length === 5;
};

export const parseCronTimezone = (expression, fallbackTimezone = 'UTC') => {
  return fallbackTimezone;
};

export const stripCronTimezonePrefix = (expression) => {
  const trimmed = String(expression || '').trim();
  const parts = trimmed.split(/\s+/);
  if (parts[0]?.startsWith('CRON_TZ=') || parts[0]?.startsWith('TZ=')) {
    return parts.slice(1).join(' ');
  }
  return trimmed;
};

export const cronToReadable = (expression, timezone = 'UTC', timeFormat = '12h') => {
  const cronExpression = stripCronTimezonePrefix(expression);
  const parts = cronExpression.split(/\s+/);
  if (parts.length !== 5) {
    return `Cron: ${expression} (${timezone})`;
  }

  const [minute, hour, day, month, weekday] = parts;

  if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && day === '*' && month === '*' && weekday === '*') {
    const hh = String(hour).padStart(2, '0');
    const mm = String(minute).padStart(2, '0');
    return `Every day at ${formatTimeForDisplay(`${hh}:${mm}`, timeFormat)} (${timezone})`;
  }

  if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && day === '*' && month === '*' && weekday === '1-5') {
    const hh = String(hour).padStart(2, '0');
    const mm = String(minute).padStart(2, '0');
    return `Weekdays at ${formatTimeForDisplay(`${hh}:${mm}`, timeFormat)} (${timezone})`;
  }

  return `Cron: ${cronExpression} (${timezone})`;
};

export const toLegacyHHMMFromCron = (expression) => {
  const cronExpression = stripCronTimezonePrefix(expression);
  const parts = cronExpression.split(/\s+/);
  if (parts.length !== 5) return null;

  const [minute, hour, day, month, weekday] = parts;
  if (!/^\d+$/.test(minute) || !/^\d+$/.test(hour)) return null;
  if (!(day === '*' && month === '*' && weekday === '*')) return null;

  const hh = Number(hour);
  const mm = Number(minute);
  if (hh < 0 || hh > 23 || mm < 0 || mm > 59) return null;

  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
};
