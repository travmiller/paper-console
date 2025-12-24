import React, { useRef } from 'react';
import { formatTimeForDisplay } from '../utils';
import CloseButton from './CloseButton';
import PrimaryButton from './PrimaryButton';

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
      <div className='border-4 rounded-xl p-4 sm:p-6 max-w-md w-full shadow-lg' style={{ backgroundColor: 'var(--color-bg-card)', borderColor: 'var(--color-border-main)' }} onClick={(e) => e.stopPropagation()}>
        <div className='flex justify-between items-center mb-6'>
          <h3 className='text-xl font-bold text-black '>Schedule Channel {position}</h3>
          <CloseButton onClick={onClose} />
        </div>

        <div className='space-y-4'>
          <div className='text-sm text-gray-600 mb-4 '>Add times when this channel should automatically print.</div>

          <div className='space-y-2 max-h-[300px] overflow-y-auto'>
            {(channel?.schedule || []).map((time, idx) => (
              <div key={idx} className='flex items-center justify-between p-3 rounded-lg border-2 border-gray-300 hover:border-black' style={{ backgroundColor: 'var(--color-bg-card)' }}>
                <span className='text-black  text-lg'>{formatTimeForDisplay(time, timeFormat)}</span>
                <button
                  onClick={() => {
                    const newSchedule = [...(channel?.schedule || [])];
                    newSchedule.splice(idx, 1);
                    onUpdate(newSchedule);
                  }}
                  className='text-red-600 hover:text-red-700 px-2  font-bold cursor-pointer hover-shimmer'>
                  &times;
                </button>
              </div>
            ))}
            {(!channel?.schedule || channel.schedule.length === 0) && (
              <div className='text-gray-500 text-center py-4 italic '>No scheduled times.</div>
            )}
          </div>

          <div className='pt-4 border-t-2 border-gray-300'>
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
                className='flex-1 border-2 border-gray-300 rounded-lg px-3 py-2 text-black focus:outline-none focus:border-black '
                style={{ backgroundColor: 'var(--color-bg-card)' }}
              />
              <PrimaryButton type="submit">
                Add
              </PrimaryButton>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ScheduleModal;
