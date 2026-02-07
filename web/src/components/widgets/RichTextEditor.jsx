import React, { useState } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';

// Toolbar button component
const ToolbarButton = ({ onClick, active, title, children }) => (
  <button
    type="button"
    onClick={onClick}
    title={title}
    className={`
      w-8 h-8 flex items-center justify-center rounded
      text-sm font-bold transition-colors cursor-pointer
      ${active 
        ? 'bg-[var(--color-border-main)] text-[var(--color-bg-card)]' 
        : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-main)] hover:bg-[var(--color-bg-white)]'
      }
    `}
  >
    {children}
  </button>
);

// Toolbar component
const Toolbar = ({ editor, isFullscreen, onToggleFullscreen }) => {
  if (!editor) return null;

  return (
    <div className="flex gap-1 p-2 border-b border-[var(--color-border-gray-300)] bg-[var(--color-bg-gray-50)]">
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
        active={editor.isActive('heading', { level: 1 })}
        title="Heading (Ctrl+Alt+1)"
      >
        H
      </ToolbarButton>
      
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleBold().run()}
        active={editor.isActive('bold')}
        title="Bold (Ctrl+B)"
      >
        B
      </ToolbarButton>
      
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleItalic().run()}
        active={editor.isActive('italic')}
        title="Italic (Ctrl+I)"
      >
        <span className="italic">I</span>
      </ToolbarButton>
      
      <div className="w-px bg-[var(--color-border-gray-300)] mx-1" />
      
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        active={editor.isActive('bulletList')}
        title="Bullet List"
      >
        •
      </ToolbarButton>
      
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        active={editor.isActive('orderedList')}
        title="Numbered List"
      >
        1.
      </ToolbarButton>
      
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleTaskList().run()}
        active={editor.isActive('taskList')}
        title="Checkbox List"
      >
        ☐
      </ToolbarButton>
      
      <div className="w-px bg-[var(--color-border-gray-300)] mx-1" />
      
      <ToolbarButton
        onClick={() => editor.chain().focus().setHorizontalRule().run()}
        active={false}
        title="Horizontal Rule"
      >
        —
      </ToolbarButton>
      
      {/* Spacer to push fullscreen button to the right */}
      <div className="flex-1" />
      
      <ToolbarButton
        onClick={onToggleFullscreen}
        active={isFullscreen}
        title={isFullscreen ? "Exit Fullscreen (Esc)" : "Fullscreen"}
      >
        {isFullscreen ? '✕' : '⛶'}
      </ToolbarButton>
    </div>
  );
};

/**
 * RichTextEditor - WYSIWYG editor using TipTap
 * Outputs Markdown-compatible content for printing
 */
const RichTextEditor = ({ value, onChange }) => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // We only need specific features
        heading: { levels: [1] },
        codeBlock: false,
        code: false,
        blockquote: false,
        strike: false,
      }),
      TaskList,
      TaskItem.configure({
        nested: false,
      }),
    ],
    content: value ? parseMarkdownToHtml(value) : '',
    onUpdate: ({ editor }) => {
      // Convert to Markdown for storage
      const markdown = htmlToMarkdown(editor.getHTML());
      onChange(markdown);
    },
    editorProps: {
      attributes: {
        class: 'prose prose-sm max-w-none p-3 min-h-[120px] focus:outline-none font-mono text-sm',
      },
    },
  });

  // Update editor when external value changes
  React.useEffect(() => {
    if (editor && value !== undefined) {
      const currentMarkdown = htmlToMarkdown(editor.getHTML());
      if (currentMarkdown !== value) {
        editor.commands.setContent(parseMarkdownToHtml(value));
      }
    }
  }, [value, editor]);
  
  // Handle Escape key to exit fullscreen
  React.useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen]);

  const containerClasses = isFullscreen
    ? 'fixed inset-0 z-50 flex flex-col bg-[var(--color-bg-base)]'
    : 'border-2 border-[var(--color-border-gray-300)] rounded-lg overflow-hidden bg-[var(--color-bg-input)] focus-within:border-[var(--color-border-main)] transition-colors';

  return (
    <div className={containerClasses}>
      <Toolbar 
        editor={editor} 
        isFullscreen={isFullscreen} 
        onToggleFullscreen={() => setIsFullscreen(!isFullscreen)} 
      />
      <div className={isFullscreen ? 'flex-1 overflow-auto' : ''}>
        <EditorContent editor={editor} />
      </div>
      <style>{`
        .ProseMirror {
          min-height: ${isFullscreen ? 'calc(100vh - 60px)' : '120px'};
          font-family: 'IBM Plex Mono', monospace;
          font-size: 14px;
          color: var(--color-text-main);
        }
        .ProseMirror:focus {
          outline: none;
        }
        .ProseMirror p {
          margin: 0.5em 0;
        }
        .ProseMirror h1 {
          font-size: 1.25em;
          font-weight: 700;
          margin: 0.75em 0 0.5em;
        }
        .ProseMirror strong {
          font-weight: 700;
        }
        .ProseMirror em {
          font-style: italic;
        }
        .ProseMirror ul, .ProseMirror.prose ul {
          list-style-type: disc !important;
          list-style-position: outside !important;
          padding-left: 1.5em !important;
          margin: 0.5em 0 !important;
        }
        .ProseMirror ol, .ProseMirror.prose ol {
          list-style-type: decimal !important;
          list-style-position: outside !important;
          padding-left: 1.5em !important;
          margin: 0.5em 0 !important;
        }
        .ProseMirror li, .ProseMirror.prose li {
          margin: 0.25em 0 !important;
          display: list-item !important;
        }
        .ProseMirror hr {
          border: none;
          border-top: 2px dashed var(--color-border-gray-400);
          margin: 1em 0;
        }
        /* Task List Styles */
        .ProseMirror ul[data-type="taskList"] {
          list-style: none !important;
          padding-left: 0 !important;
        }
        .ProseMirror ul[data-type="taskList"] li {
          display: flex !important;
          align-items: center;
          gap: 0.5em;
        }
        .ProseMirror ul[data-type="taskList"] li > label {
          flex-shrink: 0;
          margin-top: 0.15em;
        }
        .ProseMirror ul[data-type="taskList"] li > label input[type="checkbox"] {
          width: 1em;
          height: 1em;
          cursor: pointer;
        }
        .ProseMirror ul[data-type="taskList"] li > div {
          flex: 1;
        }
        .ProseMirror p.is-editor-empty:first-child::before {
          content: attr(data-placeholder);
          color: var(--color-text-muted);
          pointer-events: none;
          float: left;
          height: 0;
        }
      `}</style>
    </div>
  );
};

