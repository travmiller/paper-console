import React from 'react';
import { commonClasses } from '../design-tokens';
import LocationSearch from './widgets/LocationSearch';
import KeyValueList from './widgets/KeyValueList';
import PresetSelect from './widgets/PresetSelect';
import WebhookTest from './widgets/WebhookTest';
import ActionButton from './widgets/ActionButton';
import RichTextEditor from './widgets/RichTextEditor';
import ImageWidget from './widgets/ImageWidget';
import { generatePrintWebhookToken, normalizePrintWebhookEndpointPath } from '../utils';

const copyToClipboard = async (text) => {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  if (typeof document === 'undefined') {
    throw new Error('Clipboard is unavailable');
  }

  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  textarea.style.pointerEvents = 'none';
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();

  try {
    const copied = document.execCommand('copy');
    if (!copied) {
      throw new Error('document.execCommand("copy") returned false');
    }
  } finally {
    document.body.removeChild(textarea);
  }
};

const resolveFieldDescription = ({ description, fieldPath, rootValue }) => {
  if (!description) return description;

  if (fieldPath === 'endpoint_path' && description.includes('/hook/<endpoint_path>')) {
    const endpointPath =
      normalizePrintWebhookEndpointPath(rootValue?.endpoint_path) || 'your-endpoint';
    return description.replace('/hook/<endpoint_path>', `/hook/${endpointPath}`);
  }

  return description;
};

