import { useRef, useEffect, useMemo } from 'react';
import type { Message as MessageType, ChatArtifact } from '@/types';
import IntelligenceCard from './IntelligenceCard';
import { useChatStore } from '@stores/chatStore';
import { debounce } from 'lodash';
// Loader handled inside IntelligenceCard; avoid duplicate global loader

interface MessageListProps {
  messages: MessageType[];
}

const CancellationArtifactCard = ({ artifact }: { artifact: ChatArtifact }) => {
  const reason = artifact.data.reason;
  const reasonLabel = reason === 'send_now'
    ? 'Skipped for priority message'
    : reason === 'user'
      ? 'Cancelled'
      : reason === 'disconnect'
        ? 'Connection lost'
        : 'Cancelled';

  return (
    <span style={{ color: reason === 'send_now' ? '#f59e0b' : 'var(--danger)', fontSize: '13px', fontStyle: 'italic' }}>
      {reasonLabel}
    </span>
  );
};

const MessageList = ({ messages }: MessageListProps) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const prevMessageCount = useRef(0);
  const { currentThreadId, scrollPositions, setScrollPosition, threads } = useChatStore();

  const artifacts = useMemo(() => {
    if (!currentThreadId) return [] as ChatArtifact[];
    const thread = threads.find((t) => t.id === currentThreadId);
    return thread?.artifacts ? [...thread.artifacts] : [];
  }, [threads, currentThreadId]);

  const combinedItems = useMemo(() => {
    const items: Array<{ kind: 'message'; key: string; timestamp: number; payload: MessageType } | { kind: 'artifact'; key: string; timestamp: number; payload: ChatArtifact }> = [];

    for (const msg of messages) {
      const tsSource = msg.timestamp instanceof Date ? msg.timestamp : new Date(msg.timestamp || Date.now());
      const ts = tsSource.getTime();
      items.push({ kind: 'message', key: `msg-${msg.id}`, timestamp: ts, payload: msg });
    }

    for (const artifact of artifacts) {
      const createdSource = artifact.createdAt instanceof Date ? artifact.createdAt : new Date(artifact.createdAt || Date.now());
      const created = createdSource.getTime();
      items.push({ kind: 'artifact', key: `artifact-${artifact.id}`, timestamp: created, payload: artifact });
    }

    return items.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
  }, [messages, artifacts]);

  // Save scroll position (debounced)
  const saveScroll = useMemo(
    () => debounce((threadId: string, position: number) => {
      if (threadId) {
        setScrollPosition(threadId, position);
      }
    }, 200),
    [setScrollPosition],
  );

  // Handle scroll event
  const handleScroll = () => {
    // Find the scrollable parent (the overflow-y-auto div)
    const scrollableElement = scrollContainerRef.current?.closest('.overflow-y-auto');
    if (scrollableElement && currentThreadId) {
      saveScroll(currentThreadId, scrollableElement.scrollTop);
    }
  };

  // Restore scroll position on thread change
  useEffect(() => {
    const scrollableElement = scrollContainerRef.current?.closest('.overflow-y-auto');
    if (scrollableElement && currentThreadId && scrollPositions[currentThreadId]) {
      // Small delay to ensure content is rendered
      setTimeout(() => {
        scrollableElement.scrollTop = scrollPositions[currentThreadId];
      }, 50);
    }
  }, [currentThreadId, scrollPositions]);

  // Add scroll listener to parent scrollable container
  useEffect(() => {
    const scrollableElement = scrollContainerRef.current?.closest('.overflow-y-auto');
    if (scrollableElement) {
      scrollableElement.addEventListener('scroll', handleScroll);
      return () => scrollableElement.removeEventListener('scroll', handleScroll);
    }
  }, [currentThreadId, handleScroll]);

  useEffect(() => {
    // Only scroll when a new message is added, not when existing messages update
    if (combinedItems.length > prevMessageCount.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
    prevMessageCount.current = combinedItems.length;
  }, [combinedItems.length]);

  // Keep scroll to bottom only for new messages

  return (
    <div
      ref={scrollContainerRef}
      style={{
        background: 'var(--bg-card)',
        color: 'var(--sentry-slate)',
        paddingTop: '32px',
        paddingBottom: '32px',
      }}
    >
      <div className="px-8">
        <div className="max-w-5xl mx-auto">
          <div className="space-y-6">
            {combinedItems.map((item) => {
              if (item.kind === 'message') {
                const m = item.payload;
                return (
                  <div key={item.key} style={{
                    borderBottom: m.role === 'assistant' ? '1px solid #e5e5e5' : 'none',
                    paddingBottom: m.role === 'assistant' ? '24px' : '0',
                    marginBottom: m.role === 'assistant' ? '24px' : '0',
                  }}>
                    <IntelligenceCard message={m} />
                  </div>
                );
              }

              return (
                <div
                  key={item.key}
                  style={{ margin: '16px 0', display: 'flex', justifyContent: 'flex-start' }}
                >
                  <CancellationArtifactCard artifact={item.payload} />
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <div ref={bottomRef} />
    </div>
  );
};

export default MessageList;
