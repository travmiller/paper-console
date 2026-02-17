import { useState, useEffect } from 'react';

export default function WiFiSetup({ wifiStatus }) {
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
    } catch {
      // Connection might have been lost because AP mode stopped - that's expected!
      setConnectionStarted(true);
      setIsConnecting(false);
    }
  };

  const inputClass = 'w-full p-3 text-base bg-white border-2 border-gray-300 rounded-lg text-black focus:border-black focus:outline-none box-border';
  const buttonClass = 'w-full py-3 px-4 rounded-lg font-bold transition-all';

  // Show success screen after connection started
  if (connectionStarted) {
    return (
      <div className='max-w-[480px] w-full mx-auto px-2 pt-4 pb-12 sm:px-6 sm:pt-8 sm:pb-16 bg-white min-h-screen'>
        <div className='text-center'>
          <div className='text-6xl mb-6'>📡</div>
          <h1 className='text-3xl mb-4 font-bold text-black'>Connecting to WiFi...</h1>
          <p className='text-gray-600 mb-6'>
            Your PC-1 is now connecting to <strong className='text-black'>{selectedSSID}</strong>
          </p>
          
          <div className='bg-bg-card border-4 border-black rounded-xl p-6 text-left mb-6 shadow-lg'>
            <h2 className='font-bold text-black mb-4'>Next Steps:</h2>
            <ol className='space-y-3 text-black'>
              <li className='flex items-start gap-2'>
                <span className='bg-black text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-sm font-bold'>1</span>
                <span>
                  Disconnect from <strong>{wifiStatus?.ap_ssid || 'PC-1 Setup network'}</strong> on your phone
                </span>
              </li>
              <li className='flex items-start gap-2'>
                <span className='bg-black text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-sm font-bold'>2</span>
                <span>Connect your phone to <strong>{selectedSSID}</strong></span>
              </li>
              <li className='flex items-start gap-2'>
                <span className='bg-black text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-sm font-bold'>3</span>
                <span>Wait about 30 seconds for the device to connect</span>
              </li>
              <li className='flex items-start gap-2'>
                <span className='bg-black text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-sm font-bold'>4</span>
                <span>Visit <strong className='text-black'>http://pc-1.local</strong> to access settings</span>
              </li>
            </ol>
          </div>

          <p className='text-sm text-gray-600'>
            If the connection fails, the PC-1 will re-create the setup network automatically.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className='max-w-[480px] w-full mx-auto px-2 pt-4 pb-12 sm:px-6 sm:pt-8 sm:pb-16 bg-white min-h-screen'>
      <div className='text-center mb-8'>
        <h1 className='text-3xl sm:text-4xl mb-4 font-bold text-black'>WiFi Setup</h1>
        <p className='text-gray-600'>Connect your PC-1 to your home WiFi network</p>
      </div>

      {error && (
        <div className='bg-white border-2 border-red-500 text-red-600 p-4 rounded-lg mb-6'>
          <span className='font-bold mr-2'>ERROR:</span>{error}
        </div>
      )}

      <div className='bg-bg-card border-4 border-black rounded-xl p-4 flex flex-col shadow-lg mb-6'>
        <form onSubmit={connectToWiFi} className='space-y-6'>
        {!showManualEntry ? (
          <>
            <div>
              <div className='flex items-center justify-between mb-3'>
                <label className='block font-bold text-black'>Available Networks</label>
                <button
                  type='button'
                  onClick={scanNetworks}
                  disabled={isScanning}
                  className='text-sm px-3 py-1 bg-transparent border-2 border-gray-300 hover:border-black rounded-lg text-black transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer'>
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
              className='text-sm text-gray-600 hover:text-black underline cursor-pointer'>
              Enter network name manually
            </button>
          </>
        ) : (
          <>
            <div>
              <label className='block mb-2 font-bold text-black'>Network Name (SSID)</label>
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
              className='text-sm text-gray-600 hover:text-black underline cursor-pointer'>
              ← Back to network list
            </button>
          </>
        )}

        <div>
          <label className='block mb-2 font-bold text-black'>Password</label>
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
          className={`${buttonClass} bg-transparent border-2 border-black text-black hover:bg-black hover:text-white disabled:opacity-50 disabled:cursor-not-allowed disabled:border-gray-300 disabled:text-gray-400 cursor-pointer`}>
          {isConnecting ? 'Connecting...' : 'Connect to WiFi'}
        </button>
        </form>
      </div>

      <div className='mt-8 p-4 bg-bg-card border-4 border-black rounded-xl shadow-lg'>
        <p className='text-sm text-black mb-2'>
          <strong>Note:</strong> After clicking Connect, this device will disconnect from the setup network and join your home WiFi.
        </p>
        <p className='text-sm text-gray-600'>
          You'll need to reconnect your phone to your home WiFi to access the settings page.
        </p>
      </div>
    </div>
  );
}
