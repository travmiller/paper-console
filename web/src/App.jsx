import { useState, useEffect, useRef } from 'react';
import WiFiSetup from './WiFiSetup';
import GeneralSettings from './components/GeneralSettings';
import Assistant from './components/Assistant';
import ChannelList from './components/ChannelList';
import AddModuleModal from './components/AddModuleModal';
import EditModuleModal from './components/EditModuleModal';
import ScheduleModal from './components/ScheduleModal';
import APInstructionsModal from './components/APInstructionsModal';
import StatusMessage from './components/StatusMessage';
import ResetSettingsButton from './components/ResetSettingsButton';
import { useModuleTypes } from './hooks/useModuleTypes';
import GitHubIcon from './assets/GitHubIcon';
import BorderWidthIcon from './assets/BorderWidthIcon';
import ChatIcon from './assets/ChatIcon';
import PreferencesIcon from './assets/PreferencesIcon';


function App() {
  const [wifiMode, setWifiMode] = useState(null); // null = checking, 'client' = normal, 'ap' = setup mode
  const [wifiStatus, setWifiStatus] = useState(null); // WiFi connection status
  const { moduleTypes } = useModuleTypes();
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
  const [activeTab, setActiveTab] = useState('channels'); // 'general', 'assistant', 'channels'
  const [showAddModuleModal, setShowAddModuleModal] = useState(null); // channel position or null
  const [showCreateUnassignedModal, setShowCreateUnassignedModal] = useState(false); // true/false for unassigned module creation
  const [showEditModuleModal, setShowEditModuleModal] = useState(null); // module ID or null
  const [editingModule, setEditingModule] = useState(null); // Local copy of module being edited
  const [showScheduleModal, setShowScheduleModal] = useState(null); // channel position or null
  const [showAPInstructions, setShowAPInstructions] = useState(false);

  // Debounce timers for module updates
  // Debounce timer for location search (respects Nominatim 1 req/sec limit)
  const locationSearchTimer = useRef(null);

  // Check WiFi status on mount
  useEffect(() => {
    let isFirstLoad = true;

    const fetchWifiStatus = async () => {
      try {
        const response = await fetch('/api/wifi/status');
        const data = await response.json();
        setWifiStatus(data);
        setWifiMode(data.mode);

        // If in AP mode, don't fetch settings yet
        if (data.mode === 'ap') {
          if (isFirstLoad) setLoading(false);
          return;
        }

        // On first load, fetch settings
        if (isFirstLoad) {
          try {
            const [settingsData, modulesData] = await Promise.all([
              fetch('/api/settings').then((res) => res.json()),
              fetch('/api/modules').then((res) => res.json()),
            ]);
            setSettings(settingsData);
            setModules(modulesData.modules || {});
            setLoading(false);
          } catch (err) {
            console.error('Error fetching data:', err);
            setStatus({ type: 'error', message: 'Failed to load settings. Is the backend running?' });
            setLoading(false);
          }
          isFirstLoad = false;
        }
      } catch (err) {
        console.error('Error fetching WiFi status:', err);
        if (isFirstLoad) setLoading(false);
      }
    };

    fetchWifiStatus();

    // Update WiFi status every 10 seconds
    const interval = setInterval(fetchWifiStatus, 10000);
    return () => {
      clearInterval(interval);
      // Cleanup location search timer
      if (locationSearchTimer.current) {
        clearTimeout(locationSearchTimer.current);
      }
    };
  }, []);

  const handleSearch = async (term) => {
    setSearchTerm(term);
    if (term.length < 2) {
      setSearchResults([]);
      setIsSearching(false);
      if (locationSearchTimer.current) {
        clearTimeout(locationSearchTimer.current);
        locationSearchTimer.current = null;
      }
      return;
    }

    // Clear previous timer
    if (locationSearchTimer.current) {
      clearTimeout(locationSearchTimer.current);
    }

    // Debounce search to respect Nominatim API rate limit (1 req/sec)
    // Wait 500ms after user stops typing before searching
    setIsSearching(true);
    locationSearchTimer.current = setTimeout(async () => {
      try {
        console.log('Searching for:', term);
        // Always use local database (no API)
        // Add timeout to prevent hanging (15 seconds max)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);

        const response = await fetch(`/api/location/search?q=${encodeURIComponent(term)}&limit=20&use_api=false`, {
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Search results:', data.results?.length || 0);

        if (data.results) {
          setSearchResults(data.results);
        } else {
          setSearchResults([]);
        }
      } catch (err) {
        if (err.name === 'AbortError') {
          console.warn('Location search timed out');
          // Don't clear results on timeout, just stop spinning
        } else {
          console.error('Error fetching locations:', err);
          setSearchResults([]);
        }
      } finally {
        setIsSearching(false);
        locationSearchTimer.current = null;
      }
    }, 500); // 500ms debounce
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
      const response = await fetch(`/action/print-channel/${position}`, { method: 'POST' });

      if (!response.ok) throw new Error('Failed to trigger print');

      setStatus({ type: 'success', message: `Printing Channel ${position}...` });
      setTimeout(() => setStatus({ type: '', message: '' }), 3000);
    } catch (err) {
      console.error('Error triggering print:', err);
      setStatus({ type: 'error', message: 'Failed to trigger print' });
    }
  };

  const triggerModulePrint = async (moduleId) => {
    try {
      const response = await fetch(`/debug/print-module/${moduleId}`, { method: 'POST' });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to trigger print' }));
        throw new Error(errorData.detail || 'Failed to trigger print');
      }

      const data = await response.json();
      setStatus({ type: 'success', message: data.message || 'Printing module...' });
      setTimeout(() => setStatus({ type: '', message: '' }), 3000);
    } catch (err) {
      console.error('Error triggering module print:', err);
      setStatus({ type: 'error', message: err.message || 'Failed to trigger print' });
      setTimeout(() => setStatus({ type: '', message: '' }), 3000);
    }
  };


  // --- Settings Save ---

  const saveGlobalSettings = async (updates) => {
    // Optimistic update
    setSettings((prev) => ({ ...prev, ...updates }));

    try {
      const settingsToSave = {
        ...settings, // Include all existing settings
        channels: settings.channels || {},
        modules: modules, // Include current modules
        ...updates, // Overwrite with new values
      };

      console.log('Auto-saving settings:', updates);

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

  const selectLocation = (location) => {
    // Use city field if available (just city name), otherwise use name (which may include state)
    // This prevents double state abbreviations in display
    const cityName = location.city || location.name;

    const updates = {
      city_name: cityName,
      state: location.state,
      latitude: location.latitude,
      longitude: location.longitude,
      timezone: location.timezone,
    };

    setSearchTerm('');
    setSearchResults([]);
    saveGlobalSettings(updates);
  };

  // --- Module Management ---

  const getDefaultConfig = (moduleType) => {
    const defaults = {
      news: { news_api_key: '' },
      rss: { rss_feeds: [] },
      weather: {},
      email: { email_host: 'imap.gmail.com', email_user: '', email_password: '', polling_interval: 60 },
      games: { difficulty: 'medium' },
      astronomy: {},
      calendar: { ical_sources: [], days_to_show: 2 },
      webhook: { url: '', method: 'GET', headers: {}, json_path: '' },
      text: { content: '' },
    };
    return defaults[moduleType] || {};
  };

  const createModule = async (moduleType, name = '') => {
    try {
      const response = await fetch('/api/modules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: moduleType,
          name: name || `${moduleTypes.find((m) => m.id === moduleType)?.label || moduleType}`,
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
      const targetModule = modules[moduleId];
      if (!targetModule) {
        console.error(`[UPDATE] Module ${moduleId} not found`);
        return;
      }

      if (updates.type && updates.type !== targetModule.type) {
        console.error(
          `[UPDATE] Type mismatch! Target module is ${targetModule.type}, but update has type ${updates.type}. Rejecting update.`,
        );
        return;
      }

      if (updates.id && updates.id !== moduleId) {
        console.error(`[UPDATE] ID mismatch! Target module ID is ${moduleId}, but update has ID ${updates.id}. Rejecting update.`);
        return;
      }

      if (updates.config) {
        const cleanedConfig = { ...updates.config };
        if (targetModule.type === 'news') {
          if (cleanedConfig.rss_feeds) delete cleanedConfig.rss_feeds;
          delete cleanedConfig.enable_newsapi;
        } else if (targetModule.type === 'rss') {
          if (cleanedConfig.news_api_key) delete cleanedConfig.news_api_key;
          delete cleanedConfig.enable_newsapi;
        }
        updates.config = cleanedConfig;
      }

      setModules((prev) => {
        const module = prev[moduleId];
        if (!module) return prev;
        return { ...prev, [moduleId]: { ...module, ...updates } };
      });

      const moduleToUpdate = { ...targetModule, ...updates };
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
    } catch (err) {
      console.error('Error updating module:', err);
      setStatus({ type: 'error', message: 'Failed to update module' });
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
      const assignments = [];
      for (const [pos, channel] of Object.entries(settings.channels)) {
        if (channel.modules && channel.modules.some((m) => m.module_id === moduleId)) {
          assignments.push(pos);
        }
      }

      for (const pos of assignments) {
        await fetch(`/api/channels/${pos}/modules/${moduleId}`, {
          method: 'DELETE',
        });
      }

      const response = await fetch(`/api/modules/${moduleId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to delete module');
      }

      setModules((prev) => {
        const newModules = { ...prev };
        delete newModules[moduleId];
        return newModules;
      });

      setSettings((prev) => {
        const updatedChannels = { ...prev.channels };
        for (const pos in updatedChannels) {
          if (updatedChannels[pos].modules) {
            updatedChannels[pos].modules = updatedChannels[pos].modules.filter((m) => m.module_id !== moduleId);
          }
        }
        return { ...prev, channels: updatedChannels };
      });

      setStatus({ type: 'success', message: 'Module deleted successfully!' });
      setTimeout(() => setStatus({ type: '', message: '' }), 3000);

      if (showEditModuleModal === moduleId) {
        setShowEditModuleModal(null);
        setEditingModule(null);
      }
    } catch (err) {
      console.error('Error deleting module:', err);
      setStatus({ type: 'error', message: err.message || 'Failed to delete module' });
    }
  };

  // --- Channel Management ---

  const assignModuleToChannel = async (position, moduleId, order = null, options = {}) => {
    try {
      if (options?.optimistic) {
        setSettings((prev) => {
          const channels = { ...(prev.channels || {}) };
          const channel = channels[position] ? { ...channels[position] } : { modules: [] };
          const existing = (channel.modules || [])
            .filter((assignment) => assignment.module_id !== moduleId)
            .sort((a, b) => a.order - b.order);
          const insertIndex = order === null ? existing.length : Math.max(0, Math.min(order, existing.length));
          const next = [...existing];
          next.splice(insertIndex, 0, { module_id: moduleId, order: insertIndex });
          channel.modules = next.map((assignment, idx) => ({ ...assignment, order: idx }));
          channels[position] = channel;
          return { ...prev, channels };
        });
      }

      const response = await fetch(`/api/channels/${position}/modules?module_id=${moduleId}${order !== null ? `&order=${order}` : ''}`, {
        method: 'POST',
      });

      if (!response.ok) throw new Error('Failed to assign module');

      const data = await response.json();
      setSettings((prev) => ({
        ...prev,
        channels: { ...prev.channels, [position]: data.channel },
      }));
      if (!options?.silent) {
        setStatus({ type: 'success', message: 'Module assigned to channel!' });
        setTimeout(() => setStatus({ type: '', message: '' }), 3000);
      }
      return data.channel;
    } catch (err) {
      console.error('Error assigning module:', err);
      setStatus({ type: 'error', message: err.message || 'Failed to assign module' });
      return null;
    }
  };

  const removeModuleFromChannel = async (position, moduleId, options = {}) => {
    try {
      if (options?.optimistic) {
        setSettings((prev) => {
          const existingChannel = prev.channels?.[position];
          if (!existingChannel || !existingChannel.modules) return prev;
          const remaining = existingChannel.modules
            .filter((assignment) => assignment.module_id !== moduleId)
            .sort((a, b) => a.order - b.order)
            .map((assignment, idx) => ({ ...assignment, order: idx }));
          return {
            ...prev,
            channels: {
              ...prev.channels,
              [position]: { ...existingChannel, modules: remaining },
            },
          };
        });
      }

      const response = await fetch(`/api/channels/${position}/modules/${moduleId}`, {
        method: 'DELETE',
      });

      if (!response.ok) throw new Error('Failed to remove module');

      const data = await response.json();
      setSettings((prev) => ({
        ...prev,
        channels: { ...prev.channels, [position]: data.channel },
      }));
      if (!options?.silent) {
        setStatus({ type: 'success', message: 'Module removed from channel!' });
        setTimeout(() => setStatus({ type: '', message: '' }), 3000);
      }
      return data.channel;
    } catch (err) {
      console.error('Error removing module:', err);
      setStatus({ type: 'error', message: err.message || 'Failed to remove module' });
      return null;
    }
  };

  const reorderChannelModules = async (position, moduleOrders, options = {}) => {
    try {
      if (options?.optimistic) {
        setSettings((prev) => {
          const existingChannel = prev.channels?.[position];
          if (!existingChannel || !existingChannel.modules) return prev;
          const existingIds = existingChannel.modules.map((assignment) => assignment.module_id);
          const existingSet = new Set(existingIds);
          const orders = moduleOrders || {};
          const orderedIds = Object.entries(orders)
            .sort((a, b) => a[1] - b[1])
            .map(([id]) => id)
            .filter((id) => existingSet.has(id));
          const remaining = existingIds.filter((id) => !Object.prototype.hasOwnProperty.call(orders, id));
          const finalIds = [...orderedIds, ...remaining];
          const nextModules = finalIds.map((id, idx) => ({ module_id: id, order: idx }));
          return {
            ...prev,
            channels: {
              ...prev.channels,
              [position]: { ...existingChannel, modules: nextModules },
            },
          };
        });
      }

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
      return data.channel;
    } catch (err) {
      console.error('Error reordering modules:', err);
      setStatus({ type: 'error', message: 'Failed to reorder modules' });
      return null;
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

    const tempOrder = sortedModules[index].order;
    sortedModules[index].order = sortedModules[newIndex].order;
    sortedModules[newIndex].order = tempOrder;

    const moduleOrders = {};
    sortedModules.forEach((m) => {
      moduleOrders[m.module_id] = m.order;
    });

    reorderChannelModules(position, moduleOrders, { optimistic: true });
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

  const handleWiFiSetupComplete = () => {
    setWifiMode('client');
    window.location.reload();
  };

  const triggerAPMode = async () => {
    try {
      await fetch('/api/wifi/ap-mode', { method: 'POST' });
      setStatus({ type: 'success', message: 'AP mode activating...' });
      setShowAPInstructions(true);
    } catch {
      setStatus({ type: 'error', message: 'Failed to activate AP mode' });
    }
  };

  if (loading) {
    return <div className='max-w-[800px] w-full p-8 text-center'>Loading settings...</div>;
  }

  if (wifiMode === 'ap') {
    return <WiFiSetup onComplete={handleWiFiSetupComplete} />;
  }

  return (
    <div
      className='max-w-[480px] w-full mx-auto px-2 pt-4 pb-12 sm:px-6 sm:pt-8 sm:pb-16 min-h-screen'
      style={{ backgroundColor: 'var(--color-bg-base)', color: 'var(--color-text-main)' }}>
      <div className='mb-8 pt-4 pb-2'>
        <h1 className='text-3xl sm:text-4xl leading-none font-bold tracking-tighter' style={{ color: 'var(--color-text-main)' }}>
          PC-1 SETTINGS
        </h1>
      </div>

      {/* Tabs */}
      <div className='flex gap-2 mb-8 border-b-2 border-dashed' style={{ borderColor: 'var(--color-border-main)' }}>
        <button
          type='button'
          onClick={() => setActiveTab('general')}
          className={`px-6 py-2 font-bold tracking-wider transition-all text-sm flex items-center gap-2 ${
            activeTab === 'general' ? 'border-b-2 translate-y-[2px]' : 'border-b-2 border-transparent'
          }`}
          style={
            activeTab === 'general'
              ? { borderColor: 'var(--color-border-main)', color: 'var(--color-text-main)' }
              : { color: 'var(--color-text-muted)' }
          }
          onMouseEnter={(e) => {
            if (activeTab !== 'general') e.currentTarget.style.color = 'var(--color-text-main)';
          }}
          onMouseLeave={(e) => {
            if (activeTab !== 'general') e.currentTarget.style.color = 'var(--color-text-muted)';
          }}>
          <PreferencesIcon className='w-4 h-4' />
          GENERAL
        </button>
        <button
          type='button'
          onClick={() => setActiveTab('assistant')}
          className={`px-6 py-2 font-bold tracking-wider transition-all text-sm flex items-center gap-2 ${
            activeTab === 'assistant' ? 'border-b-2 translate-y-[2px]' : 'border-b-2 border-transparent'
          }`}
          style={
            activeTab === 'assistant'
              ? { borderColor: 'var(--color-border-main)', color: 'var(--color-text-main)' }
              : { color: 'var(--color-text-muted)' }
          }
          onMouseEnter={(e) => {
            if (activeTab !== 'assistant') e.currentTarget.style.color = 'var(--color-text-main)';
          }}
          onMouseLeave={(e) => {
            if (activeTab !== 'assistant') e.currentTarget.style.color = 'var(--color-text-muted)';
          }}>
          <ChatIcon className='w-4 h-4' />
          ASSISTANT
        </button>
        <button
          type='button'
          onClick={() => setActiveTab('channels')}
          className={`px-6 py-2 font-bold tracking-wider transition-all text-sm flex items-center gap-2 ${
            activeTab === 'channels' ? 'border-b-2 translate-y-[2px]' : 'border-b-2 border-transparent'
          }`}
          style={
            activeTab === 'channels'
              ? { borderColor: 'var(--color-border-main)', color: 'var(--color-text-main)' }
              : { color: 'var(--color-text-muted)' }
          }
          onMouseEnter={(e) => {
            if (activeTab !== 'channels') e.currentTarget.style.color = 'var(--color-text-main)';
          }}
          onMouseLeave={(e) => {
            if (activeTab !== 'channels') e.currentTarget.style.color = 'var(--color-text-muted)';
          }}>
          <BorderWidthIcon className='w-4 h-4' />
          CHANNELS
        </button>
      </div>

      <div className='contents'>
        {activeTab === 'general' && (
          <>
            <GeneralSettings
              searchTerm={searchTerm}
              searchResults={searchResults}
              isSearching={isSearching}
              handleSearch={handleSearch}
              selectLocation={selectLocation}
              settings={settings}
              saveGlobalSettings={saveGlobalSettings}
              triggerAPMode={triggerAPMode}
              wifiStatus={wifiStatus}
            />
            <div className='mt-8 flex items-center justify-between'>
              {/* GitHub Link */}
              <a
                href='https://github.com/travmiller/paper-console'
                target='_blank'
                rel='noopener noreferrer'
                className='inline-flex items-center gap-2 text-gray-600 hover:text-black transition-colors'>
                <GitHubIcon className='w-5 h-5' />
                <span className='text-sm font-mono'>paper-console</span>
              </a>

              {/* Reset Button */}
              <ResetSettingsButton setSettings={setSettings} setModules={setModules} setStatus={setStatus} />
            </div>
          </>
        )}

        {activeTab === 'assistant' && (
          <Assistant settings={settings} setStatus={setStatus} setSettings={setSettings} setModules={setModules} />
        )}

        {activeTab === 'channels' && (
          <ChannelList
            settings={settings}
            modules={modules}
            triggerChannelPrint={triggerChannelPrint}
            triggerModulePrint={triggerModulePrint}
            setShowScheduleModal={setShowScheduleModal}
            swapChannels={swapChannels}
            setShowEditModuleModal={setShowEditModuleModal}
            setEditingModule={setEditingModule}
            moveModuleInChannel={moveModuleInChannel}
            assignModuleToChannel={assignModuleToChannel}
            reorderChannelModules={reorderChannelModules}
            removeModuleFromChannel={removeModuleFromChannel}
            setShowAddModuleModal={setShowAddModuleModal}
            setShowCreateUnassignedModal={setShowCreateUnassignedModal}
            wifiStatus={wifiStatus}
          />
        )}


        <AddModuleModal
          channelPosition={showAddModuleModal}
          onClose={() => setShowAddModuleModal(null)}
          onCreateModule={createModule}
          onAssignModule={assignModuleToChannel}
          onOpenEdit={(moduleId, module) => {
            setShowEditModuleModal(moduleId);
            setEditingModule(module);
          }}
        />

        {/* Modal for creating unassigned modules */}
        {showCreateUnassignedModal && (
          <AddModuleModal
            channelPosition={null}
            isUnassigned={true}
            onClose={() => setShowCreateUnassignedModal(false)}
            onCreateModule={async (moduleType) => {
              const newModule = await createModule(moduleType);
              if (newModule) {
                setShowCreateUnassignedModal(false);
                setShowEditModuleModal(newModule.id);
                setEditingModule(JSON.parse(JSON.stringify(newModule)));
              }
              return newModule;
            }}
            onAssignModule={async () => {
              // No-op for unassigned modules
            }}
            onOpenEdit={(moduleId, module) => {
              setShowEditModuleModal(moduleId);
              setEditingModule(module);
            }}
          />
        )}

        <EditModuleModal
          moduleId={showEditModuleModal}
          module={editingModule}
          setModule={setEditingModule}
          onClose={() => {
            setShowEditModuleModal(null);
            setEditingModule(null);
          }}
          onSave={updateModule}
          onDelete={deleteModule}
        />

        <ScheduleModal
          position={showScheduleModal}
          channel={settings.channels[showScheduleModal] || {}}
          onClose={() => setShowScheduleModal(null)}
          onUpdate={(newSchedule) => updateChannelSchedule(showScheduleModal, newSchedule)}
          timeFormat={settings.time_format}
        />

        <APInstructionsModal show={showAPInstructions} />

        <StatusMessage status={status} />
      </div>
    </div>
  );
}

export default App;
