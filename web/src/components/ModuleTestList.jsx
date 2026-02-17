import React from 'react';
import { useModuleTypes } from '../hooks/useModuleTypes';
import WiFiIcon from '../assets/WiFiIcon';
import WiFiOffIcon from '../assets/WiFiOffIcon';
import PrintIcon from '../assets/PrintIcon';

const ModuleTestList = ({ settings, modules, triggerModulePrint, wifiStatus, setShowEditModuleModal, setEditingModule }) => {
  const { moduleTypes } = useModuleTypes();

  const isNonEmptyString = (v) => typeof v === 'string' && v.trim().length > 0;
  const hasVisibleRichText = (node) => {
    if (!node || typeof node !== 'object') return false;
    if (node.type === 'horizontalRule') return true;
    if (node.type === 'text') return typeof node.text === 'string' && node.text.trim().length > 0;
    if (!Array.isArray(node.content)) return false;
    return node.content.some((child) => hasVisibleRichText(child));
  };

  const moduleIsConfigured = (module) => {
    const cfg = module?.config || {};
    switch (module?.type) {
      case 'news':
        return isNonEmptyString(cfg.news_api_key);
      case 'rss':
        return Array.isArray(cfg.rss_feeds) && cfg.rss_feeds.some((f) => isNonEmptyString(String(f || '')));
      case 'email':
        return isNonEmptyString(cfg.email_user) && isNonEmptyString(cfg.email_password);
      case 'calendar':
        return Array.isArray(cfg.ical_sources) && cfg.ical_sources.some((s) => isNonEmptyString(s?.url));
      case 'webhook':
        return isNonEmptyString(cfg.url);
      case 'text':
        return hasVisibleRichText(cfg.content_doc);
      case 'weather':
        // Weather can use either module-level location OR global settings location.
        return isNonEmptyString(cfg.city_name) || isNonEmptyString(settings?.city_name);
      default:
        return true;
    }
  };

  // Find which channels each module is assigned to
  const getModuleChannels = (moduleId) => {
    const channels = [];
    for (const [pos, channel] of Object.entries(settings.channels || {})) {
      if (channel?.modules?.some((m) => m.module_id === moduleId)) {
        channels.push(parseInt(pos));
      }
    }
    return channels.sort((a, b) => a - b);
  };

  // Get all modules as an array, sorted by name
  const allModules = Object.values(modules || {}).sort((a, b) => {
    const nameA = (a.name || '').toLowerCase();
    const nameB = (b.name || '').toLowerCase();
    return nameA.localeCompare(nameB);
  });

  return (
    <div className='space-y-4'>
      {allModules.length === 0 ? (
        <div className='text-center py-8 text-gray-500'>
          <p className='text-sm'>No modules created yet.</p>
          <p className='text-xs mt-2'>Go to the Channels tab to add modules.</p>
        </div>
      ) : (
        <div className='space-y-3'>
          {allModules.map((module) => {
            const typeMeta = moduleTypes.find((t) => t.id === module.type);
            const isOnline = typeMeta ? !typeMeta.offline : false;
            const configured = moduleIsConfigured(module);
            const showState = isOnline;
            const needsSetup = showState && !configured;
            const hasWifi = wifiStatus?.connected;
            const assignedChannels = getModuleChannels(module.id);

            // Determine icon color:
            // - Red: No WiFi
            // - Brass: WiFi connected but needs setup
            // - Grey: WiFi connected and configured
            let iconColor = 'var(--color-text-muted)'; // Default grey
            if (!hasWifi) {
              iconColor = 'var(--color-error)'; // Red for no WiFi
            } else if (needsSetup) {
              iconColor = 'var(--color-brass)'; // Brass for needs setup
            }

            return (
              <div
                key={module.id}
                className='flex items-center justify-between p-3 rounded-lg border-2 border-gray-600 hover:border-black group transition-all'
                style={{ backgroundColor: 'var(--color-bg-card)' }}
                onMouseEnter={(e) => e.currentTarget.style.setProperty('background-color', 'var(--color-bg-white)', 'important')}
                onMouseLeave={(e) => e.currentTarget.style.setProperty('background-color', 'var(--color-bg-card)', 'important')}>
                <div className='flex-1 min-w-0 mr-3 cursor-pointer' onClick={() => {
                  setShowEditModuleModal(module.id);
                  setEditingModule(JSON.parse(JSON.stringify(module)));
                }}>
                  <div className='flex items-center gap-2 mb-1'>
                    <div className='text-sm font-bold text-gray-700 group-hover:text-black truncate transition-colors'>
                      {module.name}
                    </div>
                    {assignedChannels.length > 0 && (
                      <div className='flex gap-1 flex-shrink-0'>
                        {assignedChannels.map((ch) => (
                          <span
                            key={ch}
                            className='px-1.5 py-0.5 text-[10px] font-bold rounded border border-gray-400 text-gray-600'
                            style={{ backgroundColor: 'var(--color-bg-card)' }}>
                            CH {ch}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div
                    className={`text-[10px] truncate flex items-baseline gap-1 ${
                      needsSetup ? '' : 'text-gray-700'
                    }`}
                    style={needsSetup ? { color: 'var(--color-brass)' } : {}}>
                    {isOnline && (
                      hasWifi ? (
                        <WiFiIcon className="w-2.5 h-2.5 flex-shrink-0 group-hover:text-black transition-colors" style={{ transform: 'translateY(0.125rem)', color: iconColor }} />
                      ) : (
                        <WiFiOffIcon className="w-2.5 h-2.5 flex-shrink-0" style={{ transform: 'translateY(0.125rem)', color: 'var(--color-error)' }} />
                      )
                    )}
                    <span className="truncate font-mono group-hover:text-black transition-colors" style={{ color: 'var(--color-text-muted)' }}>
                      {typeMeta?.label?.toUpperCase() || 'UNKNOWN'}
                    </span>
                  </div>
                </div>
                <div className='flex items-center gap-2' onClick={(e) => e.stopPropagation()}>
                  <button
                    type='button'
                    onClick={() => triggerModulePrint(module.id)}
                    className='group flex items-center justify-center px-3 py-2 rounded border-2 bg-transparent border-gray-300 hover:border-black hover:bg-white transition-all cursor-pointer'
                    title='Print Module'>
                    <PrintIcon className='w-4 h-4 text-gray-400 group-hover:text-black transition-all' />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default ModuleTestList;
