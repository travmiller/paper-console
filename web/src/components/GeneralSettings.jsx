import React, { useState, useEffect } from 'react';

const GeneralSettings = ({
  searchTerm,
  searchResults,
  handleSearch,
  selectLocation,
  settings,
  saveGlobalSettings,
  triggerAPMode,
  wifiStatus,
}) => {
  const inputClass =
    'w-full p-3 text-base bg-[#333] border border-gray-700 rounded text-white focus:border-white focus:outline-none box-border';
  const labelClass = 'block mb-2 font-bold text-gray-200';

  // System time state
  const [currentTime, setCurrentTime] = useState(null);
  const [manualDate, setManualDate] = useState('');
  const [manualTime, setManualTime] = useState('');
  const [timeStatus, setTimeStatus] = useState({ type: '', message: '' });

  // System timezone state
  const [systemTimezone, setSystemTimezone] = useState(null);
  const [availableTimezones, setAvailableTimezones] = useState([]);
  const [timezoneStatus, setTimezoneStatus] = useState({ type: '', message: '' });

  // Fetch current system time on mount and periodically
  useEffect(() => {
    const fetchTime = async () => {
      try {
        const response = await fetch('/api/system/time');
        const data = await response.json();
        if (data.datetime) {
          setCurrentTime(data);
          // Pre-fill manual inputs with current time only once
          setManualDate((prev) => prev || data.date);
          setManualTime((prev) => prev || data.time.substring(0, 5)); // HH:MM format for input
        }
      } catch (err) {
        console.error('Error fetching system time:', err);
      }
    };

    fetchTime();
    const interval = setInterval(fetchTime, 1000); // Update every second
    return () => clearInterval(interval);
  }, []); // Only run on mount

  // Fetch system timezone and available timezones
  useEffect(() => {
    const fetchTimezone = async () => {
      try {
        const [tzResponse, listResponse] = await Promise.all([fetch('/api/system/timezone'), fetch('/api/system/timezone/list')]);

        const tzData = await tzResponse.json();
        const listData = await listResponse.json();

        if (tzData.found) {
          setSystemTimezone(tzData.timezone);
        }
        if (listData.timezones) {
          setAvailableTimezones(listData.timezones);
        }
      } catch (err) {
        console.error('Error fetching timezone:', err);
      }
    };

    fetchTimezone();
  }, []);

  // Format timezone to a more readable format
  const formatTimezone = (tz) => {
    if (!tz) return 'Not Set';

    const timezoneMap = {
      'America/New_York': 'Eastern Time (ET)',
      'America/Chicago': 'Central Time (CT)',
      'America/Denver': 'Mountain Time (MT)',
      'America/Phoenix': 'Mountain Time (MT)',
      'America/Los_Angeles': 'Pacific Time (PT)',
      'America/Anchorage': 'Alaska Time (AKT)',
      'Pacific/Honolulu': 'Hawaii Time (HST)',
      'America/Puerto_Rico': 'Atlantic Time (AST)',
      'America/St_Thomas': 'Atlantic Time (AST)',
      'Pacific/Guam': 'Chamorro Time (ChST)',
      'Pacific/Pago_Pago': 'Samoa Time (SST)',
      'Pacific/Saipan': 'Chamorro Time (ChST)',
    };

    // Check for exact match first
    if (timezoneMap[tz]) {
      return timezoneMap[tz];
    }

    // Try to extract timezone name from IANA format
    const parts = tz.split('/');
    if (parts.length >= 2) {
      const location = parts[parts.length - 1].replace(/_/g, ' ');
      return `${location} (${tz})`;
    }

    return tz;
  };

  return (
    <>
      {/* WiFi Status Display */}
      {wifiStatus && (
        <div className='mb-6 p-4 bg-[#2a2a2a] rounded border border-gray-700'>
          <div className='flex items-center justify-between'>
            <div>
              <div className='text-sm text-gray-400 mb-1'>Network Connection</div>
              <div className='flex items-center gap-2'>
                <div className={`w-3 h-3 rounded-full ${wifiStatus.connected ? 'bg-green-500' : 'bg-red-500'}`}></div>
                <span className='font-bold text-white'>
                  {wifiStatus.connected && wifiStatus.ssid
                    ? wifiStatus.ssid
                    : wifiStatus.mode === 'ap'
                    ? 'Setup Mode (AP)'
                    : 'Not Connected'}
                </span>
              </div>
              {wifiStatus.connected && wifiStatus.ip && <div className='text-xs text-gray-500 mt-1'>IP: {wifiStatus.ip}</div>}
            </div>
          </div>
        </div>
      )}

      <div className='mb-6'>
        <div className='mb-6 text-left relative'>
          <div className='flex items-center justify-between mb-2'>
            <label className={labelClass}>Search City / Location</label>
            <button
              type='button'
              onClick={async () => {
                try {
                  const response = await fetch('/api/location/system-default');
                  const data = await response.json();

                  if (data.found && data.location) {
                    selectLocation(data.location);
                  } else {
                    setTimeStatus({ type: 'error', message: data.message || 'Could not detect system location' });
                    setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
                  }
                } catch (err) {
                  setTimeStatus({ type: 'error', message: 'Error detecting system location: ' + err.message });
                  setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
                }
              }}
              className='text-sm px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors'>
              Use System Timezone
            </button>
          </div>
          <input
            type='text'
            value={searchTerm}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder='Type zip code or city name (e.g. 10001 or New York)'
            autoComplete='off'
            className={inputClass}
          />
          {searchResults.length > 0 && (
            <ul className='absolute w-full z-10 max-h-[200px] overflow-y-auto bg-[#333] border border-[#444] border-t-0 rounded-b shadow-lg list-none p-0 m-0'>
              {searchResults.map((result) => (
                <li
                  key={result.id}
                  onClick={() => selectLocation(result)}
                  className='p-3 cursor-pointer border-b border-[#444] last:border-0 hover:bg-[#444] transition-colors'>
                  <strong>{result.name}</strong>
                  <span className='text-xs text-gray-400 ml-2'>
                    {result.state} {result.zipcode ? `(${result.zipcode})` : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className='grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4 bg-[#2a2a2a] p-4 rounded border border-gray-700 mb-6'>
          <div className='flex flex-col'>
            <span className='text-xs text-gray-400 mb-1 uppercase'>Location</span>
            <span className='font-bold text-white'>
              {settings.city_name || 'Not Set'}
              {settings.state && `, ${settings.state}`}
            </span>
          </div>
          <div className='flex flex-col'>
            <span className='text-xs text-gray-400 mb-1 uppercase'>Timezone</span>
            <span className='font-bold text-white'>{formatTimezone(settings.timezone)}</span>
          </div>
          <div className='flex flex-col'>
            <span className='text-xs text-gray-400 mb-1 uppercase'>Coordinates</span>
            <span className='font-bold text-white'>
              {settings.latitude?.toFixed(4)}, {settings.longitude?.toFixed(4)}
            </span>
          </div>
        </div>

        <div className='mb-4 pt-4 border-t border-gray-700'>
          <label className={labelClass}>System Time & Date</label>

          <div className='mb-4'>
            <label className='block mb-2 text-sm text-gray-400'>System Timezone</label>
            <div className='flex gap-2'>
              <select
                value={systemTimezone || ''}
                onChange={async (e) => {
                  const newTimezone = e.target.value;
                  if (!newTimezone) return;

                  try {
                    const response = await fetch('/api/system/timezone', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ timezone: newTimezone }),
                    });

                    const data = await response.json();

                    if (data.success) {
                      setSystemTimezone(newTimezone);
                      setTimezoneStatus({ type: 'success', message: data.message });
                      // Also update the location timezone if it matches
                      if (settings.timezone === systemTimezone) {
                        saveGlobalSettings({ timezone: newTimezone });
                      }
                    } else {
                      setTimezoneStatus({ type: 'error', message: data.message || data.error || 'Failed to set timezone' });
                    }
                  } catch (err) {
                    setTimezoneStatus({ type: 'error', message: 'Error setting timezone: ' + err.message });
                  }

                  // Clear status after 5 seconds
                  setTimeout(() => setTimezoneStatus({ type: '', message: '' }), 5000);
                }}
                className={inputClass}>
                <option value=''>Select timezone...</option>
                {availableTimezones.map((tz) => (
                  <option key={tz.value} value={tz.value}>
                    {tz.label} {tz.region ? `(${tz.region})` : ''}
                  </option>
                ))}
              </select>
              {systemTimezone && (
                <button
                  type='button'
                  onClick={async () => {
                    try {
                      const response = await fetch('/api/location/system-default');
                      const data = await response.json();

                      if (data.found && data.location) {
                        selectLocation(data.location);
                        setTimezoneStatus({ type: 'success', message: 'Location updated from system timezone' });
                      } else {
                        setTimezoneStatus({ type: 'error', message: data.message || 'Could not detect location' });
                      }
                    } catch (err) {
                      setTimezoneStatus({ type: 'error', message: 'Error: ' + err.message });
                    }
                    setTimeout(() => setTimezoneStatus({ type: '', message: '' }), 5000);
                  }}
                  className='px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium transition-colors whitespace-nowrap'>
                  Use for Location
                </button>
              )}
            </div>
            {systemTimezone && <p className='text-xs text-gray-500 mt-1'>Current system timezone: {systemTimezone}</p>}
            {timezoneStatus.message && (
              <div
                className={`mt-2 p-2 rounded text-sm ${
                  timezoneStatus.type === 'success'
                    ? 'bg-green-900/30 text-green-300 border border-green-900/50'
                    : 'bg-red-900/30 text-red-300 border border-red-900/50'
                }`}>
                {timezoneStatus.message}
              </div>
            )}
          </div>

          <div className='mb-4'>
            <label className='block mb-2 text-sm text-gray-400'>Time Format</label>
            <select
              value={settings.time_format || '12h'}
              onChange={(e) => saveGlobalSettings({ time_format: e.target.value })}
              className={inputClass}>
              <option value='12h'>12-hour (3:45 PM)</option>
              <option value='24h'>24-hour (15:45)</option>
            </select>
            <p className='text-xs text-gray-500 mt-1'>Choose how times are displayed across all modules</p>
          </div>

          {currentTime && (
            <div className='mb-4 p-3 bg-[#1a1a1a] rounded border border-gray-800'>
              <div className='text-sm text-gray-400 mb-1'>Current System Time</div>
              <div className='text-lg font-bold text-white'>{currentTime.formatted}</div>
            </div>
          )}

          <div className='mb-4'>
            <div className='grid grid-cols-2 gap-3 mb-3'>
              <div>
                <label className='block mb-1 text-sm text-gray-400'>Date</label>
                <input type='date' value={manualDate} onChange={(e) => setManualDate(e.target.value)} className={inputClass} />
              </div>
              <div>
                <label className='block mb-1 text-sm text-gray-400'>Time</label>
                <input type='time' value={manualTime} onChange={(e) => setManualTime(e.target.value)} className={inputClass} step='1' />
              </div>
            </div>

            <div className='flex gap-2'>
              {wifiStatus?.connected && (
                <button
                  type='button'
                  onClick={async () => {
                    setTimeStatus({ type: '', message: '' });
                    try {
                      const response = await fetch('/api/system/time/sync', {
                        method: 'POST',
                      });

                      const data = await response.json();

                      if (data.success) {
                        setTimeStatus({ type: 'success', message: data.message || 'Time synchronized successfully' });
                        // Refresh current time
                        const timeResponse = await fetch('/api/system/time');
                        const timeData = await timeResponse.json();
                        if (timeData.datetime) {
                          setCurrentTime(timeData);
                          setManualDate(timeData.date);
                          setManualTime(timeData.time.substring(0, 5));
                        }
                      } else {
                        setTimeStatus({ type: 'error', message: data.message || data.error || 'Failed to sync time' });
                      }
                    } catch (err) {
                      setTimeStatus({ type: 'error', message: 'Error syncing time: ' + err.message });
                    }

                    // Clear status after 5 seconds
                    setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
                  }}
                  className='flex-1 py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium transition-colors'>
                  Auto Set Time
                </button>
              )}
              <button
                type='button'
                onClick={async () => {
                  if (!manualDate || !manualTime) {
                    setTimeStatus({ type: 'error', message: 'Please enter both date and time' });
                    return;
                  }

                  try {
                    // Convert time to HH:MM:SS format
                    const timeParts = manualTime.split(':');
                    const timeStr = timeParts.length === 2 ? `${manualTime}:00` : manualTime;

                    const response = await fetch('/api/system/time', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ date: manualDate, time: timeStr }),
                    });

                    const data = await response.json();

                    if (data.success) {
                      setTimeStatus({ type: 'success', message: data.message });
                      // Refresh current time
                      const timeResponse = await fetch('/api/system/time');
                      const timeData = await timeResponse.json();
                      if (timeData.datetime) {
                        setCurrentTime(timeData);
                      }
                    } else {
                      setTimeStatus({ type: 'error', message: data.message || data.error || 'Failed to set system time' });
                    }
                  } catch (err) {
                    setTimeStatus({ type: 'error', message: 'Error setting system time: ' + err.message });
                  }

                  // Clear status after 5 seconds
                  setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
                }}
                className={`${
                  wifiStatus?.connected ? 'flex-1' : 'w-full'
                } py-2 px-4 bg-green-600 hover:bg-green-700 text-white rounded font-medium transition-colors`}>
                Set System Time
              </button>
            </div>

            {timeStatus.message && (
              <div
                className={`mt-2 p-2 rounded text-sm ${
                  timeStatus.type === 'success'
                    ? 'bg-green-900/30 text-green-300 border border-green-900/50'
                    : 'bg-red-900/30 text-red-300 border border-red-900/50'
                }`}>
                {timeStatus.message}
              </div>
            )}

            <p className='text-xs text-gray-500 mt-2'>Manually set the system time and date when offline.</p>
          </div>
        </div>
      </div>

      <div className='mb-6'>
        <div className='mb-4'>
          <label className={labelClass}>Cutter Feed Lines</label>
          <input
            type='number'
            min='0'
            max='20'
            value={settings.cutter_feed_lines ?? 3}
            onChange={(e) => saveGlobalSettings({ cutter_feed_lines: parseInt(e.target.value) || 0 })}
            className={inputClass}
          />
          <p className='text-xs text-gray-500 mt-1'>
            Number of empty lines to add at the end of each print job to clear the cutter (default: 3)
          </p>
        </div>

        <div className='mb-4'>
          <label className={labelClass}>Maximum Print Lines</label>
          <input
            type='number'
            min='0'
            max='1000'
            value={settings.max_print_lines ?? 200}
            onChange={(e) => saveGlobalSettings({ max_print_lines: parseInt(e.target.value) || 0 })}
            className={inputClass}
          />
          <p className='text-xs text-gray-500 mt-1'>
            Maximum lines per print job to prevent endless prints. Set to 0 for no limit (default: 200)
          </p>
        </div>

        <div className='mb-4 pt-4 border-t border-gray-700'>
          <label className={labelClass}>WiFi Configuration</label>
          <button
            type='button'
            onClick={triggerAPMode}
            className='w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded font-bold transition-colors'>
            Reconfigure WiFi Network
          </button>
          <p className='text-xs text-gray-500 mt-2'>
            Activate setup mode to connect to a different WiFi network. Your device will create a temporary access point.
          </p>
        </div>
      </div>
    </>
  );
};

export default GeneralSettings;
