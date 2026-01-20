import React, { useState } from 'react';
import { commonClasses } from '../../design-tokens';
import GCheckIcon from '../../assets/GCheckIcon';
import WarningIcon from '../../assets/WarningIcon';

/**
 * A button widget that tests a webhook configuration and shows the response.
 * Used in SchemaForm with ui:widget: "webhook-test".
 */
const WebhookTest = ({ formData = {} }) => {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState(null);

  const handleTest = async () => {
    setTesting(true);
    setResult(null);

    try {
      const response = await fetch('/api/webhook/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      const data = await response.json();
      setResult(data);
    } catch (err) {
      setResult({ success: false, error: err.message });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={handleTest}
        disabled={testing || !formData.url}
        className="text-sm px-3 py-1.5 border-2 border-gray-300 rounded-lg hover:border-black disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {testing ? (
          <span className="flex items-center gap-2">
            <span className="w-3 h-3 border-2 border-black border-t-transparent rounded-full animate-spin"></span>
            Testing...
          </span>
        ) : (
          'Test Webhook'
        )}
      </button>

      {result && (
        <div className={`p-3 rounded-lg text-sm border-2 ${
          result.success 
            ? 'bg-gray-50 border-gray-300' 
            : 'bg-white border-black border-dashed'
        }`}>
          {result.success ? (
            <>
              <div className="flex items-center gap-2 text-black font-bold mb-2">
                <GCheckIcon className="w-4 h-4" />
                <span>Success</span>
                {result.status_code && (
                  <span className="text-xs text-gray-500 font-normal">(HTTP {result.status_code})</span>
                )}
              </div>
              {result.json_path && (
                <div className="text-xs text-gray-500 mb-1">
                  Extracted from: <code className="bg-gray-200 px-1 rounded">{result.json_path}</code>
                </div>
              )}
              <div className="bg-white border border-gray-200 rounded p-2 font-mono text-xs whitespace-pre-wrap break-words max-h-32 overflow-y-auto">
                {result.content}
              </div>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2 text-black font-bold mb-2">
                <WarningIcon className="w-4 h-4" />
                <span>Error</span>
              </div>
              <div className="text-gray-600 text-xs">
                {result.error}
              </div>
              {result.raw_response && (
                <details className="mt-2">
                  <summary className="text-xs text-gray-500 cursor-pointer">Show raw response</summary>
                  <div className="bg-gray-100 border border-gray-200 rounded p-2 font-mono text-xs whitespace-pre-wrap break-words max-h-32 overflow-y-auto mt-1">
                    {result.raw_response}
                  </div>
                </details>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default WebhookTest;
