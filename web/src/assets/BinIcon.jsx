import React from 'react';

const BinIcon = ({ className, title = 'delete', ...props }) => (
  <svg className={className} height="16" width="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" {...props}>
    <title>{title}</title>
    <g fill="currentColor">
      <path d="M2.5,5.5V14c0,.828,.672,1.5,1.5,1.5H12c.828,0,1.5-.672,1.5-1.5V5.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"/>
      <line fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x1=".5" x2="15.5" y1="3.5" y2="3.5"/>
      <line fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x1="8" x2="8" y1="7.5" y2="12.5"/>
      <line fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x1="10.5" x2="10.5" y1="7.5" y2="12.5"/>
      <line fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x1="5.5" x2="5.5" y1="7.5" y2="12.5"/>
      <polyline fill="none" points="5.5 3.5 5.5 .5 10.5 .5 10.5 3.5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"/>
    </g>
  </svg>
);

export default BinIcon;

