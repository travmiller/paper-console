import React, { useState, useEffect } from 'react';
import { AVAILABLE_MODULE_TYPES, INK_GRADIENTS } from '../constants';
import WiFiIcon from '../assets/WiFiIcon';
import WiFiOffIcon from '../assets/WiFiOffIcon';
import PrintIcon from '../assets/PrintIcon';
import ScheduleIcon from '../assets/ScheduleIcon';
import ArrowUpIcon from '../assets/ArrowUpIcon';
import ArrowDownIcon from '../assets/ArrowDownIcon';

const ChannelList = ({
  settings,
  modules,
  triggerChannelPrint,
  triggerModulePrint,
  setShowScheduleModal,
  swapChannels,
  setShowEditModuleModal,
  setEditingModule,
  moveModuleInChannel,
  setShowAddModuleModal,
  setShowCreateUnassignedModal,
  wifiStatus,
}) => {
  const isNonEmptyString = (v) => typeof v === 'string' && v.trim().length > 0;

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
        return isNonEmptyString(cfg.content);
      case 'weather':
        // Weather can use either module-level location OR global settings location.
        return isNonEmptyString(cfg.city_name) || isNonEmptyString(settings?.city_name);
      default:
        return true;
    }
  };

  // Find modules that aren't assigned to any channel
  const getUnassignedModules = () => {
    const assignedModuleIds = new Set();
    Object.values(settings.channels || {}).forEach((channel) => {
      (channel.modules || []).forEach((assignment) => {
        assignedModuleIds.add(assignment.module_id);
      });
    });
    
    return Object.values(modules || {}).filter((module) => !assignedModuleIds.has(module.id));
  };

  // Track display order of unassigned modules
  const [unassignedModuleOrder, setUnassignedModuleOrder] = useState([]);
  
  useEffect(() => {
    // Initialize order when modules change
    const assignedModuleIds = new Set();
    Object.values(settings.channels || {}).forEach((channel) => {
      (channel.modules || []).forEach((assignment) => {
        assignedModuleIds.add(assignment.module_id);
      });
    });
    
    const unassigned = Object.values(modules || {}).filter((module) => !assignedModuleIds.has(module.id));
    const currentOrder = unassigned.map(m => m.id);
    
    // Only update if the set of module IDs has changed (new modules added/removed)
    setUnassignedModuleOrder(prevOrder => {
      const prevSet = new Set(prevOrder);
      const currentSet = new Set(currentOrder);
      // Check if sets are different
      if (prevSet.size !== currentSet.size || 
          ![...prevSet].every(id => currentSet.has(id))) {
        return currentOrder;
      }
      // Keep existing order if modules haven't changed
      return prevOrder;
    });
  }, [modules, settings.channels]);

  // Get unassigned modules in display order
  const unassignedModules = unassignedModuleOrder
    .map(id => modules[id])
    .filter(Boolean);

  const moveUnassignedModule = (moduleId, direction) => {
    const currentIndex = unassignedModuleOrder.findIndex(id => id === moduleId);
    if (currentIndex === -1) return;
    
    const newOrder = [...unassignedModuleOrder];
    if (direction === 'up' && currentIndex > 0) {
      // Swap with previous
      [newOrder[currentIndex], newOrder[currentIndex - 1]] = 
        [newOrder[currentIndex - 1], newOrder[currentIndex]];
      setUnassignedModuleOrder(newOrder);
    } else if (direction === 'down' && currentIndex < newOrder.length - 1) {
      // Swap with next
      [newOrder[currentIndex], newOrder[currentIndex + 1]] = 
        [newOrder[currentIndex + 1], newOrder[currentIndex]];
      setUnassignedModuleOrder(newOrder);
    }
  };

  return (
    <div className='space-y-4'>
      <div className='space-y-4'>
        {[1, 2, 3, 4, 5, 6, 7, 8].map((pos) => {
          const channel = settings.channels?.[pos] || { modules: [] };
          const channelModules = (channel.modules || [])
            .map((assignment) => ({
              ...assignment,
              module: modules[assignment.module_id],
            }))
            .filter((item) => item.module)
            .sort((a, b) => a.order - b.order);

          // Use shared ink gradients
          const inkGradients = INK_GRADIENTS;
          
          return (
            <div key={pos} className='rounded-xl p-[4px] shadow-lg' style={{ background: inkGradients[pos - 1] }}>
              <div className='bg-bg-card rounded-lg p-4 flex flex-col h-full'>
              <div className='flex items-center justify-between mb-3 gap-4'>
                <div className='flex items-center gap-3 overflow-x-auto'>
                  <h3 className='font-bold text-black  text-lg tracking-tight'>
                    {pos}
                  </h3>
                  <div className='flex items-center gap-1'>
                    <button
                      type='button'
                      onClick={() => triggerChannelPrint(pos)}
                      className='group flex items-center justify-center px-2 py-1 rounded border-2 bg-transparent border-gray-300 hover:border-black hover:bg-white transition-all cursor-pointer'
                      title='Print Channel'>
                      <PrintIcon className='w-3.5 h-3.5 text-gray-400 group-hover:text-black transition-all' />
                    </button>
                    <button
                      type='button'
                      onClick={() => setShowScheduleModal(pos)}
                      className={`group flex items-center gap-1 px-2 py-1 rounded border-2 transition-all cursor-pointer ${
                        channel.schedule && channel.schedule.length > 0
                          ? 'bg-transparent shadow-sm'
                          : 'bg-transparent border-gray-300 hover:border-black hover:bg-white'
                      }`}
                      style={channel.schedule && channel.schedule.length > 0 ? { color: 'var(--color-brass)', borderColor: 'var(--color-brass)' } : {}}
                      onMouseEnter={(e) => { if (channel.schedule && channel.schedule.length > 0) e.currentTarget.style.backgroundColor = 'var(--color-brass-10)'; }}
                      onMouseLeave={(e) => { if (channel.schedule && channel.schedule.length > 0) e.currentTarget.style.backgroundColor = 'transparent'; }}
                      title='Configure Schedule'>
                      <ScheduleIcon className={`w-3.5 h-3.5 transition-all ${channel.schedule?.length > 0 ? '' : 'text-gray-400 group-hover:text-black'}`} style={channel.schedule?.length > 0 ? { color: 'var(--color-brass)' } : {}} />
                      <span className={`text-xs font-bold ${channel.schedule?.length > 0 ? '' : 'text-gray-400 group-hover:text-black'}`} style={channel.schedule?.length > 0 ? { color: 'var(--color-brass)' } : {}}>{channel.schedule?.length || 0}</span>
                    </button>
                  </div>
                </div>
                <div className='flex gap-1'>
                  <button
                    type='button'
                    onClick={(e) => {
                      e.preventDefault();
                      swapChannels(pos, pos - 1);
                    }}
                    disabled={pos === 1}
                    className='px-2 py-1 text-xs  border-2 border-gray-300 hover:border-black rounded text-gray-600 hover:text-black transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer hover:bg-white'
                    title='Move channel up'>
                    <ArrowUpIcon className='w-3 h-3' />
                  </button>
                  <button
                    type='button'
                    onClick={(e) => {
                      e.preventDefault();
                      swapChannels(pos, pos + 1);
                    }}
                    disabled={pos === 8}
                    className='px-2 py-1 text-xs  border-2 border-gray-300 hover:border-black rounded text-gray-600 hover:text-black transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer hover:bg-white'
                    title='Move channel down'>
                    <ArrowDownIcon className='w-3 h-3' />
                  </button>
                </div>
              </div>

              <div className='space-y-2 mb-2 flex-grow'>
                {channelModules.map((item, idx) => (
                  <div
                    key={item.module_id}
                    className='flex items-center justify-between p-2 rounded-lg border-2 border-gray-600 hover:border-black group transition-all cursor-pointer'
                    style={{ backgroundColor: 'var(--color-bg-card)' }}
                    onMouseEnter={(e) => e.currentTarget.style.setProperty('background-color', 'var(--color-bg-white)', 'important')}
                    onMouseLeave={(e) => e.currentTarget.style.setProperty('background-color', 'var(--color-bg-card)', 'important')}
                    onClick={() => {
                      setShowEditModuleModal(item.module_id);
                      setEditingModule(JSON.parse(JSON.stringify(modules[item.module_id])));
                    }}>
                    <div className='flex-1 min-w-0 mr-2'>
                      {(() => {
                        const typeMeta = AVAILABLE_MODULE_TYPES.find((t) => t.id === item.module.type);
                        const isOnline = typeMeta ? !typeMeta.offline : false;
                        const configured = moduleIsConfigured(item.module);
                        const showState = isOnline;
                        const needsSetup = showState && !configured;
                        const hasWifi = wifiStatus?.connected;
                        
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
                          <>
                      <div className='text-sm font-bold text-gray-700 group-hover:text-black  truncate transition-colors'>{item.module.name}</div>
                      <div
                        className={`text-[10px]  truncate flex items-baseline gap-1 ${
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
                        <span className="truncate font-mono group-hover:text-black transition-colors" style={{ color: 'var(--color-text-muted)' }}>{typeMeta?.label?.toUpperCase()}</span>
                      </div>
                          </>
                        );
                      })()}
                    </div>
                    <div className='flex gap-2 items-center' onClick={(e) => e.stopPropagation()}>
                      <button
                        type='button'
                        onClick={() => triggerModulePrint(item.module_id)}
                        className='px-1.5 py-1 rounded border border-gray-300 hover:border-black hover:bg-white transition-all cursor-pointer'
                        title='Print this module'>
                        <PrintIcon className='w-3 h-3 text-gray-400 hover:text-black transition-colors' />
                      </button>
                      <div className='flex flex-col gap-0.5'>
                        <button
                          type='button'
                          onClick={() => moveModuleInChannel(pos, item.module_id, 'up')}
                          disabled={idx === 0}
                          className='px-1 py-0.5 text-[10px] leading-none disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer'
                          onMouseEnter={(e) => {
                            const icon = e.currentTarget.querySelector('svg');
                            if (icon) icon.style.color = 'var(--color-text-main)';
                          }}
                          onMouseLeave={(e) => {
                            const icon = e.currentTarget.querySelector('svg');
                            if (icon) icon.style.color = 'var(--color-text-muted)';
                          }}>
                          <ArrowUpIcon className='w-2.5 h-2.5 transition-colors' style={{ color: 'var(--color-text-muted)' }} />
                        </button>
                        <button
                          type='button'
                          onClick={() => moveModuleInChannel(pos, item.module_id, 'down')}
                          disabled={idx === channelModules.length - 1}
                          className='px-1 py-0.5 text-[10px] leading-none disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer'
                          onMouseEnter={(e) => {
                            const icon = e.currentTarget.querySelector('svg');
                            if (icon) icon.style.color = 'var(--color-text-main)';
                          }}
                          onMouseLeave={(e) => {
                            const icon = e.currentTarget.querySelector('svg');
                            if (icon) icon.style.color = 'var(--color-text-muted)';
                          }}>
                          <ArrowDownIcon className='w-2.5 h-2.5 transition-colors' style={{ color: 'var(--color-text-muted)' }} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className='mt-auto'>
                <button
                  type='button'
                  onClick={() => setShowAddModuleModal(pos)}
                  className='w-full px-2 py-3 bg-transparent border-2 border-dashed border-gray-300 hover:border-black rounded-lg text-gray-400 hover:text-black transition-all text-xs  font-bold tracking-wider cursor-pointer'
                  style={{ backgroundColor: 'transparent' }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--color-bg-white)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  title='Add a module to this channel'>
                  + ADD MODULE
                </button>
              </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Unassigned Modules Section */}
      <div className='mt-8'>
        <h3 className='text-lg font-bold text-black mb-4 tracking-tight border-b-2 border-dashed pb-2' style={{ borderColor: 'var(--color-border-main)' }}>UNASSIGNED MODULES</h3>
        <div className='space-y-2'>
          {unassignedModules.length === 0 ? (
            <div className='text-sm text-gray-500 italic py-4'>
              No unassigned modules. Create a module below or assign existing modules to channels.
            </div>
          ) : (
            unassignedModules.map((module) => {
              const typeMeta = AVAILABLE_MODULE_TYPES.find((t) => t.id === module.type);
              const isOnline = typeMeta ? !typeMeta.offline : false;
              const configured = moduleIsConfigured(module);
              const needsSetup = isOnline && !configured;
              const hasWifi = wifiStatus?.connected;
              
              let iconColor = 'var(--color-text-muted)';
              if (!hasWifi) {
                iconColor = 'var(--color-error)';
              } else if (needsSetup) {
                iconColor = 'var(--color-brass)';
              }

              return (
                <div
                  key={module.id}
                  className='flex items-center justify-between p-3 rounded-lg border-2 border-gray-300 hover:border-black group transition-all cursor-pointer'
                  style={{ backgroundColor: 'var(--color-bg-card)' }}
                  onMouseEnter={(e) => e.currentTarget.style.setProperty('background-color', 'var(--color-bg-white)', 'important')}
                  onMouseLeave={(e) => e.currentTarget.style.setProperty('background-color', 'var(--color-bg-card)', 'important')}
                  onClick={() => {
                    setShowEditModuleModal(module.id);
                    setEditingModule(JSON.parse(JSON.stringify(module)));
                  }}>
                  <div className='flex-1 min-w-0 mr-2'>
                    <div className='text-sm font-bold text-gray-700 group-hover:text-black truncate transition-colors'>{module.name}</div>
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
                      <span className="truncate font-mono group-hover:text-black transition-colors" style={{ color: 'var(--color-text-muted)' }}>{typeMeta?.label?.toUpperCase()}</span>
                    </div>
                  </div>
                  <div className='flex gap-2 items-center' onClick={(e) => e.stopPropagation()}>
                    <button
                      type='button'
                      onClick={() => triggerModulePrint(module.id)}
                      className='px-1.5 py-1 rounded border border-gray-300 hover:border-black hover:bg-white transition-all cursor-pointer'
                      title='Print this module'>
                      <PrintIcon className='w-3 h-3 text-gray-400 hover:text-black transition-colors' />
                    </button>
                    <div className='flex flex-col gap-0.5'>
                      <button
                        type='button'
                        onClick={() => moveUnassignedModule(module.id, 'up')}
                        disabled={unassignedModules.findIndex(m => m.id === module.id) === 0}
                        className='px-1 py-0.5 text-[10px] leading-none disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer'
                        onMouseEnter={(e) => {
                          const icon = e.currentTarget.querySelector('svg');
                          if (icon) icon.style.color = 'var(--color-text-main)';
                        }}
                        onMouseLeave={(e) => {
                          const icon = e.currentTarget.querySelector('svg');
                          if (icon) icon.style.color = 'var(--color-text-muted)';
                        }}>
                        <ArrowUpIcon className='w-2.5 h-2.5 transition-colors' style={{ color: 'var(--color-text-muted)' }} />
                      </button>
                      <button
                        type='button'
                        onClick={() => moveUnassignedModule(module.id, 'down')}
                        disabled={unassignedModules.findIndex(m => m.id === module.id) === unassignedModules.length - 1}
                        className='px-1 py-0.5 text-[10px] leading-none disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer'
                        onMouseEnter={(e) => {
                          const icon = e.currentTarget.querySelector('svg');
                          if (icon) icon.style.color = 'var(--color-text-main)';
                        }}
                        onMouseLeave={(e) => {
                          const icon = e.currentTarget.querySelector('svg');
                          if (icon) icon.style.color = 'var(--color-text-muted)';
                        }}>
                        <ArrowDownIcon className='w-2.5 h-2.5 transition-colors' style={{ color: 'var(--color-text-muted)' }} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
        
        {/* Add Unassigned Module Button */}
        <div className='mt-4'>
          <button
            type='button'
            onClick={() => {
              if (setShowCreateUnassignedModal) {
                setShowCreateUnassignedModal(true);
              }
            }}
            className='w-full px-2 py-3 bg-transparent border-2 border-dashed border-gray-300 hover:border-black rounded-lg text-gray-400 hover:text-black transition-all text-xs font-bold tracking-wider cursor-pointer'
            style={{ backgroundColor: 'transparent' }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--color-bg-white)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
            title='Create a new unassigned module'>
            + CREATE MODULE
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChannelList;
