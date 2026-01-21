import React, { useState } from 'react';
import { commonClasses } from '../../design-tokens';

/**
 * ActionButton widget for schema forms.
 * 
 * Renders a button that triggers a module action via the API.
 * 
 * UI Options:
 * - action: The action name to call (e.g., "reset")
 * - label: Button text (default: field title)
 * - confirmMessage: Optional confirmation prompt
 * - style: "primary" | "danger" | "ghost" (default: "primary")
 */
const ActionButton = ({ 
    value, 
    onChange, 
    schema, 
    uiSchema = {},
    moduleId 
}) => {
    const [loading, setLoading] = useState(false);
    const [status, setStatus] = useState(null); // 'success' | 'error' | null
    
    const options = uiSchema['ui:options'] || {};
    const action = options.action || 'default';
    const label = options.label || schema?.title || 'Action';
    const confirmMessage = options.confirmMessage;
    const style = options.style || 'primary';
    
    const handleClick = async () => {
        // Confirmation dialog
        if (confirmMessage && !window.confirm(confirmMessage)) {
            return;
        }
        
        if (!moduleId) {
            console.error('ActionButton: moduleId is required');
            setStatus('error');
            return;
        }
        
        setLoading(true);
        setStatus(null);
        
        try {
            const response = await fetch(`/api/modules/${moduleId}/actions/${action}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            
            if (response.ok) {
                const data = await response.json();
                setStatus('success');
                
                // Reload the page if action requires it
                if (data.reload) {
                    setTimeout(() => window.location.reload(), 500);
                } else {
                    setTimeout(() => setStatus(null), 2000);
                }
            } else {
                setStatus('error');
            }
        } catch (error) {
            console.error('ActionButton error:', error);
            setStatus('error');
        } finally {
            setLoading(false);
        }
    };
    
    // Determine button classes based on style
    let buttonClass = commonClasses.buttonPrimary;
    if (style === 'danger') {
        buttonClass = 'px-4 py-2 rounded-lg font-medium bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50';
    } else if (style === 'ghost') {
        buttonClass = commonClasses.buttonGhost;
    } else if (style === 'link') {
        buttonClass = 'text-blue-600 hover:text-blue-800 underline text-sm font-medium disabled:opacity-50';
    }
    
    return (
        <div className="mb-4">
            <button
                type="button"
                onClick={handleClick}
                disabled={loading}
                className={buttonClass}
            >
                {loading ? 'Processing...' : label}
            </button>
            
            {status === 'success' && (
                <span className="ml-3 text-green-600 text-sm">✓ Done</span>
            )}
            {status === 'error' && (
                <span className="ml-3 text-red-600 text-sm">✗ Failed</span>
            )}
        </div>
    );
};

export default ActionButton;
