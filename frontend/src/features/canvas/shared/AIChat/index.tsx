import { useState, useRef, useEffect, useLayoutEffect, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';
import type { ModelId, ToolEvent } from '@/types';
import { GoogleDriveNativePicker } from '@/components/KnowledgeGraph/GoogleDriveNativePicker';
import { OneDriveNativePicker } from '@/components/KnowledgeGraph/OneDriveNativePicker';

import type { CanvasAIChatPanelProps, ChatThread, Message } from './types';
import './claude-chat-theme.css';
import { useMarkdownComponents } from './markdownConfig';

// Hooks
import { usePanelResize } from './hooks/usePanelResize';
import { useCanvasChat } from './hooks/useCanvasChat';
import { useFileAttachments } from './hooks/useFileAttachments';
import { useMessageExport } from './hooks/useMessageExport';
import { useTabChatState } from './hooks/useTabChatState';
// Store + Manager
import { useChatStreamStore } from './stores/chatStreamStore';
import * as chatStreamManager from './services/chatStreamManager';
// Components
import { ChatHeader, MessageList, MessageListHandle } from './components/Display';
import { ChatInputArea, ChatControls } from './components/Interactive';

export default function CanvasAIChatPanel({
  isOpen,
  onClose,
  process,
  dataContext,
  onResize,
  onResultUpdate,
  tabThreadId,
  onTabThreadIdChange,
  activeTabId,
  onEnsureTab,
}: CanvasAIChatPanelProps) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messageListRef = useRef<MessageListHandle>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Local UI state
  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState<ModelId>('gpt-6.1-sol');
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
  const [isWebSearchEnabled, setIsWebSearchEnabled] = useState(false);

  // Hooks
  const { panelWidth, isResizing, startResize } = usePanelResize({ panelRef, onResize });

  // Track when the open transition finishes so we can switch overflow to visible
  const [transitionDone, setTransitionDone] = useState(isOpen);
  useEffect(() => {
    if (!isOpen) {
      setTransitionDone(false);
    } else {
      const timer = setTimeout(() => setTransitionDone(true), 300);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  const {
    threads,
    currentThreadId,
    isThreadMenuOpen,
    setIsThreadMenuOpen,
    setCurrentThreadId,
    loadThreadMessages,
    createNewThread,
    deleteThread,
    updateThread,
  } = useCanvasChat({
    activeTabId,
    processId: process?.id,
    isOpen,
    isLoaded,
    getToken,
    tabThreadId,
    onTabThreadIdChange,
  });

  const {
    attachedFiles,
    uploadingFiles,
    isDraggingFiles,
    showDrivePicker,
    showOneDrivePicker,
    oneDriveAccountType,
    showCloudMenu,
    setShowDrivePicker,
    setShowOneDrivePicker,
    setOneDriveAccountType,
    setShowCloudMenu,
    handleFileUploadClick,
    handleRemoveFile,
    handleGoogleDriveSelect,
    handleOneDriveSelect,
    clearAttachedFiles,
    dragHandlers,
  } = useFileAttachments();

  const handleThreadCreated = useCallback((thread: ChatThread) => {
    if (!activeTabId) return;
    const s = useChatStreamStore.getState();
    const current = s.tabStates[activeTabId]?.threads ?? [];
    if (!current.some(t => t.id === thread.id)) {
      s.setThreads(activeTabId, [thread, ...current]);
    }
    setCurrentThreadId(thread.id);
  }, [activeTabId, setCurrentThreadId]);

  // Read chat state from Zustand store (survives tab switches)
  const {
    messages,
    toolEvents,
    isLoading,
    reasoningStreaming,
    reasoningText,
    statusMessage,
    pendingUpdate,
    applyingUpdate,
    pendingActionConfirmation,
  } = useTabChatState(activeTabId);

  const clearChatState = useCallback(() => {
    if (currentThreadId) useChatStreamStore.getState().clearThread(currentThreadId);
  }, [currentThreadId]);

  const sendMessage = useCallback(async (text: string, tabIdOverride?: string) => {
    const tabId = tabIdOverride || activeTabId;
    if (!tabId) return;
    chatStreamManager.startStream(tabId, {
      text,
      process,
      dataContext,
      currentThreadId,
      selectedModel,
      isWebSearchEnabled,
      attachedFileIds: attachedFiles.map(f => f.id),
      getToken,
      onThreadCreated: handleThreadCreated,
      onUpdateThread: updateThread,
      onResultUpdate,
    });
  }, [activeTabId, process, dataContext, currentThreadId, selectedModel, isWebSearchEnabled, attachedFiles, getToken, handleThreadCreated, updateThread, onResultUpdate]);

  const cancelStream = useCallback(() => {
    if (activeTabId) chatStreamManager.cancelStream(activeTabId);
  }, [activeTabId]);

  const applyPendingUpdate = useCallback(async () => {
    if (currentThreadId) await chatStreamManager.applyPendingUpdate(currentThreadId, getToken);
  }, [currentThreadId, getToken]);

  const dismissPendingUpdate = useCallback(() => {
    if (currentThreadId) chatStreamManager.dismissPendingUpdate(currentThreadId);
  }, [currentThreadId]);

  const confirmAction = useCallback(() => {
    if (activeTabId) chatStreamManager.confirmActionForTab(activeTabId, true);
  }, [activeTabId]);

  const cancelAction = useCallback(() => {
    if (activeTabId) chatStreamManager.confirmActionForTab(activeTabId, false);
  }, [activeTabId]);

  const exportState = useMessageExport({
    process,
    currentThreadId,
    getToken,
    isLoaded,
  });

  const markdownComponents = useMarkdownComponents();

  // Derived values
  const currentThread = threads.find(t => t.id === currentThreadId);
  const chatTitle = currentThread?.title || 'Canvas AI';
  const tickerCount = process?.tickers?.length || 0;
  const currentContext = process?.name
    ? `${process.name}${tickerCount > 0 ? ` • ${process.tickers?.slice(0, 2).join(', ')}${tickerCount > 2 ? '...' : ''}` : ''}`
    : '';

  // Track if this is the initial mount
  const isInitialMount = useRef(true);

  // Handle panel open/close transition - show placeholder during animation
  useLayoutEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    // Panel is toggling - show placeholder during transition
    document.documentElement.dataset.resizing = 'true';
    const timer = setTimeout(() => {
      delete document.documentElement.dataset.resizing;
      window.dispatchEvent(new Event('resize'));
    }, 350); // Slightly longer than 300ms transition
    return () => clearTimeout(timer);
  }, [isOpen]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Clear chat state when opening without a process context (fresh start)
  useEffect(() => {
    if (isOpen && !process && !currentThreadId) {
      clearChatState();
    }
  }, [isOpen, process, currentThreadId, clearChatState]);

  // Shared helper: restore tool events + reasoning from loaded messages
  const restoreToolEventsFromMessages = (loadedMessages: Message[]): ToolEvent[] => {
    const restoredToolEvents: ToolEvent[] = [];
    loadedMessages.forEach((msg, msgIndex) => {
      if (msg.role !== 'assistant') return;
      console.log('[Restore] msg', msgIndex, 'content:', (msg.content || '').length, 'chars, toolEvents:', msg.toolEvents?.length ?? 0, 'reasoning:', msg.reasoningSegments?.length ?? 0);

      // Restore reasoning segments as reasoning-type tool events
      const rTimestamps = (msg as any).reasoningTimestamps || [];
      if (msg.reasoningSegments && msg.reasoningSegments.length > 0) {
        const ts = rTimestamps[0];
        restoredToolEvents.push({
          id: `${msg.id}:reasoning-0`,
          toolType: 'reasoning',
          toolName: 'Reasoning',
          status: 'completed',
          startTime: ts?.startTime ?? Date.now() - 2000,
          endTime: ts?.endTime ?? Date.now() - 1000,
          messageIndex: msgIndex,
          result: msg.reasoningSegments[0],
        });
      }

      if (msg.toolEvents && msg.toolEvents.length > 0) {
        let reasoningIdx = 1;
        // Pair tool_call_started with their tool_call_output by item_id
        const startedEvents = new Map<string, any>();
        const outputEvents = new Map<string, any>();
        msg.toolEvents.forEach((evt: any) => {
          const itemId = evt.event?.item_id;
          if (evt.type === 'tool_call_started' && itemId) startedEvents.set(itemId, evt);
          else if (evt.type === 'tool_call_output' && itemId) outputEvents.set(itemId, evt);
        });

        // Build merged events: started+output pairs, then standalone agent_actions
        const mergedEvents: any[] = [];
        const consumedIds = new Set<string>();
        startedEvents.forEach((startEvt, itemId) => {
          const outEvt = outputEvents.get(itemId);
          mergedEvents.push({ started: startEvt, output: outEvt, itemId });
          consumedIds.add(itemId);
        });
        // Add any agent_action / agent_error events (not paired with started)
        msg.toolEvents.forEach((evt: any) => {
          if (evt.type === 'agent_action' || evt.type === 'agent_error') {
            mergedEvents.push({ action: evt });
          }
        });

        mergedEvents.forEach((merged: any, eventIdx: number) => {
          if (merged.started) {
            const startData = merged.started.event || {};
            const outData = merged.output?.event || {};
            const rawName = startData.tool_name || startData.name || 'Tool';
            const displayName = rawName
              .replace(/_/g, ' ')
              .replace(/([a-z])([A-Z])/g, '$1 $2')
              .replace(/\b\w/g, (c: string) => c.toUpperCase());
            const args = startData.arguments;
            restoredToolEvents.push({
              id: `${msg.id}:${merged.itemId || `evt-${eventIdx}`}`,
              toolType: 'function_call',
              toolName: displayName,
              status: 'completed',
              startTime: startData.startTime ?? Date.now() - 1000,
              endTime: startData.endTime ?? Date.now(),
              messageIndex: msgIndex,
              arguments: args ? (typeof args === 'string' ? args : JSON.stringify(args)) : undefined,
              result: outData.output,
            });
          } else if (merged.action) {
            const savedEvent = merged.action;
            const actionType = savedEvent.action?.type;
            const displayName = savedEvent.toolName || actionType || 'Action';
            const actionParams = savedEvent.action
              ? Object.fromEntries(Object.entries(savedEvent.action).filter(([k]: [string, unknown]) => k !== 'type'))
              : undefined;
            restoredToolEvents.push({
              id: `${msg.id}:${savedEvent.actionId || `action-${eventIdx}`}`,
              toolType: 'function_call',
              toolName: displayName,
              status: savedEvent.type === 'agent_error' ? 'failed' : 'completed',
              startTime: Date.now() - 1000,
              endTime: Date.now(),
              messageIndex: msgIndex,
              arguments: actionParams && Object.keys(actionParams).length > 0 ? JSON.stringify(actionParams) : undefined,
              result: savedEvent.message,
              error: savedEvent.type === 'agent_error' ? savedEvent.message : undefined,
            });
          }

          if (msg.reasoningSegments && reasoningIdx < msg.reasoningSegments.length) {
            const rts = rTimestamps[reasoningIdx];
            restoredToolEvents.push({
              id: `${msg.id}:reasoning-${reasoningIdx}`,
              toolType: 'reasoning',
              toolName: 'Reasoning',
              status: 'completed',
              startTime: rts?.startTime ?? Date.now() - 1000,
              endTime: rts?.endTime ?? Date.now(),
              messageIndex: msgIndex,
              result: msg.reasoningSegments[reasoningIdx],
            });
            reasoningIdx++;
          }
        });
      }
    });

    // Deduplicate by ID
    return restoredToolEvents.filter((event, index, self) => {
      const firstIndex = self.findIndex(e => e.id === event.id);
      if (firstIndex === index) {
        const betterLaterEvent = self.slice(index + 1).find(e => e.id === event.id && e.result);
        return !betterLaterEvent;
      }
      const firstEvent = self[firstIndex];
      return event.result && !firstEvent.result;
    });
  };

  // Load messages for persisted thread on initial open
  useEffect(() => {
    if (isOpen && isLoaded && currentThreadId && messages.length === 0) {
      const threadExists = threads.some(t => t.id === currentThreadId);
      if (threadExists) {
        loadThreadMessages(currentThreadId).then(loadedMessages => {
          const s = useChatStreamStore.getState();
          s.setMessages(currentThreadId!, loadedMessages);
          s.setToolEvents(currentThreadId!, restoreToolEventsFromMessages(loadedMessages));
        });
      }
    }
  }, [isOpen, isLoaded, currentThreadId, threads, messages.length, loadThreadMessages]);

  // Handle send message
  const handleSend = async () => {
    if (!input.trim()) return;
    let tabId = activeTabId;
    if (!tabId) {
      tabId = onEnsureTab?.();
      if (!tabId) return;
    }
    const text = input;
    setInput('');
    await sendMessage(text, tabId);
  };

  // Handle selecting a thread
  const handleSelectThread = async (threadId: string) => {
    setCurrentThreadId(threadId);
    // Load messages into threadStates if not already cached
    const s = useChatStreamStore.getState();
    const existing = s.threadStates[threadId];
    if (!existing || existing.messages.length === 0) {
      const loadedMessages = await loadThreadMessages(threadId);
      s.setMessages(threadId, loadedMessages);
      s.setToolEvents(threadId, restoreToolEventsFromMessages(loadedMessages));
    }
  };

  // Handle creating new thread — old thread's messages stay in threadStates
  const handleNewThread = async () => {
    await createNewThread();
    clearAttachedFiles();
  };

  // Cloud menu handlers
  const handleCloudMenuToggle = () => {
    setShowCloudMenu(!showCloudMenu);
  };

  const handleCloudMenuClose = () => {
    setShowCloudMenu(false);
  };

  const handleGoogleDriveOpen = () => {
    setShowDrivePicker(true);
    setShowCloudMenu(false);
  };

  const handleOneDrivePersonal = () => {
    setOneDriveAccountType('personal');
    setShowOneDrivePicker(true);
    setShowCloudMenu(false);
  };

  const handleOneDriveBusiness = () => {
    setOneDriveAccountType('business');
    setShowOneDrivePicker(true);
    setShowCloudMenu(false);
  };

  const handleSharePoint = () => {
    setOneDriveAccountType('business');
    setShowOneDrivePicker(true);
    setShowCloudMenu(false);
  };

  return (
    <>
      {/* Floating Panel Container */}
      <div
        ref={panelRef}
        className={`claude-chat-panel ${isResizing ? 'select-none' : ''}`}
        style={{
          width: isOpen ? `${panelWidth}px` : '0px',
          flexShrink: 0,
          height: '100%',
          padding: 0,
          pointerEvents: isOpen ? 'auto' : 'none',
          overflow: transitionDone ? 'visible' : 'hidden',
          transition: isResizing ? 'none' : 'width 0.3s ease-out',
        }}
      >
        {/* Inner layout — two separate floating cards like the workspace */}
        <div
          className="h-full flex flex-col gap-2 relative"
          style={{
            opacity: isOpen ? 1 : 0,
            transform: isOpen ? 'translateX(0)' : 'translateX(20px)',
            transition: isResizing ? 'none' : 'opacity 0.3s ease-out, transform 0.3s ease-out',
            minWidth: `${panelWidth}px`,
          }}
        >
          {/* Resize Handle - On the Left */}
          <div
            onMouseDown={startResize}
            className="absolute left-0 top-0 bottom-0 w-2 cursor-col-resize z-[80]"
            style={{ transform: 'translateX(-50%)' }}
            title="Drag to resize"
          />

          {/* Top card — Header */}
          <div
            className="flex-shrink-0"
            style={{
              backgroundColor: 'hsl(var(--cc-bg-100))',
              borderRadius: '1.5rem',
              boxShadow: '0 4px 24px rgba(0,0,0,0.1), 0 1px 4px rgba(0,0,0,0.06)',
              border: '1px solid hsl(30 3.3% 11.8% / 15%)',
            }}
          >
            <ChatHeader
              chatTitle={chatTitle}
              currentContext={currentContext}
              threads={threads}
              currentThreadId={currentThreadId}
              isThreadMenuOpen={isThreadMenuOpen}
              setIsThreadMenuOpen={setIsThreadMenuOpen}
              onSelectThread={handleSelectThread}
              onDeleteThread={deleteThread}
              onUpdateThread={updateThread}
              onNewThread={handleNewThread}
              onClose={onClose}
            />
          </div>

          {/* Bottom card — Messages + Input */}
          <div
            className="flex-1 flex flex-col overflow-hidden"
            style={{
              backgroundColor: 'hsl(var(--cc-bg-100))',
              borderRadius: '1.5rem',
              boxShadow: '0 4px 24px rgba(0,0,0,0.1), 0 1px 4px rgba(0,0,0,0.06)',
              border: '1px solid hsl(30 3.3% 11.8% / 15%)',
            }}
          >
            {/* Messages */}
            <MessageList
              ref={messageListRef}
              messages={messages}
              isLoading={isLoading}
              toolEvents={toolEvents}
              reasoningStreaming={reasoningStreaming}
              reasoningText={reasoningText}
              statusMessage={statusMessage}
              pendingUpdate={pendingUpdate}
              applyingUpdate={applyingUpdate}
              onApplyUpdate={applyPendingUpdate}
              onDismissUpdate={dismissPendingUpdate}
              markdownComponents={markdownComponents}
              exportState={exportState}
              pendingActionConfirmation={pendingActionConfirmation}
              onConfirmAction={confirmAction}
              onCancelAction={cancelAction}
            />

            {/* Input + Controls at Bottom */}
            <div style={{
              padding: '0.5rem',
              flexShrink: 0,
              zIndex: 20,
              position: 'relative',
            }}>
              <ChatInputArea
                inputRef={inputRef}
                input={input}
                setInput={setInput}
                isLoading={isLoading}
                process={process}
                attachedFiles={attachedFiles}
                isDraggingFiles={isDraggingFiles}
                onSend={handleSend}
                onCancel={cancelStream}
                onRemoveFile={handleRemoveFile}
                dragHandlers={dragHandlers}
              >
                <ChatControls
                  selectedModel={selectedModel}
                  isModelMenuOpen={isModelMenuOpen}
                  setIsModelMenuOpen={setIsModelMenuOpen}
                  setSelectedModel={setSelectedModel}
                  isWebSearchEnabled={isWebSearchEnabled}
                  setIsWebSearchEnabled={setIsWebSearchEnabled}
                  uploadingFiles={uploadingFiles}
                  showCloudMenu={showCloudMenu}
                  onFileUploadClick={handleFileUploadClick}
                  onCloudMenuToggle={handleCloudMenuToggle}
                  onCloudMenuClose={handleCloudMenuClose}
                  onGoogleDrive={handleGoogleDriveOpen}
                  onOneDrivePersonal={handleOneDrivePersonal}
                  onOneDriveBusiness={handleOneDriveBusiness}
                  onSharePoint={handleSharePoint}
                  process={process}
                  input={input}
                  isLoading={isLoading}
                  onSend={handleSend}
                  onCancel={cancelStream}
                />
              </ChatInputArea>
            </div>
          </div>
        </div>
      </div>

      {/* Cloud Picker Modals */}
      {showDrivePicker && (
        <GoogleDriveNativePicker
          onSelect={(file) => handleGoogleDriveSelect([file])}
          onClose={() => setShowDrivePicker(false)}
        />
      )}

      {showOneDrivePicker && (
        <OneDriveNativePicker
          onSelect={handleOneDriveSelect}
          onClose={() => setShowOneDrivePicker(false)}
          allowAllFileTypes={true}
          accountType={oneDriveAccountType || 'personal'}
        />
      )}
    </>
  );
}
