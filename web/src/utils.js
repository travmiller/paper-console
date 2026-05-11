export const formatTimeForDisplay = (time24, timeFormat = '12h') => {
  if (!time24) return '';
  if (timeFormat === '24h') return time24;

  const [hours, minutes] = time24.split(':');
  const h = parseInt(hours, 10);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const h12 = h % 12 || 12;
  return `${h12}:${minutes} ${ampm}`;
};

export const validateHHMM = (timeValue) => /^([01]\d|2[0-3]):([0-5]\d)$/.test(String(timeValue || '').trim());

export const validateCronExpression = (expression) => {
  const trimmed = String(expression || '').trim();
  if (!trimmed) return false;

  const parts = trimmed.split(/\s+/);
  if (parts[0]?.startsWith('CRON_TZ=') || parts[0]?.startsWith('TZ=')) {
    return parts.length === 6;
  }
  return parts.length === 5;
};

export const parseCronTimezone = (expression, fallbackTimezone = 'UTC') => {
  const trimmed = String(expression || '').trim();
  const parts = trimmed.split(/\s+/);
  if (parts[0]?.startsWith('CRON_TZ=') || parts[0]?.startsWith('TZ=')) {
    return parts[0].split('=', 2)[1] || fallbackTimezone;
  }
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
