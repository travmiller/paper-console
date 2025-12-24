import React from 'react';

/**
 * PrimaryButton - A reusable button component for primary actions
 * 
 * Muted colors that become main colors on hover
 */
const PrimaryButton = ({
  children,
  onClick,
  disabled = false,
  className = '',
  type = 'button',
  loading = false,
  ...props
}) => {
  const baseClasses = 'px-6 py-2 bg-transparent border-2 rounded-lg font-bold transition-all cursor-pointer flex items-center gap-2';
  
  const config = {
    className: `${baseClasses} ${className}`,
    style: { borderColor: 'var(--color-text-muted)', color: 'var(--color-text-muted)' },
    onMouseEnter: (e) => {
      if (!disabled && !loading) {
        e.currentTarget.style.backgroundColor = 'var(--color-bg-white)';
        e.currentTarget.style.borderColor = 'var(--color-border-main)';
        e.currentTarget.style.color = 'var(--color-text-main)';
      }
    },
    onMouseLeave: (e) => {
      if (!disabled && !loading) {
        e.currentTarget.style.backgroundColor = 'transparent';
        e.currentTarget.style.borderColor = 'var(--color-text-muted)';
        e.currentTarget.style.color = 'var(--color-text-muted)';
      }
    },
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={config.className}
      style={config.style}
      onMouseEnter={config.onMouseEnter}
      onMouseLeave={config.onMouseLeave}
      {...props}>
      {loading ? 'Loading...' : children}
    </button>
  );
};

export default PrimaryButton;

