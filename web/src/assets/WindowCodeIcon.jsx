import React from 'react';

const WindowCodeIcon = ({ className, title = 'code', ...props }) => (
  <svg className={className} height="16" width="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" {...props}>
    <title>{title}</title>
    <g fill="currentColor">
      <line fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x1="8.5" x2="15.5" y1="13.5" y2="13.5"/>
      <polyline fill="none" points="0.5 1.5 6.5 7.5 0.5 13.5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"/>
    </g>
  </svg>
);

export default WindowCodeIcon;

