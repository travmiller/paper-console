import React, { useState } from 'react';
import { commonClasses } from '../../design-tokens';

const KeyValueList = ({ value = {}, onChange }) => {
  // Convert dict to array for editing
  const [items, setItems] = useState(() => {
    return Object.entries(value || {}).map(([key, value]) => ({ key, value }));
  });

  const updateParent = (newItems) => {
      const newDict = {};
      newItems.forEach(item => {
          if (item.key.trim()) {
              newDict[item.key.trim()] = item.value;
          }
      });
      onChange(newDict);
  };

  const handleChange = (index, field, val) => {
    const newItems = [...items];
    newItems[index] = { ...newItems[index], [field]: val };
    setItems(newItems);
    updateParent(newItems);
  };

  const handleAdd = () => {
    setItems([...items, { key: '', value: '' }]);
  };

  const handleRemove = (index) => {
    const newItems = items.filter((_, i) => i !== index);
    setItems(newItems);
    updateParent(newItems);
  };

  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div key={index} className="flex gap-2 items-center">
          <input
            type="text"
            value={item.key}
            onChange={(e) => handleChange(index, 'key', e.target.value)}
            placeholder="Key"
            className={`${commonClasses.inputSmall} flex-1`}
          />
          <input
            type="text"
            value={item.value}
            onChange={(e) => handleChange(index, 'value', e.target.value)}
            placeholder="Value"
            className={`${commonClasses.inputSmall} flex-1`}
          />
          <button
            type="button"
            onClick={() => handleRemove(index)}
            className={`${commonClasses.buttonDanger} flex-shrink-0 px-2`}
          >
            ×
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={handleAdd}
        className={`${commonClasses.buttonGhost} text-xs w-full border-dashed border-2 border-gray-200 py-1`}
      >
        + Add Entry
      </button>
    </div>
  );
};

export default KeyValueList;
