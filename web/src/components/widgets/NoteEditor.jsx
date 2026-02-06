import React, { useEffect, useMemo, useRef, useState } from 'react';

const ALLOWED_TAGS = new Set(['p', 'div', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'h1', 'h2']);
const CHECKBOX_PREFIX = /^\s*\[( |x|X)\]\s*/;

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
    onPointerDown={(event) => event.preventDefault()}
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
  const savedRangeRef = useRef(null);

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

  const saveSelectionFromEditor = (editor) => {
    const selection = window.getSelection();
    if (!editor || !selection || selection.rangeCount === 0) return;
    const range = selection.getRangeAt(0);
    if (!editor.contains(range.commonAncestorContainer)) return;
    savedRangeRef.current = range.cloneRange();
  };

  const restoreSelectionToEditor = (editor) => {
    if (!editor || !savedRangeRef.current) return false;
    if (!editor.contains(savedRangeRef.current.commonAncestorContainer)) return false;

    const selection = window.getSelection();
    if (!selection) return false;

    try {
      selection.removeAllRanges();
      selection.addRange(savedRangeRef.current);
      return true;
    } catch {
      savedRangeRef.current = null;
      return false;
    }
  };

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

  const focusEditor = (editor) => {
    if (!editor) return;
    editor.focus({ preventScroll: true });
  };

  const prepareCommandTarget = () => {
    const editor = getActiveEditor();
    if (!editor) return null;
    focusEditor(editor);
    restoreSelectionToEditor(editor);
    return editor;
  };

  const insertPlainText = (text) => {
    const editor = prepareCommandTarget();
    if (!editor) return;

    if (document.queryCommandSupported && document.queryCommandSupported('insertText')) {
      document.execCommand('insertText', false, text);
      syncFromEditor(editor);
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
    saveSelectionFromEditor(editor);
    syncFromEditor(editor);
  };

  const transformSelectedTextLines = (transformLine, onNoSelection) => {
    const editor = prepareCommandTarget();
    if (!editor) return false;

    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) {
      if (onNoSelection) onNoSelection();
      return false;
    }

    const range = selection.getRangeAt(0);
    if (!editor.contains(range.commonAncestorContainer)) {
      if (onNoSelection) onNoSelection();
      return false;
    }

    const selectedText = range.toString();
    if (!selectedText) {
      if (onNoSelection) onNoSelection();
      return false;
    }

    const normalized = selectedText.replace(/\r\n/g, '\n');
    const lines = normalized.split('\n');
    const transformed = lines.map((line, index) => transformLine(line, index, lines)).join('\n');

    if (document.queryCommandSupported && document.queryCommandSupported('insertText')) {
      document.execCommand('insertText', false, transformed);
    } else {
      range.deleteContents();
      range.insertNode(document.createTextNode(transformed));
      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);
      saveSelectionFromEditor(editor);
    }

    syncFromEditor(editor);
    return true;
  };

  const runCommand = (command, commandValue = null) => {
    const editor = prepareCommandTarget();
    if (!editor) return false;
    const before = editor.innerHTML;
    document.execCommand(command, false, commandValue);
    syncFromEditor(editor);
    return before !== editor.innerHTML;
  };

  const setBlockTag = (tagNameLower) => {
    const editor = prepareCommandTarget();
    if (!editor) return;
    const before = editor.innerHTML;

    document.execCommand('formatBlock', false, `<${tagNameLower}>`);
    document.execCommand('formatBlock', false, tagNameLower);

    syncFromEditor(editor);

    if (before === editor.innerHTML) {
      const selection = window.getSelection();
      if (!selection || selection.rangeCount === 0) return;
      const range = selection.getRangeAt(0);
      if (!editor.contains(range.commonAncestorContainer)) return;

      const selectedText = range.toString().trim();
      if (!selectedText) return;

      const heading = document.createElement(tagNameLower);
      heading.textContent = selectedText;
      range.deleteContents();
      range.insertNode(heading);

      const newRange = document.createRange();
      newRange.selectNodeContents(heading);
      newRange.collapse(false);
      selection.removeAllRanges();
      selection.addRange(newRange);
      saveSelectionFromEditor(editor);
      syncFromEditor(editor);
    }
  };

  const applyChecklist = () => {
    transformSelectedTextLines(
      (line) => {
        if (!line.trim()) return line;
        const indent = line.match(/^\s*/)?.[0] || '';
        const text = line.slice(indent.length);
        if (CHECKBOX_PREFIX.test(text)) return `${indent}${text}`;
        return `${indent}[ ] ${text}`;
      },
      () => insertPlainText('[ ] ')
    );
  };

  const applyBullets = () => {
    const changed = runCommand('insertUnorderedList');
    if (changed) return;

    transformSelectedTextLines(
      (line) => {
        if (!line.trim()) return line;
        const indent = line.match(/^\s*/)?.[0] || '';
        const text = line.slice(indent.length).replace(/^[-*]\s+/, '');
        return `${indent}- ${text}`;
      },
      () => insertPlainText('- ')
    );
  };

  const applyNumbers = () => {
    const changed = runCommand('insertOrderedList');
    if (changed) return;

    let index = 1;
    transformSelectedTextLines(
      (line) => {
        if (!line.trim()) return line;
        const indent = line.match(/^\s*/)?.[0] || '';
        const text = line.slice(indent.length).replace(/^\d+\.\s+/, '');
        const numbered = `${indent}${index}. ${text}`;
        index += 1;
        return numbered;
      },
      () => insertPlainText('1. ')
    );
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
      <ToolbarButton label="H" title="Heading" onClick={() => setBlockTag('h2')} />
      <ToolbarButton label="B" title="Bold" onClick={() => runCommand('bold')} />
      <ToolbarButton label="I" title="Italic" onClick={() => runCommand('italic')} />
      <ToolbarButton label="Bullets" title="Bulleted List" onClick={applyBullets} />
      <ToolbarButton label="Numbers" title="Numbered List" onClick={applyNumbers} />
      <ToolbarButton label="Checklist" title="Insert Checklist Item" onClick={applyChecklist} />
      <ToolbarButton
        label="Clear"
        title="Clear Formatting"
        onClick={() => {
          runCommand('removeFormat');
          runCommand('formatBlock', 'p');
          runCommand('formatBlock', '<p>');
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
        onFocus={(event) => saveSelectionFromEditor(event.currentTarget)}
        onInput={(event) => syncFromEditor(event.currentTarget)}
        onBlur={(event) => {
          saveSelectionFromEditor(event.currentTarget);
          syncFromEditor(event.currentTarget);
        }}
        onMouseUp={(event) => saveSelectionFromEditor(event.currentTarget)}
        onTouchEnd={(event) => saveSelectionFromEditor(event.currentTarget)}
        onKeyUp={(event) => saveSelectionFromEditor(event.currentTarget)}
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
