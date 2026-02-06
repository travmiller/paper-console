import React, { useState, useEffect } from 'react';
import { formatTimeForDisplay } from '../utils';
import { INK_GRADIENTS } from '../constants';
import PrimaryButton from './PrimaryButton';
import WiFiIcon from '../assets/WiFiIcon';
import WiFiOffIcon from '../assets/WiFiOffIcon';
import LocationSearch from './widgets/LocationSearch';


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
  const inputClass = 'w-full p-3 text-base border-2 border-gray-300 rounded-lg focus:outline-none box-border';
  const labelClass = 'block mb-2 font-bold';

  // Use shared ink gradients
  const inkGradients = INK_GRADIENTS;

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

  // Update check state
  const [updateStatus, setUpdateStatus] = useState(null);
  const [checkingUpdates, setCheckingUpdates] = useState(false);
  const [installingUpdate, setInstallingUpdate] = useState(false);
  const [updateMessage, setUpdateMessage] = useState({ type: '', message: '' });
  const [currentVersion, setCurrentVersion] = useState(null);
  const [updateProgress, setUpdateProgress] = useState({ stage: '', progress: 0 });

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

  // Load saved time sync mode preference
  useEffect(() => {
    // Only initialize if settings are actually loaded (not empty initial state)
    // Check if settings has meaningful data (like timezone or city_name)
    if (settings && (settings.timezone || settings.city_name || settings.time_sync_mode !== undefined)) {
      const syncMode = settings.time_sync_mode || 'manual';
      console.log('[TimeSync] Loading preference:', { syncMode, time_sync_mode: settings.time_sync_mode });
      setUseAutoTime(syncMode === 'automatic');
    }
  }, [settings]);

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

  // Fetch current version on mount
  useEffect(() => {
    const fetchCurrentVersion = async () => {
      try {
        const response = await fetch('/api/system/version');
        const data = await response.json();
        if (data.version) {
          setCurrentVersion(data.version);
        }
      } catch (err) {
        console.error('Error fetching current version:', err);
      }
    };

    fetchCurrentVersion();
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
      {/* Update Check */}
      <div className='rounded-xl p-[4px] shadow-lg' style={{ background: inkGradients[5] || inkGradients[0] }}>
        <div className='bg-bg-card rounded-lg p-4 flex flex-col'>
          <h3 className='font-bold text-black  text-lg tracking-tight mb-3'>Updates</h3>
          <p className='text-sm text-gray-600 mb-4 '>
            Check for software updates and keep your PC-1 running the latest version.
          </p>

          {/* Current Version Display */}
          {currentVersion && (
            <div className='mb-4 text-sm'>
              <span className='text-gray-600 font-bold'>Current Version: </span>
              <span className='font-mono font-bold text-black'>{currentVersion}</span>
            </div>
          )}

          {updateStatus && !installingUpdate && (
            <div className={`mb-4 p-3 rounded-lg text-sm ${
              updateStatus.up_to_date 
                ? 'bg-gray-100 text-black' 
                : 'bg-white text-black border-2 border-gray-300 border-dashed'
            }`}>
              <div className='font-bold mb-1'>{updateStatus.message}</div>
              <div className='text-xs text-gray-600 mt-1'>
                {updateStatus.up_to_date ? (
                  <>Current version: <span className='font-mono'>{updateStatus.current_version || 'unknown'}</span></>
                ) : (
                  <>
                    Current: <span className='font-mono'>{updateStatus.current_version || 'unknown'}</span> → 
                    Latest: <span className='font-mono'>{updateStatus.latest_version || 'unknown'}</span>
                    {updateStatus.commits_behind > 0 && (
                      <> ({updateStatus.commits_behind} {updateStatus.commits_behind === 1 ? 'update' : 'updates'})</>
                    )}
                  </>
                )}
              </div>
            </div>
          )}

          {updateMessage.message && !installingUpdate && updateMessage.type === 'error' && (
            <div className='mb-4 p-3 rounded-lg text-sm border-2 bg-white text-black border-black border-dashed'>
              <span className='font-bold mr-2'>ERROR:</span>
              {updateMessage.message}
            </div>
          )}

          {/* Update Progress Bar */}
          {installingUpdate && (
            <div className='mb-4 p-4 bg-gray-50 border-2 border-gray-300 rounded-lg'>
              <div className='flex items-center justify-between mb-2'>
                <span className='text-sm font-bold text-black'>{updateProgress.stage || 'Installing update...'}</span>
                <span className='text-xs text-gray-600 font-mono'>{updateProgress.progress}%</span>
              </div>
              <div className='w-full bg-gray-200 rounded-full h-2.5 overflow-hidden'>
                <div 
                  className='bg-black h-2.5 rounded-full transition-all duration-300 ease-out'
                  style={{ width: `${updateProgress.progress}%` }}
                />
              </div>
            </div>
          )}

          {!installingUpdate && (
            <div className='flex gap-3'>
              <PrimaryButton
                onClick={async () => {
                  setCheckingUpdates(true);
                  setUpdateMessage({ type: '', message: '' });
                  try {
                    const response = await fetch('/api/system/updates/check');
                    const data = await response.json();
                    setUpdateStatus(data);
                    if (data.error) {
                      setUpdateMessage({ type: 'error', message: data.error });
                      setTimeout(() => setUpdateMessage({ type: '', message: '' }), 5000);
                    }
                  } catch (err) {
                    setUpdateMessage({ type: 'error', message: 'Could not check for updates. Check your internet connection.' });
                    setTimeout(() => setUpdateMessage({ type: '', message: '' }), 5000);
                  } finally {
                    setCheckingUpdates(false);
                  }
                }}
                disabled={checkingUpdates}
                loading={checkingUpdates}
                className='flex-1'>
                Check for Updates
              </PrimaryButton>

            {updateStatus && updateStatus.available && !installingUpdate && (
              <PrimaryButton
                onClick={async () => {
                  if (!confirm('Install the update now? The device will restart automatically. The page will refresh automatically once the update is complete.')) {
                    return;
                  }
                  setInstallingUpdate(true);
                  setUpdateMessage({ type: '', message: '' });
                  setUpdateProgress({ stage: 'Installing update...', progress: 10 });
                  
                  try {
                    // Simulate progress during installation
                    const progressInterval = setInterval(() => {
                      setUpdateProgress(prev => {
                        if (prev.progress < 50) {
                          return { ...prev, progress: Math.min(prev.progress + 2, 50) };
                        }
                        return prev;
                      });
                    }, 500);
                    
                    const response = await fetch('/api/system/updates/install', {
                      method: 'POST',
                    });
                    
                    clearInterval(progressInterval);
                    setUpdateProgress({ stage: 'Update installed! Restarting service...', progress: 60 });
                    
                    const data = await response.json();
                    if (data.success) {
                      setUpdateProgress({ stage: 'Service restarting...', progress: 70 });
                      setUpdateStatus(null);
                    } else {
                      setUpdateProgress({ stage: '', progress: 0 });
                      setUpdateMessage({ type: 'error', message: data.error || data.message || 'Update failed. Please try again.' });
                      setInstallingUpdate(false);
                      return;
                    }
                  } catch (err) {
                    // Network error is expected during restart - treat as success
                    setUpdateProgress({ stage: 'Service restarting...', progress: 70 });
                    setUpdateStatus(null);
                  }
                  
                  // Set a maximum timeout to always reload after 45 seconds
                  const maxReloadTimeout = setTimeout(() => {
                    window.location.reload();
                  }, 45000); // Always reload after 45 seconds maximum
                  
                  // Wait a bit, then start checking if service is back up
                  setTimeout(() => {
                    setUpdateProgress({ stage: 'Waiting for service to restart...', progress: 75 });
                    
                    let attempts = 0;
                    const maxAttempts = 30; // Try for up to 30 seconds
                    
                    const checkService = async () => {
                      attempts++;
                      
                      // Update progress based on attempts
                      const progress = Math.min(75 + Math.floor((attempts / maxAttempts) * 20), 95);
                      setUpdateProgress({ stage: 'Waiting for service to restart...', progress });
                      
                      // Create abort controller for timeout
                      const controller = new AbortController();
                      const timeoutId = setTimeout(() => controller.abort(), 2000); // 2 second timeout
                      
                      try {
                        const healthCheck = await fetch('/api/health', { 
                          method: 'GET',
                          signal: controller.signal
                        });
                        clearTimeout(timeoutId);
                        
                        if (healthCheck.ok) {
                          // Service is back up, clear max timeout and reload the page
                          setUpdateProgress({ stage: 'Service ready! Reloading page...', progress: 100 });
                          clearTimeout(maxReloadTimeout);
                          setTimeout(() => window.location.reload(), 500);
                          return;
                        } else {
                          // Service not ready yet, keep trying
                          if (attempts < maxAttempts) {
                            setTimeout(checkService, 1000); // Try again in 1 second
                          } else {
                            // Give up and reload anyway
                            setUpdateProgress({ stage: 'Reloading page...', progress: 100 });
                            clearTimeout(maxReloadTimeout);
                            setTimeout(() => window.location.reload(), 500);
                          }
                        }
                      } catch (err) {
                        clearTimeout(timeoutId);
                        // Service not ready yet, keep trying
                        if (attempts < maxAttempts) {
                          setTimeout(checkService, 1000); // Try again in 1 second
                        } else {
                          // Give up and reload anyway after max attempts
                          setUpdateProgress({ stage: 'Reloading page...', progress: 100 });
                          clearTimeout(maxReloadTimeout);
                          setTimeout(() => window.location.reload(), 500);
                        }
                      }
                    };
                    
                    // Start checking
                    checkService();
                  }, 5000); // Wait 5 seconds before starting checks (give service time to restart)
                }}
                disabled={installingUpdate}
                className='flex-1'>
                Install Update
              </PrimaryButton>
            )}
            </div>
          )}
        </div>
      </div>

      {/* WiFi Status Display */}
      {wifiStatus && (
        <div className='rounded-xl p-[4px] shadow-lg' style={{ background: inkGradients[0] }}>
          <div className='bg-bg-card rounded-lg p-4 flex flex-col'>
            <h3 className='font-bold text-black  text-lg tracking-tight mb-3'>Network</h3>
            <div className='flex items-center justify-between'>
              <div className='flex-1'>
                <div className='flex items-center gap-2'>
                  {wifiStatus.connected ? (
                    <WiFiIcon className='w-4 h-4' style={{ color: 'var(--color-text-muted)' }} />
                  ) : (
                    <WiFiOffIcon className='w-4 h-4' style={{ color: 'var(--color-error)' }} />
                  )}
                  <span className='font-bold text-black '>
                    {wifiStatus.connected && wifiStatus.ssid
                      ? wifiStatus.ssid
                      : wifiStatus.mode === 'ap'
                      ? 'Setup Mode (AP)'
                      : 'Not Connected'}
                  </span>
                  <button
                    type='button'
                    onClick={triggerAPMode}
                    className='text-xs underline ml-2 cursor-pointer font-bold'
                    style={{ color: 'var(--color-brass)' }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-text-main)')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-brass)')}>
                    Reset WiFi
                  </button>
                </div>
                {wifiStatus.connected && wifiStatus.ip && <div className='text-xs text-gray-600 mt-1 '>IP: {wifiStatus.ip}</div>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Time Settings */}
      <div className='rounded-xl p-[4px] shadow-lg' style={{ background: inkGradients[1] }}>
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
                    console.log('[TimeSync] Switching to manual mode');
                    setUseAutoTime(false);
                    saveGlobalSettings({ time_sync_mode: 'manual' });
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
                    console.log('[TimeSync] Switching to automatic mode');
                    setUseAutoTime(true);
                    saveGlobalSettings({ time_sync_mode: 'automatic' });
                    if (wifiStatus?.connected) {
                      syncTimeAutomatically();
                    }
                  }}
                  className='sr-only'
                />
                <div className='flex items-baseline justify-center gap-1.5'>
                  <WiFiIcon
                    className={`w-3 h-3 flex-shrink-0 ${useAutoTime ? 'text-black' : 'text-gray-600'}`}
                    style={{ transform: 'translateY(0.125rem)' }}
                  />
                  <span className={`text-sm font-medium  ${useAutoTime ? 'text-black font-bold' : 'text-gray-600'}`}>Automatic</span>
                </div>
              </label>
            </div>

            {/* Automatic Mode Actions */}
            {useAutoTime && (
              <div className='p-4 border-2 border-black rounded-b-lg -mt-[2px]'>
                {wifiStatus?.connected ? (
                  <div>
                    <p className='text-sm font-bold text-black mb-2 '>Time Set Automatically</p>
                    {currentTime && (
                      <div className='p-3 bg-gray-50 border-2 border-gray-300 rounded-lg'>
                        <div className='text-xs text-gray-600 mb-1 uppercase font-bold'>Current Time</div>
                        <div className='flex items-center gap-2'>
                          <div className='text-lg font-bold text-black'>
                            {currentTime.date} {formatTimeForDisplay(currentTime.time, settings.time_format || '12h')}
                          </div>
                          <WiFiIcon className='w-3.5 h-3.5' style={{ color: 'var(--color-text-muted)' }} />
                        </div>
                      </div>
                    )}
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
                          <WiFiOffIcon className='w-3.5 h-3.5' style={{ color: 'var(--color-error)' }} />
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
                <PrimaryButton onClick={setTimeManually} className='w-full'>
                  Set System Time
                </PrimaryButton>
                <p className='text-xs text-gray-600 mt-2 text-center '>Use this when offline or to set a specific time</p>
              </div>
            )}

            {/* Status Messages */}
            {timeStatus.message && (
              <div
                className={`mt-4 p-3 rounded-lg text-sm  border-2 ${
                  timeStatus.type === 'success' ? 'bg-gray-100 text-black border-black' : 'bg-white text-black border-black border-dashed'
                }`}>
                {timeStatus.type === 'error' && <span className='font-bold mr-2'>ERROR:</span>}
                {timeStatus.message}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Location Settings */}
      <div className='rounded-xl p-[4px] shadow-lg' style={{ background: inkGradients[2] }}>
        <div className='bg-bg-card rounded-lg p-4 flex flex-col'>
          <h3 className='font-bold text-black  text-lg tracking-tight mb-3'>Location</h3>

          {/* Universal Location Search Component */}
          <div className='mb-4'>
            <label className='block mb-2 text-sm text-gray-600 font-bold'>Set Location</label>
            <LocationSearch 
              value={settings} 
              onChange={(newLoc) => saveGlobalSettings(newLoc)} 
            />
          </div>
        </div>
      </div>

      {/* Printer Settings */}
      <div className='rounded-xl p-[4px] shadow-lg' style={{ background: inkGradients[3] }}>
        <div className='bg-bg-card rounded-lg p-4 flex flex-col'>
          <h3 className='font-bold text-black  text-lg tracking-tight mb-3'>Printer Settings</h3>
          <div>
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
                        ? 'bg-white text-black border-black'
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
                    className='flex-1 py-2.5 px-4 bg-transparent border-0 rounded-lg transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed font-bold'
                    style={{ color: 'var(--color-error-light)' }}
                    onMouseEnter={(e) => {
                      if (!sshLoading) e.currentTarget.style.color = 'var(--color-error)';
                    }}
                    onMouseLeave={(e) => {
                      if (!sshLoading) e.currentTarget.style.color = 'var(--color-error-light)';
                    }}>
                    {sshLoading ? 'Disabling...' : 'Disable SSH'}
                  </button>
                )}
                {sshStatus.enabled && (
                  <button
                    type='button'
                    onClick={() => setShowPasswordChange(!showPasswordChange)}
                    className='flex-1 py-2.5 px-4 bg-transparent border-2 border-gray-400 text-black rounded-lg  font-bold hover:border-black hover:bg-white transition-all cursor-pointer'>
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
                    <PrimaryButton
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
                      loading={changingPassword}
                      className='w-full'>
                      Change Password
                    </PrimaryButton>
                  </div>
                </div>
              )}

              {/* SSH Status Messages */}
              {sshMessage.message && (
                <div
                  className={`p-3 rounded-lg text-sm  border-2 ${
                    sshMessage.type === 'success' ? 'bg-gray-100 text-black border-black' : 'bg-white text-black border-black border-dashed'
                  }`}>
                  {sshMessage.type === 'error' && <span className='font-bold mr-2'>ERROR:</span>}
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
