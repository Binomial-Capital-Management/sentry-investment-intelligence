import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

interface ShortcutHandlers {
  onSearch?: () => void;
  onNewChat?: () => void;
  onEscape?: () => void;
  onToggleSidebar?: () => void;
}

export function useKeyboardShortcuts(handlers: ShortcutHandlers = {}) {
  const navigate = useNavigate();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input/textarea
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
        // Allow Escape even in inputs
        if (e.key === 'Escape') {
          target.blur();
          handlers.onEscape?.();
        }
        return;
      }

      // Cmd/Ctrl + K - Search
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        handlers.onSearch?.();
      }

      // Cmd/Ctrl + J - New chat
      if ((e.metaKey || e.ctrlKey) && e.key === 'j') {
        e.preventDefault();
        handlers.onNewChat?.();
      }

      // Cmd/Ctrl + B - Toggle sidebar
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault();
        handlers.onToggleSidebar?.();
      }

      // Quick navigation shortcuts
      if (e.altKey) {
        switch(e.key) {
          case '1':
            e.preventDefault();
            navigate('/chat');
            break;
          case '2':
            e.preventDefault();
            navigate('/portfolio');
            break;
          case '3':
            e.preventDefault();
            navigate('/workflows');
            break;
          case '4':
            e.preventDefault();
            navigate('/markets');
            break;
          case '5':
            e.preventDefault();
            navigate('/settings');
            break;
        }
      }

      // Escape - Close modals/overlays
      if (e.key === 'Escape') {
        handlers.onEscape?.();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handlers, navigate]);
}

// Keyboard shortcuts help modal content
export function KeyboardShortcutsHelp() {
  const shortcuts = [
    { keys: ['⌘', 'K'], description: 'Open search' },
    { keys: ['⌘', 'J'], description: 'New chat' },
    { keys: ['⌘', 'B'], description: 'Toggle sidebar' },
    { keys: ['Esc'], description: 'Close modals' },
    { keys: ['Alt', '1-5'], description: 'Quick navigation' },
  ];

  return (
    <div className="space-y-2">
      {shortcuts.map((shortcut, index) => (
        <div key={index} className="flex items-center justify-between py-2">
          <span className="text-white/70 text-sm">{shortcut.description}</span>
          <div className="flex items-center gap-1">
            {shortcut.keys.map((key, i) => (
              <span key={i}>
                <kbd className="px-2 py-1 bg-white/10 border border-white/20 rounded text-xs text-white">
                  {key}
                </kbd>
                {i < shortcut.keys.length - 1 && <span className="mx-1 text-white/40">+</span>}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
