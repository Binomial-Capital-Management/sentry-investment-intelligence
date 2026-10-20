import { useEffect, useRef, useState, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { useChatStore } from '@stores/chatStore';
import { useChat, STREAM_STATE_TTL_MS } from '@/hooks/useChat';
import MessageList from './MessageList';
import InputArea from './InputArea';
import { useUIStore } from '@stores/uiStore';
import HeroSection from '../Hero/HeroSection';
// import CommandBar from '@components/Common/CommandBar'; // Removed - not needed
import ResultsPanel from './ResultsPanel';
import ThreadSidebar from './ThreadSidebar';
import ModelDropdown from './ModelDropdown';
import PromptLibrary from './PromptLibrary';
import CompactionIndicator from './CompactionIndicator';
import WorkspaceIndicator from '@/components/Common/WorkspaceIndicator';
import { AlertCircle, Plus, HelpCircle, Sparkles } from 'lucide-react';
import MemoryIcon from '@/components/Icons/MemoryIcon';
import type { Message } from '@/types';
import { STREAM_STORAGE_KEYS, streamingStorage } from '@services/streamingStorage';
import { ChatGuidePanel } from './ChatGuidePanel';
import TextSelectionPopup from './TextSelectionPopup';
import MemoryNotebookPanel from './MemoryNotebookPanel';
import SourcesPanel from './SourcesPanel';
import StudioPanel from './StudioPanel';
import FilingPreviewPanel from './FilingPreviewPanel';

const ChatInterface = () => {
  const location = useLocation();
  const STREAM_STATE_KEY = STREAM_STORAGE_KEYS.state;
  const CONTEXT_KEY = STREAM_STORAGE_KEYS.context;
  const { threads, currentThreadId, createNewThread, setCurrentThread, loadMessages, loadThreads, getCurrentThreadModel } = useChatStore();
  const { resumeActiveStream } = useChat();
  const analystMode = useUIStore((s: any) => s.analystMode);
  const [promptInput, setPromptInput] = useState<string>('');
  const [showGuide, setShowGuide] = useState(false);
  const memoryPanelOpen = useUIStore((s: any) => s.memoryPanelOpen);
  const toggleMemoryPanel = useUIStore((s: any) => s.toggleMemoryPanel);
  const setMemoryPanelOpen = useUIStore((s: any) => s.setMemoryPanelOpen);
  const studioPanelOpen = useUIStore((s: any) => s.studioPanelOpen);
  const toggleStudioPanel = useUIStore((s: any) => s.toggleStudioPanel);
  const setStudioPanelOpen = useUIStore((s: any) => s.setStudioPanelOpen);
  const filingPreviewOpen = useUIStore((s: any) => s.filingPreviewOpen);
  const setFilingPreviewOpen = useUIStore((s: any) => s.setFilingPreviewOpen);
  const messageAreaRef = useRef<HTMLDivElement>(null);
  
  // Memory panel resize state
  const [memoryPanelWidth, setMemoryPanelWidth] = useState(340);
  const [isResizing, setIsResizing] = useState(false);
  const resizeRef = useRef<{ startX: number; startWidth: number } | null>(null);
  
  // Studio panel resize state
  const [studioPanelWidth, setStudioPanelWidth] = useState(360);
  const [isResizingStudio, setIsResizingStudio] = useState(false);
  const resizeStudioRef = useRef<{ startX: number; startWidth: number } | null>(null);
  
  // Filing preview panel resize state
  const [filingPanelWidth, setFilingPanelWidth] = useState(450);
  const [isResizingFiling, setIsResizingFiling] = useState(false);
  const resizeFilingRef = useRef<{ startX: number; startWidth: number } | null>(null);
  
  // Handle memory panel resize
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    resizeRef.current = { startX: e.clientX, startWidth: memoryPanelWidth };
  }, [memoryPanelWidth]);
  
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !resizeRef.current) return;
      // Left panel with handle on right: dragging right = wider, dragging left = thinner
      const delta = e.clientX - resizeRef.current.startX;
      const newWidth = Math.max(280, Math.min(600, resizeRef.current.startWidth + delta));
      setMemoryPanelWidth(newWidth);
    };
    
    const handleMouseUp = () => {
      setIsResizing(false);
      resizeRef.current = null;
    };
    
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);
  
  // Handle studio panel resize
  const handleStudioResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingStudio(true);
    resizeStudioRef.current = { startX: e.clientX, startWidth: studioPanelWidth };
  }, [studioPanelWidth]);
  
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizingStudio || !resizeStudioRef.current) return;
      const delta = resizeStudioRef.current.startX - e.clientX;
      const newWidth = Math.max(300, Math.min(700, resizeStudioRef.current.startWidth + delta));
      setStudioPanelWidth(newWidth);
    };
    
    const handleMouseUp = () => {
      setIsResizingStudio(false);
      resizeStudioRef.current = null;
    };
    
    if (isResizingStudio) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizingStudio]);
  
  // Handle filing preview panel resize
  const handleFilingResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingFiling(true);
    resizeFilingRef.current = { startX: e.clientX, startWidth: filingPanelWidth };
  }, [filingPanelWidth]);
  
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizingFiling || !resizeFilingRef.current) return;
      const delta = resizeFilingRef.current.startX - e.clientX;
      const newWidth = Math.max(350, Math.min(800, resizeFilingRef.current.startWidth + delta));
      setFilingPanelWidth(newWidth);
    };
    
    const handleMouseUp = () => {
      setIsResizingFiling(false);
      resizeFilingRef.current = null;
    };
    
    if (isResizingFiling) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizingFiling]);
  
  const [hasHydrated, setHasHydrated] = useState(() => {
    const persist = (useChatStore as any).persist;
    return persist?.hasHydrated?.() ?? true;
  });

  // Check if Claude or Gemini model is selected
  const selectedModel = getCurrentThreadModel();
  const isClaudeModel = selectedModel && (
    selectedModel.includes('anthropic') ||
    selectedModel.includes('claude')
  );
  const isGeminiModel = selectedModel && selectedModel.includes('gemini');
  const isGrokModel = selectedModel && (
    selectedModel.includes('xai') ||
    selectedModel.includes('grok')
  );
  const isDeepSeekModel = selectedModel && (
    selectedModel.includes('deepseek')
  );
  const isBedrockModel = selectedModel && (
    selectedModel.includes('bedrock') ||
    selectedModel.includes('llama4')
  );

  const handlePromptSelect = (prompt: string) => {
    console.log('[ChatInterface] Prompt selected:', prompt);
    setPromptInput(prompt);
  };

  const initRef = useRef(false);

  const rehydrateStreamingSnapshot = useCallback(() => {
    try {
      const contextRaw = streamingStorage.read(CONTEXT_KEY);
      if (!contextRaw) {
        return;
      }

      const parsedContext = JSON.parse(contextRaw) as {
        message?: string;
        threadId?: string;
        assistantMessageId?: string;
        streamContext?: Record<string, unknown>;
        timestamp?: number;
      } | null;

      if (!parsedContext || typeof parsedContext !== 'object') {
        streamingStorage.remove(CONTEXT_KEY);
        return;
      }

      const { message, threadId, assistantMessageId, timestamp } = parsedContext;
      if (!threadId || !assistantMessageId) {
        streamingStorage.remove(CONTEXT_KEY);
        return;
      }

      if (typeof timestamp === 'number' && Date.now() - timestamp > STREAM_STATE_TTL_MS) {
        streamingStorage.remove(CONTEXT_KEY);
        streamingStorage.remove(STREAM_STATE_KEY);
        return;
      }

      const snapshotRaw = streamingStorage.read(STREAM_STATE_KEY);
      let snapshot: any = null;
      if (snapshotRaw) {
        try {
          const parsedSnapshot = JSON.parse(snapshotRaw);
          const snapTimestamp = typeof parsedSnapshot?.timestamp === 'number' ? parsedSnapshot.timestamp : 0;
          if (snapTimestamp && Date.now() - snapTimestamp > STREAM_STATE_TTL_MS) {
            streamingStorage.remove(STREAM_STATE_KEY);
          } else if (parsedSnapshot && typeof parsedSnapshot === 'object' && parsedSnapshot.state) {
            snapshot = parsedSnapshot;
          }
        } catch {
          streamingStorage.remove(STREAM_STATE_KEY);
        }
      }

      const store = useChatStore.getState();
      const assistantId = assistantMessageId;
      const existingThread = store.threads.find((t) => t.id === threadId);

      if (!existingThread) {
        const now = new Date();
        const placeholderThread = {
          id: threadId,
          title: 'Restored Conversation',
          messages: [] as Message[],
          createdAt: now,
          updatedAt: now,
          selectedModel: store.selectedModel,
          agentMode: store.agentMode,
          artifacts: [],
          hasLoadedMessages: false,
        };
        useChatStore.setState((prev) => ({
          ...prev,
          threads: [placeholderThread, ...prev.threads],
          currentThreadId: prev.currentThreadId ?? threadId,
        }));
      }

      useChatStore.setState((prev) => {
        const nextThreads = prev.threads.map((thread) => {
          if (thread.id !== threadId) {
            return thread;
          }

          const messages = [...thread.messages];
          if (message && !messages.some((m) => m.role === 'user' && m.content === message)) {
            messages.push({
              id: `rehydrated-user-${assistantId}`,
              role: 'user',
              content: message,
              timestamp: new Date(),
              isStreaming: false,
            } as Message);
          }

          const assistantIndex = messages.findIndex((m) => m.id === assistantId);
          const restoredAssistant: Message = {
            id: assistantId,
            role: 'assistant',
            content: snapshot?.state?.content ?? '',
            timestamp: new Date(),
            isStreaming: true,
            extras: snapshot?.state?.extras ?? {},
            sources: snapshot?.state?.sources,
            charts: snapshot?.state?.charts,
            toolEvents: snapshot?.state?.toolEvents,
          } as Message;

          if (assistantIndex >= 0) {
            messages[assistantIndex] = { ...messages[assistantIndex], ...restoredAssistant };
          } else {
            messages.push(restoredAssistant);
          }

          return {
            ...thread,
            messages,
            hasLoadedMessages: thread.hasLoadedMessages || false,
          };
        });

        return {
          ...prev,
          threads: nextThreads,
          currentThreadId: prev.currentThreadId ?? threadId,
        };
      });
    } catch (error) {
      console.warn('[ChatInterface] Failed to rehydrate streaming snapshot:', error);
    }
  }, [CONTEXT_KEY, STREAM_STATE_KEY]);

  // Load threads on mount and auto-create session if none exist
  useEffect(() => {
    const persist = (useChatStore as any).persist;
    if (!persist?.onFinishHydration) {
      return;
    }
    const unsub = persist.onFinishHydration(() => {
      setHasHydrated(true);
    });
    if (!persist.hasHydrated?.()) {
      setHasHydrated(false);
    }
    return () => {
      unsub?.();
    };
  }, []);

  useEffect(() => {
    if (!hasHydrated) {
      return;
    }
    if (initRef.current) {
      return;
    }
    initRef.current = true;

    const initializeChat = async () => {
      await loadThreads();

      rehydrateStreamingSnapshot();

      let resumed = false;
      try {
        const contextRaw = streamingStorage.read(CONTEXT_KEY);
        if (contextRaw) {
          resumed = await resumeActiveStream();
        }
      } catch (e) {
        console.warn('[ChatInterface] Failed to resume stream:', e);
      }

      const storeState = useChatStore.getState();
      const currentThreads = storeState.threads;
      if (currentThreads.length === 0) {
        const newThreadId = await createNewThread('New Chat');
        setCurrentThread(newThreadId);
        await loadMessages(newThreadId);
      } else {
        const activeThreadId = storeState.currentThreadId || currentThreads[0].id;
        setCurrentThread(activeThreadId);
        const candidate = useChatStore.getState().threads.find((t) => t.id === activeThreadId);
        if (!resumed && candidate && candidate.messages.length === 0) {
          await loadMessages(activeThreadId);
        }
      }
    };

    void initializeChat();
  }, [hasHydrated, loadThreads, resumeActiveStream, createNewThread, setCurrentThread, loadMessages, rehydrateStreamingSnapshot]);

  useEffect(() => {
    // Only set current thread if we have threads but none selected
    if (!currentThreadId && threads.length > 0) {
      // Select the most recent thread
      const latest = threads[0];
      if (latest?.id) {
        setCurrentThread(latest.id);
        // Load messages for the selected thread
        if (latest.messages.length === 0) {
          loadMessages(latest.id);
        }
      }
    }
  }, [threads, currentThreadId, setCurrentThread, loadMessages]);

  // Handle initial message from navigation state (e.g., from Earnings/IPO Calendar)
  useEffect(() => {
    const state = location.state as { initialMessage?: string } | null;
    if (state?.initialMessage && hasHydrated) {
      // Create a new thread for the analysis
      const initNewChatWithMessage = async () => {
        const newThreadId = await createNewThread('New Analysis');
        setCurrentThread(newThreadId);
        // Pre-populate the input area (don't auto-send)
        setPromptInput(state.initialMessage || '');
        // Clear the state to prevent re-loading on navigation
        window.history.replaceState({}, document.title);
      };
      void initNewChatWithMessage();
    }
  }, [location.state, hasHydrated, createNewThread, setCurrentThread]);

  // Load messages when thread is selected (fixes refresh issue)
  useEffect(() => {
    if (currentThreadId) {
      const currentThread = threads.find(t => t.id === currentThreadId);
      // Load messages if thread exists and we don't have them yet
      // This handles both refresh scenarios and thread switching
      if (currentThread && !currentThread.hasLoadedMessages) {
        loadMessages(currentThreadId);
      }
    }
  }, [currentThreadId, threads, loadMessages]);

  const currentThread = threads.find(t => t.id === currentThreadId);
  const hasMessages = currentThread && currentThread.messages.length > 0;

  return (
    <div className="flex h-full" style={{ background: '#FAF9F8' }}>
      {/* Thread Sidebar */}
      <ThreadSidebar />

      {/* Main Chat Area - ChatGPT Style */}
      <div
        className="flex flex-col flex-1 overflow-hidden relative transition-all duration-300"
        style={{ marginRight: showGuide ? '576px' : '0' }}
      >
        {/* Top Bar */}
        <div style={{
          background: '#FFFFFF',
          borderBottom: '1px solid #E1DFDD',
          padding: '11px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <div className="flex items-center gap-3">
            <ModelDropdown />
            <PromptLibrary onPromptSelect={handlePromptSelect} />
            <WorkspaceIndicator size="sm" />
            {/* Claude/Gemini/Grok/DeepSeek/Bedrock Model Info */}
            {(isClaudeModel || isGeminiModel || isGrokModel || isDeepSeekModel || isBedrockModel) && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '4px 10px',
                background: 'linear-gradient(135deg, #FFF9F0 0%, #FFF4E5 100%)',
                border: '1px solid #FFD6A5',
                borderRadius: '6px',
                fontSize: '12px',
                color: '#8B5A00',
                fontWeight: '500',
              }}>
                <AlertCircle size={12} style={{ color: '#FF8C00' }} />
                <span>Code execution & real-time streaming unavailable • Code generation available</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* Compaction Indicator - Inline in header */}
            <CompactionIndicator />
            {/* Memory Notebook Toggle - always visible */}
            <button
              onClick={() => {
                // Close Studio if open, then toggle Memory Notebook
                if (studioPanelOpen) {
                  setStudioPanelOpen(false);
                  setMemoryPanelOpen(true);
                } else {
                  toggleMemoryPanel();
                }
              }}
              style={{
                padding: '6px',
                fontSize: '14px',
                background: memoryPanelOpen && !studioPanelOpen ? '#EBF5FF' : '#FFFFFF',
                border: memoryPanelOpen && !studioPanelOpen ? '1px solid #3B82F6' : '1px solid #C8C6C4',
                borderRadius: '4px',
                color: memoryPanelOpen && !studioPanelOpen ? '#3B82F6' : '#605E5C',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              title="Memory Notebook"
            >
              <MemoryIcon size={18} />
            </button>
            {/* Studio Mode Toggle - immersive 3-panel layout */}
            <button
              onClick={() => {
                const newStudioState = !studioPanelOpen;
                setStudioPanelOpen(newStudioState);
                // Close memory panel when entering studio mode (Sources replaces it)
                if (newStudioState) {
                  setMemoryPanelOpen(false);
                }
              }}
              style={{
                padding: '6px 12px',
                fontSize: '13px',
                fontWeight: 500,
                background: studioPanelOpen ? '#E6F0FF' : '#FFFFFF',
                border: studioPanelOpen ? '1px solid #0051cc' : '1px solid #C8C6C4',
                borderRadius: '6px',
                color: studioPanelOpen ? '#0051cc' : '#605E5C',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
              title="Toggle Studio Mode"
            >
              <Sparkles size={16} />
              Studio
            </button>
            <button
              onClick={() => setShowGuide(true)}
              style={{
                padding: '6px',
                fontSize: '14px',
                background: '#FFFFFF',
                border: '1px solid #C8C6C4',
                borderRadius: '4px',
                color: '#605E5C',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              title="Chat Guide"
            >
              <HelpCircle size={18} />
            </button>
          </div>
        </div>


        {/* Content area - Sources LEFT | Chat MIDDLE | Studio RIGHT */}
        <div className="flex flex-1 min-h-0 overflow-hidden">
          
          {/* LEFT: Sources Panel (only when Studio mode is active) */}
          {studioPanelOpen && currentThreadId && (
            <div 
              className="flex-shrink-0 overflow-hidden relative"
              style={{ 
                width: `${memoryPanelWidth}px`,
                background: '#FFFFFF',
                borderRight: '1px solid #E1DFDD',
                transition: isResizing ? 'none' : 'width 0.15s ease'
              }}
            >
              <SourcesPanel 
                sessionId={currentThreadId} 
                onClose={() => setStudioPanelOpen(false)}
              />
              {/* Resize Handle on RIGHT side */}
              <div
                onMouseDown={handleResizeStart}
                className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize group z-10"
                style={{ 
                  background: isResizing ? '#3B82F6' : 'transparent',
                  transition: 'background 0.15s'
                }}
              >
                <div 
                  className="absolute inset-y-0 -left-1 -right-1 group-hover:bg-blue-500/20"
                  style={{ background: isResizing ? 'rgba(59, 130, 246, 0.2)' : 'transparent' }}
                />
              </div>
            </div>
          )}
          
          {/* Memory Notebook Panel (when NOT in Studio mode) */}
          {memoryPanelOpen && !studioPanelOpen && currentThreadId && (
            <div 
              className="flex-shrink-0 overflow-hidden relative"
              style={{ 
                width: `${memoryPanelWidth}px`,
                background: '#FFFFFF',
                borderRight: '1px solid #E1DFDD',
                transition: isResizing ? 'none' : 'width 0.15s ease'
              }}
            >
              <MemoryNotebookPanel 
                sessionId={currentThreadId} 
                onClose={() => setMemoryPanelOpen(false)}
              />
              {/* Resize Handle on RIGHT side */}
              <div
                onMouseDown={handleResizeStart}
                className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize group z-10"
                style={{ 
                  background: isResizing ? '#3B82F6' : 'transparent',
                  transition: 'background 0.15s'
                }}
              >
                <div 
                  className="absolute inset-y-0 -left-1 -right-1 group-hover:bg-blue-500/20"
                  style={{ background: isResizing ? 'rgba(59, 130, 246, 0.2)' : 'transparent' }}
                />
              </div>
            </div>
          )}

          {/* MIDDLE: Chat messages + input */}
          <div className="flex flex-col flex-1 min-w-0">
            {/* Scrollable message area */}
            <div ref={messageAreaRef} className="flex-1 min-h-0" style={{ background: '#FFFFFF', position: 'relative', overflow: 'hidden' }}>
              {hasMessages ? (
                analystMode ? (
                  <div className="grid grid-cols-12 max-lg:grid-cols-1 h-full">
                    <div className="col-span-7 max-lg:col-span-1 overflow-y-auto" style={{ borderRight: '1px solid #E1DFDD' }}>
                      <div className="max-w-5xl mx-auto">
                        <MessageList messages={currentThread.messages} />
                      </div>
                    </div>
                    <div className="col-span-5 max-lg:col-span-1 overflow-hidden" style={{ background: '#FAF9F8' }}>
                      <ResultsPanel />
                    </div>
                  </div>
                ) : (
                  <div className="h-full overflow-y-auto">
                    <MessageList messages={currentThread.messages} />
                  </div>
                )
              ) : (
                <HeroSection />
              )}
              {/* Text Selection Popup for adding to notebook */}
              {currentThreadId && (
                <TextSelectionPopup 
                  sessionId={currentThreadId} 
                  containerRef={messageAreaRef}
                />
              )}
            </div>

            {/* Fixed input area at bottom */}
            <div className="flex-shrink-0" style={{
              background: '#FFFFFF',
              paddingTop: '16px',
              paddingBottom: '12px',
            }}>
              <InputArea
                externalInput={promptInput}
                onInputChange={() => setPromptInput('')}
              />
            </div>
          </div>
          
          {/* RIGHT: Studio Panel */}
          {studioPanelOpen && currentThreadId && (
            <div 
              className="flex-shrink-0 overflow-hidden relative"
              style={{ 
                width: `${studioPanelWidth}px`,
                background: '#FFFFFF',
                borderLeft: '1px solid #E1DFDD',
                transition: isResizingStudio ? 'none' : 'width 0.15s ease'
              }}
            >
              {/* Resize Handle on LEFT side */}
              <div
                onMouseDown={handleStudioResizeStart}
                className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize group z-10"
                style={{ 
                  background: isResizingStudio ? '#0051cc' : 'transparent',
                  transition: 'background 0.15s'
                }}
              >
                <div 
                  className="absolute inset-y-0 -left-1 -right-1 group-hover:bg-[#0051cc]/20"
                  style={{ background: isResizingStudio ? 'rgba(0, 81, 204, 0.2)' : 'transparent' }}
                />
              </div>
              <StudioPanel 
                sessionId={currentThreadId} 
                onClose={() => setStudioPanelOpen(false)}
                onSendToChat={(message) => {
                  setPromptInput(message);
                }}
              />
            </div>
          )}
          
          {/* RIGHT: Filing Preview Panel (can show alongside or instead of Studio) */}
          {filingPreviewOpen && (
            <div 
              className="flex-shrink-0 overflow-hidden relative"
              style={{ 
                width: `${filingPanelWidth}px`,
                background: '#FFFFFF',
                borderLeft: '1px solid #E1DFDD',
                transition: isResizingFiling ? 'none' : 'width 0.15s ease'
              }}
            >
              {/* Resize Handle on LEFT side */}
              <div
                onMouseDown={handleFilingResizeStart}
                className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize group z-10"
                style={{ 
                  background: isResizingFiling ? '#2563eb' : 'transparent',
                  transition: 'background 0.15s'
                }}
              >
                <div 
                  className="absolute inset-y-0 -left-1 -right-1 group-hover:bg-blue-500/20"
                  style={{ background: isResizingFiling ? 'rgba(37, 99, 235, 0.2)' : 'transparent' }}
                />
              </div>
              <FilingPreviewPanel onClose={() => setFilingPreviewOpen(false)} />
            </div>
          )}
        </div>
      </div>

      {/* Chat Guide Panel (slides in from right) */}
      <ChatGuidePanel isOpen={showGuide} onClose={() => setShowGuide(false)} />
    </div>
  );
};

export default ChatInterface;
