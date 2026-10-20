import { useState, useRef, useEffect, forwardRef, useImperativeHandle, useMemo, useCallback } from 'react';
import type { Components } from 'react-markdown';
import type { ToolEvent } from '@/types';
import type { Message, PendingUpdate, AgentAction } from '../../types';
import { UserMessage } from './UserMessage';
import { AssistantMessage } from './AssistantMessage';
import { PendingUpdateCard } from './PendingUpdateCard';
import { ActionConfirmationCard } from './ActionConfirmationCard';

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  toolEvents: ToolEvent[];
  reasoningStreaming: boolean;
  reasoningText: string;
  statusMessage: string;
  pendingUpdate: PendingUpdate | null;
  applyingUpdate: boolean;
  onApplyUpdate: () => void;
  onDismissUpdate: () => void;
  markdownComponents: Partial<Components>;
  exportState: {
    copyFeedback: Record<string, boolean>;
    exportingPdf: Record<string, boolean>;
    exportingPpt: Record<string, boolean>;
    exportingWorkbook: Record<string, boolean>;
    showStyleSelector: boolean;
    availableStyles: Array<{ style_name: string; is_default: boolean }>;
    selectedStyleName: string | null;
    styleSelectorRef: React.RefObject<HTMLDivElement>;
    setShowStyleSelector: (show: boolean) => void;
    setSelectedStyleName: (name: string | null) => void;
    handleCopy: (message: Message) => Promise<void>;
    handlePDFExport: (message: Message) => Promise<void>;
    handlePPTExport: (message: Message) => Promise<void>;
    handleWorkbookExport: (message: Message) => Promise<void>;
  };
  // Action confirmation (inline in chat)
  pendingActionConfirmation?: AgentAction | null;
  onConfirmAction?: () => void;
  onCancelAction?: () => void;
}

export interface MessageListHandle {
  scrollToBottom: () => void;
}

export const MessageList = forwardRef<MessageListHandle, MessageListProps>(function MessageList({
  messages,
  isLoading,
  toolEvents,
  reasoningStreaming,
  reasoningText,
  statusMessage,
  pendingUpdate,
  applyingUpdate,
  onApplyUpdate,
  onDismissUpdate,
  markdownComponents,
  exportState,
  pendingActionConfirmation,
  onConfirmAction,
  onCancelAction,
}, ref) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showFadeTop, setShowFadeTop] = useState(false);
  const [showFadeBottom, setShowFadeBottom] = useState(false);
  const userScrolledUp = useRef(false);
  const lastScrollTop = useRef(0);
  const lastUserMsgCount = useRef(0);

  useImperativeHandle(ref, () => ({
    scrollToBottom: () => {
      userScrolledUp.current = false;
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    },
  }));

  // Reset stick-to-bottom when user sends a new message
  useEffect(() => {
    const count = messages.filter(m => m.role === 'user').length;
    if (count > lastUserMsgCount.current) {
      userScrolledUp.current = false;
    }
    lastUserMsgCount.current = count;
  }, [messages]);

  // Auto-scroll when content changes (if user hasn't scrolled up)
  useEffect(() => {
    const scrollToBottom = () => {
      if (!userScrolledUp.current) {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }
    };
    scrollToBottom();

    const observer = new MutationObserver(scrollToBottom);
    if (scrollContainerRef.current) {
      observer.observe(scrollContainerRef.current, { childList: true, subtree: true, characterData: true });
    }

    let intervalId: ReturnType<typeof setInterval> | null = null;
    if (isLoading) {
      intervalId = setInterval(scrollToBottom, 100);
    }

    return () => {
      observer.disconnect();
      if (intervalId) clearInterval(intervalId);
    };
  }, [messages, isLoading]);

  const handleScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;

    setShowFadeTop(el.scrollTop > 20);
    setShowFadeBottom(el.scrollHeight - el.scrollTop - el.clientHeight > 20);

    // Track scroll direction — upward scroll disables auto-scroll
    const currentScrollTop = el.scrollTop;
    const isAtBottom = el.scrollHeight - currentScrollTop - el.clientHeight < 2;

    if (currentScrollTop < lastScrollTop.current - 5) {
      userScrolledUp.current = true;
    }
    if (isAtBottom) {
      userScrolledUp.current = false;
    }

    lastScrollTop.current = currentScrollTop;
  }, []);

  // Group tool events by messageIndex for inline display
  const toolEventsByMessage = useMemo(() => {
    const grouped: Record<number, ToolEvent[]> = {};
    for (const event of toolEvents) {
      const idx = event.messageIndex ?? -1;
      if (!grouped[idx]) {
        grouped[idx] = [];
      }
      grouped[idx].push(event);
    }
    return grouped;
  }, [toolEvents]);

  return (
    <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
      {showFadeTop && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '2rem',
            background: 'linear-gradient(to bottom, hsl(var(--cc-bg-100)) 0%, transparent 100%)',
            pointerEvents: 'none',
            zIndex: 2,
          }}
        />
      )}
      {showFadeBottom && (
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: '2rem',
            background: 'linear-gradient(to top, hsl(var(--cc-bg-100)) 0%, transparent 100%)',
            pointerEvents: 'none',
            zIndex: 2,
          }}
        />
      )}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        style={{
          height: '100%',
          overflowY: 'auto',
          padding: '1rem',
          backgroundColor: 'hsl(var(--cc-bg-100))',
        }}
      >

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {messages.map((message, index) => (
          <div key={index}>
            {message.role === 'user' && (
              <UserMessage content={message.content} />
            )}

            {message.role === 'assistant' && (
              <AssistantMessage
                message={message}
                isLoading={isLoading}
                isLastMessage={index === messages.length - 1}
                reasoningStreaming={reasoningStreaming}
                reasoningText={reasoningText}
                statusMessage={statusMessage}
                markdownComponents={markdownComponents}
                toolEvents={toolEventsByMessage[index] || []}
                exportState={exportState}
              />
            )}
          </div>
        ))}

        {/* Fallback loading indicator when no messages yet */}
        {isLoading && messages.length === 0 && (
          <div style={{ fontFamily: 'var(--cc-font-ui)', fontSize: '0.75rem', fontWeight: 500 }}>
            <span className="animate-shimmertext">Thinking...</span>
          </div>
        )}

        {/* Pending Update Card */}
        {pendingUpdate && (
          <PendingUpdateCard
            pendingUpdate={pendingUpdate}
            applyingUpdate={applyingUpdate}
            onApply={onApplyUpdate}
            onDismiss={onDismissUpdate}
          />
        )}

        {/* Action Confirmation Card (inline) */}
        {pendingActionConfirmation && onConfirmAction && onCancelAction && (
          <ActionConfirmationCard
            action={pendingActionConfirmation}
            onConfirm={onConfirmAction}
            onCancel={onCancelAction}
          />
        )}
      </div>

      <div ref={messagesEndRef} />
      </div>
    </div>
  );
});
