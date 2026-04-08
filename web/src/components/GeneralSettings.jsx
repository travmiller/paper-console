import React, { useState, useEffect } from 'react';
import { formatTimeForDisplay } from '../utils';
import { INK_GRADIENTS } from '../constants';
import PrimaryButton from './PrimaryButton';
import WiFiIcon from '../assets/WiFiIcon';
import WiFiOffIcon from '../assets/WiFiOffIcon';
import LocationSearch from './widgets/LocationSearch';
import { adminAuthFetch } from '../lib/adminAuthFetch';


const GeneralSettings = ({
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

  // Device Password state
  const [devicePasswordStatus, setDevicePasswordStatus] = useState(null);
  const [devicePasswordMessage, setDevicePasswordMessage] = useState({ type: '', message: '' });
  const [showDevicePasswordChange, setShowDevicePasswordChange] = useState(false);
  const [currentDevicePassword, setCurrentDevicePassword] = useState('');
  const [newDevicePassword, setNewDevicePassword] = useState('');
  const [confirmDevicePassword, setConfirmDevicePassword] = useState('');
  const [changingDevicePassword, setChangingDevicePassword] = useState(false);
  const devicePasswordSource = devicePasswordStatus?.source;
  const devicePasswordBadgeMuted = !['managed_file', 'managed_fallback'].includes(devicePasswordSource || '');
  const devicePasswordUnavailableMessage =
    devicePasswordSource === 'managed_fallback'
      ? 'Password changes will be available after managed device credential storage is provisioned on this unit.'
      : 'Device Password changes are only available on managed PC-1 builds.';

  // SSH management state
  const [sshStatus, setSshStatus] = useState(null);
  const [sshLoading, setSshLoading] = useState(false);
  const [sshMessage, setSshMessage] = useState({ type: '', message: '' });

  // Update check state
  const [updateStatus, setUpdateStatus] = useState(null);
  const [checkingUpdates, setCheckingUpdates] = useState(false);
  const [installingUpdate, setInstallingUpdate] = useState(false);
  const [updateMessage, setUpdateMessage] = useState({ type: '', message: '' });
  const [currentVersion, setCurrentVersion] = useState(null);
  const [installMode, setInstallMode] = useState(null);
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

  useEffect(() => {
    const fetchDevicePasswordStatus = async () => {
      try {
        const response = await fetch('/api/system/device-password/status');
        const data = await response.json();
        setDevicePasswordStatus(data);
      } catch (err) {
        console.error('Error fetching Device Password status:', err);
      }
    };

    fetchDevicePasswordStatus();
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
        if (data.install_mode) {
          setInstallMode(data.install_mode);
        }
      } catch (err) {
        console.error('Error fetching current version:', err);
      }
    };

    fetchCurrentVersion();
  }, []);

  const getApiError = (data, fallback) => {
    return data?.detail || data?.error || data?.message || fallback;
  };

  const clearStatusLater = (setter) => {
    setTimeout(() => setter({ type: '', message: '' }), 5000);
  };

  const waitForServiceRestartAndReload = () => {
    const maxReloadTimeout = setTimeout(() => {
      window.location.reload();
    }, 45000);

    setTimeout(() => {
      setUpdateProgress({ stage: 'Waiting for service to restart...', progress: 75 });

      let attempts = 0;
      const maxAttempts = 30;

      const checkService = async () => {
        attempts++;

        const progress = Math.min(75 + Math.floor((attempts / maxAttempts) * 20), 95);
        setUpdateProgress({ stage: 'Waiting for service to restart...', progress });

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2000);

        try {
          const healthCheck = await fetch('/api/health', {
            method: 'GET',
            signal: controller.signal,
          });
          clearTimeout(timeoutId);

          if (healthCheck.ok) {
            setUpdateProgress({ stage: 'Service ready! Reloading page...', progress: 100 });
            clearTimeout(maxReloadTimeout);
            setTimeout(() => window.location.reload(), 500);
            return;
          }
        } catch {
          clearTimeout(timeoutId);
        }

        if (attempts < maxAttempts) {
          setTimeout(checkService, 1000);
        } else {
          setUpdateProgress({ stage: 'Reloading page...', progress: 100 });
          clearTimeout(maxReloadTimeout);
          setTimeout(() => window.location.reload(), 500);
        }
      };

      checkService();
    }, 5000);
  };

  const runRestartingUpdateAction = async ({
    endpoint,
    confirmMessage,
    initialStage,
    successStage,
    failureFallback,
  }) => {
    if (!confirm(confirmMessage)) {
      return;
    }

    setInstallingUpdate(true);
    setUpdateMessage({ type: '', message: '' });
    setUpdateProgress({ stage: initialStage, progress: 10 });

    let progressInterval = null;
    try {
      progressInterval = setInterval(() => {
        setUpdateProgress((prev) => {
          if (prev.progress < 50) {
            return { ...prev, progress: Math.min(prev.progress + 2, 50) };
          }
          return prev;
        });
      }, 500);

      const response = await adminAuthFetch(endpoint, {
        method: 'POST',
      });

      clearInterval(progressInterval);
      setUpdateProgress({ stage: successStage, progress: 60 });

      const data = await response.json();
      if (data.success) {
        setUpdateProgress({ stage: 'Service restarting...', progress: 70 });
        setUpdateStatus(null);
      } else {
        setUpdateProgress({ stage: '', progress: 0 });
        setUpdateMessage({ type: 'error', message: getApiError(data, failureFallback) });
        setInstallingUpdate(false);
        return;
      }
    } catch {
      if (progressInterval) {
        clearInterval(progressInterval);
      }
      // Network error is expected during restart - treat as success
      setUpdateProgress({ stage: 'Service restarting...', progress: 70 });
      setUpdateStatus(null);
    }

    waitForServiceRestartAndReload();
  };

  const handleDevicePasswordChange = async () => {
    if (!currentDevicePassword) {
      setDevicePasswordMessage({ type: 'error', message: 'Enter your current Device Password' });
      clearStatusLater(setDevicePasswordMessage);
      return;
    }
    if (!newDevicePassword || newDevicePassword.length < 8) {
      setDevicePasswordMessage({ type: 'error', message: 'New Device Password must be at least 8 characters' });
      clearStatusLater(setDevicePasswordMessage);
      return;
    }
    if (newDevicePassword !== confirmDevicePassword) {
      setDevicePasswordMessage({ type: 'error', message: 'New passwords do not match' });
      clearStatusLater(setDevicePasswordMessage);
      return;
    }

    setChangingDevicePassword(true);
    setDevicePasswordMessage({ type: '', message: '' });

    try {
      const response = await adminAuthFetch('/api/system/device-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_password: currentDevicePassword,
          new_password: newDevicePassword,
        }),
      });
      const data = await response.json();

      if (data.success) {
        setDevicePasswordMessage({ type: 'success', message: data.message });
        setCurrentDevicePassword('');
        setNewDevicePassword('');
        setConfirmDevicePassword('');
        setShowDevicePasswordChange(false);

        if (data.reauth_required) {
          setTimeout(() => {
            window.dispatchEvent(
              new CustomEvent('pc1-auth-required', {
                detail: {
                  message: 'Device Password changed. Enter the new Device Password to continue.',
                },
              }),
            );
          }, 1200);
        } else {
          clearStatusLater(setDevicePasswordMessage);
        }
      } else {
        setDevicePasswordMessage({
          type: 'error',
          message: getApiError(data, 'Failed to change Device Password'),
        });
        clearStatusLater(setDevicePasswordMessage);
      }
    } catch (err) {
      setDevicePasswordMessage({ type: 'error', message: `Error changing Device Password: ${err.message}` });
      clearStatusLater(setDevicePasswordMessage);
    } finally {
      setChangingDevicePassword(false);
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
      const response = await adminAuthFetch('/api/system/time/sync', {
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
        setTimeStatus({ type: 'error', message: getApiError(data, 'Failed to sync time') });
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
      const response = await adminAuthFetch('/api/system/time', {
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
          message: getApiError(data, 'Failed to set system time. The application may need sudo privileges.'),
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

          {installMode === 'development' && (
            <div className='mb-4'>
              <div className='flex items-center justify-between gap-3'>
                <div className='text-xs text-gray-600'>
                  This unit is using git-based updates.
                </div>
                {!installingUpdate && (
                  <button
                    type='button'
                    onClick={() =>
                      runRestartingUpdateAction({
                        endpoint: '/api/system/updates/convert-to-production',
                        confirmMessage:
                          'Convert this unit to production mode now? This installs the latest published release, removes git update mode, and restarts the device automatically.',
                        initialStage: 'Converting to production...',
                        successStage: 'Production release installed! Restarting service...',
                        failureFallback: 'Conversion failed. Please try again.',
                      })
                    }
                    className='text-xs font-bold text-black underline underline-offset-2 hover:text-gray-700 transition-colors cursor-pointer'>
                    Convert to Production
                  </button>
                )}
              </div>
              <p className='text-xs text-gray-600 mt-2 '>
                Switch this unit from git-based updates to release-based OTA updates using the latest published release.
              </p>
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
                  } catch {
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
                onClick={() =>
                  runRestartingUpdateAction({
                    endpoint: '/api/system/updates/install',
                    confirmMessage:
                      'Install the update now? The device will restart automatically. The page will refresh automatically once the update is complete.',
                    initialStage: 'Installing update...',
                    successStage: 'Update installed! Restarting service...',
                    failureFallback: 'Update failed. Please try again.',
                  })
                }
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
                      await adminAuthFetch('/api/system/time/sync/disable', { method: 'POST' }).catch(() => {
                        // Ignore errors - the backend will handle NTP disable when setting time
                      });
                    } catch {
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

      {/* Device Password */}
      <div className='rounded-xl p-[4px] shadow-lg' style={{ background: inkGradients[4] }}>
        <div className='bg-bg-card rounded-lg p-4 flex flex-col'>
          <h3 className='font-bold text-black  text-lg tracking-tight mb-3'>Device Password</h3>
          <p className='text-sm text-gray-600 mb-4 '>
            The Device Password is shared across settings login, setup WiFi, printed setup instructions, and SSH access.
          </p>

          <div className='space-y-4'>
            <div className='p-4 border-2 border-gray-300 rounded-lg'>
              <div className='flex items-center justify-between mb-2 gap-3'>
                <span className='text-sm font-medium text-black  font-bold'>Password Storage</span>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-medium border-2 ${
                    devicePasswordBadgeMuted ? 'bg-white text-gray-500 border-gray-300' : 'bg-white text-black border-black'
                  }`}>
                  {devicePasswordStatus?.status_label || 'Loading...'}
                </span>
              </div>
              <p className='text-xs text-gray-600 mt-1 '>
                {devicePasswordStatus?.message || 'Loading Device Password status...'}
              </p>
            </div>

            {devicePasswordStatus?.can_change ? (
              <>
                <button
                  type='button'
                  onClick={() => setShowDevicePasswordChange(!showDevicePasswordChange)}
                  className='w-full py-2.5 px-4 bg-transparent border-2 border-gray-400 text-black rounded-lg  font-bold hover:border-black hover:bg-white transition-all cursor-pointer'>
                  {showDevicePasswordChange ? 'Cancel' : 'Change Device Password'}
                </button>

                {showDevicePasswordChange && (
                  <div className='p-4 border-2 border-gray-300 rounded-lg'>
                    <h4 className='text-sm font-medium text-black mb-3  font-bold'>Change Device Password</h4>
                    <div className='space-y-3'>
                      <div>
                        <label className='block mb-2 text-sm text-black  font-bold'>Current Device Password</label>
                        <input
                          type='password'
                          value={currentDevicePassword}
                          onChange={(e) => setCurrentDevicePassword(e.target.value)}
                          placeholder='Enter current password'
                          className={inputClass}
                          minLength={8}
                        />
                      </div>
                      <div>
                        <label className='block mb-2 text-sm text-black  font-bold'>New Device Password</label>
                        <input
                          type='password'
                          value={newDevicePassword}
                          onChange={(e) => setNewDevicePassword(e.target.value)}
                          placeholder='Minimum 8 characters'
                          className={inputClass}
                          minLength={8}
                        />
                      </div>
                      <div>
                        <label className='block mb-2 text-sm text-black  font-bold'>Confirm New Password</label>
                        <input
                          type='password'
                          value={confirmDevicePassword}
                          onChange={(e) => setConfirmDevicePassword(e.target.value)}
                          placeholder='Re-enter new password'
                          className={inputClass}
                          minLength={8}
                        />
                      </div>
                      <PrimaryButton
                        onClick={handleDevicePasswordChange}
                        disabled={
                          changingDevicePassword ||
                          !currentDevicePassword ||
                          !newDevicePassword ||
                          !confirmDevicePassword
                        }
                        loading={changingDevicePassword}
                        className='w-full'>
                        Change Device Password
                      </PrimaryButton>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className='p-4 border-2 border-gray-300 rounded-lg'>
                <p className='text-sm text-gray-500 '>
                  {devicePasswordUnavailableMessage}
                </p>
              </div>
            )}

            {devicePasswordMessage.message && (
              <div
                className={`p-3 rounded-lg text-sm  border-2 ${
                  devicePasswordMessage.type === 'success'
                    ? 'bg-gray-100 text-black border-black'
                    : 'bg-white text-black border-black border-dashed'
                }`}>
                {devicePasswordMessage.type === 'error' && <span className='font-bold mr-2'>ERROR:</span>}
                {devicePasswordMessage.message}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* SSH Management */}
      <div className='rounded-xl p-[4px] shadow-lg' style={{ background: inkGradients[5] || inkGradients[4] }}>
        <div className='bg-bg-card rounded-lg p-4 flex flex-col'>
          <h3 className='font-bold text-black  text-lg tracking-tight mb-3'>SSH Access</h3>
          <p className='text-sm text-gray-600 mb-4 '>
            Manage SSH (Secure Shell) service access to your PC-1 device. When SSH is enabled, it uses the same Device Password shown on setup instructions.
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
                <p className='text-xs text-gray-600 mt-2 '>
                  Password: <span className='text-black '>Uses your Device Password</span>
                </p>
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
                        const response = await adminAuthFetch('/api/system/ssh/enable', { method: 'POST' });
                        const data = await response.json();
                        if (data.success) {
                          setSshMessage({ type: 'success', message: data.message });
                          // Refresh status
                          const statusResponse = await fetch('/api/system/ssh/status');
                          const statusData = await statusResponse.json();
                          setSshStatus(statusData);
                        } else {
                          setSshMessage({ type: 'error', message: getApiError(data, 'Failed to enable SSH') });
                        }
                      } catch {
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
                        const response = await adminAuthFetch('/api/system/ssh/disable', { method: 'POST' });
                        const data = await response.json();
                        if (data.success) {
                          setSshMessage({ type: 'success', message: data.message });
                          // Refresh status
                          const statusResponse = await fetch('/api/system/ssh/status');
                          const statusData = await statusResponse.json();
                          setSshStatus(statusData);
                        } else {
                          setSshMessage({ type: 'error', message: getApiError(data, 'Failed to disable SSH') });
                        }
                      } catch {
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
              </div>

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
