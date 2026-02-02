import React from 'react';

const ChatIcon = ({ className, title = 'assistant', ...props }) => (
  <svg className={className} height='16' width='16' viewBox='0 0 16 16' xmlns='http://www.w3.org/2000/svg' {...props}>
    <title>{title}</title>
    <g fill='currentColor'>
      <path
        d='M13.5,2.5h-11c-1.105,0-2,.895-2,2v5c0,1.105,.895,2,2,2h2.5l2.5,2.5v-2.5h6c1.105,0,2-.895,2-2v-5c0-1.105-.895-2-2-2Z'
        fill='none'
        stroke='currentColor'
        strokeLinecap='round'
        strokeLinejoin='round'
      />
      <circle cx='5.5' cy='7' r='0.75' />
      <circle cx='8' cy='7' r='0.75' />
      <circle cx='10.5' cy='7' r='0.75' />
    </g>
  </svg>
);

export default ChatIcon;

