import React, { useRef, useEffect } from 'react';
import { commonClasses } from '../../design-tokens';

const ChecklistWidget = ({ value = [], onChange }) => {
  const items = Array.isArray(value) ? value : [];
  const inputRefs = useRef([]);

  const updateItem = (index, field, val) => {
    const newItems = [...items];
    newItems[index] = { ...newItems[index], [field]: val };
    onChange(newItems);
  };

  const addItem = (index) => {
    const newItems = [...items];
    const newItem = { text: '', checked: false };
    newItems.splice(index + 1, 0, newItem);
    onChange(newItems);
    
    // Focus new item on next render
    setTimeout(() => {
        if (inputRefs.current[index + 1]) {
            inputRefs.current[index + 1].focus();
        }
    }, 0);
  };

  const removeItem = (index) => {
    if (items.length <= 1) {
        // Just clear the text of the last item instead of removing it
        updateItem(0, 'text', '');
        return;
    }
    const newItems = items.filter((_, i) => i !== index);
    onChange(newItems);
    
    // Move focus to previous item
    const nextFocusIndex = Math.max(0, index - 1);
    setTimeout(() => {
        if (inputRefs.current[nextFocusIndex]) {
            inputRefs.current[nextFocusIndex].focus();
            // Move cursor to end of text
            const len = inputRefs.current[nextFocusIndex].value.length;
            inputRefs.current[nextFocusIndex].setSelectionRange(len, len);
        }
    }, 0);
  };

  const handleKeyDown = (e, index) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addItem(index);
    } else if (e.key === 'Backspace' && items[index].text === '' && items.length > 1) {
      e.preventDefault();
      removeItem(index);
    } else if (e.key === 'ArrowUp' && index > 0) {
        e.preventDefault();
        inputRefs.current[index - 1].focus();
    } else if (e.key === 'ArrowDown' && index < items.length - 1) {
        e.preventDefault();
        inputRefs.current[index + 1].focus();
    }
  };

  // Ensure there's at least one empty item if list is empty
  useEffect(() => {
    if (items.length === 0) {
        onChange([{ text: '', checked: false }]);
    }
  }, [items.length]);

  return (
    <div className="space-y-1">
      {items.map((item, index) => (
        <div key={index} className="flex items-center gap-3 group px-2 py-1 rounded hover:bg-gray-50 transition-colors">
          <input
            type="checkbox"
            checked={item.checked || false}
            onChange={(e) => updateItem(index, 'checked', e.target.checked)}
            className="w-5 h-5 text-black rounded border-2 border-gray-300 focus:ring-0 cursor-pointer flex-shrink-0"
            style={{ accentColor: 'black' }}
          />
          <input
            ref={el => inputRefs.current[index] = el}
            type="text"
            value={item.text || ''}
            onChange={(e) => updateItem(index, 'text', e.target.value)}
            onKeyDown={(e) => handleKeyDown(e, index)}
            placeholder="New checklist item..."
            className="flex-1 bg-transparent border-none focus:outline-none focus:ring-0 py-1 text-base placeholder-gray-300"
          />
          <button
            type="button"
            onClick={() => removeItem(index)}
            className="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-red-500 transition-all p-1"
            title="Remove Item"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 256 256">
                <path d="M205.66,194.34a8,8,0,0,1-11.32,11.32L128,139.31,61.66,205.66a8,8,0,0,1-11.32-11.32L116.69,128,50.34,61.66A8,8,0,0,1,61.66,50.34L128,116.69l66.34-66.35a8,8,0,0,1,11.32,11.32L139.31,128Z"></path>
            </svg>
          </button>
        </div>
      ))}
      <div className="pt-2">
          <button
            type="button"
            onClick={() => addItem(items.length - 1)}
            className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 px-2"
          >
            <span className="text-sm">+</span> Add another item
          </button>
      </div>
    </div>
  );
};

export default ChecklistWidget;
