import React, { useState, useEffect } from 'react';
import { commonClasses } from '../design-tokens';
import LocationSearch from './widgets/LocationSearch';
import KeyValueList from './widgets/KeyValueList';

/**
 * A lightweight JSON Schema form renderer.
 * Supports: string, number, boolean, object, array.
 * Supports ui:widget: "textarea", "location-search".
 */
const SchemaForm = ({ schema, uiSchema = {}, formData = {}, onChange }) => {
  if (!schema) return null;

  const handleChange = (path, value) => {
    // Deep clone to avoid direct mutation
    const newFormData = JSON.parse(JSON.stringify(formData));
    
    // Set value at path
    let current = newFormData;
    for (let i = 0; i < path.length - 1; i++) {
        const key = path[i];
        if (current[key] === undefined) {
            // Auto-create missing objects/arrays if needed (simple case)
            current[key] = {}; 
        }
        current = current[key];
    }
    const lastKey = path[path.length - 1];
    current[lastKey] = value;
    
    onChange(newFormData);
  };

  return (
    <div className="space-y-4">
      <SchemaField 
        schema={schema} 
        uiSchema={uiSchema} 
        value={formData} 
        onChange={(val) => onChange(val)} 
        path={[]} 
      />
    </div>
  );
};

const SchemaField = ({ schema, uiSchema, value, onChange, path, label }) => {
    const type = schema.type;
    const title = schema.title || label;
    const description = schema.description;
    
    // Handle UI Options
    const uiOptions = uiSchema?.['ui:options'] || {};
    const widget = uiSchema?.['ui:widget'];

    // 1. OBJECTS
    if (type === 'object') {
        return (
            <div className="space-y-3">
                {title && <h3 className="font-bold text-sm text-gray-700 uppercase tracking-wider">{title}</h3>}
                {description && <p className="text-xs text-gray-500 mb-2">{description}</p>}
                
                {Object.entries(schema.properties || {}).map(([key, propSchema]) => {
                    const propUiSchema = uiSchema?.[key] || {};
                    const propValue = value?.[key];
                    
                    return (
                        <div key={key}>
                            <SchemaField 
                                schema={propSchema}
                                uiSchema={propUiSchema}
                                value={propValue}
                                onChange={(val) => {
                                    const newValue = { ...value, [key]: val };
                                    onChange(newValue);
                                }}
                                path={[...path, key]}
                                label={propSchema.title || key}
                            />
                        </div>
                    );
                })}
            </div>
        );
    }

    // 2. ARRAYS
    if (type === 'array') {
        const items = value || [];
        const itemSchema = schema.items;
        const itemUiSchema = uiSchema?.items || {};
        
        const handleAdd = () => {
            const emptyItem = createEmptyValue(itemSchema);
            onChange([...items, emptyItem]);
        };

        const handleRemove = (index) => {
            const newItems = [...items];
            newItems.splice(index, 1);
            onChange(newItems);
        };

        const handleChangeItem = (index, val) => {
            const newItems = [...items];
            newItems[index] = val;
            onChange(newItems);
        };

        return (
            <div className="space-y-2">
                 <div className="flex justify-between items-center">
                    {title && <label className={commonClasses.label}>{title}</label>}
                </div>
                {description && <p className="text-xs text-gray-500 mb-2">{description}</p>}
                
                <div className="space-y-2">
                    {items.map((item, index) => (
                        <div key={index} className="flex gap-2 items-start p-2 border border-gray-100 rounded bg-gray-50/50">
                             <div className="flex-1">
                                <SchemaField 
                                    schema={itemSchema}
                                    uiSchema={itemUiSchema}
                                    value={item}
                                    onChange={(val) => handleChangeItem(index, val)}
                                    path={[...path, index]}
                                />
                             </div>
                             <button 
                                type="button" 
                                onClick={() => handleRemove(index)}
                                className="text-red-500 hover:text-red-700 px-2 py-1 mt-1 font-bold"
                                title="Remove Item"
                             >
                                ×
                             </button>
                        </div>
                    ))}
                </div>
                
                <button 
                    type="button"
                    onClick={handleAdd}
                    className={`${commonClasses.buttonGhost} text-xs w-full py-2 border-dashed border-2 border-gray-200 hover:border-gray-400`}
                >
                    + Add Item
                </button>
            </div>
        );
    }
    
    // 3. BOOLEANS
    if (type === 'boolean') {
        return (
            <div className="flex items-center gap-2 py-1">
                <input 
                    type="checkbox"
                    checked={value || false}
                    onChange={(e) => onChange(e.target.checked)}
                    className="w-4 h-4 text-amber-600 rounded focus:ring-amber-500 border-gray-300"
                    style={{ accentColor: 'var(--color-brass)' }}
                />
                <label className="text-sm text-gray-700 select-none cursor-pointer" onClick={() => onChange(!value)}>
                    {title}
                </label>
            </div>
        );
    }

    // 4. CUSTOM WIDGETS
    if (widget === 'location-search') {
        return (
            <div className="mb-4">
                {title && <label className={commonClasses.label}>{title}</label>}
                <LocationSearch value={value} onChange={onChange} />
                {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
            </div>
        );
    }
    
    if (widget === 'key-value-list') {
        return (
            <div className="mb-4">
                {title && <label className={commonClasses.label}>{title}</label>}
                <KeyValueList value={value} onChange={onChange} />
                {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
            </div>
        );
    }

    // 5. STRINGS & NUMBERS
    return (
        <div className="mb-2">
            {title && <label className={commonClasses.label}>{title}</label>}
            {widget === 'textarea' ? (
                 <textarea
                    value={value || ''}
                    onChange={(e) => onChange(e.target.value)}
                    className={`${commonClasses.input} min-h-[100px] text-sm`}
                    placeholder={uiSchema?.['ui:placeholder']}
                    rows={uiOptions.rows || 3}
                />
            ) : (
                <input
                    type={type === 'number' || type === 'integer' ? 'number' : 'text'}
                    value={value ?? ''}
                    onChange={(e) => {
                        const val = e.target.value;
                        onChange(type === 'number' || type === 'integer' ? (val === '' ? undefined : parseFloat(val)) : val);
                    }}
                    className={commonClasses.input}
                    placeholder={uiSchema?.['ui:placeholder']}
                />
            )}
             {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
        </div>
    );
};

// Helper: Create empty value based on schema type
const createEmptyValue = (schema) => {
    if (schema.default !== undefined) return schema.default;
    
    switch (schema.type) {
        case 'string': return '';
        case 'number': 
        case 'integer': return 0;
        case 'boolean': return false;
        case 'array': return [];
        case 'object':
            const obj = {};
            if (schema.properties) {
                Object.keys(schema.properties).forEach(key => {
                    obj[key] = createEmptyValue(schema.properties[key]);
                });
            }
            return obj;
        default: return null;
    }
};

export default SchemaForm;
