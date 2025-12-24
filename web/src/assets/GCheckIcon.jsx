import React from 'react';

const GCheckIcon = ({ className, title = 'check', ...props }) => (
  <svg className={className} height="16" width="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" {...props}>
    <title>{title}</title>
    <g fill="currentColor">
      <path d="M0.5,7l4,4.5 c0,0,2.5-5.5,11-8.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"/>
    </g>
  </svg>
);

export default GCheckIcon;

