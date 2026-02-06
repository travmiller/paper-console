import React, { useEffect, useMemo, useRef, useState } from 'react';

const ALLOWED_TAGS = new Set(['p', 'div', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'h1', 'h2']);

const escapeHtml = (text) =>
  String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const looksLikeHtml = (value) => /<\s*\/?\s*[a-z][^>]*>/i.test(value || '');

const plainTextToHtml = (value) => {
  const text = String(value || '').replace(/\r\n/g, '\n');
  if (!text.trim()) return '<p><br></p>';
  return text
    .split('\n')
    .map((line) => (line.trim() ? `<p>${escapeHtml(line)}</p>` : '<p><br></p>'))
    .join('');
};

const unwrapElement = (node) => {
  const parent = node.parentNode;
  if (!parent) return;
  while (node.firstChild) {
    parent.insertBefore(node.firstChild, node);
  }
  parent.removeChild(node);
};

const replaceTag = (node, tagName, doc) => {
  const replacement = doc.createElement(tagName);
  while (node.firstChild) {
    replacement.appendChild(node.firstChild);
  }
  node.parentNode.replaceChild(replacement, node);
  return replacement;
};

const sanitizeRichHtml = (value) => {
  if (typeof document === 'undefined') return value || '';

  const container = document.createElement('div');
  container.innerHTML = value || '';

  const normalizeNode = (root) => {
    const children = Array.from(root.childNodes);
    children.forEach((child) => {
      if (child.nodeType === 3) return;
      if (child.nodeType !== 1) {
        root.removeChild(child);
        return;
      }

      let node = child;
      let tagName = node.tagName.toLowerCase();

      if (tagName === 'b') {
        node = replaceTag(node, 'strong', root.ownerDocument);
        tagName = 'strong';
      } else if (tagName === 'i') {
        node = replaceTag(node, 'em', root.ownerDocument);
        tagName = 'em';
      }

      if (!ALLOWED_TAGS.has(tagName)) {
        unwrapElement(node);
        normalizeNode(root);
        return;
      }

      while (node.attributes.length > 0) {
        node.removeAttribute(node.attributes[0].name);
      }

      normalizeNode(node);
    });
  };

  normalizeNode(container);

  const html = container.innerHTML.trim();
  return html || '<p><br></p>';
};

const getTextContent = (value) => {
  if (typeof document === 'undefined') return (value || '').trim();
  const container = document.createElement('div');
  container.innerHTML = value || '';
  return (container.textContent || '').replace(/\u00A0/g, ' ').trim();
};

const normalizeIncomingValue = (value) => {
  if (!value) return '<p><br></p>';
  if (!looksLikeHtml(value)) return plainTextToHtml(value);
  return sanitizeRichHtml(value);
};

const normalizeForStorage = (value) => {
  const sanitized = sanitizeRichHtml(value || '');
  if (!getTextContent(sanitized)) return '';
  return sanitized;
};

const ToolbarButton = ({ label, onClick, title }) => (
  <button
    type="button"
    className="px-3 py-1.5 text-xs font-bold border-2 border-zinc-300 rounded-md bg-white hover:border-black transition-colors cursor-pointer whitespace-nowrap"
    onMouseDown={(event) => event.preventDefault()}
    onClick={onClick}
    title={title || label}
  >
    {label}
  </button>
);

