import { useState } from 'react';

export default function SettingsLogin({ authInfo, onLogin, isSubmitting = false, error = '' }) {
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(true);

  const inputClass = 'w-full p-3 text-base bg-white border-2 border-gray-300 rounded-lg text-black focus:border-black focus:outline-none box-border';
  const buttonClass = 'w-full py-3 px-4 rounded-lg font-bold transition-all bg-transparent border-2 border-black text-black hover:bg-black hover:text-white disabled:opacity-50 disabled:cursor-not-allowed disabled:border-gray-300 disabled:text-gray-400 cursor-pointer';

  const submit = async (event) => {
    event.preventDefault();
    const trimmed = password.trim();
    if (!trimmed) return;
    await onLogin(trimmed, remember);
  };

  return (
    <div className='max-w-[480px] w-full mx-auto px-2 pt-4 pb-12 sm:px-6 sm:pt-8 sm:pb-16 min-h-screen'>
      <div className='mb-8 pt-4 pb-2'>
        <h1 className='text-3xl sm:text-4xl leading-none font-bold tracking-tighter' style={{ color: 'var(--color-text-main)' }}>
          PC-1 SETTINGS
        </h1>
      </div>

      <div
        className='border-4 rounded-xl p-5 shadow-lg'
        style={{
          backgroundColor: 'var(--color-bg-card)',
          borderColor: 'var(--color-border-main)',
          color: 'var(--color-text-main)',
        }}>
        <h2 className='text-lg font-bold mb-2'>Unlock Settings</h2>
        <p className='text-sm mb-4' style={{ color: 'var(--color-text-muted)' }}>
          {authInfo?.message || 'Enter your Device Password to access settings.'}
        </p>

        <form onSubmit={submit} className='space-y-4'>
          <div>
            <label className='block mb-2 font-bold text-sm'>
              {authInfo?.password_label || 'Device Password'}
            </label>
            <input
              type='password'
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={inputClass}
              autoComplete='current-password'
              placeholder='Enter password'
              disabled={isSubmitting}
            />
          </div>

          <label className='flex items-start gap-3 text-sm cursor-pointer'>
            <input
              type='checkbox'
              className='mt-1'
              checked={remember}
              onChange={(event) => setRemember(event.target.checked)}
              disabled={isSubmitting}
            />
            <span style={{ color: 'var(--color-text-muted)' }}>
              Remember this browser for 1 year with a secure session cookie.
            </span>
          </label>

          {authInfo?.password_help && (
            <p className='text-xs' style={{ color: 'var(--color-text-muted)' }}>
              {authInfo.password_help}
            </p>
          )}

          {error && (
            <div className='border-2 border-red-500 text-red-600 rounded-lg px-4 py-3 text-sm'>
              {error}
            </div>
          )}

          <button type='submit' disabled={isSubmitting || !password.trim()} className={buttonClass}>
            {isSubmitting ? 'Unlocking...' : 'Unlock Settings'}
          </button>
        </form>
      </div>
    </div>
  );
}
