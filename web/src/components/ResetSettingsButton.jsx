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
        className='bg-transparent text-red-900 text-sm hover:text-red-500 border border-red-900/30 hover:border-red-500/50 rounded px-4 py-2 transition-colors cursor-pointer'>
        Reset All Settings to Default
      </button>
    </div>
  );
};

export default ResetSettingsButton;