const NoteEditor = ({ value, onChange, placeholder = 'Write your note...' }) => {
  const [editorHtml, setEditorHtml] = useState(() => normalizeIncomingValue(value || ''));
  const [isFullscreen, setIsFullscreen] = useState(false);
  const inlineEditorRef = useRef(null);
  const fullscreenEditorRef = useRef(null);
  const lastCommittedValueRef = useRef(value || '');

  useEffect(() => {
    const incoming = value || '';
    if (incoming === lastCommittedValueRef.current) return;
    setEditorHtml(normalizeIncomingValue(incoming));
    lastCommittedValueRef.current = incoming;
  }, [value]);

  useEffect(() => {
    if (!isFullscreen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isFullscreen]);

  const isEmpty = useMemo(() => !getTextContent(editorHtml), [editorHtml]);

  const getActiveEditor = () => (isFullscreen ? fullscreenEditorRef.current : inlineEditorRef.current);

  useEffect(() => {
    const editors = [inlineEditorRef.current, fullscreenEditorRef.current].filter(Boolean);
    editors.forEach((editor) => {
      if (editor.innerHTML !== editorHtml) {
        editor.innerHTML = editorHtml;
      }
    });
  }, [editorHtml, isFullscreen]);

  useEffect(() => {
    if (!isFullscreen || !fullscreenEditorRef.current) return;
    fullscreenEditorRef.current.focus();
  }, [isFullscreen]);

  const syncFromEditor = (editor) => {
    if (!editor) return;

    const sanitized = sanitizeRichHtml(editor.innerHTML);
    setEditorHtml(sanitized);

    const storedValue = normalizeForStorage(sanitized);
    lastCommittedValueRef.current = storedValue;
    onChange(storedValue);
  };

  const syncFromActiveEditor = () => {
    syncFromEditor(getActiveEditor());
  };

  const focusActiveEditor = () => {
    const editor = getActiveEditor();
    if (!editor) return;
    editor.focus();
  };

  const insertPlainText = (text) => {
    focusActiveEditor();

    if (document.queryCommandSupported && document.queryCommandSupported('insertText')) {
      document.execCommand('insertText', false, text);
      syncFromActiveEditor();
      return;
    }

    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;
    const range = selection.getRangeAt(0);
    range.deleteContents();
    range.insertNode(document.createTextNode(text));
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
    syncFromActiveEditor();
  };

  const runCommand = (command, commandValue = null) => {
    focusActiveEditor();
    document.execCommand(command, false, commandValue);
    syncFromActiveEditor();
  };

  const setBlockTag = (tagName) => {
    focusActiveEditor();
    document.execCommand('formatBlock', false, tagName);
    document.execCommand('formatBlock', false, `<${tagName.toLowerCase()}>`);
    syncFromActiveEditor();
  };

  const handleKeyDown = (event) => {
    const modifier = event.metaKey || event.ctrlKey;
    if (!modifier) return;
    const key = event.key.toLowerCase();
    if (key === 'b') {
      event.preventDefault();
      runCommand('bold');
    } else if (key === 'i') {
      event.preventDefault();
      runCommand('italic');
    }
  };

  const handlePaste = (event) => {
    event.preventDefault();
    const text = event.clipboardData?.getData('text/plain') || '';
    insertPlainText(text);
  };

  const toolbar = (
    <div className="flex gap-2 overflow-x-auto pb-1">
      <ToolbarButton label="H" title="Heading" onClick={() => setBlockTag('H2')} />
      <ToolbarButton label="B" title="Bold" onClick={() => runCommand('bold')} />
      <ToolbarButton label="I" title="Italic" onClick={() => runCommand('italic')} />
      <ToolbarButton label="Bullets" title="Bulleted List" onClick={() => runCommand('insertUnorderedList')} />
      <ToolbarButton label="Numbers" title="Numbered List" onClick={() => runCommand('insertOrderedList')} />
      <ToolbarButton label="Checklist" title="Insert Checklist Item" onClick={() => insertPlainText('[ ] ')} />
      <ToolbarButton
        label="Clear"
        title="Clear Formatting"
        onClick={() => {
          runCommand('removeFormat');
          setBlockTag('P');
        }}
      />
    </div>
  );

  const renderEditor = (ref, heightClass) => (
    <div className="relative">
      {isEmpty && (
        <div className="pointer-events-none absolute top-3 left-3 text-zinc-400 text-sm">
          {placeholder}
        </div>
      )}
      <div
        ref={ref}
        contentEditable
        suppressContentEditableWarning
        onInput={(event) => syncFromEditor(event.currentTarget)}
        onBlur={(event) => syncFromEditor(event.currentTarget)}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        className={`w-full p-3 text-base bg-white border-2 border-zinc-300 rounded-lg text-black focus:border-black focus:outline-none overflow-y-auto ${heightClass}`}
      />
    </div>
  );

  return (
    <>
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="text-xs text-zinc-500">Use toolbar buttons to format your note.</div>
          <button
            type="button"
            className="text-xs px-3 py-1.5 border-2 border-zinc-300 rounded-md bg-white hover:border-black transition-colors cursor-pointer"
            onClick={() => setIsFullscreen(true)}
          >
            Expand
          </button>
        </div>
        {toolbar}
        {renderEditor(inlineEditorRef, 'min-h-[220px] max-h-[360px]')}
      </div>

      {isFullscreen && (
        <div className="fixed inset-0 z-[70] bg-white p-3 sm:p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="text-sm font-bold text-black">Edit Note</div>
            <button
              type="button"
              className="text-sm px-3 py-1.5 border-2 border-black rounded-md bg-transparent hover:bg-black hover:text-white transition-all cursor-pointer"
              onClick={() => {
                syncFromActiveEditor();
                setIsFullscreen(false);
              }}
            >
              Done
            </button>
          </div>

          <div className="sticky top-0 bg-white z-10 pt-1">{toolbar}</div>
          <div className="flex-1">{renderEditor(fullscreenEditorRef, 'h-full min-h-[60vh]')}</div>
        </div>
      )}
    </>
  );
};

export default NoteEditor;
