import React, { useState, useEffect } from 'react';
import {
  DndContext,
  DragOverlay,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import { arrayMove } from '@dnd-kit/sortable';
import { INK_GRADIENTS } from '../constants';
import { useModuleTypes } from '../hooks/useModuleTypes';
import PrintIcon from '../assets/PrintIcon';
import ScheduleIcon from '../assets/ScheduleIcon';
import ArrowUpIcon from '../assets/ArrowUpIcon';
import ArrowDownIcon from '../assets/ArrowDownIcon';
import DraggableModuleCard from './DraggableModuleCard';
import DroppableChannel from './DroppableChannel';

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
  onMoveModuleBetweenChannels,
  onUnassignModule,
  onAssignModuleToChannel,
}) => {
  const { moduleTypes } = useModuleTypes();
  const [activeId, setActiveId] = useState(null);
  const [activeModule, setActiveModule] = useState(null);

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
    const assignedModuleIds = new Set();
    Object.values(settings.channels || {}).forEach((channel) => {
      (channel.modules || []).forEach((assignment) => {
        assignedModuleIds.add(assignment.module_id);
      });
    });

    const unassigned = Object.values(modules || {}).filter((module) => !assignedModuleIds.has(module.id));
    const currentOrder = unassigned.map((m) => m.id);

    setUnassignedModuleOrder((prevOrder) => {
      const prevSet = new Set(prevOrder);
      const currentSet = new Set(currentOrder);
      if (prevSet.size !== currentSet.size || ![...prevSet].every((id) => currentSet.has(id))) {
        return currentOrder;
      }
      return prevOrder;
    });
  }, [modules, settings.channels]);

  const unassignedModules = unassignedModuleOrder.map((id) => modules[id]).filter(Boolean);

  const moveUnassignedModule = (moduleId, direction) => {
    const currentIndex = unassignedModuleOrder.findIndex((id) => id === moduleId);
    if (currentIndex === -1) return;

    const newOrder = [...unassignedModuleOrder];
    if (direction === 'up' && currentIndex > 0) {
      [newOrder[currentIndex], newOrder[currentIndex - 1]] = [newOrder[currentIndex - 1], newOrder[currentIndex]];
      setUnassignedModuleOrder(newOrder);
    } else if (direction === 'down' && currentIndex < newOrder.length - 1) {
      [newOrder[currentIndex], newOrder[currentIndex + 1]] = [newOrder[currentIndex + 1], newOrder[currentIndex]];
      setUnassignedModuleOrder(newOrder);
    }
  };

  // Find which channel a module belongs to
  const findModuleChannel = (moduleId) => {
    for (const [pos, channel] of Object.entries(settings.channels || {})) {
      if (channel.modules?.some((m) => m.module_id === moduleId)) {
        return parseInt(pos, 10);
      }
    }
    return null; // unassigned
  };

  // Sensors for drag and drop (pointer for desktop, touch for mobile)
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8, // Require 8px movement before drag starts
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: 200, // 200ms hold before drag on touch
        tolerance: 5,
      },
    }),
    useSensor(KeyboardSensor)
  );

  const handleDragStart = (event) => {
    const { active } = event;
    setActiveId(active.id);
    setActiveModule(modules[active.id]);
  };

  const handleDragEnd = (event) => {
    const { active, over } = event;
    setActiveId(null);
    setActiveModule(null);

    if (!over) return;

    const activeModuleId = active.id;
    const sourceChannel = findModuleChannel(activeModuleId);

    // Determine destination
    let destChannel = null;
    let destIndex = null;

    if (over.data?.current?.type === 'module') {
      // Dropped on another module
      destChannel = over.data.current.channelPosition;
      // Find the index of the target module to insert before/after
      if (destChannel !== null) {
        const channel = settings.channels[destChannel];
        const sortedModules = [...(channel?.modules || [])].sort((a, b) => a.order - b.order);
        destIndex = sortedModules.findIndex((m) => m.module_id === over.id);
      } else {
        // Dropped on unassigned module
        destIndex = unassignedModuleOrder.findIndex((id) => id === over.id);
      }
    } else if (over.data?.current?.type === 'channel') {
      // Dropped on channel container
      destChannel = over.data.current.channelPosition;
      destIndex = null; // Append to end
    } else if (over.data?.current?.type === 'unassigned') {
      // Dropped on unassigned container
      destChannel = null;
      destIndex = null;
    }

    // Same channel reorder
    if (sourceChannel === destChannel && sourceChannel !== null) {
      const channel = settings.channels[sourceChannel];
      const sortedModules = [...(channel?.modules || [])].sort((a, b) => a.order - b.order);
      const oldIndex = sortedModules.findIndex((m) => m.module_id === activeModuleId);
      const newIndex = sortedModules.findIndex((m) => m.module_id === over.id);

      if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
        const reordered = arrayMove(sortedModules, oldIndex, newIndex);
        const moduleOrders = {};
        reordered.forEach((m, idx) => {
          moduleOrders[m.module_id] = idx;
        });
        // Use existing reorder function
        if (moveModuleInChannel) {
          // Directly call reorder API via parent
          onMoveModuleBetweenChannels?.(sourceChannel, sourceChannel, activeModuleId, moduleOrders);
        }
      }
      return;
    }

    // Unassigned reorder
    if (sourceChannel === null && destChannel === null) {
      const oldIndex = unassignedModuleOrder.findIndex((id) => id === activeModuleId);
      const newIndex = unassignedModuleOrder.findIndex((id) => id === over.id);
      if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
        setUnassignedModuleOrder(arrayMove(unassignedModuleOrder, oldIndex, newIndex));
      }
      return;
    }

    // Cross-channel move or assign/unassign
    if (sourceChannel !== destChannel) {
      if (sourceChannel === null && destChannel !== null) {
        // Assign from unassigned to channel
        onAssignModuleToChannel?.(destChannel, activeModuleId, destIndex);
      } else if (sourceChannel !== null && destChannel === null) {
        // Unassign from channel
        onUnassignModule?.(sourceChannel, activeModuleId);
      } else if (sourceChannel !== null && destChannel !== null) {
        // Move between channels
        onMoveModuleBetweenChannels?.(sourceChannel, destChannel, activeModuleId, destIndex);
      }
    }
  };

  const handleDragCancel = () => {
    setActiveId(null);
    setActiveModule(null);
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <div className="space-y-4">
        <div className="space-y-4">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((pos) => {
            const channel = settings.channels?.[pos] || { modules: [] };
            const channelModules = (channel.modules || [])
              .map((assignment) => ({
                ...assignment,
                module: modules[assignment.module_id],
              }))
              .filter((item) => item.module)
              .sort((a, b) => a.order - b.order);

            const moduleIds = channelModules.map((item) => item.module_id);
            const inkGradients = INK_GRADIENTS;

            return (
              <div key={pos} className="rounded-xl p-[4px] shadow-lg" style={{ background: inkGradients[pos - 1] }}>
                <div className="bg-bg-card rounded-lg p-4 flex flex-col h-full">
                  <div className="flex items-center justify-between mb-3 gap-4">
                    <div className="flex items-center gap-3 overflow-x-auto">
                      <h3 className="font-bold text-black text-lg tracking-tight">{pos}</h3>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => triggerChannelPrint(pos)}
                          className="group flex items-center justify-center px-2 py-1 rounded border-2 bg-transparent border-gray-300 hover:border-black hover:bg-white transition-all cursor-pointer"
                          title="Print Channel"
                        >
                          <PrintIcon className="w-3.5 h-3.5 text-gray-400 group-hover:text-black transition-all" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setShowScheduleModal(pos)}
                          className={`group flex items-center gap-1 px-2 py-1 rounded border-2 transition-all cursor-pointer ${
                            channel.schedule && channel.schedule.length > 0
                              ? 'bg-transparent shadow-sm'
                              : 'bg-transparent border-gray-300 hover:border-black hover:bg-white'
                          }`}
                          style={
                            channel.schedule && channel.schedule.length > 0
                              ? { color: 'var(--color-brass)', borderColor: 'var(--color-brass)' }
                              : {}
                          }
                          onMouseEnter={(e) => {
                            if (channel.schedule && channel.schedule.length > 0)
                              e.currentTarget.style.backgroundColor = 'var(--color-brass-10)';
                          }}
                          onMouseLeave={(e) => {
                            if (channel.schedule && channel.schedule.length > 0)
                              e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                          title="Configure Schedule"
                        >
                          <ScheduleIcon
                            className={`w-3.5 h-3.5 transition-all ${
                              channel.schedule?.length > 0 ? '' : 'text-gray-400 group-hover:text-black'
                            }`}
                            style={channel.schedule?.length > 0 ? { color: 'var(--color-brass)' } : {}}
                          />
                          <span
                            className={`text-xs font-bold ${
                              channel.schedule?.length > 0 ? '' : 'text-gray-400 group-hover:text-black'
                            }`}
                            style={channel.schedule?.length > 0 ? { color: 'var(--color-brass)' } : {}}
                          >
                            {channel.schedule?.length || 0}
                          </span>
                        </button>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          swapChannels(pos, pos - 1);
                        }}
                        disabled={pos === 1}
                        className="px-2 py-1 text-xs border-2 border-gray-300 hover:border-black rounded text-gray-600 hover:text-black transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer hover:bg-white"
                        title="Move channel up"
                      >
                        <ArrowUpIcon className="w-3 h-3" />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          swapChannels(pos, pos + 1);
                        }}
                        disabled={pos === 8}
                        className="px-2 py-1 text-xs border-2 border-gray-300 hover:border-black rounded text-gray-600 hover:text-black transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer hover:bg-white"
                        title="Move channel down"
                      >
                        <ArrowDownIcon className="w-3 h-3" />
                      </button>
                    </div>
                  </div>

                  <DroppableChannel id={`channel-${pos}`} moduleIds={moduleIds} className="space-y-2 mb-2 flex-grow">
                    {channelModules.map((item, idx) => (
                      <DraggableModuleCard
                        key={item.module_id}
                        module={item.module}
                        moduleId={item.module_id}
                        channelPosition={pos}
                        index={idx}
                        totalModules={channelModules.length}
                        wifiStatus={wifiStatus}
                        settings={settings}
                        moduleIsConfigured={moduleIsConfigured}
                        onEdit={() => {
                          setShowEditModuleModal(item.module_id);
                          setEditingModule(JSON.parse(JSON.stringify(modules[item.module_id])));
                        }}
                        onPrint={() => triggerModulePrint(item.module_id)}
                        onMoveUp={() => moveModuleInChannel(pos, item.module_id, 'up')}
                        onMoveDown={() => moveModuleInChannel(pos, item.module_id, 'down')}
                      />
                    ))}
                  </DroppableChannel>

                  <div className="mt-auto">
                    <button
                      type="button"
                      onClick={() => setShowAddModuleModal(pos)}
                      className="w-full px-2 py-3 bg-transparent border-2 border-dashed border-gray-300 hover:border-black rounded-lg text-gray-400 hover:text-black transition-all text-xs font-bold tracking-wider cursor-pointer"
                      style={{ backgroundColor: 'transparent' }}
                      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--color-bg-white)')}
                      onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      title="Add a module to this channel"
                    >
                      + ADD MODULE
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Unassigned Modules Section */}
        <div className="mt-8">
          <h3 className="text-lg font-bold text-black mb-4 tracking-tight border-b-2 border-dashed border-gray-300 pb-2">
            UNASSIGNED MODULES
          </h3>
          <DroppableChannel
            id="unassigned"
            moduleIds={unassignedModuleOrder}
            className="space-y-2"
            isUnassigned={true}
          >
            {unassignedModules.length === 0 ? (
              <div className="text-sm text-gray-500 italic py-4">
                No unassigned modules. Create a module below or assign existing modules to channels.
              </div>
            ) : (
              unassignedModules.map((module, idx) => (
                <DraggableModuleCard
                  key={module.id}
                  module={module}
                  moduleId={module.id}
                  channelPosition={null}
                  index={idx}
                  totalModules={unassignedModules.length}
                  wifiStatus={wifiStatus}
                  settings={settings}
                  moduleIsConfigured={moduleIsConfigured}
                  onEdit={() => {
                    setShowEditModuleModal(module.id);
                    setEditingModule(JSON.parse(JSON.stringify(module)));
                  }}
                  onPrint={() => triggerModulePrint(module.id)}
                  onMoveUp={() => moveUnassignedModule(module.id, 'up')}
                  onMoveDown={() => moveUnassignedModule(module.id, 'down')}
                />
              ))
            )}
          </DroppableChannel>

          {/* Add Unassigned Module Button */}
          <div className="mt-4">
            <button
              type="button"
              onClick={() => {
                if (setShowCreateUnassignedModal) {
                  setShowCreateUnassignedModal(true);
                }
              }}
              className="w-full px-2 py-3 bg-transparent border-2 border-dashed border-gray-300 hover:border-black rounded-lg text-gray-400 hover:text-black transition-all text-xs font-bold tracking-wider cursor-pointer"
              style={{ backgroundColor: 'transparent' }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--color-bg-white)')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
              title="Add a new unassigned module"
            >
              + ADD MODULE
            </button>
          </div>
        </div>
      </div>

      {/* Drag Overlay - Shows the dragged item */}
      <DragOverlay>
        {activeId && activeModule ? (
          <div
            className="flex items-center justify-between p-2 rounded-lg border-2 border-black shadow-xl"
            style={{ backgroundColor: 'var(--color-bg-white)', width: '100%', maxWidth: '400px' }}
          >
            <div className="flex-1 min-w-0 ml-6">
              <div className="text-sm font-bold text-black truncate">{activeModule.name}</div>
              <div className="text-[10px] text-gray-500 font-mono">
                {moduleTypes.find((t) => t.id === activeModule.type)?.label?.toUpperCase()}
              </div>
            </div>
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
};

export default ChannelList;
