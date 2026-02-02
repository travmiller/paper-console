import React, { useMemo, useRef, useState } from 'react';
import { INK_GRADIENTS } from '../constants';
import PrimaryButton from './PrimaryButton';

const makeId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`;

const Assistant = ({ settings, setStatus, setSettings, setModules }) => {
  const inkGradients = INK_GRADIENTS;
  const inputRef = useRef(null);

  const telegramConfig = settings?.telegram_bot || {
    ai_provider: 'anthropic',
    ai_api_key: '',
    ai_model: '',
  };

  const isConfigured = useMemo(() => Boolean(telegramConfig.ai_api_key), [telegramConfig.ai_api_key]);

  const [messages, setMessages] = useState([
    {
      id: makeId(),
      role: 'assistant',
      kind: 'text',
      text: 'Ask for a print, a channel, or a module. Nothing is executed until you confirm.',
    },
  ]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);

  const appendMessage = (msg) => setMessages((prev) => [...prev, msg]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isSending) return;

    appendMessage({ id: makeId(), role: 'user', kind: 'text', text });
    setInput('');
    setIsSending(true);

    try {
      const res = await fetch('/api/assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to contact assistant');
      }

      const data = await res.json();
      const type = data?.type || 'message';

      if (type === 'message') {
        appendMessage({
          id: makeId(),
          role: 'assistant',
          kind: 'text',
          text: data.message || '',
        });
      } else {
        appendMessage({
          id: makeId(),
          role: 'assistant',
          kind: 'action',
          action: data,
          state: 'pending', // pending | executing | done | error
          resultText: '',
        });
      }

      setTimeout(() => inputRef.current?.focus(), 0);
    } catch (e) {
      appendMessage({
        id: makeId(),
        role: 'assistant',
        kind: 'text',
        text: `Error: ${e.message}`,
      });
      if (setStatus) setStatus({ type: 'error', message: e.message });
    } finally {
      setIsSending(false);
    }
  };

  const setActionState = (messageId, updates) => {
    setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, ...updates } : m)));
  };

  const confirmAction = async (messageId, action) => {
    if (!action?.type) return;

    setActionState(messageId, { state: 'executing', resultText: '' });

    try {
      if (action.type === 'config_plan') {
        const res = await fetch('/api/assistant/apply-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ operations: action.operations || [] }),
        });

        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || 'Failed to apply config');

        if (setSettings && data.settings) setSettings(data.settings);
        if (setModules && data.modules) setModules(data.modules);

        setActionState(messageId, { state: 'done', resultText: '✅ Applied. Settings updated.' });
        if (setStatus) setStatus({ type: 'success', message: 'Assistant applied configuration.' });
        return;
      }

      const payload = { type: action.type };
      if (action.type === 'print') {
        payload.title = action.title || 'ASSISTANT';
        payload.content = action.content || '';
      } else if (action.type === 'run_channel') {
        payload.channel = action.channel;
      } else if (action.type === 'run_module') {
        payload.module_type = action.module_type;
      }

      const res = await fetch('/api/assistant/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to execute action');
      }

      if (action.type === 'print') {
        const ok = Boolean(data.success);
        setActionState(messageId, {
          state: ok ? 'done' : 'error',
          resultText: ok ? '✅ Done! Check your printer.' : '❌ Print failed. Check printer connection.',
        });
      } else {
        const ok = Boolean(data.success);
        const name = data.name || '';
        setActionState(messageId, {
          state: ok ? 'done' : 'error',
          resultText: ok ? `✅ Printed: ${name}` : `❌ Failed: ${name}`,
        });
      }
    } catch (e) {
      setActionState(messageId, { state: 'error', resultText: `Error: ${e.message}` });
      if (setStatus) setStatus({ type: 'error', message: e.message });
    }
  };

  const renderAssistantMessage = (m) => {
    if (m.kind === 'text') {
      return (
        <div className='text-sm whitespace-pre-wrap' style={{ color: 'var(--color-text-main)' }}>
          {m.text}
        </div>
      );
    }

    const a = m.action || {};
    const type = a.type;

    return (
      <div className='text-sm' style={{ color: 'var(--color-text-main)' }}>
        {type === 'print' && (
          <>
            <div className='font-bold'>Proposed print: {(a.title || 'ASSISTANT').toString()}</div>
            <div className='mt-2 rounded-lg border-2 border-dashed p-3 text-xs whitespace-pre-wrap' style={{ borderColor: 'var(--color-border-main)' }}>
              {(a.content || '').toString()}
            </div>
          </>
        )}

        {type === 'run_channel' && (
          <div className='font-bold'>Proposed action: Run channel {a.channel}</div>
        )}

        {type === 'run_module' && (
          <div className='font-bold'>Proposed action: Run module “{a.module_type}”</div>
        )}

        {type === 'config_plan' && (
          <>
            <div className='font-bold'>Proposed config changes</div>
            {a.summary && (
              <div className='mt-1 text-xs' style={{ color: 'var(--color-text-muted)' }}>
                {a.summary}
              </div>
            )}
            <div
              className='mt-2 rounded-lg border-2 border-dashed p-3 text-xs whitespace-pre-wrap'
              style={{ borderColor: 'var(--color-border-main)' }}>
              {Array.isArray(a.operations) && a.operations.length ? JSON.stringify(a.operations, null, 2) : 'No operations provided.'}
            </div>
          </>
        )}

        <div className='mt-3 flex items-center gap-2'>
          <PrimaryButton
            onClick={() => confirmAction(m.id, a)}
            disabled={m.state !== 'pending' || isSending}
            loading={m.state === 'executing'}>
            {type === 'config_plan' ? 'Confirm Apply' : 'Confirm'}
          </PrimaryButton>
          {m.state === 'pending' && (
            <button
              type='button'
              className='px-4 py-2 border-2 rounded-lg font-bold text-sm transition-all'
              style={{ borderColor: 'var(--color-text-muted)', color: 'var(--color-text-muted)' }}
              onClick={() => setActionState(m.id, { state: 'done', resultText: 'Cancelled.' })}>
              Cancel
            </button>
          )}
        </div>

        {m.resultText && (
          <div className='mt-3 text-xs whitespace-pre-wrap' style={{ color: 'var(--color-text-muted)' }}>
            {m.resultText}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className='rounded-xl p-[4px] shadow-lg' style={{ background: inkGradients[2] || inkGradients[0] }}>
      <div className='bg-bg-card rounded-lg p-4 flex flex-col'>
        <div className='flex items-start justify-between gap-4'>
          <div>
            <h3 className='font-bold text-black text-lg tracking-tight mb-1'>Assistant</h3>
            <p className='text-sm text-gray-600'>
              Uses the same AI provider/key as the Telegram Bot settings. No memory.
            </p>
          </div>
          {!isConfigured && (
            <div className='text-xs px-3 py-2 rounded-lg border-2 border-dashed' style={{ borderColor: 'var(--color-border-main)' }}>
              Configure AI in <span className='font-bold'>General → Telegram Bot</span>
            </div>
          )}
        </div>

        <div className='mt-4 flex flex-col gap-3'>
          {messages.map((m) => (
            <div
              key={m.id}
              className={`rounded-lg border-2 p-3 ${
                m.role === 'user' ? 'bg-white border-gray-300' : 'bg-gray-50 border-gray-300 border-dashed'
              }`}>
              {m.role === 'user' ? (
                <div className='text-sm whitespace-pre-wrap text-black'>{m.text}</div>
              ) : (
                renderAssistantMessage(m)
              )}
            </div>
          ))}
        </div>

        <div className='mt-4 flex gap-2'>
          <input
            ref={inputRef}
            type='text'
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSend();
            }}
            placeholder={isConfigured ? 'Ask for a print…' : 'Configure AI key first…'}
            className='flex-1 w-full p-3 text-base border-2 border-gray-300 rounded-lg focus:outline-none box-border'
            disabled={!isConfigured || isSending}
          />
          <PrimaryButton onClick={handleSend} disabled={!isConfigured || isSending || !input.trim()} loading={isSending}>
            Send
          </PrimaryButton>
        </div>
      </div>
    </div>
  );
};

export default Assistant;
