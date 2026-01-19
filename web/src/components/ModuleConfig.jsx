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
    const [headersList, setHeadersList] = useState(() => {
      const headers = config.headers || {};
      return Object.entries(headers).map(([key, value]) => ({ key, value }));
    });
    const isUpdatingRef = useRef(false);

    // Sync headers when config changes externally (but preserve empty headers being edited)
    useEffect(() => {
      if (isUpdatingRef.current) {
        return; // Skip sync if we're in the middle of a local update
      }
      
      const headers = config.headers || {};
      const configList = Object.entries(headers).map(([key, value]) => ({ key, value }));
      
      // Preserve empty headers from current list (user might be editing them)
      const emptyHeaders = headersList.filter((h) => !h.key.trim() && !h.value.trim());
      
      // Merge: empty headers first, then config headers
      const merged = [...emptyHeaders, ...configList];
      
      // Only update if actually different (to avoid infinite loops)
      if (JSON.stringify(merged) !== JSON.stringify(headersList)) {
        setHeadersList(merged);
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [config.headers]);

    const updateHeaders = (newHeadersList, saveToConfig = true) => {
      isUpdatingRef.current = true;
      setHeadersList(newHeadersList);
      if (saveToConfig) {
        const headersObj = {};
        newHeadersList.forEach(({ key, value }) => {
          if (key.trim()) {
            headersObj[key.trim()] = value.trim();
          }
        });
        updateConfig('headers', headersObj);
      }
      // Reset flag after state update
      setTimeout(() => {
        isUpdatingRef.current = false;
      }, 0);
    };

    const addHeader = () => {
      const newList = [...headersList, { key: '', value: '' }];
      updateHeaders(newList, false); // Don't save to config yet - wait for user to type
    };

    const removeHeader = (index) => {
      const newList = headersList.filter((_, i) => i !== index);
      updateHeaders(newList, true); // Save to config when removing
    };

    const updateHeader = (index, field, value) => {
      const newList = [...headersList];
      newList[index] = { ...newList[index], [field]: value };
      updateHeaders(newList, true); // Save to config when typing
    };

    const applyPreset = (preset) => {
      if (preset === 'dad-joke') {
        updateConfig('url', 'https://icanhazdadjoke.com/');
        updateConfig('method', 'GET');
        updateHeaders([{ key: 'Accept', value: 'application/json' }]);
        updateConfig('json_path', 'joke');
      } else if (preset === 'cat-fact') {
        updateConfig('url', 'https://catfact.ninja/fact');
        updateConfig('method', 'GET');
        updateHeaders([]);
        updateConfig('json_path', 'fact');
      } else if (preset === 'random-fact') {
        updateConfig('url', 'https://uselessfacts.jsph.pl/random.json?language=en');
        updateConfig('method', 'GET');
        updateHeaders([]);
        updateConfig('json_path', 'text');
      } else if (preset === 'clear') {
        updateConfig('url', '');
        updateConfig('method', 'GET');
        updateHeaders([]);
        updateConfig('json_path', '');
        updateConfig('body', '');
      }
    };

    return (
      <div className='space-y-4'>
        <div>
          <label className={labelClass}>Label</label>
          <input type='text' value={config.label || ''} onChange={(e) => updateConfig('label', e.target.value)} className={inputClass} placeholder='e.g. Dad Jokes' />
        </div>

        <div>
          <label className={labelClass}>Quick Presets</label>
          <div className='flex flex-wrap gap-2'>
            <button
              type='button'
              onClick={() => applyPreset('dad-joke')}
              className={`${commonClasses.buttonGhost} text-xs`}>
              Dad Joke
            </button>
            <button
              type='button'
              onClick={() => applyPreset('cat-fact')}
              className={`${commonClasses.buttonGhost} text-xs`}>
              Cat Fact
            </button>
            <button
              type='button'
              onClick={() => applyPreset('random-fact')}
              className={`${commonClasses.buttonGhost} text-xs`}>
              Random Fact
            </button>
            <button
              type='button'
              onClick={() => applyPreset('clear')}
              className={`${commonClasses.buttonGhost} text-xs`}>
              Clear
            </button>
          </div>
          <p className={`${commonClasses.textSubtle} mt-1`}>Click a preset to auto-fill common APIs</p>
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
            <input
              type='text'
              value={config.url || ''}
              onChange={(e) => updateConfig('url', e.target.value)}
              className={inputClass}
              placeholder='https://api.example.com/endpoint'
            />
          </div>
        </div>

        <div>
          <div className='flex justify-between items-center mb-2'>
            <label className={labelClass}>Headers (Optional)</label>
            <button type='button' onClick={addHeader} className={`${commonClasses.buttonGhost} text-xs`}>
              + Add Header
            </button>
          </div>
          {headersList.length === 0 ? (
            <p className={`${commonClasses.textSubtle} text-xs`}>No headers. Click "+ Add Header" to add authentication or custom headers.</p>
          ) : (
            <div className='space-y-2'>
              {headersList.map((header, index) => (
                <div key={index} className='flex gap-2 items-center'>
                  <input
                    type='text'
                    value={header.key}
                    onChange={(e) => updateHeader(index, 'key', e.target.value)}
                    placeholder='Header name'
                    className={`${commonClasses.inputSmall} flex-1`}
                  />
                  <input
                    type='text'
                    value={header.value}
                    onChange={(e) => updateHeader(index, 'value', e.target.value)}
                    placeholder='Header value'
                    className={`${commonClasses.inputSmall} flex-1`}
                  />
                  <button type='button' onClick={() => removeHeader(index)} className={`${commonClasses.buttonDanger} flex-shrink-0`}>
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {config.method === 'POST' && (
          <div>
            <label className={labelClass}>POST Body (JSON, Optional)</label>
            <textarea
              value={config.body || ''}
              onChange={(e) => updateConfig('body', e.target.value)}
              className={`${inputClass}  text-sm min-h-[80px]`}
              placeholder='{"key": "value"}'
            />
            <p className={`${commonClasses.textSubtle} mt-1`}>Enter JSON body for POST requests</p>
          </div>
        )}

        <div>
          <label className={labelClass}>JSON Path (Optional)</label>
          <input
            type='text'
            value={config.json_path || ''}
            onChange={(e) => updateConfig('json_path', e.target.value)}
            className={inputClass}
            placeholder='e.g. joke, fact, data.message, items[0].text'
          />
          <p className={`${commonClasses.textSubtle} mt-1`}>
            Extract a specific field from the JSON response. Leave empty to print the full response.
          </p>
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

        <div className={`pt-4 border-t-2 border-gray-300`}>
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
                className={`absolute w-full z-10 max-h-[200px] overflow-y-auto bg-white border-2 border-gray-300 border-t-0 rounded-b-lg shadow-lg list-none p-0 m-0`}>
                {searchResults.map((result) => (
                  <li
                    key={result.id}
                    onClick={() => selectLocation(result)}
                    className={`p-3 cursor-pointer border-b-2 border-gray-200 last:border-0 hover:bg-white transition-colors hover-shimmer`}>
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
                <span className='text-sm text-black font-medium '>{config.city_name}</span>
              </div>
              <div className='flex justify-between'>
                <span className={commonClasses.textSubtle}>Timezone</span>
                <span className='text-sm text-black '>{config.timezone || 'Not set'}</span>
              </div>
              <div className='flex justify-between'>
                <span className={commonClasses.textSubtle}>Coordinates</span>
                <span className='text-sm text-black '>
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
              className='w-5 h-5 bg-white border-2 border-gray-300 rounded focus:ring-2'
              style={{ accentColor: 'var(--color-brass)' }}
              onFocus={(e) => e.currentTarget.style.setProperty('--tw-ring-color', 'var(--color-brass)', 'important')}
            />
            <span className={`text-gray-600 text-sm `}>Automatically print new emails as they arrive (checks every minute)</span>
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
        <select value={config.count || 1} onChange={(e) => updateConfig('count', parseInt(e.target.value))} className={inputClass}>
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
            className={`${inputClass}  text-sm min-h-[120px]`}
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
      <div className='space-y-3'>
        <div>
          <label className={labelClass}>Items</label>
          <div className='space-y-1.5 max-h-[400px] overflow-y-auto pr-2'>
            {(config.items || []).map((item, index) => (
              <div key={index} className='flex gap-2 items-start group'>
                <span className='text-xs text-gray-400 flex-shrink-0 pt-1.5' style={{ fontFamily: 'monospace' }}>☐</span>
                <textarea
                  ref={(el) => {
                    inputRefs.current[`item-${index}`] = el;
                    if (el) {
                      el.style.height = 'auto';
                      el.style.height = el.scrollHeight + 'px';
                    }
                  }}
                  value={item?.text || ''}
                  onChange={(e) => {
                    updateChecklistItem(index, e.target.value);
                    e.target.style.height = 'auto';
                    e.target.style.height = e.target.scrollHeight + 'px';
                  }}
                  onKeyDown={(e) => handleKeyDown(e, index)}
                  placeholder='Enter item...'
                  rows={1}
                  className='flex-1 px-2 py-1.5 text-sm bg-transparent border-0 text-black focus:outline-none transition-colors resize-none overflow-visible'
                  style={{ backgroundColor: 'transparent', minHeight: '1.5rem', height: 'auto' }}
                  onInput={(e) => {
                    e.target.style.height = 'auto';
                    e.target.style.height = e.target.scrollHeight + 'px';
                  }}
                />
                <button 
                  type='button' 
                  onClick={() => removeChecklistItem(index)} 
                  className='opacity-0 group-hover:opacity-100 px-2 py-1 text-base text-red-600 hover:text-red-700 font-bold transition-opacity cursor-pointer'
                  title='Remove item'>
                  ×
                </button>
              </div>
            ))}
          </div>
          <button 
            type='button' 
            onClick={() => addChecklistItem()} 
            className='mt-3 w-full px-3 py-1.5 text-sm bg-transparent border-2 border-dashed border-gray-300 hover:border-black rounded-lg text-gray-500 hover:text-black transition-all cursor-pointer'>
            + Add Item
          </button>
        </div>
      </div>
    );
  }

  if (module.type === 'system_monitor') {
    return (
      <div className={commonClasses.textMuted}>
        Prints system status including IP address, disk usage, memory, uptime, and CPU temperature. No configuration needed.
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
          <label className={labelClass}>View Type</label>
          <select
            value={config.days_to_show || 2}
            onChange={(e) => updateConfig('days_to_show', parseInt(e.target.value))}
            className={inputClass}>
            <option value={1}>Timeline View (Today)</option>
            <option value={3}>Compact List (3 Days)</option>
            <option value={7}>Week View (7 Days)</option>
            <option value={2}>Month View</option>
          </select>
          <p className='text-xs text-gray-600 mt-1'>
            {config.days_to_show === 1 && 'Detailed timeline with hour markers and event positioning'}
            {config.days_to_show === 3 && 'Compact event list with visual separators'}
            {config.days_to_show === 7 && 'Week calendar grid with compact event list'}
            {config.days_to_show === 2 && 'Full month calendar grid with upcoming events list'}
          </p>
        </div>
      </div>
    );
  }

  if (module.type === 'qrcode') {
    const qrType = config.qr_type || 'text';
    
    return (
      <div className='space-y-4'>
        <div>
          <label className={labelClass}>Label</label>
          <input
            type='text'
            value={config.label || ''}
            onChange={(e) => updateConfig('label', e.target.value)}
            className={inputClass}
            placeholder='e.g. WiFi, My Contact'
          />
        </div>
        
        <div>
          <label className={labelClass}>QR Code Type</label>
          <select
            value={qrType}
            onChange={(e) => updateConfig('qr_type', e.target.value)}
            className={inputClass}>
            <option value='text'>Plain Text</option>
            <option value='url'>URL / Website</option>
            <option value='wifi'>WiFi Network</option>
            <option value='contact'>Contact Card (vCard)</option>
            <option value='phone'>Phone Number</option>
            <option value='sms'>SMS Message</option>
            <option value='email'>Email Address</option>
          </select>
        </div>
        
        {/* Text / URL / Phone / SMS / Email content */}
        {['text', 'url', 'phone', 'sms', 'email'].includes(qrType) && (
          <div>
            <label className={labelClass}>
              {qrType === 'text' && 'Text Content'}
              {qrType === 'url' && 'Website URL'}
              {qrType === 'phone' && 'Phone Number'}
              {qrType === 'sms' && 'Phone Number for SMS'}
              {qrType === 'email' && 'Email Address'}
            </label>
            {qrType === 'text' ? (
              <textarea
                value={config.content || ''}
                onChange={(e) => updateConfig('content', e.target.value)}
                className={`${inputClass} text-sm min-h-[80px]`}
                placeholder='Enter text to encode...'
              />
            ) : (
              <input
                type={qrType === 'email' ? 'email' : 'text'}
                value={config.content || ''}
                onChange={(e) => updateConfig('content', e.target.value)}
                className={inputClass}
                placeholder={
                  qrType === 'url' ? 'https://example.com' :
                  qrType === 'phone' ? '+1-555-123-4567' :
                  qrType === 'sms' ? '+1-555-123-4567' :
                  'email@example.com'
                }
              />
            )}
          </div>
        )}
        
        {/* WiFi fields */}
        {qrType === 'wifi' && (
          <>
            <div>
              <label className={labelClass}>Network Name (SSID)</label>
              <input
                type='text'
                value={config.wifi_ssid || ''}
                onChange={(e) => updateConfig('wifi_ssid', e.target.value)}
                className={inputClass}
                placeholder='MyWiFiNetwork'
              />
            </div>
            <div>
              <label className={labelClass}>Password</label>
              <input
                type='text'
                value={config.wifi_password || ''}
                onChange={(e) => updateConfig('wifi_password', e.target.value)}
                className={inputClass}
                placeholder='WiFi password'
              />
            </div>
            <div>
              <label className={labelClass}>Security Type</label>
              <select
                value={config.wifi_security || 'WPA'}
                onChange={(e) => updateConfig('wifi_security', e.target.value)}
                className={inputClass}>
                <option value='WPA'>WPA/WPA2/WPA3</option>
                <option value='WEP'>WEP</option>
                <option value='nopass'>Open (No Password)</option>
              </select>
            </div>
            <div className='flex items-center gap-2'>
              <input
                type='checkbox'
                checked={config.wifi_hidden || false}
                onChange={(e) => updateConfig('wifi_hidden', e.target.checked)}
                className='w-5 h-5 bg-white border-2 border-gray-300 rounded'
                style={{ accentColor: 'var(--color-brass)' }}
              />
              <span className={`text-gray-600 text-sm`}>Hidden Network</span>
            </div>
          </>
        )}
        
        {/* Contact (vCard) fields */}
        {qrType === 'contact' && (
          <>
            <div>
              <label className={labelClass}>Full Name</label>
              <input
                type='text'
                value={config.contact_name || ''}
                onChange={(e) => updateConfig('contact_name', e.target.value)}
                className={inputClass}
                placeholder='John Doe'
              />
            </div>
            <div>
              <label className={labelClass}>Phone Number (Optional)</label>
              <input
                type='text'
                value={config.contact_phone || ''}
                onChange={(e) => updateConfig('contact_phone', e.target.value)}
                className={inputClass}
                placeholder='+1-555-123-4567'
              />
            </div>
            <div>
              <label className={labelClass}>Email (Optional)</label>
              <input
                type='email'
                value={config.contact_email || ''}
                onChange={(e) => updateConfig('contact_email', e.target.value)}
                className={inputClass}
                placeholder='john@example.com'
              />
            </div>
          </>
        )}
        
      </div>
    );
  }

  return <div className={commonClasses.textMuted}>No configuration needed for this module type.</div>;
};

export default ModuleConfig;
