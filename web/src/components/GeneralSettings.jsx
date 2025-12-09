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
  const [useAutoTime, setUseAutoTime] = useState(true);

  // Location state
  const [locationStatus, setLocationStatus] = useState({ type: '', message: '' });

  // Fetch current system time on mount and periodically
  useEffect(() => {
    const fetchTime = async () => {
      try {
        const response = await fetch('/api/system/time');
        const data = await response.json();
        if (data.datetime) {
          setCurrentTime(data);
          // Pre-fill manual inputs with current time only once
          if (!manualDate) setManualDate(data.date);
          if (!manualTime) setManualTime(data.time.substring(0, 5)); // HH:MM format for input
        }
      } catch (err) {
        console.error('Error fetching system time:', err);
      }
    };

    fetchTime();
    const interval = setInterval(fetchTime, 1000); // Update every second
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

  // Set location from system
  const setLocationFromSystem = async () => {
    setLocationStatus({ type: '', message: '' });
    try {
      const response = await fetch('/api/location/system-default');
      const data = await response.json();

      if (data.found && data.location) {
        selectLocation(data.location);
        setLocationStatus({ type: 'success', message: 'Location set from system timezone' });
        setTimeout(() => setLocationStatus({ type: '', message: '' }), 5000);
      } else {
        setLocationStatus({ type: 'error', message: data.message || 'Could not detect system location' });
        setTimeout(() => setLocationStatus({ type: '', message: '' }), 5000);
      }
    } catch (err) {
      setLocationStatus({ type: 'error', message: 'Error detecting system location: ' + err.message });
      setTimeout(() => setLocationStatus({ type: '', message: '' }), 5000);
    }
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
    if (!manualDate || !manualTime) {
      setTimeStatus({ type: 'error', message: 'Please enter both date and time' });
      setTimeout(() => setTimeStatus({ type: '', message: '' }), 5000);
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
        setUseAutoTime(false);
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

        {/* API Search Toggle */}
        <div className='mb-4 p-3 bg-[#2a2a2a] rounded border border-gray-700'>
          <div className='flex items-center justify-between mb-2'>
            <div>
              <label className='block text-sm font-medium text-gray-200 mb-1'>Enable Online Location Search</label>
              <p className='text-xs text-gray-400'>Use OpenStreetMap API for better search results. Requires internet connection.</p>
            </div>
            <label className='relative inline-flex items-center cursor-pointer'>
              <input
                type='checkbox'
                checked={settings.use_api_location_search || false}
                onChange={(e) => saveGlobalSettings({ use_api_location_search: e.target.checked })}
                className='sr-only peer'
              />
              <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>
          {settings.use_api_location_search && (
            <div className='mt-2 p-2 bg-blue-900/20 border border-blue-800/50 rounded text-xs text-blue-300'>
              <strong>Note:</strong> Online search uses OpenStreetMap Nominatim API. Your search queries will be sent to their servers. This
              feature requires an active internet connection.
            </div>
          )}
        </div>

        {/* Search for location */}
        <div className='mb-4 text-left relative'>
          <label className='block mb-2 text-sm text-gray-400'>Search City / Location</label>
          <div className='relative'>
            <input
              type='text'
              value={searchTerm || ''}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder={
                settings.use_api_location_search
                  ? 'Type city name (e.g. Malden, London, Tokyo)'
                  : 'Type city name (offline global database)'
              }
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

        {/* Set from system timezone */}
        <div className='mb-4'>
          <button
            type='button'
            onClick={setLocationFromSystem}
            className='w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium transition-colors'>
            Set Location from System Timezone
          </button>
          <p className='text-xs text-gray-500 mt-1'>
            Use the Raspberry Pi's system timezone to automatically set your location (defaults to major city in timezone)
          </p>
        </div>

        {locationStatus.message && (
          <div
            className={`mb-4 p-2 rounded text-sm ${
              locationStatus.type === 'success'
                ? 'bg-green-900/30 text-green-300 border border-green-900/50'
                : 'bg-red-900/30 text-red-300 border border-red-900/50'
            }`}>
            {locationStatus.message}
          </div>
        )}

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

        {/* Current System Time */}
        {currentTime && (
          <div className='mb-4 p-3 bg-[#1a1a1a] rounded border border-gray-800'>
            <div className='text-sm text-gray-400 mb-1'>Current System Time</div>
            <div className='text-lg font-bold text-white'>{currentTime.formatted}</div>
          </div>
        )}

        {/* Time Control */}
        <div className='mb-4'>
          <div className='flex items-center gap-2 mb-3'>
            <input
              type='checkbox'
              id='useAutoTime'
              checked={useAutoTime}
              onChange={(e) => {
                setUseAutoTime(e.target.checked);
                if (e.target.checked && wifiStatus?.connected) {
                  syncTimeAutomatically();
                }
              }}
              className='w-4 h-4'
            />
            <label htmlFor='useAutoTime' className='text-sm text-gray-300'>
              Use automatic time synchronization
            </label>
          </div>

          {!useAutoTime && (
            <div className='mb-3'>
              <div className='grid grid-cols-2 gap-3'>
                <div>
                  <label className='block mb-1 text-sm text-gray-400'>Date</label>
                  <input type='date' value={manualDate} onChange={(e) => setManualDate(e.target.value)} className={inputClass} />
                </div>
                <div>
                  <label className='block mb-1 text-sm text-gray-400'>Time</label>
                  <input type='time' value={manualTime} onChange={(e) => setManualTime(e.target.value)} className={inputClass} step='1' />
                </div>
              </div>
              <button
                type='button'
                onClick={setTimeManually}
                className='mt-2 w-full py-2 px-4 bg-green-600 hover:bg-green-700 text-white rounded font-medium transition-colors'>
                Set System Time
              </button>
            </div>
          )}

          {useAutoTime && wifiStatus?.connected && (
            <button
              type='button'
              onClick={syncTimeAutomatically}
              className='w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium transition-colors'>
              Sync Time Now
            </button>
          )}

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

          {!useAutoTime && <p className='text-xs text-gray-500 mt-2'>Manually set the system time and date when offline.</p>}
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
