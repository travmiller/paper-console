import React from 'react';

const PreferencesIcon = ({ className, title = 'preferences', ...props }) => (
  <svg className={className} height="16" width="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" {...props}>
    <title>{title}</title>
    <g fill="currentColor">
      <line fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x1="12.5" x2="15.5" y1="12.5" y2="12.5"/>
      <line fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x1="0.5" x2="3.5" y1="3.5" y2="3.5"/>
      <line fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x1="9.5" x2="15.5" y1="3.5" y2="3.5"/>
      <line fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x1="0.5" x2="6.5" y1="12.5" y2="12.5"/>
      <rect height="6" width="3" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x="3.5" y="0.5"/>
      <rect height="6" width="3" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x="9.5" y="9.5"/>
    </g>
  </svg>
);

export default PreferencesIcon;

