import { useState, useEffect } from 'react';

export default function WiFiSetup({ onComplete }) {
  const [networks, setNetworks] = useState([]);
  const [selectedSSID, setSelectedSSID] = useState('');
  const [password, setPassword] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionStarted, setConnectionStarted] = useState(false);
  const [error, setError] = useState('');
  const [showManualEntry, setShowManualEntry] = useState(false);

  useEffect(() => {
    scanNetworks();
  }, []);

  const scanNetworks = async () => {
    setIsScanning(true);
    setError('');
    try {
      const response = await fetch('/api/wifi/networks');
      const data = await response.json();
      setNetworks(data.networks || []);
    } catch (err) {
      setError('Failed to scan networks');
      console.error(err);
    } finally {
      setIsScanning(false);
    }
  };

  const connectToWiFi = async (e) => {
    e.preventDefault();
    if (!selectedSSID) {
      setError('Please select a network');
      return;
    }

    setIsConnecting(true);
    setError('');

    try {
      const response = await fetch('/api/wifi/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ssid: selectedSSID,
          password: password || null
        })
      });

      if (response.ok) {
        // Connection started in background
        setConnectionStarted(true);
        setIsConnecting(false);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to connect');
        setIsConnecting(false);
      }
    } catch (err) {
      // Connection might have been lost because AP mode stopped - that's expected!
      setConnectionStarted(true);
      setIsConnecting(false);
    }
  };

  const inputClass = 'w-full p-3 text-base bg-[#333] border border-gray-700 rounded text-white focus:border-white focus:outline-none';
  const buttonClass = 'w-full py-3 px-4 rounded font-bold transition-colors';

  // Show success screen after connection started
  if (connectionStarted) {
    return (
      <div className='max-w-[600px] w-full p-8'>
        <div className='text-center'>
          <div className='text-6xl mb-6'>📡</div>
          <h1 className='text-3xl mb-4 font-bold text-green-400'>Connecting to WiFi...</h1>
          <p className='text-gray-300 mb-6'>
            Your PC-1 is now connecting to <strong>{selectedSSID}</strong>
          </p>
          
          <div className='bg-gray-800 rounded-lg p-6 text-left mb-6'>
            <h2 className='font-bold text-white mb-4'>Next Steps:</h2>
            <ol className='space-y-3 text-gray-300'>
              <li className='flex items-start gap-2'>
                <span className='bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-sm'>1</span>
                <span>Disconnect from <strong>PC-1-Setup</strong> network on your phone</span>
              </li>
              <li className='flex items-start gap-2'>
                <span className='bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-sm'>2</span>
                <span>Connect your phone to <strong>{selectedSSID}</strong></span>
              </li>
              <li className='flex items-start gap-2'>
                <span className='bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-sm'>3</span>
                <span>Wait about 30 seconds for the device to connect</span>
              </li>
              <li className='flex items-start gap-2'>
                <span className='bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-sm'>4</span>
                <span>Visit <strong className='text-blue-400'>http://pc-1.local</strong> to access settings</span>
              </li>
            </ol>
          </div>

          <p className='text-sm text-gray-500'>
            If the connection fails, the PC-1 will re-create the setup network automatically.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className='max-w-[600px] w-full p-8'>
      <div className='text-center mb-8'>
        <h1 className='text-4xl mb-4 font-bold'>WiFi Setup</h1>
        <p className='text-gray-400'>Connect your PC-1 to your home WiFi network</p>
      </div>

      {error && (
        <div className='bg-red-900/30 border border-red-700 text-red-200 p-4 rounded mb-6'>
          {error}
        </div>
      )}

      <form onSubmit={connectToWiFi} className='space-y-6'>
        {!showManualEntry ? (
          <>
            <div>
              <div className='flex items-center justify-between mb-3'>
                <label className='block font-bold text-gray-200'>Available Networks</label>
                <button
                  type='button'
                  onClick={scanNetworks}
                  disabled={isScanning}
                  className='text-sm px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded transition-colors disabled:opacity-50'>
                  {isScanning ? 'Scanning...' : 'Refresh'}
                </button>
              </div>

              <select
                value={selectedSSID}
                onChange={(e) => setSelectedSSID(e.target.value)}
                className={inputClass}
                required
                disabled={isConnecting}>
                <option value=''>-- Select a network --</option>
                {networks.map((network) => (
                  <option key={network.ssid} value={network.ssid}>
                    {network.ssid} ({network.signal}%) {network.secure ? '🔒' : ''}
                  </option>
                ))}
              </select>
            </div>

            <button
              type='button'
              onClick={() => setShowManualEntry(true)}
              className='text-sm text-blue-400 hover:text-blue-300'>
              Enter network name manually
            </button>
          </>
        ) : (
          <>
            <div>
              <label className='block mb-2 font-bold text-gray-200'>Network Name (SSID)</label>
              <input
                type='text'
                value={selectedSSID}
                onChange={(e) => setSelectedSSID(e.target.value)}
                className={inputClass}
                placeholder='Enter WiFi network name'
                required
                disabled={isConnecting}
              />
            </div>

            <button
              type='button'
              onClick={() => {
                setShowManualEntry(false);
                setSelectedSSID('');
              }}
              className='text-sm text-blue-400 hover:text-blue-300'>
              ← Back to network list
            </button>
          </>
        )}

        <div>
          <label className='block mb-2 font-bold text-gray-200'>Password</label>
          <input
            type='password'
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
            placeholder='Enter WiFi password (leave blank if open network)'
            disabled={isConnecting}
          />
        </div>

        <button
          type='submit'
          disabled={isConnecting || !selectedSSID}
          className={`${buttonClass} bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed`}>
          {isConnecting ? 'Connecting...' : 'Connect to WiFi'}
        </button>
      </form>

      <div className='mt-8 p-4 bg-gray-800 rounded border border-gray-700'>
        <p className='text-sm text-gray-300 mb-2'>
          <strong>Note:</strong> After clicking Connect, this device will disconnect from the setup network and join your home WiFi.
        </p>
        <p className='text-sm text-gray-400'>
          You'll need to reconnect your phone to your home WiFi to access the settings page.
        </p>
      </div>
    </div>
  );
}
