import React from 'react';

const ResetSettingsButton = ({ setSettings, setModules, setStatus }) => {
  const handleReset = async () => {
    if (confirm('Are you sure you want to reset ALL settings to default? This cannot be undone.')) {
      try {
        const res = await fetch('/api/settings/reset', { method: 'POST' });
        const data = await res.json();
        setSettings(data.config);
        setModules({});
        setStatus({ type: 'success', message: 'Settings reset to defaults.' });
      } catch (err) {
        console.error(err);
        setStatus({ type: 'error', message: 'Failed to reset settings.' });
      }
    }
  };

  return (
    <div className='mt-8 pt-8 border-t border-gray-800 text-center'>
      <button
        onClick={handleReset}
        className='text-xs text-red-400 hover:text-red-300 border border-red-800/40 hover:border-red-700/60 rounded px-3 py-1.5 bg-transparent transition-colors cursor-pointer'>
        Reset All Settings to Default
      </button>
    </div>
  );
};

export default ResetSettingsButton;