const PrintWebhookHelp = ({ rootValue = {} }) => {
  const [copiedLabel, setCopiedLabel] = React.useState('');
  const endpointPath =
    normalizePrintWebhookEndpointPath(rootValue.endpoint_path) || 'your-endpoint';
  const token = rootValue.token || '';
  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://pc-1.local';
  const endpointUrl = `${origin}/hook/${endpointPath}`;
  const authHeader = token
    ? `-H 'Authorization: Bearer YOUR_TOKEN_HERE' \\\n`
    : '';
  const authNote = token
    ? "Auth enabled: send the bearer token in the Authorization header."
    : "Auth disabled: leave out the Authorization header.";
  const jsonExample = `curl -X POST '${endpointUrl}' \\
${authHeader}-H 'Content-Type: application/json' \\
-d '{
  "title": "Front Door",
  "subtitle": "Motion detected",
  "items": [
    { "type": "text", "text": "Someone is at the front door." },
    { "type": "image_url", "url": "https://example.com/snapshot.jpg" }
  ]
}'`;
  const textExample = `curl -X POST '${endpointUrl}' \\
${authHeader}-H 'Content-Type: text/plain' \\
--data 'Package delivered at the front door.'`;
  const imageExample = `curl -X POST '${endpointUrl}' \\
${authHeader}-H 'Content-Type: image/png' \\
--data-binary @snapshot.png`;

  const copyText = async (label, text) => {
    try {
      await copyToClipboard(text);
      setCopiedLabel(label);
      window.setTimeout(() => {
        setCopiedLabel((current) => (current === label ? '' : current));
      }, 1200);
    } catch (error) {
      console.error('Failed to copy print endpoint example:', error);
    }
  };

  return (
    <div className="mb-4 rounded-lg border-2 border-dashed border-zinc-300 bg-zinc-50 p-4 space-y-3">
      <div>
        <div className="text-sm font-bold text-black">How to send to this print endpoint</div>
        <p className="text-xs text-zinc-600 mt-1">
          POST to <code className="bg-white px-1 py-0.5 rounded">{endpointUrl}</code>
        </p>
        <p className="text-xs text-zinc-600 mt-1">{authNote}</p>
        {token ? (
          <p className="text-xs text-zinc-600 mt-1">
            Header format: <code className="bg-white px-1 py-0.5 rounded">Authorization: Bearer YOUR_TOKEN_HERE</code>
          </p>
        ) : null}
      </div>

      <div className="space-y-3">
        {[
          { label: 'JSON Print Job', value: jsonExample },
          { label: 'Plain Text', value: textExample },
          { label: 'Raw Image', value: imageExample },
        ].map((example) => (
          <div key={example.label} className="space-y-1">
            <div className="flex items-center justify-between gap-2">
              <div className="text-xs font-bold text-black uppercase tracking-wide">{example.label}</div>
              <button
                type="button"
                onClick={() => copyText(example.label, example.value)}
                className={commonClasses.buttonGhost}
              >
                {copiedLabel === example.label ? 'Copied' : 'Copy'}
              </button>
            </div>
            <pre className="overflow-x-auto rounded border border-zinc-200 bg-white p-3 text-[11px] leading-5 text-zinc-700 whitespace-pre-wrap">
              {example.value}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
};

const AdvancedSection = ({
  title = 'Advanced',
  description = '',
  fields = [],
  parentSchema,
  parentUiSchema = {},
  parentValue,
  parentPath,
  parentRequired = [],
  rootValue,
  onRootChange,
  moduleId,
  moduleType,
  onActionComplete,
  validationErrors = {},
  showValidation = false,
  onUserInteraction = () => {},
}) => {
  const validFields = fields.filter((field) => parentSchema?.properties?.[field]);
  if (validFields.length === 0) {
    return null;
  }

  return (
    <details className="mb-6 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3">
      <summary className="cursor-pointer select-none list-none">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-bold text-black">{title}</div>
          <div className="text-xs text-zinc-400 uppercase tracking-wide">Show</div>
        </div>
        {description ? (
          <p className="mt-1 pr-8 text-xs leading-4 text-zinc-500">{description}</p>
        ) : null}
      </summary>
      <div className="mt-4">
        {validFields.map((field) => {
          const fieldSchema = parentSchema.properties[field];
          const fieldUiSchema = parentUiSchema?.[field] || {};
          const fieldValue = parentValue?.[field];

          return (
            <SchemaField
              key={field}
              schema={fieldSchema}
              uiSchema={fieldUiSchema}
              value={fieldValue}
              onChange={(val) => {
                onUserInteraction();
                onRootChange({
                  ...rootValue,
                  [field]: val,
                });
              }}
              path={[...parentPath, field]}
              label={fieldSchema.title || field}
              required={parentRequired.includes(field)}
              rootValue={rootValue}
              onRootChange={onRootChange}
              moduleId={moduleId}
              moduleType={moduleType}
              onActionComplete={onActionComplete}
              validationErrors={validationErrors}
              showValidation={showValidation}
              onUserInteraction={onUserInteraction}
            />
          );
        })}
      </div>
    </details>
  );
};

const FieldHeading = ({
  title,
  required = false,
  compact = false,
  description = '',
  action = null,
}) => {
  if (!title && !description && !action) {
    return null;
  }

  return (
    <div className={compact ? 'mb-1.5 space-y-0' : 'mb-2 space-y-0'}>
      {(title || action) ? (
        <div className="flex justify-between items-center gap-2">
          {title ? (
            <label
              className={`${compact ? commonClasses.labelSmall : commonClasses.label} leading-tight`}
            >
              {title} {required && <span className="text-red-500 ml-1" title="Required">*</span>}
            </label>
          ) : <div />}
          {action}
        </div>
      ) : null}
      {description ? (
        <p className="text-xs leading-4 text-zinc-500">{description}</p>
      ) : null}
    </div>
  );
};

/**
 * A lightweight JSON Schema form renderer.
 * Supports: string, number, boolean, object, array.
 * Supports ui:widget: "textarea", "location-search".
 */
const SchemaForm = ({
  schema,
  uiSchema = {},
  formData = {},
  onChange,
  suppressRootDescription = false,
  moduleId,
  moduleType,
  onActionComplete,
  validationErrors = {},
  showValidation = false,
  onUserInteraction = () => {},
}) => {
  if (!schema) return null;

  return (
    <div>
      <SchemaField 
        schema={schema} 
        uiSchema={uiSchema} 
        value={formData} 
        onChange={(val) => onChange(val)} 
        path={[]} 
        suppressRootDescription={suppressRootDescription}
        rootValue={formData}
        onRootChange={onChange}
        moduleId={moduleId}
        moduleType={moduleType}
        onActionComplete={onActionComplete}
        validationErrors={validationErrors}
        showValidation={showValidation}
        onUserInteraction={onUserInteraction}
      />
    </div>
  );
};

const SchemaField = ({
  schema,
  uiSchema,
  value,
  onChange,
  path,
  suppressRootDescription = false,
  label,
  required,
  compact,
  rootValue,
  onRootChange,
  moduleId,
  moduleType,
  onActionComplete,
  validationErrors = {},
  showValidation = false,
  onUserInteraction = () => {},
}) => {
    const type = schema.type;
    const title = schema.title || label;
    const fieldPath = path.join('.');
    const description = resolveFieldDescription({
        description: schema.description,
        fieldPath,
        rootValue,
    });
    const fieldError = showValidation && fieldPath ? validationErrors[fieldPath] : '';
    const hasError = Boolean(fieldError);
    const errorId = hasError
      ? `schema-error-${fieldPath.replace(/[^a-zA-Z0-9_-]/g, '-')}`
      : undefined;
    const isNumberField = type === 'number' || type === 'integer';
    const numericRangeText = isNumberField && (typeof schema.minimum === 'number' || typeof schema.maximum === 'number')
        ? [
            typeof schema.minimum === 'number' ? `Min ${schema.minimum}` : null,
            typeof schema.maximum === 'number' ? `Max ${schema.maximum}` : null,
        ].filter(Boolean).join(', ')
        : '';
    const parseNumberValue = (rawValue) => {
        if (rawValue === '') return undefined;

        const parsed = type === 'integer'
            ? parseInt(rawValue, 10)
            : parseFloat(rawValue);

        if (!Number.isFinite(parsed)) return undefined;

        let nextValue = parsed;
        if (typeof schema.minimum === 'number') {
            nextValue = Math.max(schema.minimum, nextValue);
        }
        if (typeof schema.maximum === 'number') {
            nextValue = Math.min(schema.maximum, nextValue);
        }
        return nextValue;
    };
    
    // Handle UI Options
    const uiOptions = uiSchema?.['ui:options'] || {};
    const widget = uiSchema?.['ui:widget'];

    // 4. CUSTOM WIDGETS
    if (widget === 'location-search') {
        return (
            <div className="mb-6">
                <FieldHeading title={title} description={description} />
                <LocationSearch
                    value={value}
                    onChange={(next) => {
                        onUserInteraction();
                        onChange(next);
                    }}
                />
                {hasError && <p id={errorId} className="text-xs mt-1" style={{ color: 'var(--color-error)' }}>{fieldError}</p>}
            </div>
        );
    }

    if (widget === 'hidden') {
        return null;
    }
    
    if (widget === 'key-value-list') {
        return (
            <div className="mb-6">
                <FieldHeading title={title} description={description} />
                <KeyValueList
                    value={value}
                    onChange={(next) => {
                        onUserInteraction();
                        onChange(next);
                    }}
                />
                {hasError && <p id={errorId} className="text-xs mt-1" style={{ color: 'var(--color-error)' }}>{fieldError}</p>}
            </div>
        );
    }
    
    if (widget === 'preset-select') {
        const presets = uiOptions.presets || {};
        return (
            <div className="mb-6">
                <FieldHeading title={title} description={description} />
                <PresetSelect 
                    value={value} 
                    onChange={(next) => {
                        onUserInteraction();
                        onChange(next);
                    }} 
                    presets={presets}
                    onPresetSelect={(presetValues) => {
                        // Merge preset values with root form data
                        if (onRootChange && rootValue) {
                            onUserInteraction();
                            onRootChange({ ...rootValue, ...presetValues });
                        }
                    }}
                />
                {hasError && <p id={errorId} className="text-xs mt-1" style={{ color: 'var(--color-error)' }}>{fieldError}</p>}
            </div>
        );
    }
    
    if (widget === 'webhook-test') {
        return (
            <div className="mb-6">
                <WebhookTest formData={rootValue} />
            </div>
        );
    }
    
    if (widget === 'action-button') {
        return (
            <ActionButton
                schema={schema}
                uiSchema={uiSchema}
                moduleId={moduleId}
                onActionComplete={onActionComplete}
            />
        );
    }
    
    if (widget === 'image') {
      return (
        <div className='mb-6'>
          <FieldHeading title={title} description={description} />
          <ImageWidget
            value={value}
            onChange={(next) => {
              onUserInteraction();
              onChange(next);
            }}
            schema={schema}
            uiSchema={uiSchema}
          />
          {hasError && (
            <p id={errorId} className='text-xs mt-1' style={{ color: 'var(--color-error)' }}>
              {fieldError}
            </p>
          )}
        </div>
      );
    }

    if (widget === 'print-webhook-help') {
        return <PrintWebhookHelp rootValue={rootValue} />;
    }

    if (widget === 'richtext') {
        return (
            <div className="mb-6">
                <FieldHeading title={title} description={description} />
                <RichTextEditor
                    value={value}
                    onChange={(next) => {
                        onUserInteraction();
                        onChange(next);
                    }}
                />
            </div>
        );
    }

    // 1. OBJECTS
    if (type === 'object') {
        const isInline = uiOptions.layout === 'inline' || uiOptions.layout === 'compact';
        const showObjectDescription = !(suppressRootDescription && path.length === 0);
        const advancedSectionFields = new Set();

        Object.entries(schema.properties || {}).forEach(([key]) => {
            const propUiSchema = uiSchema?.[key] || {};
            if (propUiSchema['ui:widget'] !== 'advanced-section') {
                return;
            }

            const sectionFields = propUiSchema['ui:options']?.fields || [];
            sectionFields.forEach((field) => {
                if (field !== key) {
                    advancedSectionFields.add(field);
                }
            });
        });
        
        return (
            <div className={isInline ? "flex flex-wrap gap-x-4 gap-y-2 items-end" : ""}>
                {(title || (description && showObjectDescription)) && !isInline ? (
                    <div className="mb-4 space-y-0">
                        {title ? (
                            <h3 className="font-bold text-sm leading-tight text-zinc-700 uppercase tracking-wider">
                                {title}
                            </h3>
                        ) : null}
                        {description && showObjectDescription ? (
                            <p className="text-xs leading-4 text-zinc-500">{description}</p>
                        ) : null}
                    </div>
                ) : null}
                
                {Object.entries(schema.properties || {}).map(([key, propSchema]) => {
                    const propUiSchema = uiSchema?.[key] || {};
                    const propValue = value?.[key];
                    const isCompactItem = isInline || propUiSchema['ui:options']?.compact;
                    const propWidget = propUiSchema['ui:widget'];
                    
                    // Support conditional visibility with ui:showWhen
                    const showWhen = propUiSchema['ui:showWhen'];
                    if (showWhen) {
                        const siblingValue = value?.[showWhen.field];
                        const allowedValues = Array.isArray(showWhen.values)
                            ? showWhen.values
                            : (Object.prototype.hasOwnProperty.call(showWhen, 'value') ? [showWhen.value] : []);
                        if (!allowedValues.includes(siblingValue)) {
                            return null; // Hide this field
                        }
                    }

                    if (advancedSectionFields.has(key) && propWidget !== 'advanced-section') {
                        return null;
                    }

                    if (propWidget === 'advanced-section') {
                        return (
                            <AdvancedSection
                                key={key}
                                title={propSchema.title || key}
                                description={propSchema.description || ''}
                                fields={propUiSchema['ui:options']?.fields || []}
                                parentSchema={schema}
                                parentUiSchema={uiSchema}
                                parentValue={value}
                                parentPath={path}
                                parentRequired={schema.required || []}
                                rootValue={rootValue}
                                onRootChange={onRootChange}
                                moduleId={moduleId}
                                moduleType={moduleType}
                                onActionComplete={onActionComplete}
                                validationErrors={validationErrors}
                                showValidation={showValidation}
                                onUserInteraction={onUserInteraction}
                            />
                        );
                    }
                    
                    return (
                        <div key={key} className={isInline ? "flex-1 min-w-[120px]" : ""}>
                            <SchemaField 
                                schema={propSchema}
                                uiSchema={propUiSchema}
                                value={propValue}
                                onChange={(val) => {
                                    const newValue = { ...value, [key]: val };
                                    onChange(newValue);
                                }}
                                path={[...path, key]}
                                suppressRootDescription={suppressRootDescription}
                                label={propSchema.title || key}
                                required={schema.required && schema.required.includes(key)}
                                compact={isCompactItem}
                                rootValue={rootValue}
                                onRootChange={onRootChange}
                                moduleId={moduleId}
                                moduleType={moduleType}
                                onActionComplete={onActionComplete}
                                validationErrors={validationErrors}
                                showValidation={showValidation}
                                onUserInteraction={onUserInteraction}
                            />
                        </div>
                    );
                })}
            </div>
        );
    }

    // 2. ARRAYS
    if (type === 'array') {
        const items = value || [];
        const itemSchema = schema.items;
        const itemUiSchema = uiSchema?.items || {};

        const handleAdd = () => {
            const emptyItem = createEmptyValue(itemSchema);
            onUserInteraction();
            onChange([...items, emptyItem]);
        };

        const handleRemove = (index) => {
            const newItems = [...items];
            newItems.splice(index, 1);
            onUserInteraction();
            onChange(newItems);
        };

        const handleChangeItem = (index, val) => {
            const newItems = [...items];
            newItems[index] = val;
            onUserInteraction();
            onChange(newItems);
        };

        return (
            <div className="mb-6 space-y-3">
                {(title || description) ? (
                    <div className="space-y-0">
                        <div className="flex justify-between items-center">
                            {title ? (
                                <label className={`${commonClasses.label} leading-tight`}>
                                    {title}
                                </label>
                            ) : null}
                        </div>
                        {description ? (
                            <p className="text-xs leading-4 text-zinc-500">{description}</p>
                        ) : null}
                    </div>
                ) : null}
                
                <div className="space-y-2">
                    {items.map((item, index) => (
                        <div key={index} className="flex gap-2 items-center p-3 border border-zinc-200 rounded-lg bg-white relative group">
                             {/* Item Number Indicator */}
                             <div className="flex-shrink-0 w-6 h-6 rounded-full bg-zinc-100 flex items-center justify-center text-xs font-mono font-bold text-zinc-500">
                                {index + 1}
                             </div>
                             
                             <div className="flex-1">
                                <SchemaField 
                                    schema={itemSchema}
                                    uiSchema={itemUiSchema}
                                    value={item}
                                    onChange={(val) => handleChangeItem(index, val)}
                                    path={[...path, index]}
                                    moduleId={moduleId}
                                    moduleType={moduleType}
                                    validationErrors={validationErrors}
                                    showValidation={showValidation}
                                    onUserInteraction={onUserInteraction}
                                />
                             </div>
                             <button 
                                type="button" 
                                onClick={() => handleRemove(index)}
                                className="text-gray-400 hover:text-red-500 transition-colors p-1"
                                title="Remove Item"
                                aria-label={`Remove item ${index + 1}`}
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" viewBox="0 0 256 256">
                                    <path d="M205.66,194.34a8,8,0,0,1-11.32,11.32L128,139.31,61.66,205.66a8,8,0,0,1-11.32-11.32L116.69,128,50.34,61.66A8,8,0,0,1,61.66,50.34L128,116.69l66.34-66.35a8,8,0,0,1,11.32,11.32L139.31,128Z"></path>
                                </svg>
                             </button>
                        </div>
                    ))}
                </div>
                
                {(!schema.maxItems || items.length < schema.maxItems) && (
                    <button 
                        type="button"
                        onClick={handleAdd}
                        className="w-full px-2 py-3 bg-transparent border-2 border-dashed border-gray-300 hover:border-black rounded-lg text-gray-400 hover:text-black transition-all text-xs font-bold tracking-wider cursor-pointer"
                    >
                        + {uiSchema?.['ui:addLabel'] || 'Add Item'}
                    </button>
                )}
                {schema.maxItems && items.length >= schema.maxItems && (
                    <div className="text-center text-xs text-zinc-400 py-2">
                        Maximum limit of {schema.maxItems} reached
                    </div>
                )}
            </div>
        );
    }
    
    // 3. BOOLEANS
    if (type === 'boolean') {
        return (
            <div className={compact ? 'mb-0' : 'mb-6'}>
                <div className={`flex items-start gap-3 ${compact ? 'py-0' : 'py-0.5'}`}>
                <input 
                    type="checkbox"
                    checked={value || false}
                    onChange={(e) => {
                        onUserInteraction();
                        onChange(e.target.checked);
                    }}
                    className="w-4 h-4 text-black rounded border-2 border-zinc-300 focus:ring-0 focus:ring-offset-0"
                    style={{ accentColor: 'black' }}
                />
                <div
                  className="cursor-pointer select-none"
                  onClick={() => {
                    onUserInteraction();
                    onChange(!value);
                  }}>
                    {title ? (
                        <div className={`text-sm text-black ${compact ? 'font-medium' : ''}`}>
                            {title}
                        </div>
                    ) : null}
                    {description ? (
                        <p className="text-xs leading-4 text-zinc-500 mt-0">{description}</p>
                    ) : null}
                </div>
            </div>
            {hasError && <p id={errorId} className="text-xs mt-1" style={{ color: 'var(--color-error)' }}>{fieldError}</p>}
            </div>
        );
    }

    // 5. STRINGS & NUMBERS
    const headerText = [description, numericRangeText].filter(Boolean).join(' ');
    const randomExampleAction = uiSchema?.['ui:randomExample'] ? (
        <button
            type="button"
            onClick={() => {
                const examples = uiSchema['ui:randomExample'];
                if (Array.isArray(examples) && examples.length > 0) {
                    const available = examples.filter(ex => ex !== value);
                    if (available.length === 0) {
                        const random = examples[Math.floor(Math.random() * examples.length)];
                        onChange(random);
                    } else {
                        const random = available[Math.floor(Math.random() * available.length)];
                        onChange(random);
                    }
                }
            }}
            className="text-xs text-zinc-400 hover:text-black hover:underline cursor-pointer transition-colors"
            title="Insert random example"
        >
            Generate Example
        </button>
    ) : null;

    return (
        <div className={compact ? "mb-0" : "mb-6"}>
            <FieldHeading
                title={title}
                required={required}
                compact={compact}
                description={!compact ? headerText : ''}
                action={randomExampleAction}
            />
            {schema.enum ? (
                <select
                    value={value ?? schema.default ?? ''}
                    onChange={(e) => {
                        onUserInteraction();
                        onChange(e.target.value);
                    }}
                    className={`${compact ? commonClasses.inputSmall : commonClasses.input} ${hasError ? 'border-red-500' : ''}`}
                    style={hasError ? { borderColor: 'var(--color-error)' } : undefined}
                    aria-invalid={hasError}
                    aria-describedby={errorId}
                >
                    {!required && <option value="">Select...</option>}
                    {schema.enum.map((option) => (
                        <option key={option} value={option}>
                            {option}
                        </option>
                    ))}
                </select>
            ) : widget === 'textarea' ? (
                 <textarea
                    value={value ?? schema.default ?? ''}
                    onChange={(e) => {
                        onUserInteraction();
                        onChange(e.target.value);
                    }}
                    className={`${compact ? commonClasses.inputSmall : commonClasses.input} min-h-[100px] text-sm ${hasError ? 'border-red-500' : ''}`}
                    style={hasError ? { borderColor: 'var(--color-error)' } : undefined}
                    placeholder={uiSchema?.['ui:placeholder']}
                    rows={uiOptions.rows || 3}
                    aria-invalid={hasError}
                    aria-describedby={errorId}
                />
            ) : widget === 'password' ? (
                <PasswordInput
                    compact={compact}
                    hasError={hasError}
                    value={value ?? schema.default ?? ''}
                    allowRegenerate={moduleType === 'print_webhook' && fieldPath === 'token'}
                    onChange={(nextValue) => {
                        onUserInteraction();
                        onChange(nextValue);
                    }}
                    placeholder={uiSchema?.['ui:placeholder']}
                    errorId={errorId}
                />
            ) : (
                <input
                    type={isNumberField ? 'number' : 'text'}
                    min={isNumberField ? schema.minimum : undefined}
                    max={isNumberField ? schema.maximum : undefined}
                    step={isNumberField ? (type === 'integer' ? 1 : (schema.multipleOf || 'any')) : undefined}
                    value={value ?? schema.default ?? ''}
                    onChange={(e) => {
                        onUserInteraction();
                        const val = e.target.value;
                        if (!isNumberField) {
                            onChange(val);
                            return;
                        }
                        if (val === '') {
                            onChange(undefined);
                            return;
                        }
                        const parsed = type === 'integer' ? parseInt(val, 10) : parseFloat(val);
                        onChange(Number.isFinite(parsed) ? parsed : undefined);
                    }}
                    onBlur={(e) => {
                        if (!isNumberField) return;
                        const nextValue = parseNumberValue(e.target.value);
                        if (nextValue !== value) {
                            onUserInteraction();
                            onChange(nextValue);
                        }
                    }}
                    className={`${compact ? commonClasses.inputSmall : commonClasses.input} ${hasError ? 'border-red-500' : ''}`}
                    style={hasError ? { borderColor: 'var(--color-error)' } : undefined}
                    placeholder={uiSchema?.['ui:placeholder']}
                    aria-invalid={hasError}
                    aria-describedby={errorId}
                />
            )}
             {hasError && <p id={errorId} className="text-xs mt-1" style={{ color: 'var(--color-error)' }}>{fieldError}</p>}
        </div>
    );
};

const PasswordInput = ({
    compact,
    hasError,
    value,
    allowRegenerate = false,
    onChange,
    placeholder,
    errorId,
}) => {
    const [revealed, setRevealed] = React.useState(false);
    const [copied, setCopied] = React.useState(false);

    const inputClass = compact ? commonClasses.inputSmall : commonClasses.input;

    const handleCopy = async () => {
        if (typeof navigator === 'undefined' || !navigator.clipboard || !value) {
            return;
        }
        try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1200);
        } catch (error) {
            console.error('Failed to copy secret field:', error);
        }
    };

    const handleRegenerate = () => {
        onChange(generatePrintWebhookToken());
    };

    return (
        <div className="flex flex-wrap gap-2 items-stretch">
            <input
                type={revealed ? 'text' : 'password'}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className={`${inputClass} ${hasError ? 'border-red-500' : ''}`}
                style={hasError ? { borderColor: 'var(--color-error)' } : undefined}
                placeholder={placeholder}
                aria-invalid={hasError}
                aria-describedby={errorId}
            />
            <button
                type="button"
                onClick={() => setRevealed((current) => !current)}
                className={commonClasses.buttonGhost}
            >
                {revealed ? 'Hide' : 'Show'}
            </button>
            {allowRegenerate ? (
                <button
                    type="button"
                    onClick={handleRegenerate}
                    className={commonClasses.buttonGhost}
                    title="Generate a new bearer token"
                >
                    Regenerate
                </button>
            ) : null}
            <button
                type="button"
                onClick={handleCopy}
                className={commonClasses.buttonGhost}
                disabled={!value}
                title={value ? 'Copy value' : 'Nothing to copy'}
            >
                {copied ? 'Copied' : 'Copy'}
            </button>
        </div>
    );
};

// Helper: Create empty value based on schema type
const createEmptyValue = (schema) => {
    if (schema.default !== undefined) return schema.default;
    
    switch (schema.type) {
        case 'string': return '';
        case 'number': 
        case 'integer': return 0;
        case 'boolean': return false;
        case 'array': return [];
        case 'object': {
            const obj = {};
            if (schema.properties) {
                Object.keys(schema.properties).forEach(key => {
                    obj[key] = createEmptyValue(schema.properties[key]);
                });
            }
            return obj;
        }
        default: return null;
    }
};

export default SchemaForm;
