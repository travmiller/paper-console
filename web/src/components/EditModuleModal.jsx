import React, { useRef } from 'react';
import ModuleConfig from './ModuleConfig';
import { AVAILABLE_MODULE_TYPES } from '../constants';

const EditModuleModal = ({ moduleId, module, setModule, onClose, onSave, onDelete }) => {
  const modalMouseDownTarget = useRef(null);

  if (moduleId === null || !module) return null;

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
          onSave(moduleId, module, true);
          onClose();
        }
        modalMouseDownTarget.current = null;
      }}>
      <div
        className='bg-[#2a2a2a] border border-gray-700 rounded-lg p-4 sm:p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto'
        onClick={(e) => e.stopPropagation()}>
        <div className='flex justify-between items-start mb-6'>
          <div>
            <h3 className='text-xl font-bold text-white mb-1'>Edit Module</h3>
            <div className='text-sm text-gray-400 flex gap-4'>
              <span>ID: {moduleId}</span>
              <span>Type: {AVAILABLE_MODULE_TYPES.find((t) => t.id === module?.type)?.label}</span>
            </div>
          </div>
          <button
            onClick={() => {
              onSave(moduleId, module, true);
              onClose();
            }}
            className='text-gray-400 hover:text-white text-2xl'>
            &times;
          </button>
        </div>

        <div className='mb-6'>
          <label className='block mb-2 text-sm text-gray-400'>Module Name</label>
          <input
            type='text'
            value={module?.name || ''}
            onChange={(e) => {
              setModule((prev) => (prev ? { ...prev, name: e.target.value } : prev));
            }}
            className='w-full p-3 text-base bg-[#333] border border-gray-700 rounded text-white focus:border-white focus:outline-none'
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

        <div className='mt-8 pt-6 border-t border-gray-700 flex justify-end gap-3'>
          <button
            type='button'
            onClick={() => onDelete(moduleId)}
            className='px-4 py-2 bg-red-900/20 text-red-400 border border-red-900/50 hover:bg-red-900/40 rounded transition-colors'>
            Delete Module
          </button>
          <button
            type='button'
            onClick={() => {
              onSave(moduleId, module, true);
              onClose();
            }}
            className='px-6 py-2 bg-white text-black font-medium rounded hover:bg-gray-200 transition-colors'>
            Done
          </button>
        </div>
      </div>
    </div>
  );
};

export default EditModuleModal;
