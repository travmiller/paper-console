import React, { useRef } from 'react';
import ModuleConfig from './ModuleConfig';
import { useModuleTypes } from '../hooks/useModuleTypes';
import { commonClasses } from '../design-tokens';
import CloseButton from './CloseButton';
import PrimaryButton from './PrimaryButton';
import BinIcon from '../assets/BinIcon';


const EditModuleModal = ({ moduleId, module, setModule, onClose, onSave, onDelete }) => {
  const modalMouseDownTarget = useRef(null);
  const { moduleTypes } = useModuleTypes();

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
              <span className="font-mono">Type: {moduleTypes.find((t) => t.id === module?.type)?.label}</span>
            </div>
          </div>
          <CloseButton
            onClick={() => {
              onSave(moduleId, module, true);
              onClose();
            }}
          />
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
            onRefresh={async () => {
              // Fetch fresh settings and update the module state
              try {
                const res = await fetch('/api/settings');
                const data = await res.json();
                const freshModule = data.modules?.[moduleId];
                if (freshModule) {
                  setModule(freshModule);
                }
              } catch (e) {
                console.error('Failed to refresh module:', e);
              }
            }}
          />
        )}

        <div className={`mt-8 pt-6 border-t-2 border-gray-300 flex justify-end gap-3`}>
          <button 
            type='button' 
            onClick={() => onDelete(moduleId)} 
            className='px-4 py-2 bg-transparent border-0 rounded-lg transition-all cursor-pointer flex items-center gap-2'
            style={{ color: 'var(--color-error-light)' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--color-error)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--color-error-light)';
            }}>
            <BinIcon className='w-4 h-4' />
            Delete Module
          </button>
          <PrimaryButton
            onClick={() => {
              onSave(moduleId, module, true);
              onClose();
            }}>
            Save
          </PrimaryButton>
        </div>
      </div>
    </div>
  );
};

export default EditModuleModal;
