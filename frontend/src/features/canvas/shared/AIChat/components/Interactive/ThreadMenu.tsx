import { useState, useRef, useEffect } from 'react';
import { Trash2, Pin, PinOff, Pencil, Check, X } from 'lucide-react';
import type { ChatThread } from '../../types';

const FADE_MASK = 'linear-gradient(to right, black 70%, transparent 100%)';

function applyFadeIfOverflowing(el: HTMLSpanElement | null) {
  if (!el) return;
  const needs = el.scrollWidth > el.clientWidth;
  el.style.maskImage = needs ? FADE_MASK : 'none';
  el.style.webkitMaskImage = needs ? FADE_MASK : 'none';
}

interface ThreadMenuProps {
  threads: ChatThread[];
  currentThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  onDeleteThread: (threadId: string) => void;
  onUpdateThread: (threadId: string, updates: { title?: string; pinned?: boolean }) => void;
  onClose: () => void;
}

export function ThreadMenu({
  threads,
  currentThreadId,
  onSelectThread,
  onDeleteThread,
  onUpdateThread,
  onClose,
}: ThreadMenuProps) {
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const editInputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  useEffect(() => {
    if (editingThreadId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingThreadId]);

  const handleStartEdit = (thread: ChatThread, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingThreadId(thread.id);
    setEditTitle(thread.title || '');
  };

  const handleSaveEdit = (threadId: string, e?: React.MouseEvent | React.KeyboardEvent) => {
    e?.stopPropagation();
    if (editTitle.trim()) {
      onUpdateThread(threadId, { title: editTitle.trim() });
    }
    setEditingThreadId(null);
    setEditTitle('');
  };

  const handleCancelEdit = (e?: React.MouseEvent | React.KeyboardEvent) => {
    e?.stopPropagation();
    setEditingThreadId(null);
    setEditTitle('');
  };

  const handleTogglePin = (thread: ChatThread, e: React.MouseEvent) => {
    e.stopPropagation();
    onUpdateThread(thread.id, { pinned: !thread.pinned });
  };

  const handleKeyDown = (threadId: string, e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSaveEdit(threadId, e);
    } else if (e.key === 'Escape') {
      handleCancelEdit(e);
    }
  };

  const pinnedThreads = threads.filter(t => t.pinned);
  const unpinnedThreads = threads.filter(t => !t.pinned);

  const actionBtnStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 20,
    height: 20,
    background: 'transparent',
    border: 'none',
    borderRadius: 'var(--cc-radius-sm)',
    color: 'hsl(var(--cc-text-400))',
    cursor: 'pointer',
    transition: 'color 0.1s ease',
  };

  const renderThread = (thread: ChatThread) => {
    const isEditing = editingThreadId === thread.id;
    const isSelected = currentThreadId === thread.id;

    return (
      <div
        key={thread.id}
        className="cc-thread-item"
        style={{
          width: '100%',
          textAlign: 'left',
          padding: '0.375rem 0.75rem',
          fontFamily: 'var(--cc-font-ui)',
          fontSize: '0.75rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          backgroundColor: isSelected ? 'hsl(var(--cc-bg-200))' : 'transparent',
          color: isSelected ? 'hsl(var(--cc-text-000))' : 'hsl(var(--cc-text-200))',
          borderRadius: 'var(--cc-radius-lg)',
          transition: 'background-color 0.1s ease',
        }}
      >
        {thread.pinned && !isEditing && (
          <Pin style={{ width: 12, height: 12, color: 'hsl(var(--cc-accent-main-000))', flexShrink: 0 }} />
        )}

        {isEditing ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <input
              ref={editInputRef}
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onKeyDown={(e) => handleKeyDown(thread.id, e)}
              onClick={(e) => e.stopPropagation()}
              style={{
                flex: 1,
                padding: '0.25rem 0.5rem',
                fontFamily: 'var(--cc-font-ui)',
                fontSize: '0.75rem',
                border: '1px solid hsl(var(--cc-border-300) / 30%)',
                borderRadius: 'var(--cc-radius-md)',
                outline: 'none',
                backgroundColor: 'hsl(var(--cc-bg-000))',
                color: 'hsl(var(--cc-text-100))',
              }}
              placeholder="Chat name..."
            />
            <button
              onClick={(e) => handleSaveEdit(thread.id, e)}
              className="cc-btn-ghost"
              title="Save"
              style={{ ...actionBtnStyle, color: 'hsl(142 71% 45%)' }}
            >
              <Check style={{ width: 14, height: 14 }} />
            </button>
            <button
              onClick={handleCancelEdit}
              className="cc-btn-ghost"
              title="Cancel"
              style={actionBtnStyle}
            >
              <X style={{ width: 14, height: 14 }} />
            </button>
          </div>
        ) : (
          <>
            <button
              onClick={() => {
                onSelectThread(thread.id);
                onClose();
              }}
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '0.5rem',
                minWidth: 0,
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                fontFamily: 'var(--cc-font-ui)',
                fontSize: '0.75rem',
                color: 'inherit',
                textAlign: 'left',
              }}
            >
              <span
                ref={applyFadeIfOverflowing}
                style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}
                title={thread.title || 'Untitled'}
              >
                {thread.title || 'Untitled'}
              </span>
              <span style={{ fontSize: '0.625rem', color: 'hsl(var(--cc-text-500))', flexShrink: 0 }}>
                {new Date(thread.updated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
              </span>
            </button>

            <div className="cc-thread-actions" style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.125rem',
                opacity: 0,
                transition: 'opacity 0.15s ease',
              }}>
                <button
                  onClick={(e) => handleTogglePin(thread, e)}
                  className="cc-btn-ghost"
                  title={thread.pinned ? 'Unpin' : 'Pin'}
                  style={actionBtnStyle}
                >
                  {thread.pinned ? (
                    <PinOff style={{ width: 12, height: 12 }} />
                  ) : (
                    <Pin style={{ width: 12, height: 12 }} />
                  )}
                </button>
                <button
                  onClick={(e) => handleStartEdit(thread, e)}
                  className="cc-btn-ghost"
                  title="Rename"
                  style={actionBtnStyle}
                >
                  <Pencil style={{ width: 12, height: 12 }} />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteThread(thread.id);
                  }}
                  className="cc-btn-ghost"
                  title="Delete"
                  style={{ ...actionBtnStyle }}
                >
                  <Trash2 style={{ width: 12, height: 12 }} />
                </button>
              </div>
          </>
        )}
      </div>
    );
  };

  return (
    <div
      ref={menuRef}
      style={{
        position: 'absolute',
        top: '100%',
        right: 0,
        marginTop: 8,
        width: 300,
        backgroundColor: 'hsl(var(--cc-bg-000))',
        borderRadius: 'var(--cc-radius-2xl)',
        boxShadow: '0 4px 20px -2px rgba(0,0,0,0.12)',
        border: '0.5px solid hsl(var(--cc-border-200) / 30%)',
        zIndex: 101,
        maxHeight: 320,
        overflowY: 'auto',
        padding: '0.375rem',
        animation: 'fadeSlideIn 0.15s ease-out',
      }}
    >
      {threads.length === 0 ? (
        <div style={{
          padding: '0.75rem',
          fontFamily: 'var(--cc-font-ui)',
          fontSize: '0.75rem',
          color: 'hsl(var(--cc-text-500))',
        }}>
          No history
        </div>
      ) : (
        <>
          {pinnedThreads.length > 0 && (
            <>
              <div style={{
                padding: '0.25rem 0.75rem',
                fontFamily: 'var(--cc-font-ui)',
                fontSize: '0.625rem',
                fontWeight: 500,
                color: 'hsl(var(--cc-text-500))',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}>
                Pinned
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                {pinnedThreads.map(renderThread)}
              </div>
              {unpinnedThreads.length > 0 && (
                <div style={{
                  borderTop: '1px solid hsl(var(--cc-border-300) / 10%)',
                  margin: '0.25rem 0',
                }} />
              )}
            </>
          )}

          {unpinnedThreads.length > 0 && (
            <>
              {pinnedThreads.length > 0 && (
                <div style={{
                  padding: '0.25rem 0.75rem',
                  fontFamily: 'var(--cc-font-ui)',
                  fontSize: '0.625rem',
                  fontWeight: 500,
                  color: 'hsl(var(--cc-text-500))',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}>
                  Recent
                </div>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                {unpinnedThreads.map(renderThread)}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
