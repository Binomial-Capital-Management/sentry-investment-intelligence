import { SquarePen, History } from 'lucide-react';
import type { ChatThread } from '../../types';
import { ThreadMenu } from '../Interactive/ThreadMenu';
import { Tooltip } from '@/features/canvas/shared/Tooltip';

const hslIcon = 'hsl(30 3.3% 11.8% / 85%)';
const hslHoverBg = 'hsl(30 3.3% 11.8% / 6%)';
const hslActiveBg = 'hsl(30 3.3% 11.8% / 8%)';
const hslDisabled = 'hsl(30 3.3% 11.8% / 25%)';

interface ChatHeaderProps {
  chatTitle: string;
  currentContext: string;
  threads: ChatThread[];
  currentThreadId: string | null;
  isThreadMenuOpen: boolean;
  setIsThreadMenuOpen: (open: boolean) => void;
  onSelectThread: (threadId: string) => void;
  onDeleteThread: (threadId: string) => void;
  onUpdateThread: (threadId: string, updates: { title?: string; pinned?: boolean }) => void;
  onNewThread: () => void;
  onClose: () => void;
}

export function ChatHeader({
  chatTitle,
  currentContext,
  threads,
  currentThreadId,
  isThreadMenuOpen,
  setIsThreadMenuOpen,
  onSelectThread,
  onDeleteThread,
  onUpdateThread,
  onNewThread,
  onClose,
}: ChatHeaderProps) {
  return (
    <div className="shrink-0 relative z-[90] flex items-center justify-between px-3" style={{ height: 44 }}>
      <div className="flex items-center min-w-0 flex-1">
        <Tooltip label="Close Agent">
          <button
            onClick={onClose}
            className="p-1.5 rounded-md transition-colors"
            style={{ color: hslIcon }}
            onMouseEnter={e => (e.currentTarget.style.backgroundColor = hslHoverBg)}
            onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
          >
            <img src="/sentry-icon.png" alt="" className="w-5 h-5 block" />
          </button>
        </Tooltip>
      </div>

      <div className="flex items-center gap-1">
        {/* New Chat Button */}
        <Tooltip label="New chat">
          <button
            onClick={() => onNewThread()}
            className="p-1.5 rounded-md transition-colors"
            style={{ color: hslIcon }}
            onMouseEnter={e => { e.currentTarget.style.backgroundColor = hslHoverBg; }}
            onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            <SquarePen className="w-4 h-4" />
          </button>
        </Tooltip>

        {/* History Button */}
        <div className="relative flex">
          <Tooltip label="Chat history">
            <button
              onClick={() => setIsThreadMenuOpen(!isThreadMenuOpen)}
              className="p-1.5 rounded-md transition-colors"
              style={{
                color: hslIcon,
                backgroundColor: isThreadMenuOpen ? hslActiveBg : 'transparent',
              }}
              onMouseEnter={e => { if (!isThreadMenuOpen) e.currentTarget.style.backgroundColor = hslHoverBg; }}
              onMouseLeave={e => { if (!isThreadMenuOpen) e.currentTarget.style.backgroundColor = 'transparent'; }}
            >
              <History className="w-4 h-4" />
            </button>
          </Tooltip>

          {isThreadMenuOpen && (
            <ThreadMenu
              threads={threads}
              currentThreadId={currentThreadId}
              onSelectThread={onSelectThread}
              onDeleteThread={onDeleteThread}
              onUpdateThread={onUpdateThread}
              onClose={() => setIsThreadMenuOpen(false)}
            />
          )}
        </div>
      </div>
    </div>
  );
}