/**
 * Convert simple Markdown to HTML for TipTap
 */
function parseMarkdownToHtml(markdown) {
  if (!markdown) return '';
  
  let html = markdown
    // Headers (must be at line start)
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic (using * or _)
    .replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>')
    .replace(/_(.+?)_/g, '<em>$1</em>')
    // Horizontal rule
    .replace(/^---$/gm, '<hr>')
    // Task list items (must be before regular lists)
    .replace(/^- \[x\] (.+)$/gm, '<taskitem checked>$1</taskitem>')
    .replace(/^- \[ \] (.+)$/gm, '<taskitem>$1</taskitem>')
    // Unordered lists
    .replace(/^[*-] (.+)$/gm, '<li>$1</li>')
    // Ordered lists
    .replace(/^\d+\. (.+)$/gm, '<oli>$1</oli>')
    // Wrap consecutive <taskitem> in task list
    .replace(/(<taskitem[^>]*>.*<\/taskitem>\n?)+/g, '<ul data-type="taskList">$&</ul>')
    .replace(/<taskitem checked>/g, '<li data-type="taskItem" data-checked="true"><label><input type="checkbox" checked></label><div><p>')
    .replace(/<taskitem>/g, '<li data-type="taskItem" data-checked="false"><label><input type="checkbox"></label><div><p>')
    .replace(/<\/taskitem>/g, '</p></div></li>')
    // Wrap consecutive <li> in <ul>
    .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
    // Wrap consecutive <oli> in <ol>
    .replace(/(<oli>.*<\/oli>\n?)+/g, '<ol>$&</ol>')
    .replace(/<\/?oli>/g, (m) => m.replace('oli', 'li'))
    // Paragraphs (lines not already wrapped)
    .split('\n')
    .map(line => {
      if (line.match(/^<(h1|ul|ol|hr|li)/)) return line;
      if (line.trim() === '') return '';
      if (!line.match(/^<[a-z]/)) return `<p>${line}</p>`;
      return line;
    })
    .join('\n');
  
  return html;
}

/**
 * Convert TipTap HTML back to Markdown
 */
function htmlToMarkdown(html) {
  if (!html) return '';
  
  // Create a temporary div to parse HTML
  const div = document.createElement('div');
  div.innerHTML = html;
  
  let markdown = '';
  
  const processNode = (node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      return node.textContent;
    }
    
    if (node.nodeType !== Node.ELEMENT_NODE) {
      return '';
    }
    
    const children = Array.from(node.childNodes).map(processNode).join('');
    
    switch (node.tagName.toLowerCase()) {
      case 'h1':
        return `# ${children}\n`;
      case 'p':
        return `${children}\n`;
      case 'strong':
        return `**${children}**`;
      case 'em':
        return `*${children}*`;
      case 'ul':
        return children;
      case 'ol':
        return children;
      case 'li':
        const parent = node.parentElement;
        // Check if this is a task item
        if (node.dataset?.type === 'taskItem' || node.getAttribute('data-type') === 'taskItem') {
          const isChecked = node.dataset?.checked === 'true' || node.getAttribute('data-checked') === 'true';
          const checkbox = isChecked ? '[x]' : '[ ]';
          return `- ${checkbox} ${children}\n`;
        }
        if (parent.tagName.toLowerCase() === 'ol') {
          const index = Array.from(parent.children).indexOf(node) + 1;
          return `${index}. ${children}\n`;
        }
        return `- ${children}\n`;
      case 'hr':
        return '---\n';
      case 'br':
        return '\n';
      case 'label':
        return ''; // Skip checkbox labels
      case 'input':
        return ''; // Skip checkbox inputs
      default:
        return children;
    }
  };
  
  markdown = Array.from(div.childNodes).map(processNode).join('');
  
  // Clean up extra newlines
  return markdown.replace(/\n{3,}/g, '\n\n').trim();
}

export default RichTextEditor;
