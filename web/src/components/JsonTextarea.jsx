import { useState } from 'react';

const JsonTextarea = ({ value, onChange, onBlur, className }) => {
  const [text, setText] = useState(JSON.stringify(value || {}, null, 2));
  const [isValid, setIsValid] = useState(true);
  const [isFocused, setIsFocused] = useState(false);
  const externalText = JSON.stringify(value || {}, null, 2);

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

  const handleBlur = () => {
    setIsFocused(false);
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
      value={isFocused ? text : externalText}
      onChange={handleChange}
      onFocus={() => {
        setIsFocused(true);
        setText(externalText);
      }}
      onBlur={handleBlur}
      className={`${className} ${!isValid ? 'border-red-500' : ''}`}
    />
  );
};

export default JsonTextarea;
