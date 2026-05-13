import React, { useMemo, useRef, useState } from 'react';
import cronstrue from 'cronstrue';
import {
  cronToReadable,
  validateCronExpression,
} from '../utils';
import CloseButton from './CloseButton';
import PrimaryButton from './PrimaryButton';

const ScheduleModal = ({ position, channel, onClose, onUpdate, timeFormat, timezone }) => {
  const modalMouseDownTarget = useRef(null);
  const [cronInput, setCronInput] = useState('* * * * *');
  const [quickDailyTime, setQuickDailyTime] = useState('');
  const [error, setError] = useState('');
  const scheduleTimezone = timezone || 'UTC';

  const formatCronDescription = (expression) => {
    if (!validateCronExpression(expression)) {
      return `Cron: ${expression} (${scheduleTimezone})`;
    }

    try {
      return `${cronstrue.toString(expression)} (${scheduleTimezone})`;
    } catch {
      return cronToReadable(expression, scheduleTimezone, timeFormat);
    }
  };

  const scheduleRules = useMemo(() => {
    if (channel?.schedule_rules?.length) {
      return channel.schedule_rules;
    }

    if (!channel?.schedule?.length) {
      return [];
    }

    return channel.schedule
      .map((hhmm) => {
        const [hour, minute] = String(hhmm).split(':');
        if (!hour || !minute) return null;
        return {
          expression: `${Number(minute)} ${Number(hour)} * * *`,
          timezone: scheduleTimezone,
          enabled: true,
          description: formatCronDescription(`${Number(minute)} ${Number(hour)} * * *`),
        };
      })
      .filter(Boolean);
  }, [channel, scheduleTimezone, timeFormat]);

  if (position === null) return null;

  const commitRules = (rules) => {
    const normalizedRules = rules.map((rule) => {
      const expression = String(rule.expression || rule.cron || '').trim();
      return {
        ...rule,
        expression,
        timezone: scheduleTimezone,
        description: formatCronDescription(expression),
      };
    });

    onUpdate({ rules: normalizedRules });
  };

  return (
    <div
      className='fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4'
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) {
          modalMouseDownTarget.current = 'backdrop';
        }
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && modalMouseDownTarget.current === 'backdrop') {
          onClose();
        }
        modalMouseDownTarget.current = null;
      }}>
      <div className='border-4 rounded-xl p-4 sm:p-6 max-w-xl w-full shadow-lg' style={{ backgroundColor: 'var(--color-bg-card)', borderColor: 'var(--color-border-main)' }} onClick={(e) => e.stopPropagation()}>
        <div className='flex justify-between items-center mb-6'>
          <h3 className='text-xl font-bold text-black '>Schedule Channel {position}</h3>
          <CloseButton onClick={onClose} />
        </div>

        <div className='space-y-4'>
          <div className='text-sm text-gray-600'>
            Use <a href="https://crontab.guru/" target="_blank" rel="noopener noreferrer" className="underline text-blue-600 hover:text-blue-800">cron rules</a> to define when this channel should automatically print. Schedules use the timezone from General Settings.
          </div>

          <div className='text-sm text-gray-600'>
            All schedules run in the system timezone: <span className='font-mono text-black'>{scheduleTimezone}</span>
          </div>

          <div className='space-y-2 max-h-[280px] overflow-y-auto'>
            {scheduleRules.map((rule, idx) => {
              const expression = String(rule.expression || rule.cron || '').trim();
              const readable = formatCronDescription(expression);
              return (
                <div key={`${expression}-${idx}`} className='p-3 rounded-lg border-2 border-gray-300 hover:border-black' style={{ backgroundColor: 'var(--color-bg-card)' }}>
                  <div className='flex items-center justify-between gap-3'>
                    <div className='flex-1 min-w-0'>
                      <div className='text-sm font-mono text-black break-all'>{expression}</div>
                      <div className='text-xs text-gray-600 mt-1'>{readable}</div>
                    </div>
                    <button
                      onClick={() => {
                        const newRules = [...scheduleRules];
                        newRules.splice(idx, 1);
                        commitRules(newRules);
                      }}
                      className='text-red-600 hover:text-red-700 px-2 font-bold cursor-pointer hover-shimmer'
                      aria-label='Remove schedule rule'>
                      &times;
                    </button>
                  </div>
                </div>
              );
            })}

            {scheduleRules.length === 0 && (
              <div className='text-gray-500 text-center py-4 italic '>No schedule rules yet.</div>
            )}
          </div>

          <div className='pt-4 border-t-2 border-gray-300'>
            <pre className='font-mono text-xs text-gray-600 mb-4 overflow-x-auto'>
{`  ┌───────────── minute   (0-59)
  │  ┌────────── hour     (0-23)
  │  │  ┌─────── day      (1-31)
  │  │  │  ┌──── month    (1-12)
  │  │  │  │  ┌─ weekday  (0-6, MON-SUN)
  │  │  │  │  │
  *  *  *  *  *`}
            </pre>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                const expression = cronInput.trim();
                
                // Clear previous errors
                setError('');
                
                // Validate cron expression format
                if (!expression) {
                  setError('Cron expression is required (e.g., "54 13 * * *" for 1:54 PM daily)');
                  return;
                }

                if (!validateCronExpression(expression)) {
                  const fieldCount = expression.split(/\s+/).length;

                  if (fieldCount !== 5) {
                    setError(`Cron needs exactly 5 fields (minute hour day month weekday). Found ${fieldCount}. Format: "minute hour day month weekday"`);
                  } else {
                    setError('Invalid cron expression. Check field values: minute (0-59), hour (0-23), day (1-31), month (1-12), weekday (0-6 or MON-SUN)');
                  }
                  return;
                }

                // Check for duplicates
                const dedupe = scheduleRules.some(
                  (existing) => String(existing.expression || existing.cron || '').trim() === expression,
                );
                if (dedupe) {
                  setError('This cron rule already exists for this channel.');
                  return;
                }

                // All validation passed - add the rule
                const newRule = {
                  expression,
                  timezone: scheduleTimezone,
                  enabled: true,
                  description: formatCronDescription(expression),
                };

                setCronInput('');
                commitRules([...scheduleRules, newRule]);
              }}
              className='space-y-3'>
              <div className='space-y-0.5'>
                <input
                  name='cronInput'
                  value={cronInput}
                  onChange={(e) => {
                    setCronInput(e.target.value);
                    if (error) setError('');
                  }}
                  placeholder='54 13 * * *'
                  required
                  className='w-full border-2 border-gray-300 rounded-lg px-3 py-2 text-black focus:outline-none focus:border-black font-mono'
                  style={{ backgroundColor: 'var(--color-bg-card)' }}
                />

                {cronInput.trim() && (
                  <div className='text-xs text-gray-600 italic px-1'>
                    {!validateCronExpression(cronInput.trim()) 
                      ? 'Invalid cron expression' 
                      : cronstrue.toString(cronInput.trim())}
                  </div>
                )}
              </div>

              <div className='grid grid-cols-1 sm:grid-cols-[auto_1fr] items-end gap-3'>
                <PrimaryButton type='submit' className='w-full sm:w-auto'>Add Cron Rule</PrimaryButton>
                <div className='justify-self-end w-full sm:w-44'>
                  <label className='text-[11px] text-gray-500 font-semibold'>Quick daily time</label>
                  <input
                    type='time'
                    value={quickDailyTime}
                    className='mt-1 w-full border border-gray-300 rounded-md px-2 py-1 text-sm text-black focus:outline-none focus:border-black'
                    onChange={(e) => {
                      const hhmm = e.target.value;
                      setQuickDailyTime(hhmm);
                      if (!hhmm) return;
                      const [hour, minute] = hhmm.split(':');
                      const cron = `${Number(minute)} ${Number(hour)} * * *`;
                      setCronInput(cron);
                    }}
                  />
                </div>
              </div>

              {error && (
                <div className='p-3 rounded-lg border-2 border-red-400 bg-red-50'>
                  <div className='text-sm text-red-700 font-semibold'>Validation Error</div>
                  <div className='text-xs text-red-600 mt-1'>{error}</div>
                </div>
              )}
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ScheduleModal;
