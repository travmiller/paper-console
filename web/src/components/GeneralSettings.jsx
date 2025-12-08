import React from 'react';

const GeneralSettings = ({
  searchTerm,
  searchResults,
  handleSearch,
  selectLocation,
  settings,
  saveGlobalSettings,
  triggerAPMode,
}) => {
  const inputClass =
    'w-full p-3 text-base bg-[#333] border border-gray-700 rounded text-white focus:border-white focus:outline-none box-border';
  const labelClass = 'block mb-2 font-bold text-gray-200';

  return (
    <>
      <div className='mb-6'>
        <div className='mb-6 text-left relative'>
          <label className={labelClass}>Search City / Location</label>
          <input
            type='text'
            value={searchTerm}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder='Type to search (e.g. London)'
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
                    {result.admin1} {result.country}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className='grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4 bg-[#2a2a2a] p-4 rounded border border-gray-700 mb-6'>
          <div className='flex flex-col'>
            <span className='text-xs text-gray-400 mb-1 uppercase'>Selected City</span>
            <span className='font-bold text-white'>{settings.city_name || 'Not Set'}</span>
          </div>
          <div className='flex flex-col'>
            <span className='text-xs text-gray-400 mb-1 uppercase'>Timezone</span>
            <span className='font-bold text-white'>{settings.timezone || 'Not Set'}</span>
          </div>
          <div className='flex flex-col'>
            <span className='text-xs text-gray-400 mb-1 uppercase'>Coordinates</span>
            <span className='font-bold text-white'>
              {settings.latitude?.toFixed(4)}, {settings.longitude?.toFixed(4)}
            </span>
          </div>
        </div>
      </div>

      <div className='mb-6'>
        <div className='mb-4'>
          <label className={labelClass}>Time Format</label>
          <select
            value={settings.time_format || '12h'}
            onChange={(e) => saveGlobalSettings({ time_format: e.target.value })}
            className={inputClass}>
            <option value='12h'>12-hour (3:45 PM)</option>
            <option value='24h'>24-hour (15:45)</option>
          </select>
          <p className='text-xs text-gray-500 mt-1'>Choose how times are displayed across all modules</p>
        </div>

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
