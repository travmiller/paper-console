import React from 'react';
import { commonClasses } from '../../design-tokens';

/**
 * A dropdown widget for selecting presets that prefill form fields.
 * Used in SchemaForm with ui:widget: "preset-select".
 * 
 * Props:
 *   - value: current preset key (e.g., "dad_jokes")
 *   - onChange: function to update form data
 *   - presets: object mapping preset keys to their configurations
 *   - onPresetSelect: callback to apply preset values to the parent form
 */
const PresetSelect = ({ value, onChange, presets = {}, onPresetSelect }) => {
  const handleChange = (e) => {
    const presetKey = e.target.value;
    onChange(presetKey);
    
    // If a preset is selected and we have a callback, apply its values
    if (presetKey && presets[presetKey] && onPresetSelect) {
      const preset = presets[presetKey];
      
      // If the preset has a 'values' property, use that.
      // Otherwise, use the whole preset object (excluding meta properties like label).
      let valuesToApply = {};
      
      if (preset.values) {
        valuesToApply = preset.values;
      } else {
        // Exclude UI-only properties
        const { label, ...rest } = preset;
        valuesToApply = rest;
      }
      
      onPresetSelect(valuesToApply);
    }
  };

  return (
    <select
      value={value || 'custom'}
      onChange={handleChange}
      className={commonClasses.input}
    >
      {Object.entries(presets).map(([key, preset]) => (
        <option key={key} value={key}>
          {preset.label || key}
        </option>
      ))}
    </select>
  );
};

export default PresetSelect;
