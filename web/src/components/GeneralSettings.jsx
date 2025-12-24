import React, { useState, useEffect } from 'react';
import { formatTimeForDisplay } from '../utils';
import WiFiIcon from '../assets/WiFiIcon';
import WiFiOffIcon from '../assets/WiFiOffIcon';


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
    'w-full p-3 text-base bg-white border-2 border-gray-300 rounded-lg text-black focus:border-black focus:outline-none box-border';
  const labelClass = 'block mb-2 font-bold text-black';

  // Create unique ink-like gradient for each card
  const inkGradients = [
    'radial-gradient(circle at 20% 30%, #000000 0%, #3a3a3a 25%, #000000 50%, #4a4a4a 75%, #000000 100%)',
    'radial-gradient(circle at 80% 70%, #000000 0%, #4a4a4a 20%, #000000 40%, #3a3a3a 60%, #000000 80%, #525252 100%)',
    'radial-gradient(ellipse at 50% 20%, #000000 0%, #3a3a3a 30%, #000000 60%, #4a4a4a 90%, #000000 100%)',
    'radial-gradient(circle at 70% 50%, #000000 0%, #525252 15%, #000000 35%, #3a3a3a 55%, #000000 75%, #4a4a4a 100%)',
    'radial-gradient(ellipse at 30% 80%, #000000 0%, #4a4a4a 25%, #000000 50%, #3a3a3a 75%, #000000 100%)',
  ];

  // System time state
  const [currentTime, setCurrentTime] = useState(null);
  const [manualDate, setManualDate] = useState('');
  const [manualTime, setManualTime] = useState('');
  const [timeStatus, setTimeStatus] = useState({ type: '', message: '' });
  const [useAutoTime, setUseAutoTime] = useState(false);

  // SSH management state
  const [sshStatus, setSshStatus] = useState(null);
  const [sshLoading, setSshLoading] = useState(false);
  const [sshMessage, setSshMessage] = useState({ type: '', message: '' });
  const [showPasswordChange, setShowPasswordChange] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);

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

  // Fetch SSH status on mount
  useEffect(() => {
    const fetchSshStatus = async () => {
      try {
        const response = await fetch('/api/system/ssh/status');
        const data = await response.json();
        setSshStatus(data);
      } catch (err) {
        console.error('Error fetching SSH status:', err);
      }
    };

    fetchSshStatus();
    // Refresh SSH status every 30 seconds
    const interval = setInterval(fetchSshStatus, 30000);
    return () => clearInterval(interval);
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
    <div className='space-y-4'>
      {/* WiFi Status Display */}
      {wifiStatus && (
        <div className='rounded-xl p-[4px] shadow-lg' style={{ background: inkGradients[0] }}>
          <div className='bg-bg-card rounded-lg p-4 flex flex-col'>
          <h3 className='font-bold text-black  text-lg tracking-tight mb-3'>Network</h3>
          <div className='flex items-center justify-between'>
            <div className='flex-1'>
              <div className='flex items-center gap-2'>
                {wifiStatus.connected ? (
                  <WiFiIcon className='w-4 h-4 text-blue-600' />
                ) : (
                  <WiFiOffIcon className='w-4 h-4 text-amber-700' />
                )}
                <span className='font-bold text-black '>
                  {wifiStatus.connected && wifiStatus.ssid
                    ? wifiStatus.ssid
                    : wifiStatus.mode === 'ap'
                    ? 'Setup Mode (AP)'
                    : 'Not Connected'}
                </span>
                <button type='button' onClick={triggerAPMode} className='text-xs text-blue-500 hover:text-black underline ml-2  cursor-pointer'>
                  Reset WiFi
                </button>
              </div>
              {wifiStatus.connected && wifiStatus.ip && <div className='text-xs text-gray-600 mt-1 '>IP: {wifiStatus.ip}</div>}
            </div>
          </div>
          </div>
        </div>
      )}

      {/* Location Settings */}
      <div className='rounded-xl p-[4px] shadow-lg' style={{ background: inkGradients[1] }}>
        <div className='bg-bg-card rounded-lg p-4 flex flex-col'>
        <h3 className='font-bold text-black  text-lg tracking-tight mb-3'>Location</h3>

        {/* Search for location */}
        <div className='mb-4 text-left relative'>
          <label className='block mb-2 text-sm text-gray-600  font-bold'>Search City / Location</label>
          <div className='relative'>
            <input
              type='text'
              value={searchTerm || ''}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder='Type city name (e.g. Boston, London, Tokyo)'
              autoComplete='off'
              className={inputClass}
            />
            {isSearching && (
              <div className='absolute right-3 top-1/2 transform -translate-y-1/2'>
                <div className='w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin'></div>
              </div>
            )}
          </div>
          {searchResults.length > 0 && (
            <ul className='absolute w-full z-10 max-h-[300px] overflow-y-auto bg-white border-2 border-gray-300 border-t-0 rounded-b-lg shadow-lg list-none p-0 m-0'>
              {searchResults.map((result) => (
                <li
                  key={result.id}
                  onClick={() => selectLocation(result)}
                  className='p-3 cursor-pointer border-b-2 border-gray-200 last:border-0 hover:bg-gray-100 transition-colors group'>
                  <div className='flex items-start justify-between'>
                    <div className='flex-1 min-w-0'>
                      <div className='flex items-center gap-2'>
                        <strong className='text-black transition-colors '>{result.name}</strong>
                        {result.population && result.population > 0 && (
                          <span className='text-xs text-gray-600 '>
                            {result.population >= 1000000
                              ? `${(result.population / 1000000).toFixed(1)}M`
                              : result.population >= 1000
                              ? `${(result.population / 1000).toFixed(0)}K`
                              : result.population}
                          </span>
                        )}
                        {result.country_code && result.country_code !== 'US' && (
                          <span className='text-xs px-1.5 py-0.5 bg-gray-100 text-gray-700 rounded  border border-gray-300'>{result.country_code}</span>
                        )}
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className='grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4 p-4 rounded-lg'>
          <div className='flex flex-row items-baseline gap-6'>
            <span className='text-xs text-gray-600 uppercase  font-bold w-20'>Location</span>
            <span className='font-bold text-black font-mono'>
              {settings.city_name || 'Not Set'}
              {settings.state && `, ${settings.state}`}
            </span>
          </div>
          <div className='flex flex-row items-baseline gap-6'>
            <span className='text-xs text-gray-600 uppercase  font-bold w-20'>Timezone</span>
            <span className='font-bold text-black font-mono'>{formatTimezone(settings.timezone)}</span>
          </div>
          <div className='flex flex-row items-baseline gap-6'>
            <span className='text-xs text-gray-600 uppercase  font-bold w-20'>Coordinates</span>
            <span className='font-bold text-black font-mono'>
              {settings.latitude?.toFixed(4) || 'N/A'}, {settings.longitude?.toFixed(4) || 'N/A'}
            </span>
          </div>
        </div>
        </div>
      </div>

      {/* Time Settings */}
      <div className='rounded-xl p-[4px] shadow-lg' style={{ background: inkGradients[2] }}>
        <div className='bg-bg-card rounded-lg p-4 flex flex-col'>
        <h3 className='font-bold text-black  text-lg tracking-tight mb-3'>Time Settings</h3>

        {/* Time Format */}
        <div className='mb-4'>
          <label className='block mb-2 text-sm text-gray-600  font-bold'>Time Format</label>
          <select
            value={settings.time_format || '12h'}
            onChange={(e) => saveGlobalSettings({ time_format: e.target.value })}
            className={inputClass}>
            <option value='12h'>12-hour (3:45 PM)</option>
            <option value='24h'>24-hour (15:45)</option>
          </select>
          <p className='text-xs text-gray-600 mt-1 '>Choose how times are displayed across all modules</p>
        </div>

        {/* Time Synchronization Mode */}
        <div className='mb-4'>
          <label className='block mb-3 text-sm font-medium text-black  font-bold'>Set Time</label>

          {/* Mode Selection - Tabs */}
          <div className='flex gap-0 mb-0'>
            <label
              className={`relative flex flex-col items-center px-4 py-2 border-t-2 border-l-2 border-r-2 cursor-pointer transition-all rounded-tl-lg ${
                !useAutoTime 
                  ? 'border-black border-b-0 bg-white z-10' 
                  : 'border-gray-300 border-b-2 border-b-black bg-white hover:border-black z-0'
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
              <span className={`text-sm font-medium  ${!useAutoTime ? 'text-black font-bold' : 'text-gray-600'}`}>Manual</span>
            </label>

            <label
              className={`relative flex flex-col items-center px-4 py-2 border-t-2 border-l-2 border-r-2 cursor-pointer transition-all rounded-tr-lg ${
                useAutoTime 
                  ? 'border-black border-b-0 bg-white z-10' 
                  : 'border-gray-300 border-b-2 border-b-black bg-white hover:border-black z-0'
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
              <div className="flex items-baseline justify-center gap-1.5">
                <WiFiIcon className={`w-3 h-3 flex-shrink-0 ${useAutoTime ? 'text-black' : 'text-gray-600'}`} style={{ transform: 'translateY(0.125rem)' }} />
                <span className={`text-sm font-medium  ${useAutoTime ? 'text-black font-bold' : 'text-gray-600'}`}>Automatic</span>
              </div>
            </label>
          </div>

          {/* Automatic Mode Actions */}
          {useAutoTime && (
            <div className='p-4 border-2 border-black rounded-b-lg -mt-[2px]'>
              {wifiStatus?.connected ? (
                <div>
                  {currentTime && (
                    <div className='mb-3 p-3 bg-gray-50 border-2 border-gray-300 rounded-lg'>
                      <div className='text-xs text-gray-600 mb-1 uppercase font-bold'>Current Time</div>
                      <div className='flex items-center gap-2'>
                        <div className='text-lg font-bold text-black'>
                          {currentTime.date} {formatTimeForDisplay(currentTime.time, settings.time_format || '12h')}
                        </div>
                        <WiFiIcon className='w-3.5 h-3.5 text-blue-600' />
                      </div>
                    </div>
                  )}
                  <button
                    type='button'
                    onClick={syncTimeAutomatically}
                    className='w-full py-2 px-4 bg-transparent border-2 border-black text-black rounded-lg  font-bold hover:bg-black hover:text-white transition-all cursor-pointer'>
                    Sync Now
                  </button>
                </div>
              ) : (
                <div>
                  <p className='text-sm font-bold text-black mb-2 '>Not Syncing</p>
                  <p className='text-sm text-yellow-700 mb-3 '>
                    Internet connection required for automatic time synchronization. Connect to WiFi or use manual mode.
                  </p>
                  {currentTime && (
                    <div className='p-3 bg-gray-50 border-2 border-gray-300 rounded-lg'>
                      <div className='text-xs text-gray-600 mb-1 uppercase font-bold'>Current Time</div>
                      <div className='flex items-center gap-2'>
                        <div className='text-lg font-bold text-black'>
                          {currentTime.date} {formatTimeForDisplay(currentTime.time, settings.time_format || '12h')}
                        </div>
                        <WiFiOffIcon className='w-3.5 h-3.5 text-amber-700' />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Manual Mode Inputs */}
          {!useAutoTime && (
            <div className='p-4 border-2 border-black rounded-b-lg -mt-[2px]'>
              <div className='grid grid-cols-1 min-[340px]:grid-cols-2 gap-3 mb-3'>
                <div>
                  <label className='block mb-2 text-sm text-black  font-bold'>Date</label>
                  <input
                    type='date'
                    value={manualDate}
                    onChange={(e) => setManualDate(e.target.value)}
                    className='w-full py-3 px-2 text-base bg-white border-2 border-gray-300 rounded-lg text-black focus:border-black focus:outline-none box-border '
                  />
                </div>
                <div>
                  <label className='block mb-2 text-sm text-black  font-bold'>Time</label>
                  <input
                    type='time'
                    value={manualTime || ''}
                    onChange={(e) => {
                      const value = e.target.value;
                      setManualTime(value);
                      console.log('Time input changed:', value, 'Type:', typeof value);
                    }}
                    className='w-full py-3 px-2 text-base bg-white border-2 border-gray-300 rounded-lg text-black focus:border-black focus:outline-none box-border '
                    step='1'
                    required
                  />
                </div>
              </div>
              <button
                type='button'
                onClick={setTimeManually}
                className='w-full py-2.5 px-4 bg-transparent border-2 border-black text-black rounded-lg  font-bold hover:bg-white transition-all cursor-pointer'>
                Set System Time
              </button>
              <p className='text-xs text-gray-600 mt-2 text-center '>Use this when offline or to set a specific time</p>
            </div>
          )}

          {/* Status Messages */}
          {timeStatus.message && (
            <div
              className={`mt-4 p-3 rounded-lg text-sm  border-2 ${
                timeStatus.type === 'success'
                  ? 'bg-gray-100 text-black border-black'
                  : 'bg-white text-black border-black border-dashed'
              }`}>
              {timeStatus.type === 'error' && <span className="font-bold mr-2">ERROR:</span>}
              {timeStatus.message}
            </div>
          )}
        </div>
        </div>
      </div>

      {/* Printer Settings */}
      <div className='rounded-xl p-[4px] shadow-lg' style={{ background: inkGradients[3] }}>
        <div className='bg-bg-card rounded-lg p-4 flex flex-col'>
        <h3 className='font-bold text-black  text-lg tracking-tight mb-3'>Printer Settings</h3>
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
          <p className='text-xs text-gray-600 mt-1 '>
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
          <p className='text-xs text-gray-600 mt-1 '>
            Maximum lines per print job to prevent endless prints. Set to 0 for no limit (default: 200)
          </p>
        </div>
        </div>
      </div>

      {/* SSH Management */}
      <div className='rounded-xl p-[4px] shadow-lg' style={{ background: inkGradients[4] }}>
        <div className='bg-bg-card rounded-lg p-4 flex flex-col'>
        <h3 className='font-bold text-black  text-lg tracking-tight mb-3'>SSH Access</h3>
        <p className='text-sm text-gray-600 mb-4 '>
          Manage SSH (Secure Shell) access to your PC-1 device. SSH allows advanced users to access the device via command line.
        </p>

        {sshStatus && sshStatus.available ? (
          <div className='space-y-4'>
            {/* SSH Status */}
            <div className='p-4 border-2 border-gray-300 rounded-lg'>
              <div className='flex items-center justify-between mb-2'>
                <span className='text-sm font-medium text-black  font-bold'>SSH Service</span>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-medium  border-2 ${
                    sshStatus.enabled && sshStatus.active
                      ? 'bg-black text-white border-black'
                      : sshStatus.enabled
                      ? 'bg-gray-200 text-black border-gray-400'
                      : 'bg-white text-gray-500 border-gray-300'
                  }`}>
                  {sshStatus.enabled && sshStatus.active
                    ? 'Enabled & Active'
                    : sshStatus.enabled
                    ? 'Enabled'
                    : sshStatus.active
                    ? 'Active'
                    : 'Disabled'}
                </span>
              </div>
              {sshStatus.username && (
                <p className='text-xs text-gray-600 mt-1 '>
                  Username: <span className='text-black '>{sshStatus.username}</span>
                </p>
              )}
              {sshStatus.enabled && (
                <p className='text-xs text-gray-600 mt-1 '>
                  Connect via: <span className='text-black '>ssh {sshStatus.username || 'admin'}@pc-1.local</span>
                </p>
              )}
            </div>

            {/* Enable/Disable SSH */}
            <div className='flex gap-3'>
              {!sshStatus.enabled ? (
                <button
                  type='button'
                  onClick={async () => {
                    setSshLoading(true);
                    setSshMessage({ type: '', message: '' });
                    try {
                      const response = await fetch('/api/system/ssh/enable', { method: 'POST' });
                      const data = await response.json();
                      if (data.success) {
                        setSshMessage({ type: 'success', message: data.message });
                        // Refresh status
                        const statusResponse = await fetch('/api/system/ssh/status');
                        const statusData = await statusResponse.json();
                        setSshStatus(statusData);
                      } else {
                        setSshMessage({ type: 'error', message: data.message || 'Failed to enable SSH' });
                      }
                    } catch (err) {
                      setSshMessage({ type: 'error', message: 'Error enabling SSH' });
                    } finally {
                      setSshLoading(false);
                      setTimeout(() => setSshMessage({ type: '', message: '' }), 5000);
                    }
                  }}
                  disabled={sshLoading}
                  className='flex-1 py-2.5 px-4 bg-transparent border-2 border-black text-black disabled:border-gray-300 disabled:text-gray-400 disabled:cursor-not-allowed rounded-lg  font-bold hover:bg-black hover:text-white transition-all cursor-pointer'>
                  {sshLoading ? 'Enabling...' : 'Enable SSH'}
                </button>
              ) : (
                <button
                  type='button'
                  onClick={async () => {
                    if (!confirm('Are you sure you want to disable SSH? You may lose remote access to the device.')) {
                      return;
                    }
                    setSshLoading(true);
                    setSshMessage({ type: '', message: '' });
                    try {
                      const response = await fetch('/api/system/ssh/disable', { method: 'POST' });
                      const data = await response.json();
                      if (data.success) {
                        setSshMessage({ type: 'success', message: data.message });
                        // Refresh status
                        const statusResponse = await fetch('/api/system/ssh/status');
                        const statusData = await statusResponse.json();
                        setSshStatus(statusData);
                      } else {
                        setSshMessage({ type: 'error', message: data.message || 'Failed to disable SSH' });
                      }
                    } catch (err) {
                      setSshMessage({ type: 'error', message: 'Error disabling SSH' });
                    } finally {
                      setSshLoading(false);
                      setTimeout(() => setSshMessage({ type: '', message: '' }), 5000);
                    }
                  }}
                  disabled={sshLoading}
                  className='flex-1 py-2.5 px-4 bg-transparent border-2 border-black text-black disabled:border-gray-300 disabled:text-gray-400 disabled:cursor-not-allowed rounded-lg  font-bold hover:bg-black hover:text-white transition-all cursor-pointer'>
                  {sshLoading ? 'Disabling...' : 'Disable SSH'}
                </button>
              )}
              {sshStatus.enabled && (
                <button
                  type='button'
                  onClick={() => setShowPasswordChange(!showPasswordChange)}
                  className='flex-1 py-2.5 px-4 bg-transparent border-2 border-gray-400 text-black rounded-lg  font-bold hover:border-black hover:bg-gray-100 transition-all cursor-pointer'>
                  {showPasswordChange ? 'Cancel' : 'Change Password'}
                </button>
              )}
            </div>

            {/* Change Password Form */}
            {showPasswordChange && sshStatus.enabled && (
              <div className='p-4 border-2 border-gray-300 rounded-lg'>
                <h4 className='text-sm font-medium text-black mb-3  font-bold'>Change SSH Password</h4>
                <div className='space-y-3'>
                  <div>
                    <label className='block mb-2 text-sm text-black  font-bold'>New Password</label>
                    <input
                      type='password'
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder='Minimum 8 characters'
                      className={inputClass}
                      minLength={8}
                    />
                  </div>
                  <div>
                    <label className='block mb-2 text-sm text-black  font-bold'>Confirm Password</label>
                    <input
                      type='password'
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder='Re-enter password'
                      className={inputClass}
                      minLength={8}
                    />
                  </div>
                  <button
                    type='button'
                    onClick={async () => {
                      if (!newPassword || newPassword.length < 8) {
                        setSshMessage({ type: 'error', message: 'Password must be at least 8 characters' });
                        setTimeout(() => setSshMessage({ type: '', message: '' }), 5000);
                        return;
                      }
                      if (newPassword !== confirmPassword) {
                        setSshMessage({ type: 'error', message: 'Passwords do not match' });
                        setTimeout(() => setSshMessage({ type: '', message: '' }), 5000);
                        return;
                      }
                      setChangingPassword(true);
                      setSshMessage({ type: '', message: '' });
                      try {
                        const response = await fetch('/api/system/ssh/password', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ new_password: newPassword }),
                        });
                        const data = await response.json();
                        if (data.success) {
                          setSshMessage({ type: 'success', message: data.message });
                          setNewPassword('');
                          setConfirmPassword('');
                          setShowPasswordChange(false);
                        } else {
                          setSshMessage({ type: 'error', message: data.message || 'Failed to change password' });
                        }
                      } catch (err) {
                        setSshMessage({ type: 'error', message: 'Error changing password' });
                      } finally {
                        setChangingPassword(false);
                        setTimeout(() => setSshMessage({ type: '', message: '' }), 5000);
                      }
                    }}
                    disabled={changingPassword || !newPassword || !confirmPassword}
                    className='w-full py-2.5 px-4 bg-transparent border-2 border-black text-black disabled:border-gray-300 disabled:text-gray-400 disabled:cursor-not-allowed rounded-lg  font-bold hover:bg-black hover:text-white transition-all cursor-pointer'>
                    {changingPassword ? 'Changing...' : 'Change Password'}
                  </button>
                </div>
              </div>
            )}

            {/* SSH Status Messages */}
            {sshMessage.message && (
              <div
                className={`p-3 rounded-lg text-sm  border-2 ${
                  sshMessage.type === 'success'
                    ? 'bg-gray-100 text-black border-black'
                    : 'bg-white text-black border-black border-dashed'
                }`}>
                {sshMessage.type === 'error' && <span className="font-bold mr-2">ERROR:</span>}
                {sshMessage.message}
              </div>
            )}
          </div>
        ) : (
          <div className='p-4 border-2 border-gray-300 rounded-lg'>
            <p className='text-sm text-gray-500 '>SSH isn't available in testing mode</p>
          </div>
        )}
        </div>
      </div>
    </div>
  );
};

export default GeneralSettings;
