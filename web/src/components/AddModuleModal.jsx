import React, { useRef } from 'react';
import { AVAILABLE_MODULE_TYPES } from '../constants';
import { commonClasses } from '../design-tokens';

const AddModuleModal = ({ channelPosition, onClose, onCreateModule, onAssignModule, onOpenEdit }) => {
  const modalMouseDownTarget = useRef(null);

  if (channelPosition === null) return null;

  return (
    <div
      className={commonClasses.modalBackdrop}
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
      <div className={commonClasses.modalContent} onClick={(e) => e.stopPropagation()}>
        <div className='flex justify-between items-center mb-6'>
          <h3 className='text-xl font-bold text-white'>Add Module to Channel {channelPosition}</h3>
          <button onClick={onClose} className={`text-gray-400 hover:text-white text-2xl`}>
            &times;
          </button>
        </div>

        <div className='grid grid-cols-2 md:grid-cols-3 gap-3'>
          {AVAILABLE_MODULE_TYPES.map((type) => (
            <button
              key={type.id}
              type='button'
              onClick={async () => {
                const newModule = await onCreateModule(type.id);
                if (newModule) {
                  await onAssignModule(channelPosition, newModule.id);
                  onClose();
                  onOpenEdit(newModule.id, newModule);
                }
              }}
              className={`flex flex-col items-center p-4 bg-[#1a1a1a] border border-gray-700 hover:border-white rounded-lg transition-colors text-center group`}>
              <span className={`font-bold text-white group-hover:text-blue-300 mb-1`}>{type.label}</span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${
                  type.offline ? 'bg-green-900/40 text-green-400' : 'bg-blue-900/30 text-blue-300'
                }`}>
                {type.offline ? 'Offline' : 'Online'}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default AddModuleModal;
