import React, { useRef } from 'react';
import { AVAILABLE_MODULE_TYPES } from '../constants';
import { commonClasses } from '../design-tokens';
import WiFiIcon from '../assets/WiFiIcon';

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
          <h3 className='text-xl font-bold text-black '>Add Module to Channel {channelPosition}</h3>
          <button onClick={onClose} className={`text-gray-500 hover:text-black text-2xl  cursor-pointer hover-shimmer`}>
            &times;
          </button>
        </div>

        <div className='grid grid-cols-2 md:grid-cols-3 gap-3'>
          {[...AVAILABLE_MODULE_TYPES].sort((a, b) => {
            // Offline modules first (offline: true), then online modules (offline: false)
            if (a.offline && !b.offline) return -1;
            if (!a.offline && b.offline) return 1;
            // Within each group, alphabetize by label
            return a.label.localeCompare(b.label);
          }).map((type) => (
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
              className={`flex flex-col items-center p-4 bg-white border-2 border-gray-300 hover:border-black rounded-lg transition-colors text-center group cursor-pointer hover-shimmer`}>
              <div className="flex items-baseline justify-center gap-1.5">
                {!type.offline && (
                  <WiFiIcon className="w-3 h-3 text-blue-600 flex-shrink-0" style={{ transform: 'translateY(0.125rem)' }} />
                )}
                <span className={`font-bold text-black group-hover:text-black `}>{type.label}</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default AddModuleModal;
