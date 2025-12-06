import { useState, useEffect, useRef } from 'react';

const JsonTextarea = ({ value, onChange, onBlur, className }) => {
  const [text, setText] = useState(JSON.stringify(value || {}, null, 2));
  const [isValid, setIsValid] = useState(true);

  // Update local text when external value changes (but only if we're not focused)
  const textareaRef = useRef(null);
  const isFocused = useRef(false);

  useEffect(() => {
    if (!isFocused.current) {
      setText(JSON.stringify(value || {}, null, 2));
    }
  }, [value]);

  // Parse JSON, treating empty/whitespace as empty object
  const parseJson = (str) => {
    const trimmed = str.trim();
    if (trimmed === '') {
      return {};
    }
    return JSON.parse(trimmed);
  };

  const handleChange = (e) => {
    const newText = e.target.value;
    setText(newText);
    try {
      const parsed = parseJson(newText);
      setIsValid(true);
      onChange(parsed);
    } catch {
      setIsValid(false);
    }
  };

  const handleBlur = (e) => {
    isFocused.current = false;
    try {
      const parsed = parseJson(text);
      setIsValid(true);
      // If empty, also clear the text display
      if (text.trim() === '') {
        setText('{}');
      }
      onBlur(parsed);
    } catch {
      // Reset to valid JSON on blur if invalid
      setText(JSON.stringify(value || {}, null, 2));
      setIsValid(true);
    }
  };

  return (
    <textarea
      ref={textareaRef}
      value={text}
      onChange={handleChange}
      onFocus={() => (isFocused.current = true)}
      onBlur={handleBlur}
      className={`${className} ${!isValid ? 'border-red-500' : ''}`}
    />
  );
};

export default JsonTextarea;
