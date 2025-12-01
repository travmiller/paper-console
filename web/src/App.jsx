import { useState, useEffect, useRef, useCallback } from 'react';

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
  // Track where mouse down occurred to prevent accidental modal closes
  const modalMouseDownTarget = useRef(null);

  // Refs for debounced saving
  const settingsRef = useRef(settings);
  const modulesRef = useRef(modules);
  const settingsUpdateTimer = useRef(null);

  // Keep refs updated
  useEffect(() => { settingsRef.current = settings; }, [settings]);
  useEffect(() => { modulesRef.current = modules; }, [modules]);

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
      const response = await fetch('/action/trigger', { method: 'POST' });
      if (response.ok) {
        setStatus({ type: 'success', message: 'Triggered!' });
        setTimeout(() => setStatus({ type: '', message: '' }), 3000);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const triggerModulePrint = async (moduleId) => {
    try {
      const response = await fetch(`/debug/print-module/${moduleId}`, { method: 'POST' });
      if (response.ok) {
        setStatus({ type: 'success', message: 'Module triggered!' });
        setTimeout(() => setStatus({ type: '', message: '' }), 3000);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // --- Settings Save ---

  const saveGlobalSettings = async (updates, debounce = false) => {
    // Optimistic update immediately
    setSettings((prev) => ({ ...prev, ...updates }));

    // Helper to perform the actual fetch
    const performSave = async (finalUpdates) => {
      try {
        // Use Refs to get the absolutely latest state, merging with our specific updates
        const settingsToSave = {
          ...settingsRef.current, 
          channels: settingsRef.current.channels || {},
          modules: modulesRef.current, // Use latest modules
          ...finalUpdates, // Apply the specific updates on top
        };

        // Log for debugging
        console.log('Auto-saving settings:', finalUpdates);

        const response = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(settingsToSave),
        });

        if (!response.ok) {
          throw new Error('Failed to save settings');
        }
      } catch (err) {
        console.error('Error auto-saving settings:', err);
        setStatus({ type: 'error', message: 'Failed to save settings automatically.' });
      }
    };

    if (debounce) {
      // Clear existing timer
      if (settingsUpdateTimer.current) {
        clearTimeout(settingsUpdateTimer.current);
      }
      // Set new timer
      settingsUpdateTimer.current = setTimeout(() => {
        performSave(updates);
      }, 1000);
    } else {
      // Immediate save
      performSave(updates);
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

  // Simple ID generator for optimistic updates
  const generateId = () => 'mod_' + Math.random().toString(36).substr(2, 9);

  const createModule = async (moduleType, name = '') => {
    const tempId = generateId();
    const newModule = {
      id: tempId,
      type: moduleType,
      name: name || moduleType,
      config: {}
    };

    // Optimistic update
    setModules((prev) => ({ ...prev, [tempId]: newModule }));
    
    // If we were in "Add Module" flow for a channel, assign it immediately (optimistically)
    if (showAddModuleModal) {
      assignModuleToChannel(showAddModuleModal, tempId); // This is now optimistic too
      setShowAddModuleModal(null);
    }
    
    // Open edit modal immediately
    setShowEditModuleModal(tempId);

    try {
      const response = await fetch('/api/modules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newModule), // Send the ID we generated
      });
      
      if (!response.ok) throw new Error('Failed to create module');
      
      // The server might return a normalized object, but ID should match if we sent it.
      // If backend ignores our ID, we'd be in trouble, but app/main.py uses provided ID if present.
      const data = await response.json();
      
      // Update with server response just in case (e.g. server-side defaults)
      setModules((prev) => ({ ...prev, [data.module.id]: data.module }));
      
    } catch (err) {
      console.error('Error creating module:', err);
      setStatus({ type: 'error', message: 'Failed to create module' });
      // Revert optimistic creation
      setModules((prev) => {
        const next = { ...prev };
        delete next[tempId];
        return next;
      });
      setShowEditModuleModal(null);
    }
  };

  const assignModuleToChannel = async (position, moduleId) => {
    // Optimistic update
    setSettings((prev) => {
      const channel = prev.channels[position] || { modules: [] };
      const currentModules = channel.modules || [];
      // Calculate next order
      const maxOrder = currentModules.reduce((max, m) => Math.max(max, m.order), -1);
      const newAssignment = { module_id: moduleId, order: maxOrder + 1 };
      
      return {
        ...prev,
        channels: {
          ...prev.channels,
          [position]: { ...channel, modules: [...currentModules, newAssignment] }
        }
      };
    });

    try {
      const response = await fetch(`/api/channels/${position}/modules?module_id=${moduleId}`, {
        method: 'POST',
      });
      
      if (!response.ok) throw new Error('Failed to assign module');
      
      // Sync with server response to ensure consistency
      const data = await response.json();
      setSettings((prev) => ({
        ...prev,
        channels: { ...prev.channels, [position]: data.channel }
      }));
      
    } catch (err) {
      console.error('Error assigning module:', err);
      setStatus({ type: 'error', message: 'Failed to assign module' });
      // Revert logic could go here (reload settings)
      // For now, user sees error and can refresh
    }
  };

  const removeModuleFromChannel = async (position, moduleId) => {
    // Optimistic update
    setSettings((prev) => {
      const channel = prev.channels[position];
      if (!channel || !channel.modules) return prev;
      
      return {
        ...prev,
        channels: {
          ...prev.channels,
          [position]: {
            ...channel,
            modules: channel.modules.filter(m => m.module_id !== moduleId)
          }
        }
      };
    });

    try {
      const response = await fetch(`/api/channels/${position}/modules/${moduleId}`, {
        method: 'DELETE',
      });
      
      if (!response.ok) throw new Error('Failed to remove module');
      
      const data = await response.json();
      // Sync with server response
      setSettings((prev) => ({
        ...prev,
        channels: { ...prev.channels, [position]: data.channel }
      }));
      
    } catch (err) {
      console.error('Error removing module:', err);
      setStatus({ type: 'error', message: 'Failed to remove module' });
    }
  };

  const moveModule = async (position, moduleId, direction) => {
    // Calculate new state first for optimistic update
    let optimisticSuccess = false;
    
    setSettings((prev) => {
      const channel = prev.channels[position];
      if (!channel || !channel.modules) return prev;
      
      const currentIndex = channel.modules.findIndex(m => m.module_id === moduleId);
      if (currentIndex === -1) return prev;
      
      const newIndex = currentIndex + direction;
      if (newIndex < 0 || newIndex >= channel.modules.length) return prev;
      
      // Create copy and swap
      const newModules = [...channel.modules];
      // Swap orders logic: in array representation, we swap positions. 
      // But we also need to swap the 'order' property if we rely on it for sorting.
      // The render sorts by order. So we must swap order values.
      
      const tempOrder = newModules[currentIndex].order;
      newModules[currentIndex] = { ...newModules[currentIndex], order: newModules[newIndex].order };
      newModules[newIndex] = { ...newModules[newIndex], order: tempOrder };
      
      optimisticSuccess = true;
      
      return {
        ...prev,
        channels: {
          ...prev.channels,
          [position]: { ...channel, modules: newModules }
        }
      };
    });

    if (!optimisticSuccess) return;
    
    // We need to calculate the order map to send to server
    // We can grab the state we just set? No, React state update is async.
    // We need to reconstruct the map from the logic we just used.
    // Actually, reusing the existing moveModule logic for the API call is fine, 
    // but we need to construct the moduleOrders map based on the *new* state.
    
    // Let's reconstruct the channel modules from the *current* settings (before update) + the swap
    const channel = settings.channels[position];
    const currentIndex = channel.modules.findIndex(m => m.module_id === moduleId);
    const newIndex = currentIndex + direction;
    const newModules = [...channel.modules];
    [newModules[currentIndex], newModules[newIndex]] = [newModules[newIndex], newModules[currentIndex]];
    
    const moduleOrders = {};
    newModules.forEach((m, index) => {
      // We assign index as order to be clean
      moduleOrders[m.module_id] = index;
    });
    
    try {
      const response = await fetch(`/api/channels/${position}/modules/reorder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(moduleOrders),
      });
      
      if (!response.ok) throw new Error('Failed to reorder modules');
      
      const data = await response.json();
      // Confirm with server state
      setSettings((prev) => ({
        ...prev,
        channels: { ...prev.channels, [position]: data.channel }
      }));
      
    } catch (err) {
      console.error('Error reordering modules:', err);
      // Revert by reloading settings (lazy way)
      // fetch('/api/settings').then(res => res.json()).then(setSettings);
    }
  };

  const moduleUpdateTimers = useRef({});

  const updateModule = async (moduleId, updates, immediate = false) => {
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

  // Debounced version for when modal is open
  const updateModuleDebounced = useCallback((moduleId, updates, delay = 1500) => {
    // Clear existing timer for this module
    if (moduleUpdateTimers.current[moduleId]) {
      clearTimeout(moduleUpdateTimers.current[moduleId]);
    }

    // Set new timer
    moduleUpdateTimers.current[moduleId] = setTimeout(() => {
      updateModule(moduleId, updates, true);
      delete moduleUpdateTimers.current[moduleId];
    }, delay);
  }, []);

  const deleteModule = async (moduleId) => {
    if (!confirm('Are you sure you want to delete this module?')) return;
    
    // Optimistic update
    setModules((prev) => {
      const next = { ...prev };
      delete next[moduleId];
      return next;
    });
    
    setSettings((prev) => {
      const newChannels = { ...prev.channels };
      Object.keys(newChannels).forEach(pos => {
        if (newChannels[pos].modules) {
          newChannels[pos].modules = newChannels[pos].modules.filter(m => m.module_id !== moduleId);
        }
      });
      return { ...prev, channels: newChannels };
    });
    
    setShowEditModuleModal(null);

    try {
      const response = await fetch(`/api/modules/${moduleId}`, {
        method: 'DELETE',
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to delete module');
      }
      
      // Success - UI already updated
      setStatus({ type: 'success', message: 'Module deleted' });
      setTimeout(() => setStatus({ type: '', message: '' }), 3000);
      
    } catch (err) {
      console.error('Error deleting module:', err);
      setStatus({ type: 'error', message: err.message });
      // Revert: reload full state
      fetch('/api/settings').then(res => res.json()).then(setSettings);
      fetch('/api/modules').then(res => res.json()).then(data => setModules(data.modules));
    }
  };

  // --- UI Helper Components ---

  const Modal = ({ title, children, onClose }) => (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4" onClick={(e) => {
      // Only close if clicking the background, not the modal content
      if (e.target === e.currentTarget) onClose();
    }}>
      <div 
        className="bg-[#222] rounded-lg border border-gray-700 w-full max-w-2xl max-h-[90vh] overflow-y-auto flex flex-col shadow-2xl"
        onMouseDown={(e) => { modalMouseDownTarget.current = e.currentTarget; }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center p-6 border-b border-gray-700 sticky top-0 bg-[#222] z-10">
          <h2 className="text-xl font-bold">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        <div className="p-6 flex-grow">
          {children}
        </div>
      </div>
    </div>
  );

  // --- Module Configuration Rendering ---

  const renderModuleConfig = (module, onUpdate) => {
    const config = module.config || {};
    const inputClass = 'w-full p-3 text-base bg-[#333] border border-gray-700 rounded text-white focus:border-white focus:outline-none';
    const labelClass = 'block mb-2 text-sm text-gray-400';
    
    // Capture the module ID to ensure we always update the correct module
    const moduleId = module.id;
    const moduleType = module.type;

    const updateConfig = (field, value, immediate = false) => {
      // Always use the latest module.config to avoid stale closures
      const currentConfig = module.config || {};
      // Only update the config, preserving the module ID and type from closure
      const updated = { 
        id: moduleId,
        type: moduleType,
        name: module.name,
        config: { ...currentConfig, [field]: value } 
      };
      
      // Always update local state immediately for responsive UI
      setModules((prev) => {
        const mod = prev[moduleId];
        if (!mod) return prev;
        return { ...prev, [moduleId]: { ...mod, ...updated } };
      });
      
      if (immediate) {
        // For immediate updates (on blur), call updateModule directly
        updateModule(moduleId, updated, true);
      } else {
        // For typing, use debounced update (but local state already updated above)
        onUpdate(updated);
      }
    };

    if (module.type === 'webhook') {
      return (
        <div className='space-y-4'>
          <div>
            <label className={labelClass}>Label (for receipt)</label>
            <input
              type='text'
              value={config.label || ''}
              onChange={(e) => updateConfig('label', e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>URL</label>
            <input
              type='url'
              value={config.url || ''}
              onChange={(e) => updateConfig('url', e.target.value)}
              onBlur={(e) => updateConfig('url', e.target.value, true)}
              className={inputClass}
              placeholder='https://api.example.com/data'
            />
          </div>
          <div className='grid grid-cols-2 gap-4'>
            <div>
              <label className={labelClass}>Method</label>
              <select
                value={config.method || 'GET'}
                onChange={(e) => updateConfig('method', e.target.value)}
                className={inputClass}>
                <option value='GET'>GET</option>
                <option value='POST'>POST</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>JSON Path (Optional)</label>
              <input
                type='text'
                value={config.json_path || ''}
                onChange={(e) => updateConfig('json_path', e.target.value)}
                className={inputClass}
                placeholder='e.g. data.fact'
              />
            </div>
          </div>
          <div>
            <label className={labelClass}>Test Webhook</label>
            <button
              onClick={async () => {
                try {
                  const res = await fetch('/debug/test-webhook', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config),
                  });
                  if (res.ok) {
                    setStatus({ type: 'success', message: 'Webhook test triggered!' });
                    setTimeout(() => setStatus({ type: '', message: '' }), 3000);
                  }
                } catch (err) {
                  console.error(err);
                }
              }}
              className='bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded text-sm transition-colors'>
              Test Fire
            </button>
          </div>
        </div>
      );
    }

    if (module.type === 'news') {
      return (
        <div className='space-y-4'>
          <div className='p-4 bg-blue-900/20 border border-blue-800 rounded mb-4 text-sm text-blue-200'>
            This module fetches top headlines from NewsAPI.org. Requires a valid API Key.
          </div>
          <div>
            <label className={labelClass}>NewsAPI Key</label>
            <input
              type='text'
              value={config.news_api_key || ''}
              onChange={(e) => updateConfig('news_api_key', e.target.value)}
              onBlur={(e) => updateConfig('news_api_key', e.target.value, true)}
              className={inputClass}
              placeholder='Get key from newsapi.org'
            />
          </div>
        </div>
      );
    }

    if (module.type === 'rss') {
      const feeds = config.rss_feeds || [];
      
      const updateFeed = (index, value) => {
        const newFeeds = [...feeds];
        newFeeds[index] = value;
        updateConfig('rss_feeds', newFeeds);
      };

      const addFeed = () => {
        updateConfig('rss_feeds', [...feeds, '']);
      };

      const removeFeed = (index) => {
        const newFeeds = feeds.filter((_, i) => i !== index);
        updateConfig('rss_feeds', newFeeds);
      };

      return (
        <div className='space-y-4'>
          <div className='p-4 bg-gray-800 rounded mb-4 text-sm text-gray-300'>
            Add one or more RSS feed URLs. The printer will summarize headlines.
          </div>
          
          <label className={labelClass}>RSS Feeds</label>
          {feeds.map((feed, idx) => (
            <div key={idx} className='flex gap-2 mb-2'>
              <input
                type='url'
                value={feed}
                onChange={(e) => updateFeed(idx, e.target.value)}
                onBlur={(e) => updateFeed(idx, e.target.value, true)}
                className={inputClass}
                placeholder='https://example.com/feed.xml'
              />
              <button
                onClick={() => removeFeed(idx)}
                className='bg-red-900/50 hover:bg-red-900 text-red-200 px-3 rounded border border-red-800 transition-colors'>
                ×
              </button>
            </div>
          ))}
          <button
            onClick={addFeed}
            className='text-sm text-blue-400 hover:text-blue-300 font-medium'>
            + Add Feed URL
          </button>
        </div>
      );
    }

    if (module.type === 'email') {
      return (
        <div className='space-y-4'>
          <div className='grid grid-cols-2 gap-4'>
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
              <label className={labelClass}>Polling (sec)</label>
              <input
                type='number'
                value={config.polling_interval || 30}
                onChange={(e) => updateConfig('polling_interval', parseInt(e.target.value) || 30)}
                className={inputClass}
              />
            </div>
          </div>
          <div>
            <label className={labelClass}>Email User</label>
            <input
              type='text'
              value={config.email_user || ''}
              onChange={(e) => updateConfig('email_user', e.target.value)}
              onBlur={(e) => updateConfig('email_user', e.target.value, true)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>App Password</label>
            <input
              type='password'
              value={config.email_password || ''}
              onChange={(e) => updateConfig('email_password', e.target.value)}
              onBlur={(e) => updateConfig('email_password', e.target.value, true)}
              className={inputClass}
              placeholder='Google App Password (not login pw)'
            />
          </div>
          <div className='flex items-center gap-2 mt-2'>
            <input 
              type="checkbox" 
              checked={config.auto_print_new !== false} 
              onChange={(e) => updateConfig('auto_print_new', e.target.checked)}
              className="w-4 h-4"
            />
            <span className="text-sm text-gray-300">Auto-print new emails on arrival</span>
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
              onBlur={(e) => updateConfig('content', e.target.value, true)}
              className={`${inputClass} font-mono text-sm min-h-[120px]`}
            />
          </div>
        </div>
      );
    }

    if (module.type === 'calendar') {
      const sources = config.ical_sources || [];
      
      const updateSource = (index, field, value) => {
        const newSources = [...sources];
        newSources[index] = { ...newSources[index], [field]: value };
        updateConfig('ical_sources', newSources);
      };

      const addSource = () => {
        updateConfig('ical_sources', [...sources, { label: 'New Cal', url: '' }]);
      };

      const removeSource = (index) => {
        const newSources = sources.filter((_, i) => i !== index);
        updateConfig('ical_sources', newSources);
      };

      return (
        <div className='space-y-4'>
          <div>
            <label className={labelClass}>Header Label</label>
            <input
              type='text'
              value={config.label || 'Calendar'}
              onChange={(e) => updateConfig('label', e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Days to Show</label>
            <input
              type='number'
              min="1"
              max="7"
              value={config.days_to_show || 2}
              onChange={(e) => updateConfig('days_to_show', parseInt(e.target.value) || 1)}
              className={inputClass}
            />
          </div>
          
          <div className="border-t border-gray-700 pt-4 mt-2">
            <label className={labelClass}>iCal Sources</label>
            {sources.map((source, idx) => (
              <div key={idx} className='bg-gray-800 p-3 rounded mb-3'>
                <div className="flex justify-between mb-2">
                  <span className="text-xs text-gray-500">Source #{idx+1}</span>
                  <button onClick={() => removeSource(idx)} className="text-red-400 hover:text-red-300 text-xs">Remove</button>
                </div>
                <input
                  type='text'
                  value={source.label}
                  onChange={(e) => updateSource(idx, 'label', e.target.value)}
                  className={`${inputClass} mb-2 text-sm py-2`}
                  placeholder='Label (e.g. Work)'
                />
                <input
                  type='url'
                  value={source.url}
                  onChange={(e) => updateSource(idx, 'url', e.target.value)}
                  onBlur={(e) => updateSource(idx, 'url', e.target.value, true)}
                  className={`${inputClass} text-sm py-2`}
                  placeholder='https://...'
                />
              </div>
            ))}
            <button
              onClick={addSource}
              className='text-sm text-blue-400 hover:text-blue-300 font-medium'>
              + Add iCal Source
            </button>
          </div>
        </div>
      );
    }

    return <div className='text-gray-500 italic'>No configuration available for this module.</div>;
  };

  const inputClass = 'w-full p-3 text-base bg-[#333] border border-gray-700 rounded text-white focus:border-white focus:outline-none';
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
            <div className='mb-6 relative'>
              <label className={labelClass}>Location</label>
              <div className='relative'>
                <input
                  type='text'
                  placeholder='Search for your city...'
                  value={searchTerm}
                  onChange={(e) => handleSearch(e.target.value)}
                  className={inputClass}
                />
                {isSearching && (
                  <div className='absolute right-3 top-3 text-gray-400'>
                    <svg className='animate-spin h-5 w-5' viewBox='0 0 24 24'>
                      <circle
                        className='opacity-25'
                        cx='12'
                        cy='12'
                        r='10'
                        stroke='currentColor'
                        strokeWidth='4'></circle>
                      <path
                        className='opacity-75'
                        fill='currentColor'
                        d='M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z'></path>
                    </svg>
                  </div>
                )}
              </div>

              {searchResults.length > 0 && (
                <div className='absolute top-full left-0 right-0 bg-[#222] border border-gray-700 rounded-b shadow-xl z-10 max-h-[200px] overflow-y-auto'>
                  {searchResults.map((result) => (
                    <button
                      key={result.id}
                      onClick={() => selectLocation(result)}
                      className='w-full text-left p-3 hover:bg-gray-800 border-b border-gray-700 last:border-0 transition-colors'>
                      <div className='font-bold'>
                        {result.name}, {result.admin1}
                      </div>
                      <div className='text-xs text-gray-400'>
                        {result.country} • {result.latitude.toFixed(2)}, {result.longitude.toFixed(2)}
                      </div>
                    </button>
                  ))}
                </div>
              )}

              <div className='mt-2 text-sm text-gray-400 flex justify-between'>
                <span>
                  Current: <span className='text-white font-medium'>{settings.city_name || 'Unknown'}</span>
                </span>
                <span>{settings.timezone}</span>
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
                  onChange={(e) => saveGlobalSettings({ cutter_feed_lines: parseInt(e.target.value) || 0 }, true)} 
                  className={inputClass}
                />
                <p className='text-xs text-gray-500 mt-1'>
                  Number of empty lines to add at the end of each print job to clear the cutter (default: 3)
                </p>
              </div>
              
              <div className='mb-4'>
                <label className={labelClass}>Invert Print</label>
                <div className='flex items-center gap-2'>
                  <input
                    type='checkbox'
                    checked={settings.invert_print || false}
                    onChange={(e) => saveGlobalSettings({ invert_print: e.target.checked })}
                    className='w-4 h-4'
                  />
                  <span className='text-sm text-gray-300'>Rotate output 180°</span>
                </div>
              </div>
            </div>

          </>
        )}


        {/* Channels Tab */}
        {activeTab === 'channels' && (
          
          <div className='space-y-6'>
            {[1, 2, 3, 4, 5, 6, 7, 8].map((position) => {
              const channel = settings.channels[position] || { modules: [] };
              const hasModules = channel.modules && channel.modules.length > 0;
              
              // Sort modules based on order
              const sortedAssignments = [...(channel.modules || [])].sort((a, b) => a.order - b.order);

              return (
                <div key={position} className='bg-[#222] border border-gray-700 rounded-lg p-4'>
                  <div className='flex justify-between items-start mb-4'>
                    <div>
                      <h3 className='text-xl font-bold text-white flex items-center gap-2'>
                        <span className='bg-gray-700 text-xs px-2 py-1 rounded text-gray-300 font-mono'>CH {position}</span>
                      </h3>
                    </div>
                    <div className='flex gap-2'>
                      <button
                        onClick={() => triggerChannelPrint(position)}
                        className='text-xs bg-green-900/30 hover:bg-green-900/50 text-green-400 border border-green-900/50 px-3 py-1 rounded transition-colors'
                        title="Test Print"
                      >
                        Test Print
                      </button>
                      <button
                        onClick={() => setShowScheduleModal(position)}
                        className={`text-xs px-3 py-1 rounded border transition-colors ${
                          channel.schedule && channel.schedule.length > 0 
                            ? 'bg-blue-900/30 text-blue-400 border-blue-900/50' 
                            : 'bg-gray-800 text-gray-400 border-gray-700 hover:text-white'
                        }`}
                        title="Configure Schedule"
                      >
                        {channel.schedule && channel.schedule.length > 0 ? 'Scheduled' : 'Schedule'}
                      </button>
                    </div>
                  </div>

                  {/* Module List */}
                  <div className='space-y-2'>
                    {sortedAssignments.length === 0 ? (
                      <div className='text-center py-4 border-2 border-dashed border-gray-800 rounded text-gray-600 text-sm'>
                        No modules assigned
                      </div>
                    ) : (
                      sortedAssignments.map((assignment, index) => {
                        const module = modules[assignment.module_id];
                        if (!module) return null; // Should not happen
                        
                        return (
                          <div key={assignment.module_id} className='bg-[#333] p-3 rounded flex justify-between items-center group'>
                            <div>
                              <div className='font-medium text-white'>
                                {module.name || module.type.toUpperCase()}
                              </div>
                              <div className='text-xs text-gray-500'>
                                {module.type}
                              </div>
                            </div>
                            <div className='flex items-center gap-2 opacity-50 group-hover:opacity-100 transition-opacity'>
                              {/* Reordering */}
                              <div className='flex flex-col mr-2'>
                                <button 
                                  disabled={index === 0}
                                  onClick={() => moveModule(position, assignment.module_id, -1)}
                                  className='text-gray-400 hover:text-white disabled:opacity-20 text-[10px] leading-none mb-1'
                                >▲</button>
                                <button 
                                  disabled={index === sortedAssignments.length - 1}
                                  onClick={() => moveModule(position, assignment.module_id, 1)}
                                  className='text-gray-400 hover:text-white disabled:opacity-20 text-[10px] leading-none'
                                >▼</button>
                              </div>
                              
                              <button
                                onClick={() => setShowEditModuleModal(assignment.module_id)}
                                className='p-1 hover:bg-gray-700 rounded text-blue-400'
                                title="Configure Module"
                              >
                                ⚙
                              </button>
                              <button
                                onClick={() => removeModuleFromChannel(position, assignment.module_id)}
                                className='p-1 hover:bg-gray-700 rounded text-red-400'
                                title="Remove from Channel"
                              >
                                ×
                              </button>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>

                  <button
                    onClick={() => setShowAddModuleModal(position)}
                    className='w-full mt-3 py-2 border border-gray-700 hover:border-gray-500 text-gray-400 hover:text-white rounded text-sm transition-colors flex items-center justify-center gap-2'
                  >
                    + Add Module
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Add Module Modal */}
      {showAddModuleModal !== null && (
        <Modal title={`Add Module to Channel ${showAddModuleModal}`} onClose={() => setShowAddModuleModal(null)}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="md:col-span-2 mb-4">
              <h3 className="text-sm font-bold text-gray-400 mb-2">EXISTING MODULES</h3>
              <div className="grid grid-cols-1 gap-2 max-h-[200px] overflow-y-auto custom-scrollbar">
                {Object.values(modules).length === 0 && (
                  <div className="text-gray-500 text-sm italic">No existing modules found. Create one below.</div>
                )}
                {Object.values(modules).map(mod => (
                  <button
                    key={mod.id}
                    onClick={async () => {
                      await assignModuleToChannel(showAddModuleModal, mod.id);
                      setShowAddModuleModal(null);
                    }}
                    className="flex items-center justify-between bg-[#333] hover:bg-[#444] p-3 rounded text-left transition-colors border border-gray-700"
                  >
                    <div>
                      <div className="font-medium text-white">{mod.name || mod.type}</div>
                      <div className="text-xs text-gray-500">{mod.type}</div>
                    </div>
                    <span className="text-blue-400 text-xs px-2 py-1 bg-blue-900/20 rounded">Select</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="md:col-span-2 mt-4 mb-2">
              <h3 className="text-sm font-bold text-gray-400 border-t border-gray-700 pt-4">CREATE NEW MODULE</h3>
            </div>

            {AVAILABLE_MODULE_TYPES.map((type) => (
              <button
                key={type.id}
                onClick={() => createModule(type.id, type.label)}
                className="bg-[#333] hover:bg-[#444] p-4 rounded border border-gray-700 transition-colors text-left group"
              >
                <div className="font-bold text-gray-200 group-hover:text-white">{type.label}</div>
                <div className="text-xs text-gray-500">Create new {type.label.toLowerCase()} instance</div>
              </button>
            ))}
          </div>
        </Modal>
      )}

      {/* Edit Module Modal */}
      {showEditModuleModal !== null && modules[showEditModuleModal] && (
        <Modal 
          title={`Edit ${modules[showEditModuleModal].name || 'Module'}`} 
          onClose={() => setShowEditModuleModal(null)}
        >
          <div>
            <div className='flex justify-between items-center mb-6 bg-gray-800 p-3 rounded'>
              <div>
                <span className='text-xs text-gray-500 uppercase tracking-wider'>Module Type</span>
                <div className='font-mono text-blue-300'>{modules[showEditModuleModal].type}</div>
              </div>
              <div>
                <span className='text-xs text-gray-500 uppercase tracking-wider'>ID</span>
                <div className='font-mono text-xs text-gray-600'>{modules[showEditModuleModal].id.split('-')[0]}...</div>
              </div>
            </div>

            <div className='mb-6'>
              <label className='block mb-2 text-sm text-gray-400'>Module Name</label>
              <input 
                type="text" 
                value={modules[showEditModuleModal].name}
                onChange={(e) => {
                  const moduleId = showEditModuleModal;
                  const newName = e.target.value;
                  // Update local state immediately for responsive UI
                  setModules((prev) => {
                    const mod = prev[moduleId];
                    if (!mod) return prev;
                    return { ...prev, [moduleId]: { ...mod, name: newName } };
                  });
                  // Debounce the API call
                  updateModuleDebounced(moduleId, { name: newName });
                }}
                onBlur={(e) => {
                  // Save immediately on blur with a short delay
                  const moduleId = showEditModuleModal;
                  if (moduleUpdateTimers.current[moduleId]) {
                    clearTimeout(moduleUpdateTimers.current[moduleId]);
                  }
                  setTimeout(() => updateModule(moduleId, { name: e.target.value }, true), 300);
                }}
                className="w-full p-3 text-base bg-[#333] border border-gray-700 rounded text-white focus:border-white focus:outline-none"
              />
            </div>

            {renderModuleConfig(modules[showEditModuleModal], (updated) => {
              // Always use the module ID from the current module, not from updated object
              const moduleId = modules[showEditModuleModal].id;
              console.log('[UPDATE] Updating module:', moduleId, 'Type:', modules[showEditModuleModal].type, 'Config:', updated.config);
              updateModuleDebounced(moduleId, updated);
            })}

            <div className='mt-8 pt-6 border-t border-gray-700 flex justify-end gap-3'>
              <button
                onClick={() => triggerModulePrint(showEditModuleModal)}
                className='bg-green-900/30 hover:bg-green-900/50 text-green-400 border border-green-900/50 px-4 py-2 rounded transition-colors'
              >
                Test Print
              </button>
              <button
                onClick={() => deleteModule(showEditModuleModal)}
                className='bg-red-900/30 hover:bg-red-900/50 text-red-400 border border-red-900/50 px-4 py-2 rounded transition-colors'
              >
                Delete Module
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Schedule Modal */}
      {showScheduleModal !== null && (
        <Modal title={`Schedule for Channel ${showScheduleModal}`} onClose={() => setShowScheduleModal(null)}>
          <div className="space-y-6">
            <p className="text-gray-400 text-sm">
              Set specific times for this channel to print automatically every day.
            </p>
            
            <div className="space-y-2">
              {(settings.channels[showScheduleModal]?.schedule || []).map((time, idx) => (
                <div key={idx} className="flex gap-2">
                  <input 
                    type="time" 
                    value={time}
                    onChange={(e) => {
                      const newSchedule = [...(settings.channels[showScheduleModal].schedule || [])];
                      newSchedule[idx] = e.target.value;
                      updateChannelSchedule(showScheduleModal, newSchedule);
                    }}
                    className="flex-grow p-3 bg-[#333] border border-gray-700 rounded text-white"
                  />
                  <button 
                    onClick={() => {
                      const newSchedule = (settings.channels[showScheduleModal].schedule || []).filter((_, i) => i !== idx);
                      updateChannelSchedule(showScheduleModal, newSchedule);
                    }}
                    className="px-4 bg-red-900/30 text-red-400 rounded border border-red-900/50 hover:bg-red-900/50"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
            
            <button 
              onClick={() => {
                const newSchedule = [...(settings.channels[showScheduleModal]?.schedule || []), "09:00"];
                updateChannelSchedule(showScheduleModal, newSchedule);
              }}
              className="w-full py-3 bg-[#333] hover:bg-[#444] border border-gray-700 rounded text-gray-300 hover:text-white transition-colors"
            >
              + Add Time
            </button>
          </div>
        </Modal>
      )}

      {/* Status Toast */}
      {status.message && (
        <div
          className={`fixed bottom-4 right-4 p-4 rounded shadow-lg transition-opacity duration-500 ${
            status.type === 'error' ? 'bg-red-900 text-white' : 'bg-green-900 text-white'
          }`}>
          {status.message}
        </div>
      )}

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
