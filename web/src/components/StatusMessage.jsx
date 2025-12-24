import React from 'react';

const StatusMessage = ({ status }) => {
  if (!status.message) return null;

  return (
    <div
      className={`fixed bottom-8 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-full shadow-xl text-sm font-medium transition-all transform duration-300 ${
        status.type === 'success'
          ? 'text-gray-200 shadow-black/50'
          : 'text-red-400 shadow-black/50'
      }`}
      style={{ backgroundColor: 'var(--color-bg-dark)' }}>
      {status.message}
    </div>
  );
};

export default StatusMessage;
