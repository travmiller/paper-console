import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';

/**
 * A droppable container for modules - used for both channels and the unassigned section.
 * Provides visual feedback when items are being dragged over.
 */
const DroppableChannel = ({
  id,
  moduleIds,
  children,
  className = '',
  isUnassigned = false,
}) => {
  const { isOver, setNodeRef } = useDroppable({
    id,
    data: {
      type: isUnassigned ? 'unassigned' : 'channel',
      channelPosition: isUnassigned ? null : parseInt(id.replace('channel-', ''), 10),
    },
  });

  return (
    <SortableContext items={moduleIds} strategy={verticalListSortingStrategy}>
      <div
        ref={setNodeRef}
        className={`${className} ${isOver ? 'ring-2 ring-black ring-opacity-50 rounded-lg' : ''}`}
        style={{
          minHeight: moduleIds.length === 0 ? '40px' : undefined,
          transition: 'box-shadow 200ms ease',
        }}
      >
        {children}
      </div>
    </SortableContext>
  );
};

export default DroppableChannel;
