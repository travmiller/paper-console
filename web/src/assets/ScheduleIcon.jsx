import React from 'react';

const ScheduleIcon = ({ className, title = 'schedule', ...props }) => (
  <svg className={className} height="16" width="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" {...props}>
    <title>{title}</title>
    <g fill="currentColor">
      <line fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x1="11.5" x2="15.5" y1="0.5" y2="4.5" />
      <line fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" x1="7" x2="7" y1="5.5" y2="8.5" />
      <circle cx="7" cy="9" fill="none" r="6.5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />
    </g>
  </svg>
);

export default ScheduleIcon;

