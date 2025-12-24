import React from 'react';

const CloseButton = ({ onClick, className = '', ...props }) => {
  return (
    <button
      onClick={onClick}
      className={`text-gray-500 hover:text-black text-2xl cursor-pointer hover-shimmer ${className}`}
      type="button"
      {...props}>
      &times;
    </button>
  );
};

export default CloseButton;

