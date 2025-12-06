import React from 'react';

const StatusMessage = ({ status }) => {
  if (!status.message) return null;

  return (
    <div
      className={`fixed bottom-8 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-full shadow-xl border text-sm font-medium transition-all transform duration-300 ${
        status.type === 'success'
          ? 'bg-[#1a1a1a] text-gray-200 border-gray-700 shadow-black/50'
          : 'bg-[#1a1a1a] text-red-400 border-red-900/50 shadow-black/50'
      }`}>
      {status.message}
    </div>
  );
};

export default StatusMessage;
