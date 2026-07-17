import React, { useState } from 'react';
import GCheckIcon from '../../assets/GCheckIcon';
import WarningIcon from '../../assets/WarningIcon';
import { adminAuthFetch } from '../../lib/adminAuthFetch';

const APP_MANIFEST = {
  display_information: {
    name: 'PC-1 Printer',
    description: 'Print Slack messages on your Paper Console',
    background_color: '#000000',
  },
  features: {
    app_home: {
      messages_tab_enabled: true,
      messages_tab_read_only_enabled: false,
    },
    bot_user: {
      display_name: 'pc1_printer',
      always_online: true,
    },
    slash_commands: [
      {
        command: '/channels',
        description: 'List PC-1 dial channels',
        should_escape: false,
      },
      {
        command: '/channel',
        description: 'Print a PC-1 channel',
        usage_hint: '[1-8]',
        should_escape: false,
      },
    ],
  },
  oauth_config: {
    scopes: {
      bot: ['chat:write', 'im:history', 'reactions:write', 'users:read', 'files:read'],
    },
  },
  settings: {
    event_subscriptions: {
      bot_events: ['message.im'],
    },
    org_deploy_enabled: false,
    socket_mode_enabled: true,
    token_rotation_enabled: false,
  },
};

const MANIFEST_JSON = JSON.stringify(APP_MANIFEST, null, 2);

const SETUP_STEPS = [
  <>
    Copy the app manifest below, then go to{' '}
    <a
      href="https://api.slack.com/apps"
      target="_blank"
      rel="noreferrer"
      className="underline"
    >
      api.slack.com/apps
    </a>{' '}
    → <strong>Create New App</strong> → <strong>From a manifest</strong>. Pick
    your workspace, paste the manifest (JSON tab), and create the app. This
    configures all permissions, events, and slash commands automatically.
  </>,
  <>
    Under <strong>Basic Information → App-Level Tokens</strong>, click{' '}
    <strong>Generate Token and Scopes</strong>, add the{' '}
    <code className="bg-white px-1 py-0.5 rounded">connections:write</code>{' '}
    scope, and generate. Paste the token (xapp-...) into the App-Level Token
    field above.
  </>,
  <>
    Under <strong>Install App</strong> (or the banner at the top), install the
    app to your workspace, then copy the Bot User OAuth Token (xoxb-...) into
    the field above.
  </>,
  <>
    In Slack, open the app's <strong>Messages</strong> tab (find it under Apps,
    or press Cmd/Ctrl+K and search for the bot) and send it a DM. Text, links,
    and images all print. Links print as QR codes, and{' '}
    <code className="bg-white px-1 py-0.5 rounded">/channel 3</code> prints
    dial channel 3.
  </>,
];

/**
 * Setup walkthrough + connection test for the Slack module.
 * Used in SchemaForm with ui:widget: "slack-help".
 */
const SlackHelp = ({ rootValue = {} }) => {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const [showSetup, setShowSetup] = useState(false);

  const botToken = String(rootValue.bot_token || '').trim();
  const appToken = String(rootValue.app_token || '').trim();

  const copyManifest = async () => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(MANIFEST_JSON);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = MANIFEST_JSON;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch (error) {
      console.error('Failed to copy Slack app manifest:', error);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setResult(null);
    try {
      const response = await adminAuthFetch('/api/slack/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot_token: botToken, app_token: appToken }),
      });
      const data = await response.json();
      setResult(data);
    } catch (err) {
      setResult({ ok: false, error: err.message });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="mb-4 space-y-3">
      <div className="space-y-3">
        <button
          type="button"
          onClick={handleTest}
          disabled={testing || !botToken || !appToken}
          className="text-sm px-3 py-1.5 border-2 border-gray-300 rounded-lg hover:border-black disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {testing ? (
            <span className="flex items-center gap-2">
              <span className="w-3 h-3 border-2 border-black border-t-transparent rounded-full animate-spin"></span>
              Testing...
            </span>
          ) : (
            'Test Connection'
          )}
        </button>

        {result && (
          <div
            className={`p-3 rounded-lg text-sm border-2 ${
              result.ok ? 'bg-gray-50 border-gray-300' : 'bg-white border-black border-dashed'
            }`}
          >
            {result.ok ? (
              <div className="flex items-center gap-2 text-black font-bold">
                <GCheckIcon className="w-4 h-4" />
                <span>
                  Connected to {result.team || 'workspace'}
                  {result.bot ? ` as @${result.bot}` : ''}
                </span>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-2 text-black font-bold mb-1">
                  <WarningIcon className="w-4 h-4" />
                  <span>Connection failed</span>
                </div>
                <div className="text-gray-600 text-xs">{result.error}</div>
              </>
            )}
          </div>
        )}
      </div>

      <p className="text-xs text-gray-500 leading-5">
        Pressing the print button on a channel with this module prints a
        connection status receipt.
      </p>

      <button
        type="button"
        onClick={() => setShowSetup((open) => !open)}
        className="text-sm px-3 py-1.5 border-2 border-gray-300 rounded-lg hover:border-black transition-colors"
      >
        {showSetup ? 'Hide setup instructions' : 'How to connect Slack'}
      </button>

      {showSetup && (
        <div className="rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 p-4 space-y-2">
          <div className="text-sm font-bold text-black">How to connect Slack</div>
          <ol className="list-decimal pl-4 space-y-2">
            {SETUP_STEPS.map((step, idx) => (
              <li key={idx} className="text-xs text-gray-600 leading-5">
                {step}
              </li>
            ))}
          </ol>

          <div className="space-y-1 pt-1">
            <div className="flex items-center justify-between gap-2">
              <div className="text-xs font-bold text-black uppercase tracking-wide">App Manifest</div>
              <button
                type="button"
                onClick={copyManifest}
                className="text-xs px-2 py-1 border-2 border-gray-300 rounded-lg hover:border-black transition-colors"
              >
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <pre className="overflow-x-auto rounded border border-gray-200 bg-white p-3 text-[11px] leading-4 text-gray-700 whitespace-pre max-h-48 overflow-y-auto">
              {MANIFEST_JSON}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};

export default SlackHelp;
