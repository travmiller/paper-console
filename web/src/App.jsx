import { useState, useEffect } from 'react';

const AVAILABLE_MODULE_TYPES = [
  { id: 'news', label: 'News API' },
  { id: 'rss', label: 'RSS Feeds' },
  { id: 'weather', label: 'Weather' },
  { id: 'email', label: 'Email Inbox' },
  { id: 'games', label: 'Sudoku' },
  { id: 'astronomy', label: 'Astronomy' },
  { id: 'calendar', label: 'Calendar' },
  { id: 'webhook', label: 'Webhook' },
  { id: 'text', label: 'Text / Note' },
];

function App() {
  const [settings, setSettings] = useState({
    timezone: '',
    latitude: 0,
    longitude: 0,
    city_name: '',
    time_format: '12h',
    modules: {},
    channels: {},
  });
  const [modules, setModules] = useState({});
  const [status, setStatus] = useState({ type: '', message: '' });
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [activeTab, setActiveTab] = useState('channels'); // 'general', 'channels'
  const [showAddModuleModal, setShowAddModuleModal] = useState(null); // channel position or null
  const [showEditModuleModal, setShowEditModuleModal] = useState(null); // module ID or null
  const [showScheduleModal, setShowScheduleModal] = useState(null); // channel position or null

  // Fetch settings and modules on mount
  useEffect(() => {
    Promise.all([
      fetch('/api/settings').then((res) => res.json()),
      fetch('/api/modules').then((res) => res.json()),
    ])
      .then(([settingsData, modulesData]) => {
        setSettings(settingsData);
        setModules(modulesData.modules || {});
        setLoading(false);
      })
      .catch((err) => {
        console.error('Error fetching data:', err);
        setStatus({ type: 'error', message: 'Failed to load settings. Is the backend running?' });
        setLoading(false);
      });
  }, []);

  const handleSearch = async (term) => {
    setSearchTerm(term);
    if (term.length < 3) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    try {
      const response = await fetch(
        `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(term)}&count=5&language=en&format=json`,
      );
      const data = await response.json();
      if (data.results) {
        setSearchResults(data.results);
      } else {
        setSearchResults([]);
      }
    } catch (err) {
      console.error('Error fetching locations:', err);
    } finally {
      setIsSearching(false);
    }
  };

  const updateChannelSchedule = async (position, schedule) => {
    try {
      const response = await fetch(`/api/channels/${position}/schedule`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(schedule),
      });

      if (!response.ok) throw new Error('Failed to update schedule');

      const data = await response.json();
      setSettings((prev) => ({
        ...prev,
        channels: { ...prev.channels, [position]: data.channel },
      }));
      setStatus({ type: 'success', message: 'Schedule updated!' });
      setTimeout(() => setStatus({ type: '', message: '' }), 3000);
    } catch (err) {
      console.error('Error updating schedule:', err);
      setStatus({ type: 'error', message: 'Failed to update schedule' });
    }
  };

  const triggerChannelPrint = async (position) => {
    try {
      // Set dial position and trigger print
      await fetch(`/action/dial/${position}`, { method: 'POST' });
      const response = await fetch('/action/trigger', { method: 'POST' });
      
      if (!response.ok) throw new Error('Failed to trigger print');
      
      setStatus({ type: 'success', message: `Printing Channel ${position}...` });
      setTimeout(() => setStatus({ type: '', message: '' }), 3000);
    } catch (err) {
      console.error('Error triggering print:', err);
      setStatus({ type: 'error', message: 'Failed to trigger print' });
    }
  };

  const formatTimeForDisplay = (time24) => {
    if (!time24) return '';
    if (settings.time_format === '24h') return time24;
    
    const [hours, minutes] = time24.split(':');
    const h = parseInt(hours, 10);
    const ampm = h >= 12 ? 'PM' : 'AM';
    const h12 = h % 12 || 12;
    return `${h12}:${minutes} ${ampm}`;
  };

  // --- Settings Save ---

  const saveGlobalSettings = async (updates) => {
    // Optimistic update
    setSettings((prev) => ({ ...prev, ...updates }));

    try {
      const settingsToSave = {
        timezone: settings.timezone,
        latitude: settings.latitude,
        longitude: settings.longitude,
        city_name: settings.city_name,
        time_format: settings.time_format,
        openweather_api_key: settings.openweather_api_key,
        channels: settings.channels || {},
        modules: modules, // Include current modules
        ...updates, // Overwrite with new values
      };

      // Log for debugging
      console.log('Auto-saving settings:', updates);

      const response = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settingsToSave),
      });

      if (!response.ok) {
        throw new Error('Failed to save settings');
      }

      // We don't necessarily need to update state from response here if we trust our optimistic update,
      // but it's good practice to handle any server-side sanitization.
      // For now, we'll just rely on the optimistic update to keep UI snappy.
      
    } catch (err) {
      console.error('Error auto-saving settings:', err);
      setStatus({ type: 'error', message: 'Failed to save settings automatically.' });
    }
  };

  const selectLocation = (location) => {
    const updates = {
      city_name: location.name,
      latitude: location.latitude,
      longitude: location.longitude,
      timezone: location.timezone,
    };
    
    setSearchTerm('');
    setSearchResults([]);
    saveGlobalSettings(updates);
  };

  // --- Module Management ---

  const createModule = async (moduleType, name = '') => {
    try {
      const response = await fetch('/api/modules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: moduleType,
          name: name || `${AVAILABLE_MODULE_TYPES.find((m) => m.id === moduleType)?.label || moduleType}`,
          config: getDefaultConfig(moduleType),
        }),
      });

      if (!response.ok) throw new Error('Failed to create module');

      const data = await response.json();
      setModules((prev) => ({ ...prev, [data.module.id]: data.module }));
      setStatus({ type: 'success', message: 'Module created successfully!' });
      setTimeout(() => setStatus({ type: '', message: '' }), 3000);
      return data.module;
    } catch (err) {
      console.error('Error creating module:', err);
      setStatus({ type: 'error', message: 'Failed to create module' });
      return null;
    }
  };

  const updateModule = async (moduleId, updates) => {
    try {
      // Ensure we're updating the correct module by ID
      const targetModule = modules[moduleId];
      if (!targetModule) {
        console.error(`[UPDATE] Module ${moduleId} not found`);
        return;
      }

      // CRITICAL: Verify the update is for the correct module type
      if (updates.type && updates.type !== targetModule.type) {
        console.error(`[UPDATE] Type mismatch! Target module is ${targetModule.type}, but update has type ${updates.type}. Rejecting update.`);
        return;
      }

      // Ensure updates.id matches (if provided)
      if (updates.id && updates.id !== moduleId) {
        console.error(`[UPDATE] ID mismatch! Target module ID is ${moduleId}, but update has ID ${updates.id}. Rejecting update.`);
        return;
      }

      // Clean up config based on module type - remove invalid fields
      if (updates.config) {
        const cleanedConfig = { ...updates.config };
        if (targetModule.type === 'news') {
          // News modules should not have rss_feeds
          if (cleanedConfig.rss_feeds) {
            console.warn(`[UPDATE] Removing rss_feeds from news module ${moduleId}`);
          }
          delete cleanedConfig.rss_feeds;
          delete cleanedConfig.enable_newsapi; // This is also legacy
        } else if (targetModule.type === 'rss') {
          // RSS modules should not have news_api_key
          if (cleanedConfig.news_api_key) {
            console.warn(`[UPDATE] Removing news_api_key from RSS module ${moduleId}`);
          }
          delete cleanedConfig.news_api_key;
          delete cleanedConfig.enable_newsapi;
        }
        updates.config = cleanedConfig;
      }

      // Update local state optimistically for immediate UI feedback
      setModules((prev) => {
        const module = prev[moduleId];
        if (!module) return prev;
        return { ...prev, [moduleId]: { ...module, ...updates } };
      });

      // Build the full module object to send to backend
      const moduleToUpdate = { ...targetModule, ...updates };
      // Ensure ID is set correctly
      moduleToUpdate.id = moduleId;

      const response = await fetch(`/api/modules/${moduleId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(moduleToUpdate),
      });

      if (!response.ok) throw new Error('Failed to update module');

      const data = await response.json();
      setModules((prev) => ({ ...prev, [moduleId]: data.module }));
      setStatus({ type: 'success', message: 'Module updated successfully!' });
      setTimeout(() => setStatus({ type: '', message: '' }), 3000);
      // Don't close the editor automatically - let user control it
    } catch (err) {
      console.error('Error updating module:', err);
      setStatus({ type: 'error', message: 'Failed to update module' });
      // Revert optimistic update on error
      const response = await fetch(`/api/modules/${moduleId}`);
      if (response.ok) {
        const data = await response.json();
        setModules((prev) => ({ ...prev, [moduleId]: data.module }));
      }
    }
  };

  const deleteModule = async (moduleId) => {
    if (!confirm('Are you sure you want to delete this module?')) {
      return;
    }

    try {
      // 1. Find all channels this module is assigned to
      const assignments = [];
      for (const [pos, channel] of Object.entries(settings.channels)) {
        if (channel.modules && channel.modules.some(m => m.module_id === moduleId)) {
          assignments.push(pos);
        }
      }

      // 2. Remove from all channels first (Backend requires this before deletion)
      for (const pos of assignments) {
        await fetch(`/api/channels/${pos}/modules/${moduleId}`, {
          method: 'DELETE',
        });
      }

      // 3. Delete the module instance
      const response = await fetch(`/api/modules/${moduleId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to delete module');
      }

      // 4. Update Local State
      setModules((prev) => {
        const newModules = { ...prev };
        delete newModules[moduleId];
        return newModules;
      });

      setSettings((prev) => {
        const updatedChannels = { ...prev.channels };
        for (const pos in updatedChannels) {
          if (updatedChannels[pos].modules) {
            updatedChannels[pos].modules = updatedChannels[pos].modules.filter(
              (m) => m.module_id !== moduleId
            );
          }
        }
        return { ...prev, channels: updatedChannels };
      });

      setStatus({ type: 'success', message: 'Module deleted successfully!' });
      setTimeout(() => setStatus({ type: '', message: '' }), 3000);

      // Close edit modal if open
      if (showEditModuleModal === moduleId) {
        setShowEditModuleModal(null);
      }

    } catch (err) {
      console.error('Error deleting module:', err);
      setStatus({ type: 'error', message: err.message || 'Failed to delete module' });
    }
  };

  const getDefaultConfig = (moduleType) => {
    const defaults = {
      news: { news_api_key: '' },
      rss: { rss_feeds: [] },
      weather: {},
      email: { email_host: 'imap.gmail.com', email_user: '', email_password: '', polling_interval: 60 },
      games: { difficulty: 'medium' },
      astronomy: {},
      calendar: { ical_sources: [], label: 'My Calendar', days_to_show: 2 },
      webhook: { label: 'Webhook', url: '', method: 'GET', headers: {}, json_path: '' },
      text: { label: 'Note', content: '' },
    };
    return defaults[moduleType] || {};
  };

  // --- Channel Management ---

  const assignModuleToChannel = async (position, moduleId, order = null) => {
    try {
      const response = await fetch(`/api/channels/${position}/modules?module_id=${moduleId}${order !== null ? `&order=${order}` : ''}`, {
        method: 'POST',
      });

      if (!response.ok) throw new Error('Failed to assign module');

      const data = await response.json();
      setSettings((prev) => ({
        ...prev,
        channels: { ...prev.channels, [position]: data.channel },
      }));
      setStatus({ type: 'success', message: 'Module assigned to channel!' });
      setTimeout(() => setStatus({ type: '', message: '' }), 3000);
    } catch (err) {
      console.error('Error assigning module:', err);
      setStatus({ type: 'error', message: err.message || 'Failed to assign module' });
    }
  };

  const reorderChannelModules = async (position, moduleOrders) => {
    try {
      const response = await fetch(`/api/channels/${position}/modules/reorder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(moduleOrders),
      });

      if (!response.ok) throw new Error('Failed to reorder modules');

      const data = await response.json();
      setSettings((prev) => ({
        ...prev,
        channels: { ...prev.channels, [position]: data.channel },
      }));
    } catch (err) {
      console.error('Error reordering modules:', err);
      setStatus({ type: 'error', message: 'Failed to reorder modules' });
    }
  };

  const moveModuleInChannel = (position, moduleId, direction) => {
    const channel = settings.channels[position];
    if (!channel || !channel.modules) return;

    const sortedModules = [...channel.modules].sort((a, b) => a.order - b.order);
    const index = sortedModules.findIndex((m) => m.module_id === moduleId);
    if (index === -1) return;

    const newIndex = direction === 'up' ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= sortedModules.length) return;

    // Swap orders
    const tempOrder = sortedModules[index].order;
    sortedModules[index].order = sortedModules[newIndex].order;
    sortedModules[newIndex].order = tempOrder;

    const moduleOrders = {};
    sortedModules.forEach((m) => {
      moduleOrders[m.module_id] = m.order;
    });

    reorderChannelModules(position, moduleOrders);
  };

  const swapChannels = (pos1, pos2) => {
    const channel1 = settings.channels[pos1];
    const channel2 = settings.channels[pos2];
    
    const newChannels = {
      ...settings.channels,
      [pos1]: channel2 || { modules: [] },
      [pos2]: channel1 || { modules: [] },
    };

    saveGlobalSettings({ channels: newChannels });
  };

  // --- Settings Save ---
  // saveGlobalSettings defined above


  // --- Module Configuration Rendering ---

  const renderModuleConfig = (module, onUpdate) => {
    const config = module.config || {};
    const inputClass = 'w-full p-3 text-base bg-[#333] border border-gray-700 rounded text-white focus:border-white focus:outline-none';
    const labelClass = 'block mb-2 text-sm text-gray-400';
    
    // Capture the module ID to ensure we always update the correct module
    const moduleId = module.id;
    const moduleType = module.type;

    const updateConfig = (field, value) => {
      // Always use the latest module.config to avoid stale closures
      const currentConfig = module.config || {};
      // Only update the config, preserving the module ID and type from closure
      onUpdate({ 
        id: moduleId,
        type: moduleType,
        name: module.name,
        config: { ...currentConfig, [field]: value } 
      });
    };

    if (module.type === 'webhook') {
      return (
        <div className='space-y-3'>
          <div>
            <label className={labelClass}>Label</label>
            <input
              type='text'
              value={config.label || ''}
              onChange={(e) => updateConfig('label', e.target.value)}
              className={inputClass}
            />
          </div>
          <div className='flex gap-2'>
            <div className='w-1/4'>
              <label className={labelClass}>Method</label>
              <select
                value={config.method || 'GET'}
                onChange={(e) => updateConfig('method', e.target.value)}
                className={inputClass}>
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
              />
            </div>
          </div>
          <div>
            <label className={labelClass}>Headers (JSON)</label>
            <textarea
              value={JSON.stringify(config.headers || {}, null, 2)}
              onChange={(e) => {
                try {
                  updateConfig('headers', JSON.parse(e.target.value));
                } catch {}
              }}
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
            <p className='text-xs text-gray-500 mt-1'>
              Get your free API key from newsapi.org
            </p>
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
          Weather uses the global location settings configured in the General tab.
          No additional configuration needed.
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
              <span className='text-sm text-gray-300'>
                Automatically print new emails as they arrive (checks every minute)
              </span>
            </div>
          </div>
        </div>
      );
    }

    if (module.type === 'games') {
      return (
        <div>
          <label className={labelClass}>Difficulty</label>
          <select
            value={config.difficulty || 'medium'}
            onChange={(e) => updateConfig('difficulty', e.target.value)}
            className={inputClass}>
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
            <input
              type='text'
              value={config.label || ''}
              onChange={(e) => updateConfig('label', e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Content</label>
            <textarea
              value={config.content || ''}
              onChange={(e) => updateConfig('content', e.target.value)}
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

  if (loading) {
    return <div className='max-w-[800px] w-full p-8 text-center'>Loading settings...</div>;
  }

  const inputClass = 'w-full p-3 text-base bg-[#333] border border-gray-700 rounded text-white focus:border-white focus:outline-none box-border';
  const labelClass = 'block mb-2 font-bold text-gray-200';

  return (
    <div className='max-w-[800px] w-full p-8'>
      <h1 className='text-4xl mb-8 text-center leading-tight font-bold'>PC-1 Settings</h1>
      <p className='text-center text-gray-500 mb-8'>Configure your Paper Console</p>

      {/* Tabs */}
      <div className='flex gap-2 mb-6 border-b border-gray-700'>
        <button
          type='button'
          onClick={() => setActiveTab('general')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'general' ? 'border-b-2 border-white text-white' : 'text-gray-400 hover:text-white'
          }`}>
          General
        </button>
        <button
          type='button'
          onClick={() => setActiveTab('channels')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'channels' ? 'border-b-2 border-white text-white' : 'text-gray-400 hover:text-white'
          }`}>
          Channels
        </button>
      </div>

      <div className='contents'>
        {/* General Tab */}
        {activeTab === 'general' && (
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
                <p className='text-xs text-gray-500 mt-1'>
                  Choose how times are displayed across all modules
                </p>
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
                <label className={labelClass}>Invert Print (Upside Down)</label>
                <div className='flex items-center gap-2'>
                  <input
                    type='checkbox'
                    checked={settings.invert_print || false}
                    onChange={(e) => saveGlobalSettings({ invert_print: e.target.checked })}
                    className='w-4 h-4'
                  />
                  <span className='text-sm text-gray-300'>Rotate print output 180 degrees</span>
                </div>
                <p className='text-xs text-gray-500 mt-1'>
                  Enable if your printer outputs text upside down (due to paper orientation or hardware mounting)
                </p>
              </div>
            </div>

          </>
        )}


        {/* Channels Tab */}
        {activeTab === 'channels' && (
          <div className='space-y-4'>
            <h2 className='text-xl font-bold mb-4'>Channel Configuration</h2>
            <div className='grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-4'>
              {[1, 2, 3, 4, 5, 6, 7, 8].map((pos) => {
                const channel = settings.channels?.[pos] || { modules: [] };
                const channelModules = (channel.modules || [])
                  .map((assignment) => ({
                    ...assignment,
                    module: modules[assignment.module_id],
                  }))
                  .filter((item) => item.module)
                  .sort((a, b) => a.order - b.order);

                return (
                  <div key={pos} className='bg-[#2a2a2a] border border-gray-700 rounded-md p-4 flex flex-col h-full'>
                    <div className='flex items-center justify-between mb-3'>
                      <div className='flex items-center gap-2'>
                        <h3 className='font-bold text-white'>Channel {pos}</h3>
                        <button
                          type='button'
                          onClick={() => triggerChannelPrint(pos)}
                          className='text-xs px-2 py-0.5 rounded border bg-transparent text-gray-300 border-gray-500 hover:text-white hover:border-gray-400 transition-colors'
                          title='Print Channel'>
                          🖨
                        </button>
                        <button
                          type='button'
                          onClick={() => setShowScheduleModal(pos)}
                          className={`text-xs px-2 py-0.5 rounded border transition-colors ${
                            channel.schedule && channel.schedule.length > 0
                              ? 'bg-blue-900/30 text-blue-300 border-blue-800 hover:bg-blue-900/50'
                              : 'bg-transparent text-gray-500 border-gray-700 hover:text-gray-300'
                          }`}
                          title='Configure Schedule'>
                          ⏱ {channel.schedule?.length || 0}
                        </button>
                      </div>
                      <div className='flex gap-1'>
                        <button
                          type='button'
                          onClick={(e) => {
                            e.preventDefault();
                            swapChannels(pos, pos - 1);
                          }}
                          disabled={pos === 1}
                          className='px-2 py-1 text-xs bg-[#1a1a1a] border border-gray-600 hover:border-white rounded text-white transition-colors disabled:opacity-30'>
                          ↑
                        </button>
                        <button
                          type='button'
                          onClick={(e) => {
                            e.preventDefault();
                            swapChannels(pos, pos + 1);
                          }}
                          disabled={pos === 8}
                          className='px-2 py-1 text-xs bg-[#1a1a1a] border border-gray-600 hover:border-white rounded text-white transition-colors disabled:opacity-30'>
                          ↓
                        </button>
                      </div>
                    </div>

                    <div className='space-y-2 mb-4 flex-grow'>
                      {channelModules.map((item, idx) => (
                        <div
                          key={item.module_id}
                          className='flex items-center justify-between p-2 bg-[#1a1a1a] rounded border border-gray-800 group hover:border-gray-600 transition-colors cursor-pointer'
                          onClick={() => setShowEditModuleModal(item.module_id)}>
                          <div className='flex-1 min-w-0 mr-2'>
                            <div className='text-sm font-medium text-white truncate'>{item.module.name}</div>
                            <div className='text-xs text-gray-400 truncate'>
                              {AVAILABLE_MODULE_TYPES.find((t) => t.id === item.module.type)?.label}
                            </div>
                          </div>
                          <div className='flex gap-1' onClick={(e) => e.stopPropagation()}>
                            <div className='flex flex-col gap-0.5'>
                              <button
                                type='button'
                                onClick={() => moveModuleInChannel(pos, item.module_id, 'up')}
                                disabled={idx === 0}
                                className='px-1 text-[10px] leading-none text-gray-400 hover:text-white disabled:opacity-30'>
                                ▲
                              </button>
                              <button
                                type='button'
                                onClick={() => moveModuleInChannel(pos, item.module_id, 'down')}
                                disabled={idx === channelModules.length - 1}
                                className='px-1 text-[10px] leading-none text-gray-400 hover:text-white disabled:opacity-30'>
                                ▼
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}

                      {channelModules.length === 0 && (
                        <div className='text-center text-gray-500 py-8 text-sm border-2 border-dashed border-gray-800 rounded-md'>
                          Empty Channel
                        </div>
                      )}
                    </div>

                    <div className='pt-3 border-t border-gray-700 mt-auto'>
                      <button
                        type='button'
                        onClick={() => setShowAddModuleModal(pos)}
                        className='w-full py-2 bg-[#333] hover:bg-[#444] border border-gray-600 hover:border-gray-500 rounded text-white transition-colors text-sm font-medium'>
                        + Add Module
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Unassigned Modules Section removed */}
          </div>
        )}

        {/* Add Module Modal */}
        {showAddModuleModal !== null && (
          <div className='fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4' onClick={() => setShowAddModuleModal(null)}>
            <div className='bg-[#2a2a2a] border border-gray-700 rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto' onClick={e => e.stopPropagation()}>
              <div className='flex justify-between items-center mb-6'>
                <h3 className='text-xl font-bold text-white'>Add Module to Channel {showAddModuleModal}</h3>
                <button onClick={() => setShowAddModuleModal(null)} className='text-gray-400 hover:text-white text-2xl'>&times;</button>
              </div>
              
              <div className='grid grid-cols-2 md:grid-cols-3 gap-3'>
                {AVAILABLE_MODULE_TYPES.map((type) => (
                  <button
                    key={type.id}
                    type='button'
                    onClick={async () => {
                      const newModule = await createModule(type.id);
                      if (newModule) {
                        await assignModuleToChannel(showAddModuleModal, newModule.id);
                        setShowAddModuleModal(null);
                        setShowEditModuleModal(newModule.id);
                      }
                    }}
                    className='flex flex-col items-center p-4 bg-[#1a1a1a] border border-gray-700 hover:border-white rounded-lg transition-colors text-center group'>
                    <span className='font-bold text-white group-hover:text-blue-300 mb-1'>{type.label}</span>
                    <span className='text-xs text-gray-500'>Create new</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Edit Module Modal */}
        {showEditModuleModal !== null && modules[showEditModuleModal] && (
          <div className='fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4' onClick={() => setShowEditModuleModal(null)}>
            <div className='bg-[#2a2a2a] border border-gray-700 rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto' onClick={e => e.stopPropagation()}>
              <div className='flex justify-between items-start mb-6'>
                <div>
                  <h3 className='text-xl font-bold text-white mb-1'>Edit Module</h3>
                  <div className='text-sm text-gray-400 flex gap-4'>
                    <span>ID: {showEditModuleModal}</span>
                    <span>Type: {AVAILABLE_MODULE_TYPES.find(t => t.id === modules[showEditModuleModal].type)?.label}</span>
                  </div>
                </div>
                <button onClick={() => setShowEditModuleModal(null)} className='text-gray-400 hover:text-white text-2xl'>&times;</button>
              </div>

              <div className='mb-6'>
                <label className='block mb-2 text-sm text-gray-400'>Module Name</label>
                <input 
                  type="text" 
                  value={modules[showEditModuleModal].name}
                  onChange={(e) => updateModule(showEditModuleModal, { name: e.target.value })}
                  className="w-full p-3 text-base bg-[#333] border border-gray-700 rounded text-white focus:border-white focus:outline-none"
                />
              </div>

              {renderModuleConfig(modules[showEditModuleModal], (updated) => {
                // Always use the module ID from the current module, not from updated object
                const moduleId = modules[showEditModuleModal].id;
                console.log('[UPDATE] Updating module:', moduleId, 'Type:', modules[showEditModuleModal].type, 'Config:', updated.config);
                updateModule(moduleId, updated);
              })}

              <div className='mt-8 pt-6 border-t border-gray-700 flex justify-end gap-3'>
                <button
                  type='button'
                  onClick={() => deleteModule(showEditModuleModal)}
                  className='px-4 py-2 bg-red-900/20 text-red-400 border border-red-900/50 hover:bg-red-900/40 rounded transition-colors'>
                  Delete Module
                </button>
                <button
                  type='button'
                  onClick={() => setShowEditModuleModal(null)}
                  className='px-6 py-2 bg-white text-black font-medium rounded hover:bg-gray-200 transition-colors'>
                  Done
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Schedule Modal */}
        {showScheduleModal !== null && (
          <div className='fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4' onClick={() => setShowScheduleModal(null)}>
            <div className='bg-[#2a2a2a] border border-gray-700 rounded-lg p-6 max-w-md w-full' onClick={e => e.stopPropagation()}>
              <div className='flex justify-between items-center mb-6'>
                <h3 className='text-xl font-bold text-white'>Schedule Channel {showScheduleModal}</h3>
                <button onClick={() => setShowScheduleModal(null)} className='text-gray-400 hover:text-white text-2xl'>&times;</button>
              </div>

              <div className='space-y-4'>
                <div className='text-sm text-gray-400 mb-4'>
                  Add times when this channel should automatically print.
                </div>

                <div className='space-y-2 max-h-[300px] overflow-y-auto'>
                  {((settings.channels[showScheduleModal]?.schedule || [])).map((time, idx) => (
                    <div key={idx} className='flex items-center justify-between bg-[#1a1a1a] p-3 rounded border border-gray-800'>
                      <span className='text-white font-mono text-lg'>{formatTimeForDisplay(time)}</span>
                      <button
                        onClick={() => {
                          const newSchedule = [...(settings.channels[showScheduleModal]?.schedule || [])];
                          newSchedule.splice(idx, 1);
                          updateChannelSchedule(showScheduleModal, newSchedule);
                        }}
                        className='text-red-400 hover:text-red-300 px-2'>
                        &times;
                      </button>
                    </div>
                  ))}
                  {(!settings.channels[showScheduleModal]?.schedule || settings.channels[showScheduleModal]?.schedule.length === 0) && (
                    <div className='text-gray-600 text-center py-4 italic'>No scheduled times.</div>
                  )}
                </div>

                <div className='pt-4 border-t border-gray-700'>
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      const input = e.target.elements.timeInput;
                      const time = input.value;
                      if (time) {
                        const currentSchedule = settings.channels[showScheduleModal]?.schedule || [];
                        if (!currentSchedule.includes(time)) {
                          const newSchedule = [...currentSchedule, time].sort();
                          updateChannelSchedule(showScheduleModal, newSchedule);
                          input.value = '';
                        }
                      }
                    }}
                    className='flex gap-2'>
                    <input
                      name='timeInput'
                      type='time'
                      required
                      className='flex-1 bg-[#333] border border-gray-600 rounded px-3 py-2 text-white focus:outline-none focus:border-white'
                    />
                    <button
                      type='submit'
                      className='bg-white text-black px-4 py-2 rounded font-medium hover:bg-gray-200 transition-colors'>
                      Add
                    </button>
                  </form>
                </div>
              </div>
            </div>
          </div>
        )}

        {status.message && (
          <div
            className={`mt-4 p-4 rounded text-center border ${
              status.type === 'success' ? 'bg-green-500/10 text-green-400 border-green-500' : 'bg-red-500/10 text-red-400 border-red-400'
            }`}>
            {status.message}
          </div>
        )}
      </div>

      <div className='mt-8 pt-8 border-t border-gray-800 text-center'>
        <button
          onClick={async () => {
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
          }}
          className='bg-transparent text-red-900 text-sm hover:text-red-500 border border-red-900/30 hover:border-red-500/50 rounded px-4 py-2 transition-colors cursor-pointer'>
          Reset All Settings to Default
        </button>
      </div>
    </div>
  );
}

export default App;
