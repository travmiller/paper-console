import React, { useState, useEffect } from 'react';

const GeneralSettings = ({
  searchTerm,
  searchResults,
  isSearching,
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
  const [useAutoTime, setUseAutoTime] = useState(false);

  // Fetch current system time on mount and periodically
  useEffect(() => {
    const fetchTime = async () => {
      try {
        const response = await fetch('/api/system/time');
        const data = await response.json();
        if (data.datetime) {
          setCurrentTime(data);
          // Pre-fill manual inputs with current time if they're empty
          setManualDate((prev) => prev || data.date);
          setManualTime((prev) => prev || data.time.substring(0, 5)); // HH:MM format for input
        }
      } catch (err) {
        console.error('Error fetching system time:', err);
      }
    };

    fetchTime();
    const interval = setInterval(fetchTime, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, []); // Only run on mount

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

  // Auto sync time
  const syncTimeAutomatically = async () => {
    if (!wifiStatus?.connected) {
      setTimeStatus({ type: 'error', message: 'Internet connection required for automatic time sync' });
      setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
      return;
    }

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

    setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
  };

  // Set time manually
  const setTimeManually = async () => {
    // Validate inputs
    if (!manualDate || !manualTime) {
      setTimeStatus({ type: 'error', message: 'Please enter both date and time' });
      setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
      return;
    }

    // Normalize and validate date format (YYYY-MM-DD)
    const normalizedDate = manualDate.trim();
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    if (!dateRegex.test(normalizedDate)) {
      setTimeStatus({ type: 'error', message: 'Invalid date format. Please use YYYY-MM-DD format.' });
      setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
      return;
    }

    // Normalize and validate time format
    // HTML5 time input should return HH:MM format
    let normalizedTime = String(manualTime || '').trim();

    // Check if it's empty
    if (!normalizedTime || normalizedTime.length === 0) {
      setTimeStatus({ type: 'error', message: 'Please enter a valid time' });
      setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
      return;
    }

    // HTML5 time input returns HH:MM format (e.g., "14:30")
    // Accept both HH:MM and HH:MM:SS formats
    const timeRegex = /^(\d{1,2}):(\d{2})(:(\d{2}))?$/;
    const timeMatch = normalizedTime.match(timeRegex);

    if (!timeMatch) {
      console.error('Time validation failed:', {
        normalizedTime,
        original: manualTime,
        type: typeof manualTime,
        length: normalizedTime.length,
        charCodes: normalizedTime.split('').map((c) => `${c}(${c.charCodeAt(0)})`),
      });
      setTimeStatus({ type: 'error', message: `Invalid time format: "${normalizedTime}". Please use HH:MM format (e.g., 14:30).` });
      setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
      return;
    }

    // Extract and normalize time components
    const hours = timeMatch[1].padStart(2, '0');
    const minutes = timeMatch[2];
    const seconds = timeMatch[4] || '00';

    // Validate ranges
    const hourNum = parseInt(hours, 10);
    const minNum = parseInt(minutes, 10);
    const secNum = parseInt(seconds, 10);

    if (isNaN(hourNum) || hourNum < 0 || hourNum > 23) {
      setTimeStatus({ type: 'error', message: `Invalid hours: ${hours}. Must be between 00 and 23.` });
      setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
      return;
    }

    if (isNaN(minNum) || minNum < 0 || minNum > 59) {
      setTimeStatus({ type: 'error', message: `Invalid minutes: ${minutes}. Must be between 00 and 59.` });
      setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
      return;
    }

    if (isNaN(secNum) || secNum < 0 || secNum > 59) {
      setTimeStatus({ type: 'error', message: `Invalid seconds: ${seconds}. Must be between 00 and 59.` });
      setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
      return;
    }

    // Format as HH:MM:SS
    const normalizedTimeStr = `${hours}:${minutes}:${seconds}`;

    setTimeStatus({ type: '', message: '' }); // Clear previous status

    try {
      console.log('Setting time:', { date: normalizedDate, time: normalizedTimeStr });
      const response = await fetch('/api/system/time', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: normalizedDate, time: normalizedTimeStr }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        setTimeStatus({ type: 'success', message: data.message || 'System time set successfully' });
        setUseAutoTime(false); // Ensure we're in manual mode
        // Refresh current time after a short delay to verify it was set correctly
        setTimeout(async () => {
          try {
            const timeResponse = await fetch('/api/system/time');
            const timeData = await timeResponse.json();
            if (timeData.datetime) {
              setCurrentTime(timeData);
              // Update manual inputs to match what was actually set
              setManualDate(timeData.date);
              setManualTime(timeData.time.substring(0, 5));
            }
          } catch (err) {
            console.error('Error refreshing time:', err);
          }
        }, 1000); // Increased delay to ensure time is set before checking
      } else {
        setTimeStatus({
          type: 'error',
          message: data.message || data.error || 'Failed to set system time. The application may need sudo privileges.',
        });
      }
    } catch (err) {
      console.error('Error setting system time:', err);
      setTimeStatus({
        type: 'error',
        message: `Error setting system time: ${err.message}. Make sure the backend is running and has proper permissions.`,
      });
    }

    setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
  };

  return (
    <>
      {/* WiFi Status Display */}
      {wifiStatus && (
        <div className='mb-6 p-4 bg-[#2a2a2a] rounded border border-gray-700'>
          <div className='flex items-center justify-between'>
            <div className='flex-1'>
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
                <button type='button' onClick={triggerAPMode} className='text-xs text-blue-400 hover:text-blue-300 underline ml-2'>
                  Reset WiFi
                </button>
              </div>
              {wifiStatus.connected && wifiStatus.ip && <div className='text-xs text-gray-500 mt-1'>IP: {wifiStatus.ip}</div>}
            </div>
          </div>
        </div>
      )}

      {/* Location Settings */}
      <div className='mb-6'>
        <label className={labelClass}>Location</label>

        {/* Search for location */}
        <div className='mb-4 text-left relative'>
          <label className='block mb-2 text-sm text-gray-400'>Search City / Location</label>
          <div className='relative'>
            <input
              type='text'
              value={searchTerm || ''}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder='Type city name (e.g. Malden, London, Tokyo)'
              autoComplete='off'
              className={inputClass}
            />
            {isSearching && (
              <div className='absolute right-3 top-1/2 transform -translate-y-1/2'>
                <div className='w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin'></div>
              </div>
            )}
          </div>
          {searchResults.length > 0 && (
            <ul className='absolute w-full z-10 max-h-[300px] overflow-y-auto bg-[#333] border border-[#444] border-t-0 rounded-b shadow-lg list-none p-0 m-0'>
              {searchResults.map((result) => (
                <li
                  key={result.id}
                  onClick={() => selectLocation(result)}
                  className='p-3 cursor-pointer border-b border-[#444] last:border-0 hover:bg-[#444] transition-colors group'>
                  <div className='flex items-start justify-between'>
                    <div className='flex-1 min-w-0'>
                      <div className='flex items-center gap-2'>
                        <strong className='text-white group-hover:text-blue-300 transition-colors'>{result.name}</strong>
                        {result.population && result.population > 0 && (
                          <span className='text-xs text-gray-400'>
                            {result.population >= 1000000
                              ? `${(result.population / 1000000).toFixed(1)}M`
                              : result.population >= 1000
                              ? `${(result.population / 1000).toFixed(0)}K`
                              : result.population}
                          </span>
                        )}
                        {result.country_code && result.country_code !== 'US' && (
                          <span className='text-xs px-1.5 py-0.5 bg-blue-900/30 text-blue-300 rounded'>{result.country_code}</span>
                        )}
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className='grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4 bg-[#2a2a2a] p-4 rounded border border-gray-700'>
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
              {settings.latitude?.toFixed(4) || 'N/A'}, {settings.longitude?.toFixed(4) || 'N/A'}
            </span>
          </div>
        </div>
      </div>

      {/* Time Settings */}
      <div className='mb-6 pt-4 border-t border-gray-700'>
        <label className={labelClass}>Time Settings</label>

        {/* Time Format */}
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

        {/* Current System Time Display */}
        {currentTime && (
          <div className='mb-6 p-4 bg-[#1a1a1a] rounded-lg border border-gray-800'>
            <div className='flex items-center justify-between'>
              <div>
                <div className='text-xs text-gray-400 mb-1 uppercase tracking-wide'>Current System Time</div>
                <div className='text-2xl font-bold text-white font-mono'>{currentTime.formatted}</div>
              </div>
              <div
                className={`w-3 h-3 rounded-full ${useAutoTime && wifiStatus?.connected ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`}
                title={useAutoTime && wifiStatus?.connected ? 'Auto-sync enabled' : 'Manual mode'}></div>
            </div>
          </div>
        )}

        {/* Time Synchronization Mode */}
        <div className='mb-4'>
          <label className='block mb-3 text-sm font-medium text-gray-300'>Set Time</label>

          {/* Mode Selection - Radio Buttons */}
          <div className='grid grid-cols-2 gap-3 mb-4'>
            <label
              className={`relative flex flex-col items-center p-4 rounded-lg border-2 cursor-pointer transition-all ${
                !useAutoTime ? 'border-green-500 bg-green-900/20' : 'border-gray-700 bg-[#2a2a2a] hover:border-gray-600'
              }`}>
              <input
                type='radio'
                name='timeMode'
                checked={!useAutoTime}
                onChange={async () => {
                  setUseAutoTime(false);
                  // When switching to manual, disable NTP sync to prevent override
                  try {
                    // Disable NTP sync when switching to manual mode
                    await fetch('/api/system/time/sync/disable', { method: 'POST' }).catch(() => {
                      // Ignore errors - the backend will handle NTP disable when setting time
                    });
                  } catch (err) {
                    // Ignore errors
                  }
                  // When switching to manual, ensure inputs are populated
                  if (currentTime) {
                    if (!manualDate && currentTime.date) {
                      setManualDate(currentTime.date);
                    }
                    if (!manualTime && currentTime.time) {
                      setManualTime(currentTime.time.substring(0, 5));
                    }
                  }
                }}
                className='sr-only'
              />
              <span className={`text-sm font-medium ${!useAutoTime ? 'text-green-300' : 'text-gray-400'}`}>Manual</span>
              <span className='text-xs text-gray-500 mt-1 text-center'>Set time manually</span>
            </label>

            <label
              className={`relative flex flex-col items-center p-4 rounded-lg border-2 cursor-pointer transition-all ${
                useAutoTime ? 'border-blue-500 bg-blue-900/20' : 'border-gray-700 bg-[#2a2a2a] hover:border-gray-600'
              }`}>
              <input
                type='radio'
                name='timeMode'
                checked={useAutoTime}
                onChange={() => {
                  setUseAutoTime(true);
                  if (wifiStatus?.connected) {
                    syncTimeAutomatically();
                  }
                }}
                className='sr-only'
              />
              <span className={`text-sm font-medium ${useAutoTime ? 'text-blue-300' : 'text-gray-400'}`}>Automatic</span>
              <span className='text-xs text-gray-500 mt-1 text-center'>Sync with NTP servers</span>
            </label>
          </div>

          {/* Automatic Mode Actions */}
          {useAutoTime && (
            <div className='p-4 bg-blue-900/10 border border-blue-800/30 rounded-lg'>
              {wifiStatus?.connected ? (
                <div>
                  <p className='text-sm text-gray-300 mb-3'>
                    Time will automatically sync with NTP servers when connected to the internet.
                  </p>
                  <button
                    type='button'
                    onClick={syncTimeAutomatically}
                    className='w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium transition-colors'>
                    Sync Now
                  </button>
                </div>
              ) : (
                <p className='text-sm text-amber-300'>
                  ⚠️ Internet connection required for automatic time synchronization. Connect to WiFi or use manual mode.
                </p>
              )}
            </div>
          )}

          {/* Manual Mode Inputs */}
          {!useAutoTime && (
            <div className='p-4 bg-green-900/10 border border-green-800/30 rounded-lg'>
              <div className='grid grid-cols-2 gap-3 mb-3'>
                <div>
                  <label className='block mb-2 text-sm text-gray-300'>Date</label>
                  <input type='date' value={manualDate} onChange={(e) => setManualDate(e.target.value)} className={inputClass} />
                </div>
                <div>
                  <label className='block mb-2 text-sm text-gray-300'>Time</label>
                  <input
                    type='time'
                    value={manualTime || ''}
                    onChange={(e) => {
                      const value = e.target.value;
                      setManualTime(value);
                      console.log('Time input changed:', value, 'Type:', typeof value);
                    }}
                    className={inputClass}
                    step='1'
                    required
                  />
                </div>
              </div>
              <button
                type='button'
                onClick={setTimeManually}
                className='w-full py-2.5 px-4 bg-green-600 hover:bg-green-700 text-white rounded font-medium transition-colors'>
                Set System Time
              </button>
              <p className='text-xs text-gray-400 mt-2 text-center'>Use this when offline or to set a specific time</p>
            </div>
          )}

          {/* Status Messages */}
          {timeStatus.message && (
            <div
              className={`mt-4 p-3 rounded-lg text-sm ${
                timeStatus.type === 'success'
                  ? 'bg-green-900/30 text-green-300 border border-green-900/50'
                  : 'bg-red-900/30 text-red-300 border border-red-900/50'
              }`}>
              {timeStatus.message}
            </div>
          )}
        </div>
      </div>

      {/* Printer Settings */}
      <div className='mb-6 pt-4 border-t border-gray-700'>
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
      </div>
    </>
  );
};

export default GeneralSettings;
