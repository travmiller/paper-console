import React, { useState, useRef, useEffect } from 'react';
import JsonTextarea from './JsonTextarea';
import { commonClasses } from '../design-tokens';

const ModuleConfig = ({ module, updateConfig }) => {
  const config = module.config || {};
  const inputClass = commonClasses.input;
  const labelClass = commonClasses.label;

  // Location search state for weather module
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);

  const handleLocationSearch = async (term) => {
    setSearchTerm(term);
    if (term.length < 2) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    try {
      const response = await fetch(`/api/location/search?q=${encodeURIComponent(term)}&limit=10`);
      const data = await response.json();
      if (data.results) {
        setSearchResults(data.results);
      } else {
        setSearchResults([]);
      }
    } catch (err) {
      console.error('Error fetching locations:', err);
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const selectLocation = (location) => {
    updateConfig('city_name', location.name);
    updateConfig('latitude', location.latitude);
    updateConfig('longitude', location.longitude);
    updateConfig('timezone', location.timezone);
    setSearchTerm('');
    setSearchResults([]);
  };

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
          <p className={`${commonClasses.textSubtle} mt-1`}>Get your free API key from newsapi.org</p>
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
              <div key={index} className={commonClasses.cardNested}>
                <div className='flex justify-between items-start mb-2'>
                  <span className={`${commonClasses.textMuted} text-sm`}>Feed {index + 1}</span>
                  <button type='button' onClick={() => removeRssFeed(index)} className={commonClasses.buttonDanger}>
                    Remove
                  </button>
                </div>
                <div>
                  <label className={commonClasses.labelSmall}>RSS Feed URL</label>
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
            <button type='button' onClick={addRssFeed} className={`${commonClasses.buttonSecondary} w-full text-sm`}>
              + Add RSS Feed
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (module.type === 'weather') {
    return (
      <div className='space-y-3'>
        <div>
          <label className={labelClass}>OpenWeather API Key (Optional)</label>
          <input
            type='password'
            value={config.openweather_api_key || ''}
            onChange={(e) => updateConfig('openweather_api_key', e.target.value)}
            className={inputClass}
            placeholder='Enter your OpenWeather API key (optional)'
          />
          <p className={`${commonClasses.textSubtle} mt-1`}>
            Optional: Get your free API key from openweathermap.org. If not provided, uses free Open-Meteo API.
          </p>
        </div>

        <div className={`pt-4 border-t border-gray-700`}>
          <label className={labelClass}>Location</label>
          <div className='mb-6 text-left relative'>
            <input
              type='text'
              value={searchTerm}
              onChange={(e) => handleLocationSearch(e.target.value)}
              placeholder='Type zip code or city name (e.g. 10001 or New York)'
              autoComplete='off'
              className={inputClass}
            />
            {searchResults.length > 0 && (
              <ul
                className={`absolute w-full z-10 max-h-[200px] overflow-y-auto bg-bg-input border border-bg-hover border-t-0 rounded-b shadow-lg list-none p-0 m-0`}>
                {searchResults.map((result) => (
                  <li
                    key={result.id}
                    onClick={() => selectLocation(result)}
                    className={`p-3 cursor-pointer border-b border-bg-hover last:border-0 hover:bg-bg-hover transition-colors`}>
                    <strong>{result.name}</strong>
                    <span className={`${commonClasses.textSubtle} text-xs ml-2`}>
                      {result.state} {result.zipcode ? `(${result.zipcode})` : ''}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {config.city_name && (
            <div className={`${commonClasses.cardNested} space-y-2`}>
              <div className='flex justify-between'>
                <span className={commonClasses.textSubtle}>City</span>
                <span className='text-sm text-white font-medium'>{config.city_name}</span>
              </div>
              <div className='flex justify-between'>
                <span className={commonClasses.textSubtle}>Timezone</span>
                <span className='text-sm text-white'>{config.timezone || 'Not set'}</span>
              </div>
              <div className='flex justify-between'>
                <span className={commonClasses.textSubtle}>Coordinates</span>
                <span className='text-sm text-white'>
                  {config.latitude?.toFixed(4)}, {config.longitude?.toFixed(4)}
                </span>
              </div>
            </div>
          )}
          {!config.city_name && (
            <p className={`${commonClasses.textSubtle} mt-1`}>
              Search and select a location above. If not set, will use global location settings as fallback.
            </p>
          )}
        </div>
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
            <span className={`text-gray-300 text-sm`}>Automatically print new emails as they arrive (checks every minute)</span>
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

  if (module.type === 'maze') {
    return <div className={commonClasses.textMuted}>Standard 15x15 maze. No configuration needed.</div>;
  }

  if (module.type === 'quotes') {
    return (
      <div className={commonClasses.textMuted}>
        Prints a random quote from the offline database (5,000+ quotes). No configuration needed.
      </div>
    );
  }

  if (module.type === 'history') {
    return (
      <div className='space-y-3'>
        <label className={labelClass}>Number of Events</label>
        <select value={config.count || 3} onChange={(e) => updateConfig('count', parseInt(e.target.value))} className={inputClass}>
          <option value={1}>1 Event</option>
          <option value={3}>3 Events</option>
          <option value={5}>5 Events</option>
          <option value={10}>10 Events</option>
        </select>
        <p className={commonClasses.textSubtle}>Prints random historical events that happened on today's date (from offline database).</p>
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

  if (module.type === 'checklist') {
    const inputRefs = useRef({});

    const addChecklistItem = (afterIndex = null) => {
      const currentConfig = module.config || {};
      const currentItems = currentConfig.items || [];
      const newIndex = afterIndex !== null ? afterIndex + 1 : currentItems.length;
      const newItems = [...currentItems];
      newItems.splice(newIndex, 0, { text: '' });
      updateConfig('items', newItems);

      // Focus the new input after it's rendered
      setTimeout(() => {
        const input = inputRefs.current[`item-${newIndex}`];
        if (input) {
          input.focus();
        }
      }, 0);
    };

    const updateChecklistItem = (index, value) => {
      const currentConfig = module.config || {};
      const currentItems = [...(currentConfig.items || [])];
      if (!currentItems[index]) {
        currentItems[index] = { text: '' };
      }
      currentItems[index] = { ...currentItems[index], text: value };
      updateConfig('items', currentItems);
    };

    const removeChecklistItem = (index) => {
      const currentConfig = module.config || {};
      const currentItems = [...(currentConfig.items || [])];
      currentItems.splice(index, 1);
      updateConfig('items', currentItems);

      // Focus the previous input or the next one if it was the first
      setTimeout(() => {
        const focusIndex = index > 0 ? index - 1 : 0;
        if (currentItems.length > 0) {
          const input = inputRefs.current[`item-${focusIndex}`];
          if (input) {
            input.focus();
          }
        }
      }, 0);
    };

    const handleKeyDown = (e, index) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        addChecklistItem(index);
      } else if (e.key === 'Backspace' && e.target.value === '') {
        e.preventDefault();
        if ((config.items || []).length > 0) {
          removeChecklistItem(index);
        }
      }
    };

    // Ensure at least one item exists on initial mount
    useEffect(() => {
      const currentItems = config.items || [];
      if (currentItems.length === 0) {
        const currentConfig = module.config || {};
        const newItems = [{ text: '' }];
        updateConfig('items', newItems);
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
      <div className='space-y-2'>
        <div>
          <label className={labelClass}>Items</label>
          <div className='space-y-2'>
            {(config.items || []).map((item, index) => (
              <div key={index} className={`${commonClasses.cardNestedSmall} flex gap-2 items-center`}>
                <input
                  ref={(el) => (inputRefs.current[`item-${index}`] = el)}
                  type='text'
                  value={item?.text || ''}
                  onChange={(e) => updateChecklistItem(index, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(e, index)}
                  placeholder='Enter item...'
                  className={`${commonClasses.inputSmall} flex-1`}
                />
                <button type='button' onClick={() => removeChecklistItem(index)} className={`${commonClasses.buttonDanger} flex-shrink-0`}>
                  ×
                </button>
              </div>
            ))}
            <button type='button' onClick={() => addChecklistItem()} className={`${commonClasses.buttonSecondary} w-full py-1.5 text-sm`}>
              + Add Item
            </button>
          </div>
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
              <div key={index} className={commonClasses.cardNested}>
                <div className='flex justify-between items-start mb-2'>
                  <span className={`${commonClasses.textMuted} text-sm`}>Calendar {index + 1}</span>
                  <button type='button' onClick={() => removeCalendarSource(index)} className={commonClasses.buttonDanger}>
                    Remove
                  </button>
                </div>
                <div className='space-y-2'>
                  <div>
                    <label className={commonClasses.labelSmall}>Label</label>
                    <input
                      type='text'
                      value={source.label || ''}
                      onChange={(e) => updateCalendarSource(index, 'label', e.target.value)}
                      placeholder='e.g. Work, Holidays'
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className={commonClasses.labelSmall}>iCal URL</label>
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
            <button type='button' onClick={addCalendarSource} className={`${commonClasses.buttonSecondary} w-full text-sm`}>
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

  return <div className={commonClasses.textMuted}>No configuration needed for this module type.</div>;
};

export default ModuleConfig;
