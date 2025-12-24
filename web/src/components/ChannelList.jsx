import React from 'react';
import { AVAILABLE_MODULE_TYPES } from '../constants';
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
  setShowScheduleModal,
  swapChannels,
  setShowEditModuleModal,
  setEditingModule,
  moveModuleInChannel,
  setShowAddModuleModal,
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

          return (
            <div key={pos} className='bg-bg-card border-4 border-black rounded-xl p-4 flex flex-col h-full shadow-lg'>
              <div className='flex items-center justify-between mb-3 gap-4'>
                <div className='flex items-center gap-3 overflow-x-auto'>
                  <h3 className='font-bold text-black  text-lg tracking-tight'>
                    {pos}
                  </h3>
                  <div className='flex items-center gap-1'>
                    <button
                      type='button'
                      onClick={() => triggerChannelPrint(pos)}
                      className='group flex items-center justify-center px-2 py-1 rounded border-2 bg-transparent border-gray-300 hover:border-black hover:bg-gray-100 transition-all cursor-pointer'
                      title='Print Channel'>
                      <PrintIcon className='w-3.5 h-3.5 text-gray-400 group-hover:text-black transition-all' />
                    </button>
                    <button
                      type='button'
                      onClick={() => setShowScheduleModal(pos)}
                      className={`group flex items-center gap-1 px-2 py-1 rounded border-2 transition-all cursor-pointer ${
                        channel.schedule && channel.schedule.length > 0
                          ? 'bg-transparent text-blue-600 border-blue-600 hover:bg-blue-50 shadow-sm'
                          : 'bg-transparent border-gray-300 hover:border-black hover:bg-gray-100'
                      }`}
                      title='Configure Schedule'>
                      <ScheduleIcon className={`w-3.5 h-3.5 transition-all ${channel.schedule?.length > 0 ? 'text-blue-600' : 'text-gray-400 group-hover:text-black'}`} />
                      <span className={`text-xs  font-bold ${channel.schedule?.length > 0 ? 'text-blue-600' : 'text-gray-400 group-hover:text-black'}`}>{channel.schedule?.length || 0}</span>
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
                    className='px-2 py-1 text-xs  border-2 border-gray-300 hover:border-black rounded text-gray-600 hover:text-black transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer hover:bg-gray-100'
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
                    className='px-2 py-1 text-xs  border-2 border-gray-300 hover:border-black rounded text-gray-600 hover:text-black transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer hover:bg-gray-100'
                    title='Move channel down'>
                    <ArrowDownIcon className='w-3 h-3' />
                  </button>
                </div>
              </div>

              <div className='space-y-2 mb-2 flex-grow'>
                {channelModules.map((item, idx) => (
                  <div
                    key={item.module_id}
                    className='flex items-center justify-between p-2 bg-bg-input rounded-lg border-2 border-gray-600 hover:border-black hover:bg-gray-100 group transition-all cursor-pointer'
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

                        return (
                          <>
                      <div className='text-sm font-bold text-gray-700 group-hover:text-black  truncate transition-colors'>{item.module.name}</div>
                      <div
                        className={`text-[10px]  truncate flex items-baseline gap-1 ${
                          needsSetup ? 'text-amber-700' : 'text-gray-700'
                        }`}>
                        {isOnline && (
                          wifiStatus?.connected ? (
                            <WiFiIcon className="w-2.5 h-2.5 flex-shrink-0" style={{ transform: 'translateY(0.125rem)' }} />
                          ) : (
                            <WiFiOffIcon className="w-2.5 h-2.5 flex-shrink-0 text-amber-700" style={{ transform: 'translateY(0.125rem)' }} />
                          )
                        )}
                        <span className="truncate">{typeMeta?.label?.toUpperCase()}</span>
                      </div>
                          </>
                        );
                      })()}
                    </div>
                    <div className='flex gap-2 items-center' onClick={(e) => e.stopPropagation()}>
                      <div className='flex flex-col gap-0.5'>
                        <button
                          type='button'
                          onClick={() => moveModuleInChannel(pos, item.module_id, 'up')}
                          disabled={idx === 0}
                          className='px-1 text-[10px] leading-none text-gray-600 hover:text-black disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer'>
                          <ArrowUpIcon className='w-2.5 h-2.5' />
                        </button>
                        <button
                          type='button'
                          onClick={() => moveModuleInChannel(pos, item.module_id, 'down')}
                          disabled={idx === channelModules.length - 1}
                          className='px-1 text-[10px] leading-none text-gray-600 hover:text-black disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer'>
                          <ArrowDownIcon className='w-2.5 h-2.5' />
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
                  className='w-full px-2 py-3 bg-transparent border-2 border-dashed border-gray-300 hover:border-black rounded-lg text-gray-400 hover:text-black transition-all text-xs  font-bold tracking-wider cursor-pointer hover:bg-gray-50'
                  title='Add a module to this channel'>
                  + ADD MODULE
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ChannelList;
