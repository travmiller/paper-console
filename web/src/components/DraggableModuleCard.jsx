import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useModuleTypes } from '../hooks/useModuleTypes';
import WiFiIcon from '../assets/WiFiIcon';
import WiFiOffIcon from '../assets/WiFiOffIcon';
import PrintIcon from '../assets/PrintIcon';
import ArrowUpIcon from '../assets/ArrowUpIcon';
import ArrowDownIcon from '../assets/ArrowDownIcon';
import GripIcon from '../assets/GripIcon';

/**
 * A draggable module card component that can be reordered within channels
 * or moved between channels via drag and drop.
 */
const DraggableModuleCard = ({
  module,
  moduleId,
  channelPosition, // null for unassigned
  index,
  totalModules,
  wifiStatus,
  settings,
  onEdit,
  onPrint,
  onMoveUp,
  onMoveDown,
  moduleIsConfigured,
  isDragOverlay = false,
}) => {
  const { moduleTypes } = useModuleTypes();
  
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: moduleId,
    data: {
      type: 'module',
      module,
      channelPosition,
    },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    backgroundColor: 'var(--color-bg-card)',
  };

  const typeMeta = moduleTypes.find((t) => t.id === module?.type);
  const isOnline = typeMeta ? !typeMeta.offline : false;
  const configured = moduleIsConfigured ? moduleIsConfigured(module) : true;
  const needsSetup = isOnline && !configured;
  const hasWifi = wifiStatus?.connected;

  // Determine icon color
  let iconColor = 'var(--color-text-muted)';
  if (!hasWifi) {
    iconColor = 'var(--color-error)';
  } else if (needsSetup) {
    iconColor = 'var(--color-brass)';
  }

  const handleCardClick = (e) => {
    // Don't open edit if clicking on buttons or drag handle
    if (e.target.closest('button') || e.target.closest('[data-drag-handle]')) {
      return;
    }
    onEdit?.();
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center justify-between p-2 rounded-lg border-2 group transition-all cursor-pointer ${
        isDragging ? 'border-black shadow-lg' : 'border-gray-600 hover:border-black'
      }`}
      onMouseEnter={(e) => {
        if (!isDragging) {
          e.currentTarget.style.setProperty('background-color', 'var(--color-bg-white)', 'important');
        }
      }}
      onMouseLeave={(e) => {
        if (!isDragging) {
          e.currentTarget.style.setProperty('background-color', 'var(--color-bg-card)', 'important');
        }
      }}
      onClick={handleCardClick}
    >
      {/* Drag Handle */}
      <div
        data-drag-handle
        className="flex items-center justify-center px-1 mr-2 cursor-grab active:cursor-grabbing touch-none"
        {...attributes}
        {...listeners}
      >
        <GripIcon className="w-4 h-4 text-gray-400 group-hover:text-gray-600 transition-colors" />
      </div>

      {/* Module Info */}
      <div className="flex-1 min-w-0 mr-2">
        <div className="text-sm font-bold text-gray-700 group-hover:text-black truncate transition-colors">
          {module?.name}
        </div>
        <div
          className={`text-[10px] truncate flex items-baseline gap-1 ${needsSetup ? '' : 'text-gray-700'}`}
          style={needsSetup ? { color: 'var(--color-brass)' } : {}}
        >
          {isOnline && (
            hasWifi ? (
              <WiFiIcon
                className="w-2.5 h-2.5 flex-shrink-0 group-hover:text-black transition-colors"
                style={{ transform: 'translateY(0.125rem)', color: iconColor }}
              />
            ) : (
              <WiFiOffIcon
                className="w-2.5 h-2.5 flex-shrink-0"
                style={{ transform: 'translateY(0.125rem)', color: 'var(--color-error)' }}
              />
            )
          )}
          <span
            className="truncate font-mono group-hover:text-black transition-colors"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {typeMeta?.label?.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2 items-center" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          onClick={() => onPrint?.()}
          className="px-1.5 py-1 rounded border border-gray-300 hover:border-black hover:bg-white transition-all cursor-pointer"
          title="Print this module"
        >
          <PrintIcon className="w-3 h-3 text-gray-400 hover:text-black transition-colors" />
        </button>
        <div className="flex flex-col gap-0.5">
          <button
            type="button"
            onClick={() => onMoveUp?.()}
            disabled={index === 0}
            className="px-1 py-0.5 text-[10px] leading-none disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
            onMouseEnter={(e) => {
              const icon = e.currentTarget.querySelector('svg');
              if (icon) icon.style.color = 'var(--color-text-main)';
            }}
            onMouseLeave={(e) => {
              const icon = e.currentTarget.querySelector('svg');
              if (icon) icon.style.color = 'var(--color-text-muted)';
            }}
          >
            <ArrowUpIcon className="w-2.5 h-2.5 transition-colors" style={{ color: 'var(--color-text-muted)' }} />
          </button>
          <button
            type="button"
            onClick={() => onMoveDown?.()}
            disabled={index === totalModules - 1}
            className="px-1 py-0.5 text-[10px] leading-none disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
            onMouseEnter={(e) => {
              const icon = e.currentTarget.querySelector('svg');
              if (icon) icon.style.color = 'var(--color-text-main)';
            }}
            onMouseLeave={(e) => {
              const icon = e.currentTarget.querySelector('svg');
              if (icon) icon.style.color = 'var(--color-text-muted)';
            }}
          >
            <ArrowDownIcon className="w-2.5 h-2.5 transition-colors" style={{ color: 'var(--color-text-muted)' }} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default DraggableModuleCard;
