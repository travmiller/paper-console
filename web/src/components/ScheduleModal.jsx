import React, { useRef } from 'react';
import { formatTimeForDisplay } from '../utils';

const ScheduleModal = ({ position, channel, onClose, onUpdate, timeFormat }) => {
  const modalMouseDownTarget = useRef(null);

  if (position === null) return null;

  return (
    <div
      className='fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4'
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) {
          modalMouseDownTarget.current = 'backdrop';
        }
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && modalMouseDownTarget.current === 'backdrop') {
          onClose();
        }
        modalMouseDownTarget.current = null;
      }}>
      <div className='bg-[#2a2a2a] border border-gray-700 rounded-lg p-4 sm:p-6 max-w-md w-full' onClick={(e) => e.stopPropagation()}>
        <div className='flex justify-between items-center mb-6'>
          <h3 className='text-xl font-bold text-white'>Schedule Channel {position}</h3>
          <button onClick={onClose} className='text-gray-400 hover:text-white text-2xl'>
            &times;
          </button>
        </div>

        <div className='space-y-4'>
          <div className='text-sm text-gray-400 mb-4'>Add times when this channel should automatically print.</div>

          <div className='space-y-2 max-h-[300px] overflow-y-auto'>
            {(channel?.schedule || []).map((time, idx) => (
              <div key={idx} className='flex items-center justify-between bg-[#1a1a1a] p-3 rounded border border-gray-800'>
                <span className='text-white font-mono text-lg'>{formatTimeForDisplay(time, timeFormat)}</span>
                <button
                  onClick={() => {
                    const newSchedule = [...(channel?.schedule || [])];
                    newSchedule.splice(idx, 1);
                    onUpdate(newSchedule);
                  }}
                  className='text-red-400 hover:text-red-300 px-2'>
                  &times;
                </button>
              </div>
            ))}
            {(!channel?.schedule || channel.schedule.length === 0) && (
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
                  const currentSchedule = channel?.schedule || [];
                  if (!currentSchedule.includes(time)) {
                    const newSchedule = [...currentSchedule, time].sort();
                    onUpdate(newSchedule);
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
              <button type='submit' className='bg-white text-black px-4 py-2 rounded font-medium hover:bg-gray-200 transition-colors'>
                Add
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ScheduleModal;
