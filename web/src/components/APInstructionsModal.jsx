import React from 'react';

const APInstructionsModal = ({ show }) => {
  if (!show) return null;

  return (
    <div className='fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4'>
      <div className='bg-white border-4 border-black rounded-xl p-4 sm:p-6 md:p-8 max-w-md w-full text-center shadow-lg'>
        <div className='text-6xl mb-4'>📡</div>
        <h3 className='text-2xl font-bold text-black mb-4'>Setup Mode Activating...</h3>

        <div className='text-left space-y-4 bg-gray-50 p-4 rounded-lg border-2 border-gray-300 mb-6'>
          <div className='flex gap-3'>
            <span
              className='flex-shrink-0 w-6 h-6 rounded-full text-white flex items-center justify-center text-sm font-bold'
              style={{ backgroundColor: 'var(--color-brass)' }}>
              1
            </span>
            <p className='text-black text-sm'>Wait for the printer to print setup instructions.</p>
          </div>
          <div className='flex gap-3'>
            <span
              className='flex-shrink-0 w-6 h-6 rounded-full text-white flex items-center justify-center text-sm font-bold'
              style={{ backgroundColor: 'var(--color-brass)' }}>
              2
            </span>
            <p className='text-black text-sm'>
              Connect your device to the <span className='text-black bg-gray-200 px-1 rounded border border-gray-300'>PC-1-Setup-XXXX</span>{' '}
              WiFi network.
            </p>
          </div>
          <div className='flex gap-3'>
            <span
              className='flex-shrink-0 w-6 h-6 rounded-full text-white flex items-center justify-center text-sm font-bold'
              style={{ backgroundColor: 'var(--color-brass)' }}>
              3
            </span>
            <p className='text-black text-sm'>
              Navigate to <span className='text-black bg-gray-200 px-1 rounded border border-gray-300'>http://10.42.0.1</span> to configure
              WiFi.
            </p>
          </div>
        </div>

        <p className='text-yellow-600 text-xs italic'>Note: This page will stop responding as the device switches networks.</p>
      </div>
    </div>
  );
};

export default APInstructionsModal;
