import React from 'react';
import JsonTextarea from './JsonTextarea';

const ModuleConfig = ({ module, updateConfig }) => {
  const config = module.config || {};
  const inputClass = 'w-full p-3 text-base bg-[#333] border border-gray-700 rounded text-white focus:border-white focus:outline-none';
  const labelClass = 'block mb-2 text-sm text-gray-400';

  if (module.type === 'webhook') {
    return (
      <div className='space-y-3'>
        <div>
          <label className={labelClass}>Label</label>
          <input type='text' value={config.label || ''} onChange={(e) => updateConfig('label', e.target.value)} className={inputClass} />
        </div>
        <div className='flex gap-2'>
          <div className='w-1/4'>
            <label className={labelClass}>Method</label>
            <select value={config.method || 'GET'} onChange={(e) => updateConfig('method', e.target.value)} className={inputClass}>
              <option value='GET'>GET</option>
              <option value='POST'>POST</option>
            </select>
          </div>
          <div className='w-3/4'>
            <label className={labelClass}>URL</label>
            <input type='text' value={config.url || ''} onChange={(e) => updateConfig('url', e.target.value)} className={inputClass} />
          </div>
        </div>
        <div>
          <label className={labelClass}>Headers (JSON)</label>
          <JsonTextarea
            value={config.headers || {}}
            onChange={(parsed) => updateConfig('headers', parsed)}
            onBlur={(parsed) => updateConfig('headers', parsed)}
            className={`${inputClass} font-mono text-sm min-h-[80px]`}
          />
        </div>
        <div>
          <label className={labelClass}>JSON Path (Optional)</label>
          <input
            type='text'
            value={config.json_path || ''}
            onChange={(e) => updateConfig('json_path', e.target.value)}
            className={inputClass}
            placeholder='e.g. data.message or items[0].text'
          />
        </div>
      </div>
    );
  }

  if (module.type === 'news') {
    return (
      <div className='space-y-3'>
        <div>
          <label className={labelClass}>NewsAPI Key</label>
          <input
            type='password'
            value={config.news_api_key || ''}
            onChange={(e) => updateConfig('news_api_key', e.target.value)}
            className={inputClass}
            placeholder='Enter your NewsAPI key'
          />
          <p className='text-xs text-gray-500 mt-1'>Get your free API key from newsapi.org</p>
        </div>
      </div>
    );
  }

  if (module.type === 'rss') {
    const addRssFeed = () => {
      const currentConfig = module.config || {};
      const currentFeeds = currentConfig.rss_feeds || [];
      updateConfig('rss_feeds', [...currentFeeds, '']);
    };

    const updateRssFeed = (index, value) => {
      // Read fresh from module.config to avoid stale closures
      const currentConfig = module.config || {};
      const currentFeeds = [...(currentConfig.rss_feeds || [])];
      currentFeeds[index] = value;
      updateConfig('rss_feeds', currentFeeds);
    };

    const removeRssFeed = (index) => {
      const currentConfig = module.config || {};
      const currentFeeds = [...(currentConfig.rss_feeds || [])];
      currentFeeds.splice(index, 1);
      updateConfig('rss_feeds', currentFeeds);
    };

    return (
      <div className='space-y-3'>
        <div>
          <label className={labelClass}>RSS Feed URLs</label>
          <div className='space-y-3'>
            {(config.rss_feeds || []).map((feed, index) => (
              <div key={index} className='bg-[#1a1a1a] p-3 rounded border border-gray-800'>
                <div className='flex justify-between items-start mb-2'>
                  <span className='text-sm text-gray-400'>Feed {index + 1}</span>
                  <button
                    type='button'
                    onClick={() => removeRssFeed(index)}
                    className='px-2 py-1 text-xs bg-red-900/30 text-red-300 rounded hover:bg-red-900/50 transition-colors'>
                    Remove
                  </button>
                </div>
                <div>
                  <label className='block mb-1 text-xs text-gray-400'>RSS Feed URL</label>
                  <input
                    type='text'
                    value={feed || ''}
                    onChange={(e) => updateRssFeed(index, e.target.value)}
                    placeholder='https://feeds.bbci.co.uk/news/rss.xml'
                    className={inputClass}
                  />
                </div>
              </div>
            ))}
            <button
              type='button'
              onClick={addRssFeed}
              className='w-full py-2 bg-[#1a1a1a] border border-gray-600 hover:border-white rounded text-white transition-colors text-sm'>
              + Add RSS Feed
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (module.type === 'weather') {
    return (
      <div className='text-gray-400 text-sm'>
        Weather uses the global location settings configured in the General tab. No additional configuration needed.
      </div>
    );
  }

  if (module.type === 'email') {
    return (
      <div className='space-y-3'>
        <div>
          <label className={labelClass}>IMAP Host</label>
          <input
            type='text'
            value={config.email_host || 'imap.gmail.com'}
            onChange={(e) => updateConfig('email_host', e.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Email</label>
          <input
            type='email'
            value={config.email_user || ''}
            onChange={(e) => updateConfig('email_user', e.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>App Password</label>
          <input
            type='password'
            value={config.email_password || ''}
            onChange={(e) => updateConfig('email_password', e.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Auto-Print New Emails</label>
          <div className='flex items-center gap-2'>
            <input
              type='checkbox'
              checked={config.auto_print_new !== false} // Default to true
              onChange={(e) => updateConfig('auto_print_new', e.target.checked)}
              className='w-5 h-5 accent-blue-500 bg-[#333] border-gray-600 rounded focus:ring-blue-500 focus:ring-2'
            />
            <span className='text-sm text-gray-300'>Automatically print new emails as they arrive (checks every minute)</span>
          </div>
        </div>
      </div>
    );
  }

  if (module.type === 'games') {
    return (
      <div>
        <label className={labelClass}>Difficulty</label>
        <select value={config.difficulty || 'medium'} onChange={(e) => updateConfig('difficulty', e.target.value)} className={inputClass}>
          <option value='medium'>Medium</option>
          <option value='hard'>Hard</option>
        </select>
      </div>
    );
  }

  if (module.type === 'text') {
    return (
      <div className='space-y-3'>
        <div>
          <label className={labelClass}>Label</label>
          <input type='text' value={config.label || ''} onChange={(e) => updateConfig('label', e.target.value)} className={inputClass} />
        </div>
        <div>
          <label className={labelClass}>Content</label>
          <textarea
            value={config.content || ''}
            onChange={(e) => updateConfig('content', e.target.value)}
            onBlur={(e) => updateConfig('content', e.target.value, true)}
            className={`${inputClass} font-mono text-sm min-h-[120px]`}
          />
        </div>
      </div>
    );
  }

  if (module.type === 'calendar') {
    const addCalendarSource = () => {
      const currentSources = config.ical_sources || [];
      updateConfig('ical_sources', [...currentSources, { label: '', url: '' }]);
    };

    const updateCalendarSource = (index, field, value) => {
      const currentSources = [...(config.ical_sources || [])];
      currentSources[index] = { ...currentSources[index], [field]: value };
      updateConfig('ical_sources', currentSources);
    };

    const removeCalendarSource = (index) => {
      const currentSources = [...(config.ical_sources || [])];
      currentSources.splice(index, 1);
      updateConfig('ical_sources', currentSources);
    };

    return (
      <div className='space-y-3'>
        <div>
          <label className={labelClass}>Calendar Sources</label>
          <div className='space-y-3'>
            {(config.ical_sources || []).map((source, index) => (
              <div key={index} className='bg-[#1a1a1a] p-3 rounded border border-gray-800'>
                <div className='flex justify-between items-start mb-2'>
                  <span className='text-sm text-gray-400'>Calendar {index + 1}</span>
                  <button
                    type='button'
                    onClick={() => removeCalendarSource(index)}
                    className='px-2 py-1 text-xs bg-red-900/30 text-red-300 rounded hover:bg-red-900/50 transition-colors'>
                    Remove
                  </button>
                </div>
                <div className='space-y-2'>
                  <div>
                    <label className='block mb-1 text-xs text-gray-400'>Label</label>
                    <input
                      type='text'
                      value={source.label || ''}
                      onChange={(e) => updateCalendarSource(index, 'label', e.target.value)}
                      placeholder='e.g. Work, Holidays'
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className='block mb-1 text-xs text-gray-400'>iCal URL</label>
                    <input
                      type='text'
                      value={source.url || ''}
                      onChange={(e) => updateCalendarSource(index, 'url', e.target.value)}
                      placeholder='https://calendar.google.com/calendar/ical/...'
                      className={inputClass}
                    />
                  </div>
                </div>
              </div>
            ))}
            <button
              type='button'
              onClick={addCalendarSource}
              className='w-full py-2 bg-[#1a1a1a] border border-gray-600 hover:border-white rounded text-white transition-colors text-sm'>
              + Add Calendar
            </button>
          </div>
        </div>
        <div>
          <label className={labelClass}>Days to Show</label>
          <select
            value={config.days_to_show || 2}
            onChange={(e) => updateConfig('days_to_show', parseInt(e.target.value))}
            className={inputClass}>
            <option value={1}>Today Only</option>
            <option value={2}>Today + Tomorrow</option>
            <option value={3}>3 Days</option>
            <option value={7}>Next 7 Days</option>
          </select>
        </div>
      </div>
    );
  }

  return <div className='text-gray-400 text-sm'>No configuration needed for this module type.</div>;
};

export default ModuleConfig;
