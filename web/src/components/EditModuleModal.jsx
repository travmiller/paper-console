import React, { useRef } from 'react';
import ModuleConfig from './ModuleConfig';
import { AVAILABLE_MODULE_TYPES } from '../constants';
import { commonClasses } from '../design-tokens';
import BinIcon from '../assets/BinIcon';
import GCheckIcon from '../assets/GCheckIcon';

const EditModuleModal = ({ moduleId, module, setModule, onClose, onSave, onDelete }) => {
  const modalMouseDownTarget = useRef(null);

  if (moduleId === null || !module) return null;

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
          onSave(moduleId, module, true);
          onClose();
        }
        modalMouseDownTarget.current = null;
      }}>
      <div className={commonClasses.modalContent} onClick={(e) => e.stopPropagation()}>
        <div className='flex justify-between items-start mb-6'>
          <div>
            <h3 className='text-xl font-bold text-black mb-1 '>Edit Module</h3>
            <div className={`text-gray-600 text-sm `}>
              <span className="font-mono">Type: {AVAILABLE_MODULE_TYPES.find((t) => t.id === module?.type)?.label}</span>
            </div>
          </div>
          <button
            onClick={() => {
              onSave(moduleId, module, true);
              onClose();
            }}
            className={`text-gray-500 hover:text-black text-2xl `}>
            &times;
          </button>
        </div>

        <div className='mb-6'>
          <label className={commonClasses.label}>Module Name</label>
          <input
            type='text'
            value={module?.name || ''}
            onChange={(e) => {
              setModule((prev) => (prev ? { ...prev, name: e.target.value } : prev));
            }}
            className={commonClasses.input}
          />
        </div>

        {module && (
          <ModuleConfig
            module={module}
            updateConfig={(field, value) => {
              setModule((prev) =>
                prev
                  ? {
                      ...prev,
                      config: { ...prev.config, [field]: value },
                    }
                  : prev,
              );
            }}
          />
        )}

        <div className={`mt-8 pt-6 border-t-2 border-gray-300 flex justify-end gap-3`}>
          <button 
            type='button' 
            onClick={() => onDelete(moduleId)} 
            className='px-4 py-2 bg-transparent border-0 rounded-lg transition-all cursor-pointer flex items-center gap-2'
            style={{ color: '#DC7171' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#DC2626';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#DC7171';
            }}>
            <BinIcon className='w-4 h-4' />
            Delete Module
          </button>
          <button
            type='button'
            onClick={() => {
              onSave(moduleId, module, true);
              onClose();
            }}
            className='px-6 py-2 bg-transparent border-2 rounded-lg font-bold transition-all cursor-pointer flex items-center gap-2'
            style={{ borderColor: '#7A756E', color: '#7A756E' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#FFFFFF';
              e.currentTarget.style.borderColor = '#2A2A2A';
              e.currentTarget.style.color = '#2A2A2A';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.borderColor = '#7A756E';
              e.currentTarget.style.color = '#7A756E';
            }}>
            Save
          </button>
        </div>
      </div>
    </div>
  );
};

export default EditModuleModal;
