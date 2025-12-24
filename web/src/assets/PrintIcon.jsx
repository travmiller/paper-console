import React from 'react';

const PrintIcon = ({ className, title = 'print', ...props }) => (
  <svg className={className} height="16" width="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" {...props}>
    <title>{title}</title>
    <g fill="currentColor">
      <polyline fill="none" points="3.5 3.5 3.5 0.5 12.5 0.5 12.5 3.5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M3.5,12.5H.5v-4a3,3,0,0,1,3-3h9a3,3,0,0,1,3,3v4h-3" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />
      <rect height="6" width="9" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x="3.5" y="9.5" />
    </g>
  </svg>
);

export default PrintIcon;

