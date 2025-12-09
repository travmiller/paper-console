import React from 'react';
import { AVAILABLE_MODULE_TYPES } from '../constants';

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
}) => {
  return (
    <div className='space-y-4'>
      <h2 className='text-xl font-bold mb-4'>Channel Configuration</h2>
      <div className='space-y-6'>
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
              <div className='flex items-center justify-between mb-3 gap-4'>
                <div className='flex items-center gap-2 overflow-x-auto'>
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
                    onClick={() => {
                      setShowEditModuleModal(item.module_id);
                      setEditingModule(JSON.parse(JSON.stringify(modules[item.module_id])));
                    }}>
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
                  <div className='text-center text-gray-500 py-8 text-sm border-2 border-dashed border-gray-700 rounded-md'>
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
    </div>
  );
};

export default ChannelList;
