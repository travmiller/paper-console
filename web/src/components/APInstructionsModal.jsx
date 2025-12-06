import React from 'react';

const APInstructionsModal = ({ show }) => {
  if (!show) return null;

  return (
    <div className='fixed inset-0 bg-black/90 flex items-center justify-center z-50 p-4'>
      <div className='bg-[#2a2a2a] border border-gray-700 rounded-lg p-4 sm:p-6 md:p-8 max-w-md w-full text-center'>
        <div className='text-6xl mb-4'>📡</div>
        <h3 className='text-2xl font-bold text-white mb-4'>Setup Mode Activating...</h3>

        <div className='text-left space-y-4 bg-[#1a1a1a] p-4 rounded border border-gray-800 mb-6'>
          <div className='flex gap-3'>
            <span className='flex-shrink-0 w-6 h-6 rounded-full bg-blue-900 text-blue-200 flex items-center justify-center text-sm font-bold'>
              1
            </span>
            <p className='text-gray-300 text-sm'>Wait for the printer to print setup instructions.</p>
          </div>
          <div className='flex gap-3'>
            <span className='flex-shrink-0 w-6 h-6 rounded-full bg-blue-900 text-blue-200 flex items-center justify-center text-sm font-bold'>
              2
            </span>
            <p className='text-gray-300 text-sm'>
              Connect your device to the <span className='font-mono text-white bg-black px-1 rounded'>PC-1-Setup-XXXX</span> WiFi network.
            </p>
          </div>
          <div className='flex gap-3'>
            <span className='flex-shrink-0 w-6 h-6 rounded-full bg-blue-900 text-blue-200 flex items-center justify-center text-sm font-bold'>
              3
            </span>
            <p className='text-gray-300 text-sm'>
              Navigate to <span className='font-mono text-white bg-black px-1 rounded'>http://10.42.0.1</span> to configure WiFi.
            </p>
          </div>
        </div>

        <p className='text-yellow-500/80 text-xs italic'>Note: This page will stop responding as the device switches networks.</p>
      </div>
    </div>
  );
};

export default APInstructionsModal;
