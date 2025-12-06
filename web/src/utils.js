export const formatTimeForDisplay = (time24, timeFormat = '12h') => {
  if (!time24) return '';
  if (timeFormat === '24h') return time24;

  const [hours, minutes] = time24.split(':');
  const h = parseInt(hours, 10);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const h12 = h % 12 || 12;
  return `${h12}:${minutes} ${ampm}`;
};
