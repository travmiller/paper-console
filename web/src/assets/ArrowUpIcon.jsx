import React from 'react';

const ArrowUpIcon = ({ className, title = 'arrow up', ...props }) => (
  <svg className={className} height="16" width="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" {...props}>
    <title>{title}</title>
    <g fill="currentColor">
      <polyline fill="none" points="15.5,10.5 8,5.5 0.5,10.5 " stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />
    </g>
  </svg>
);

export default ArrowUpIcon;

