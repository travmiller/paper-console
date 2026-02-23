import React, { useEffect, useMemo, useRef, useState } from 'react';
import ModuleConfig from './ModuleConfig';
import { useModuleTypes } from '../hooks/useModuleTypes';
import { commonClasses } from '../design-tokens';
import CloseButton from './CloseButton';
import PrimaryButton from './PrimaryButton';
import BinIcon from '../assets/BinIcon';
import { adminAuthFetch } from '../lib/adminAuthFetch';
import { getModuleValidationErrors } from '../lib/moduleValidation';

const stableSort = (value) => {
  if (Array.isArray(value)) {
    return value.map((item) => stableSort(item));
  }
  if (value && typeof value === 'object') {
    return Object.keys(value)
      .sort()
      .reduce((acc, key) => {
        acc[key] = stableSort(value[key]);
        return acc;
      }, {});
  }
  return value;
};

const stableSerialize = (value) => JSON.stringify(stableSort(value));


const EditModuleModal = ({ moduleId, module, setModule, onClose, onSave, onDelete }) => {
  const modalMouseDownTarget = useRef(null);
  const initialSnapshotRef = useRef('');
  const trackedModuleIdRef = useRef(null);
  const { moduleTypes } = useModuleTypes();
  const [showValidation, setShowValidation] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [hasUserEdited, setHasUserEdited] = useState(false);

  useEffect(() => {
    if (!moduleId || !module) return;
    if (trackedModuleIdRef.current === moduleId) return;
    trackedModuleIdRef.current = moduleId;
    initialSnapshotRef.current = stableSerialize(module);
    setShowValidation(false);
    setIsSaving(false);
    setHasUserEdited(false);
  }, [moduleId, module]);

  useEffect(() => {
    if (!module || hasUserEdited) return;
    // Some schema widgets normalize defaults on first render; treat that as baseline.
    initialSnapshotRef.current = stableSerialize(module);
  }, [module, hasUserEdited]);

  const validationErrors = useMemo(() => getModuleValidationErrors(module), [module]);

  const isDirty = stableSerialize(module) !== initialSnapshotRef.current;
  const canSave = hasUserEdited && isDirty && !isSaving;

  const handleRequestClose = () => {
    if (isSaving) return;
    if (hasUserEdited && isDirty && !window.confirm('Discard unsaved changes?')) {
      return;
    }
    onClose();
  };

  const handleSave = async () => {
    setShowValidation(true);
    if (!canSave) return;

    try {
      setIsSaving(true);
      await Promise.resolve(onSave(moduleId, module, true));
      initialSnapshotRef.current = stableSerialize(module);
      setHasUserEdited(false);
      onClose();
    } finally {
      setIsSaving(false);
    }
  };

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
          handleRequestClose();
        }
        modalMouseDownTarget.current = null;
      }}>
      <div className={commonClasses.modalContent} onClick={(e) => e.stopPropagation()} role='dialog' aria-modal='true' aria-labelledby='edit-module-title'>
        <div className='flex justify-between items-start mb-6'>
          <div>
            <h3 id='edit-module-title' className='text-xl font-bold text-black mb-1 '>Edit Module</h3>
            <div className={`text-gray-600 text-sm `}>
              <span className="font-mono">Type: {moduleTypes.find((t) => t.id === module?.type)?.label}</span>
            </div>
            {hasUserEdited && isDirty && (
              <div className='mt-2 text-xs font-bold' style={{ color: 'var(--color-brass)' }}>
                Unsaved changes
              </div>
            )}
          </div>
          <CloseButton
            onClick={handleRequestClose}
            ariaLabel='Close edit module dialog'
          />
        </div>

        <div className='mb-6'>
          <label className={commonClasses.label}>Module Name</label>
          <input
            type='text'
            value={module?.name || ''}
            onChange={(e) => {
              setHasUserEdited(true);
              setModule((prev) => (prev ? { ...prev, name: e.target.value } : prev));
            }}
            className={`${commonClasses.input} ${
              showValidation && validationErrors.name ? 'border-red-500' : ''
            }`}
            aria-invalid={Boolean(showValidation && validationErrors.name)}
            aria-describedby={showValidation && validationErrors.name ? 'module-name-error' : undefined}
          />
          {showValidation && validationErrors.name && (
            <p id='module-name-error' className='text-xs mt-1' style={{ color: 'var(--color-error)' }}>
              {validationErrors.name}
            </p>
          )}
        </div>

        {module && (
          <div className='pb-28'>
            <ModuleConfig
              module={module}
              validationErrors={validationErrors}
              showValidation={showValidation}
              onUserInteraction={() => setHasUserEdited(true)}
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
                  const res = await adminAuthFetch('/api/settings');
                  const data = await res.json();
                  const freshModule = data.modules?.[moduleId];
                  if (freshModule) {
                    setModule(freshModule);
                    initialSnapshotRef.current = stableSerialize(freshModule);
                    setShowValidation(false);
                    setHasUserEdited(false);
                  }
                } catch (e) {
                  console.error('Failed to refresh module:', e);
                }
              }}
            />
          </div>
        )}

        <div className='sticky bottom-0 -mx-4 sm:-mx-6 mt-6 px-4 sm:px-6 py-4 border-t-2 border-gray-300 bg-bg-card flex items-center justify-between gap-3'>
          <div className='flex items-center'>
            <button
              type='button'
              onClick={() => onDelete(moduleId)}
              className='px-1 py-1 bg-transparent border-0 rounded-lg transition-all cursor-pointer flex items-center gap-2'
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
          </div>
          <div className='flex items-center'>
            <PrimaryButton
              onClick={handleSave}
              disabled={!canSave}>
              {isSaving ? 'Saving...' : 'Save'}
            </PrimaryButton>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EditModuleModal;
