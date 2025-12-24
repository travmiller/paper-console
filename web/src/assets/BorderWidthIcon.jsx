import React from 'react';

const BorderWidthIcon = ({ className, title = 'border width', ...props }) => (
  <svg className={className} height="16" width="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" {...props}>
    <title>{title}</title>
    <g fill="currentColor">
      <rect height="3" width="15" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x=".5" y="2.5"/>
      <rect height="2" width="15" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x=".5" y="8.5"/>
      <line fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x1=".5" x2="15.5" y1="13.5" y2="13.5"/>
    </g>
  </svg>
);

export default BorderWidthIcon;

