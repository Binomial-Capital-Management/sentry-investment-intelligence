import React from 'react';

interface CommandActionsProps {
  onHistory?: () => void;
  onBookmarks?: () => void;
  onSettings?: () => void;
}

const IconBtn: React.FC<{ title: string; onClick?: () => void; children: React.ReactNode }> = ({ title, onClick, children }) => (
  <button
    className="w-8 h-8 rounded-md flex items-center justify-center"
    title={title}
    aria-label={title}
    onClick={onClick}
    style={{ boxShadow: '0 0 0 1px var(--border) inset', color: 'var(--text-secondary)' }}
  >
    {children}
  </button>
);

const CommandActions: React.FC<CommandActionsProps> = ({ onHistory, onBookmarks, onSettings }) => (
  <div className="flex items-center gap-2">
    <IconBtn title="History" onClick={onHistory}>
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3M4 12a8 8 0 108 8 8 8 0 00-8-8z"/></svg>
    </IconBtn>
    <IconBtn title="Bookmarks" onClick={onBookmarks}>
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/></svg>
    </IconBtn>
    <IconBtn title="Settings" onClick={onSettings}>
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8a4 4 0 100 8 4 4 0 000-8z"/><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.477 0 8.268 2.943 9.542 7-1.274 4.057-5.065 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
    </IconBtn>
  </div>
);

export default CommandActions;
