/**
 * ChatPanel — composition shell for the chat feature.
 * Delegates to sub-components in messages/ and toolbar/.
 */

import React, { useState, useRef, useEffect, useCallback, useMemo, memo } from "react";
import { AgentMessage, AgentStatus, InteractionMode, EditApprovalMode, PendingOperation } from "../../../shared/types";
import { useMemoryNotebook } from "../../hooks/useMemoryNotebook";

import { SimpleMarkdown, ActivitySection, PlanCard, VbaCodeCard } from "./messages";
import { ChatInput, ChatInputHandle } from "./input";
import { PermissionDialog, MemoryPanel } from "./overlays";
import { PulseLoader, ArrowUp, StopCircle, Copy, Check, FileText, Presentation, SheetIcon, Pencil, PaperclipIcon, BriefcaseIcon, UndoIcon } from "./shared";
import { PlusMenu, ModeMenu, EditModeMenu, ModelMenu } from "./toolbar";
import { Tooltip } from "../Tooltip";

interface UploadedFileInfo {
  file_id: string;
  filename: string;
  thumbnailUrl?: string;
}

interface PortfolioInfo {
  id: string;
  name: string;
  tickers: string[];
}

interface SelectionInfo {
  range: string;
  sheet: string;
  rowCount: number;
  colCount: number;
}

interface ChatPanelProps {
  messages: AgentMessage[];
  onSend: (message: string) => void;
  disabled: boolean;
  status?: AgentStatus;
  workbookId?: string | null;
  chatTitle?: string | null;
  selectedModel: string;
  onModelChange: (modelId: string) => void;
  mode: InteractionMode;
  onModeChange: (mode: InteractionMode) => void;
  onBuildPlan?: (messageIndex: number) => void;
  onUndoPlan?: (messageIndex: number) => void;
  onRejectPlan?: (messageIndex: number) => void;
  onStop?: () => void;
  onFileUpload?: (file: File) => Promise<UploadedFileInfo | null>;
  attachedFiles?: UploadedFileInfo[];
  onRemoveFile?: (fileId: string) => void;
  memorySessionId?: string | null;
  portfolios?: PortfolioInfo[];
  selectedPortfolioId?: string | null;
  onPortfolioChange?: (id: string | null) => void;
  bloombergEnabled?: boolean;
  onBloombergToggle?: (enabled: boolean) => void;
  onToggleActivity?: (messageIndex: number) => void;
  onExportConversation?: () => void;
  selection?: SelectionInfo | null;
  onClearSelection?: () => void;
  editApprovalMode?: EditApprovalMode;
  onEditApprovalModeChange?: (mode: EditApprovalMode) => void;
  pendingOperation?: PendingOperation | null;
  onAllowOnce?: () => void;
  onAlwaysAllow?: () => void;
  onDenyOperation?: () => void;
  onRestoreCheckpoint?: (messageId: string) => void;
  onEditMessage?: (messageIndex: number, content: string, revert: boolean) => void;
}

const ThinkingCollapsible = memo(function ThinkingCollapsible({
  content,
  isActive,
  startTime,
  durationSecs,
}: {
  content: string;
  isActive: boolean;
  startTime: number;
  durationSecs?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [elapsedSecs, setElapsedSecs] = useState(durationSecs ?? 0);
  const finalSecsRef = useRef<number | null>(durationSecs ?? null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isActive) {
      if (finalSecsRef.current === null) {
        finalSecsRef.current = Math.round((Date.now() - startTime) / 1000);
        setElapsedSecs(finalSecsRef.current);
      }
      return;
    }
    const update = () => setElapsedSecs(Math.round((Date.now() - startTime) / 1000));
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [isActive, startTime]);

  const titleBase = isActive ? "Thinking" : "Thought";
  const titleSuffix = !isActive ? ` for ${elapsedSecs}s` : "";

  const toggle = useCallback(() => {
    const el = wrapperRef.current;
    if (!el) { setExpanded(v => !v); return; }
    if (expanded) {
      el.style.overflow = "hidden";
      el.style.height = `${el.scrollHeight}px`;
      el.offsetHeight; // force reflow
      el.style.height = "0px";
      el.style.opacity = "0";
      setExpanded(false);
    } else {
      setExpanded(true);
      userScrolledUpRef.current = false;
      requestAnimationFrame(() => {
        el.style.height = "0px";
        el.style.opacity = "0";
        el.style.overflow = "hidden";
        el.offsetHeight; // force reflow
        el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
        el.style.opacity = "1";
      });
    }
  }, [expanded]);

  const handleTransitionEnd = useCallback((e: React.TransitionEvent<HTMLDivElement>) => {
    if (e.propertyName !== "height" || !wrapperRef.current) return;
    if (expanded) {
      wrapperRef.current.style.height = "auto";
      wrapperRef.current.style.overflowY = "auto";
    }
  }, [expanded]);

  const [thinkingScrolledFromTop, setThinkingScrolledFromTop] = useState(false);

  // Auto-scroll to bottom when new thinking content arrives while expanded & active
  const userScrolledUpRef = useRef(false);
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el || !expanded || !isActive) return;
    // Ensure element is scrollable even during animation
    el.style.overflowY = "auto";
    if (!userScrolledUpRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [content, expanded, isActive]);

  // Track if user manually scrolled up in the thinking box
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const onScroll = () => {
      const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
      userScrolledUpRef.current = !atBottom;
    };
    el.addEventListener("scroll", onScroll);
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  const handleThinkingScroll = useCallback(() => {
    const el = wrapperRef.current;
    if (!el) return;
    setThinkingScrolledFromTop(el.scrollTop > 4);
  }, []);

  return (
    <div style={{ paddingLeft: "4px" }}>
      <button className="thinking-outer-header" onClick={toggle}>
        <div className="thinking-outer-title-group">
          <span className={`thinking-outer-label${isActive ? " timeline-label-shimmer" : ""}`}>
            {titleBase}
            {titleSuffix && <span style={{ opacity: 0.72 }}>{titleSuffix}</span>}
          </span>
          {content && (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
              style={{ transform: expanded ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.2s ease", flexShrink: 0, opacity: 0.5 }}>
              <polyline points="9 18 15 12 9 6" />
            </svg>
          )}
        </div>
      </button>
      <div style={{ position: "relative" }}>
        {expanded && thinkingScrolledFromTop && <div className="thinking-fade-top" />}
        <div ref={wrapperRef} className="thinking-content-wrapper" onTransitionEnd={handleTransitionEnd}
          onScroll={handleThinkingScroll}
          style={expanded ? undefined : { height: 0, opacity: 0, overflow: "hidden" }}>
          <div className="thinking-raw-content">{content}</div>
        </div>
      </div>
    </div>
  );
});

export const ChatPanel: React.FC<ChatPanelProps> = ({
  messages,
  onSend,
  disabled,
  status,
  selectedModel,
  onModelChange,
  mode,
  onModeChange,
  onBuildPlan,
  onUndoPlan,
  onRejectPlan,
  onStop,
  onFileUpload,
  attachedFiles,
  onRemoveFile,
  memorySessionId,
  portfolios,
  selectedPortfolioId,
  onPortfolioChange,
  bloombergEnabled,
  onBloombergToggle,
  onExportConversation,
  selection,
  onClearSelection,
  editApprovalMode = "accept",
  onEditApprovalModeChange,
  pendingOperation,
  onAllowOnce,
  onAlwaysAllow,
  onDenyOperation,
  onRestoreCheckpoint,
  onEditMessage,
}) => {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<ChatInputHandle>(null);
  const silentThinkStartRef = useRef(0);
  const [copyFeedback, setCopyFeedback] = useState<Record<number, boolean>>({});
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [pendingCheckpointRestore, setPendingCheckpointRestore] = useState<string | null>(null);
  const [editingMessageIndex, setEditingMessageIndex] = useState<number | null>(null);
  const [editText, setEditText] = useState("");
  const [pendingEditSend, setPendingEditSend] = useState<{ index: number; content: string; checkpointId?: string } | null>(null);
  const [isSelectionClosing, setIsSelectionClosing] = useState(false);
  const [selectionHeight, setSelectionHeight] = useState<string>("0px");
  const selectionContentRef = useRef<HTMLDivElement>(null);
  const wasSelectionVisible = useRef(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const dragCounterRef = useRef(0);

  const memory = useMemoryNotebook(memorySessionId);

  // File upload handler
  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !onFileUpload) return;
    try {
      await onFileUpload(file);
    } catch {
      // Parent handles errors
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }, [onFileUpload]);

  // Drag-and-drop handlers for images/files
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current++;
    if (e.dataTransfer.types.includes("Files")) setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) setIsDragOver(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    dragCounterRef.current = 0;
    if (!onFileUpload) return;
    const files = Array.from(e.dataTransfer.files);
    for (const file of files.slice(0, 5)) {
      try {
        await onFileUpload(file);
      } catch {
        // Parent handles errors
      }
    }
  }, [onFileUpload]);

  // Paste handler for images from clipboard
  useEffect(() => {
    const handlePaste = async (e: ClipboardEvent) => {
      if (!onFileUpload) return;
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of Array.from(items)) {
        if (item.type.startsWith("image/")) {
          e.preventDefault();
          const file = item.getAsFile();
          if (file) {
            try { await onFileUpload(file); } catch { /* parent handles */ }
          }
          break;
        }
      }
    };
    document.addEventListener("paste", handlePaste);
    return () => document.removeEventListener("paste", handlePaste);
  }, [onFileUpload]);

  // Selection height animation
  useEffect(() => {
    const isNowVisible = !!selection && !isSelectionClosing;
    const wasVisible = wasSelectionVisible.current;

    if (isNowVisible && !wasVisible) {
      requestAnimationFrame(() => {
        const h = selectionContentRef.current?.scrollHeight || 0;
        setSelectionHeight(`${h}px`);
        setTimeout(() => { setSelectionHeight("auto"); }, 220);
      });
      wasSelectionVisible.current = true;
    } else if (isSelectionClosing && wasVisible) {
      const el = selectionContentRef.current;
      if (el) {
        const h = el.scrollHeight;
        setSelectionHeight(`${h}px`);
        // eslint-disable-next-line @typescript-eslint/no-unused-expressions
        el.offsetHeight;
        requestAnimationFrame(() => {
          requestAnimationFrame(() => { setSelectionHeight("0px"); });
        });
      }
      wasSelectionVisible.current = false;
    } else if (!selection && !isSelectionClosing) {
      setSelectionHeight("0px");
      wasSelectionVisible.current = false;
    }
  }, [selection, isSelectionClosing]);

  const isLoading = status === "indexing" || status === "planning" || status === "executing" || status === "validating" || status === "re_indexing" || status === "preparing" || status === "thinking" || status === "writing_excel" || status === "responding" || status === "awaiting_approval";

  // Indices of agent messages that are the last response in a *completed* block
  // (i.e. followed by a user message). The last/current block is handled separately.
  const toolbarIndices = useMemo(() => {
    const indices = new Set<number>();
    let lastAgentInBlock = -1;

    for (let i = 0; i < messages.length; i++) {
      if (messages[i].role === "agent" && messages[i].content) {
        lastAgentInBlock = i;
      }
      if (messages[i].role === "user" && lastAgentInBlock >= 0) {
        indices.add(lastAgentInBlock);
        lastAgentInBlock = -1;
      }
    }

    return indices;
  }, [messages]);

  // Index of the agent message whose toolbar should appear at the very end of the
  // chat (after all messages), so it stays at the bottom even if activity rows follow.
  const lastBlockToolbarIndex = useMemo(() => {
    if (isLoading) return -1;
    let lastAgentInBlock = -1;
    for (let i = 0; i < messages.length; i++) {
      if (messages[i].role === "agent" && messages[i].content) {
        lastAgentInBlock = i;
      }
      if (messages[i].role === "user" && lastAgentInBlock >= 0) {
        lastAgentInBlock = -1;
      }
    }
    return lastAgentInBlock;
  }, [messages, isLoading]);

  // Auto-scroll: only if user is near bottom, respects manual scrolling
  const chatAreaRef = useRef<HTMLDivElement>(null);
  const userScrolledUp = useRef(false);
  const [isScrolledToTop, setIsScrolledToTop] = useState(true);
  const lastMessageCount = useRef(messages.length);

  // Reset stick-to-bottom when user sends a new message
  useEffect(() => {
    const userMessages = messages.filter(m => m.role === "user").length;
    const prevUserMessages = lastMessageCount.current;
    if (userMessages > prevUserMessages) {
      userScrolledUp.current = false;
    }
    lastMessageCount.current = userMessages;
  }, [messages]);

  // Track user scroll direction - any upward scroll disables auto-scroll
  const lastScrollTop = useRef(0);
  useEffect(() => {
    const el = chatAreaRef.current;
    if (!el) return;

    const handleScroll = () => {
      const currentScrollTop = el.scrollTop;
      const isAtBottom = el.scrollHeight - currentScrollTop - el.clientHeight < 2;

      setIsScrolledToTop(currentScrollTop <= 5);

      if (currentScrollTop < lastScrollTop.current - 5) {
        userScrolledUp.current = true;
      }
      if (isAtBottom) {
        userScrolledUp.current = false;
      }

      lastScrollTop.current = currentScrollTop;
    };

    el.addEventListener("scroll", handleScroll);
    return () => el.removeEventListener("scroll", handleScroll);
  }, []);

  // Auto-scroll when content changes (if user hasn't scrolled up)
  useEffect(() => {
    const scrollToBottom = () => {
      if (!userScrolledUp.current) {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
      }
    };
    scrollToBottom();

    const observer = new MutationObserver(scrollToBottom);
    if (chatAreaRef.current) {
      observer.observe(chatAreaRef.current, { childList: true, subtree: true, characterData: true });
    }

    let intervalId: ReturnType<typeof setInterval> | null = null;
    if (isLoading) {
      intervalId = setInterval(scrollToBottom, 100);
    }

    return () => {
      observer.disconnect();
      if (intervalId) clearInterval(intervalId);
    };
  }, [messages, status, isLoading]);

  useEffect(() => { if (!disabled && inputRef.current) inputRef.current.focus(); }, [disabled]);

  const handleSend = () => {
    const t = input.trim();
    if (!t || disabled) return;
    onSend(t);
    setInput("");
    inputRef.current?.clear();
  };

  const handleEditSubmit = () => {
    const t = editText.trim();
    if (!t || editingMessageIndex === null) return;
    const scrollTop = chatAreaRef.current?.scrollTop ?? 0;
    const msg = messages[editingMessageIndex];
    setPendingEditSend({
      index: editingMessageIndex,
      content: t,
      checkpointId: msg?.checkpointId ?? undefined,
    });
    requestAnimationFrame(() => {
      if (chatAreaRef.current) chatAreaRef.current.scrollTop = scrollTop;
    });
  };

  const cancelEdit = () => {
    const scrollTop = chatAreaRef.current?.scrollTop ?? 0;
    setEditingMessageIndex(null);
    setEditText("");
    requestAnimationFrame(() => {
      if (chatAreaRef.current) chatAreaRef.current.scrollTop = scrollTop;
    });
  };

  const handleCopy = useCallback(async (i: number, c: string) => {
    try {
      await navigator.clipboard.writeText(c);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = c;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopyFeedback((p) => ({ ...p, [i]: true }));
    setTimeout(() => setCopyFeedback((p) => ({ ...p, [i]: false })), 800);
  }, []);

  // Derive effective status from message state to handle React 18 batching:
  // when the agent emits explanation tokens between tool batches, status transitions
  // (thinking → responding → executing) get batched into a single render and "responding"
  // is never seen. Instead, check if the last message is an agent text message with content.
  const lastMsgForLabel = messages[messages.length - 1];
  const effectiveStatus = (isLoading && lastMsgForLabel?.role === "agent" && !!lastMsgForLabel.content && status !== "thinking")
    ? "responding"
    : status;

  const statusLabel =
    effectiveStatus === "preparing" ? "Preparing..." :
    effectiveStatus === "indexing" ? "Indexing workbook..." :
    effectiveStatus === "planning" ? "Planning..." :
    effectiveStatus === "thinking" ? "Thinking..." :
    effectiveStatus === "executing" ? "Executing..." :
    effectiveStatus === "writing_excel" ? "Writing to Excel..." :
    effectiveStatus === "responding" ? "Responding..." :
    effectiveStatus === "validating" ? "Validating..." :
    effectiveStatus === "re_indexing" ? "Re-indexing..." :
    effectiveStatus === "awaiting_approval" ? "Awaiting approval..." : "Executing...";

  return (
    <div
      className="claude-chat-root"
      style={{ display: "flex", flexDirection: "column", height: "100%", fontFamily: "var(--font-ui)", position: "relative" }}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Drop overlay */}
      {isDragOver && (
        <div className="drop-overlay">
          <div className="drop-overlay-content">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <span>Drop images or files here</span>
          </div>
        </div>
      )}

      {/* Memory Notebook Panel */}
      {memory.showMemory && (
        <MemoryPanel
          memoryNotes={memory.memoryNotes}
          memoryLoading={memory.memoryLoading}
          newNoteText={memory.newNoteText}
          setNewNoteText={memory.setNewNoteText}
          addNote={memory.addNote}
          removeNote={memory.removeNote}
        />
      )}

      {/* Messages */}
      <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
        {!isScrolledToTop && <div className="chat-fade-top" />}
        <div ref={chatAreaRef} className="chat-area" style={{ height: "100%", overflowY: "auto", padding: "1rem", paddingBottom: pendingOperation ? "220px" : "10rem", background: "hsl(var(--bg-100))" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {messages.map((msg, index) => (
            <div key={msg.id}>

              {msg.role === "user" && (
                <div className="message-user">
                  {editingMessageIndex === index ? (
                    <div className="message-user-bubble message-user-bubble-editing">
                      <textarea
                        className="message-edit-textarea"
                        value={editText}
                        onChange={(e) => {
                          setEditText(e.target.value);
                          e.target.style.height = "auto";
                          e.target.style.height = e.target.scrollHeight + "px";
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleEditSubmit(); }
                          if (e.key === "Escape") cancelEdit();
                        }}
                        autoFocus
                        rows={1}
                        ref={(el) => {
                          if (el && !el.dataset.initialized) {
                            el.dataset.initialized = "1";
                            const st = chatAreaRef.current?.scrollTop ?? 0;
                            el.style.height = "auto";
                            el.style.height = el.scrollHeight + "px";
                            el.setSelectionRange(el.value.length, el.value.length);
                            if (chatAreaRef.current) chatAreaRef.current.scrollTop = st;
                          }
                        }}
                      />
                      <div className="message-edit-actions">
                        <button className="message-edit-cancel" onClick={cancelEdit}>Cancel</button>
                        <button
                          className="message-edit-send"
                          onClick={handleEditSubmit}
                          disabled={!editText.trim()}
                        >
                          Send
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="message-user-bubble">
                        <div className="message-user-text">{msg.content}</div>
                      </div>
                      {!isLoading && (
                        <div className="message-user-actions">
                          <Tooltip label={copyFeedback[index] ? "Copied!" : "Copy"}>
                            <button
                              className="message-user-action-btn"
                              onClick={() => handleCopy(index, msg.content)}
                            >
                              <Copy />
                            </button>
                          </Tooltip>
                          {msg.checkpointId && onRestoreCheckpoint && (
                            <Tooltip label="Restore workbook">
                              <button
                                className="message-user-action-btn"
                                onClick={() => setPendingCheckpointRestore(msg.checkpointId!)}
                              >
                                <UndoIcon />
                              </button>
                            </Tooltip>
                          )}
                          <Tooltip label="Edit message">
                            <button
                              className="message-user-action-btn"
                              onClick={() => {
                                // Preserve scroll position when entering edit mode
                                const scrollTop = chatAreaRef.current?.scrollTop ?? 0;
                                setEditingMessageIndex(index);
                                setEditText(msg.content);
                                requestAnimationFrame(() => {
                                  if (chatAreaRef.current) chatAreaRef.current.scrollTop = scrollTop;
                                });
                              }}
                            >
                              <Pencil />
                            </button>
                          </Tooltip>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {msg.role === "agent" && (
                <article className="message-assistant" style={{ marginBottom: "0.75rem" }}>
                  <div className="message-assistant-content">
                    {isLoading && index === messages.length - 1 && !msg.content && (
                      <PulseLoader label={statusLabel} />
                    )}
                    <div className="message-assistant-text">
                      <SimpleMarkdown content={msg.content} />
                    </div>
                    {msg.content && toolbarIndices.has(index) && (
                      <div className="message-actions">
                        <Tooltip label="Copy">
                          <button onClick={() => handleCopy(index, msg.content)} className="btn btn-ghost btn-sm">
                            {copyFeedback[index] ? <Check /> : <Copy />}
                          </button>
                        </Tooltip>
                        <Tooltip label="PDF">
                          <button className="btn btn-ghost btn-sm"><FileText /></button>
                        </Tooltip>
                        <Tooltip label="PowerPoint">
                          <button className="btn btn-ghost btn-sm"><Presentation /></button>
                        </Tooltip>
                        <Tooltip label="Excel">
                          <button className="btn btn-ghost btn-sm"><SheetIcon /></button>
                        </Tooltip>
                        <Tooltip label="Style">
                          <button className="btn btn-ghost btn-sm"><Pencil /></button>
                        </Tooltip>
                      </div>
                    )}
                  </div>
                </article>
              )}

              {msg.role === "plan" && msg.plan && (
                <PlanCard msg={msg} index={index} onBuildPlan={onBuildPlan} onUndoPlan={onUndoPlan} onRejectPlan={onRejectPlan} />
              )}

              {msg.role === "vba_code" && msg.vbaCode && (
                <VbaCodeCard msg={msg} index={index} />
              )}

              {msg.role === "system" && (
                <div style={{ display: "flex", alignItems: "center", gap: "6px", paddingLeft: "28px" }}>
                  <div style={{ width: "5px", height: "5px", borderRadius: "50%", background: "#9ca3af", flexShrink: 0 }} />
                  <span style={{ fontSize: "11px", color: "#6b7280", fontStyle: "italic" }}>{msg.content}</span>
                </div>
              )}

              {msg.role === "activity" && msg.activity && (
                <div style={{ paddingLeft: "4px" }}>
                  <ActivitySection activity={msg.activity} isPending={!!pendingOperation && index === messages.length - 1} />
                </div>
              )}

              {msg.role === "thinking" && (() => {
                const rawContent = msg.content || msg.thinkingSections?.map(s =>
                  s.content ? `${s.title}\n${s.content}` : s.title
                ).join('\n\n') || "";
                if (!rawContent) return null;
                const isActiveThinking = status === "thinking" && index === messages.length - 1;
                return <ThinkingCollapsible content={rawContent} isActive={isActiveThinking} startTime={msg.timestamp} durationSecs={msg.thinkingDurationSecs} />;
              })()}
            </div>
          ))}

          {(() => {
            const lastMsg = messages[messages.length - 1];
            const activeThinkingShimmer = status === "thinking" && lastMsg?.role === "thinking";
            const activeResponseStreaming = effectiveStatus === "responding" && lastMsg?.role === "agent" && !!lastMsg.content;
            if (!isLoading || activeThinkingShimmer || activeResponseStreaming) {
              silentThinkStartRef.current = 0;
              return null;
            }
            // Silent thinking: show collapsible style (no icon) instead of PulseLoader
            if (status === "thinking") {
              if (silentThinkStartRef.current === 0) silentThinkStartRef.current = Date.now();
              return <ThinkingCollapsible content="" isActive={true} startTime={silentThinkStartRef.current} />;
            }
            silentThinkStartRef.current = 0;
            return (
              <div style={{ paddingLeft: "4px" }}>
                <PulseLoader label={statusLabel} />
              </div>
            );
          })()}

          {/* End-of-chat toolbar — always after all messages so it stays at the bottom */}
          {lastBlockToolbarIndex >= 0 && (
            <div className="message-actions" style={{ paddingLeft: "4px", marginTop: "-10px", marginBottom: "4rem" }}>
              <Tooltip label="Copy">
                <button onClick={() => handleCopy(lastBlockToolbarIndex, messages[lastBlockToolbarIndex].content)} className="btn btn-ghost btn-sm">
                  {copyFeedback[lastBlockToolbarIndex] ? <Check /> : <Copy />}
                </button>
              </Tooltip>
              <Tooltip label="PDF">
                <button className="btn btn-ghost btn-sm"><FileText /></button>
              </Tooltip>
              <Tooltip label="PowerPoint">
                <button className="btn btn-ghost btn-sm"><Presentation /></button>
              </Tooltip>
              <Tooltip label="Excel">
                <button className="btn btn-ghost btn-sm"><SheetIcon /></button>
              </Tooltip>
              <Tooltip label="Style">
                <button className="btn btn-ghost btn-sm"><Pencil /></button>
              </Tooltip>
            </div>
          )}
        </div>
        <div ref={bottomRef} />
      </div>
      </div>

      {/* Input + Controls */}
      <div className="input-area">
        {/* Selection context chip */}
        <div className="selection-context-layer">
          <div
            ref={selectionContentRef}
            className="selection-context-wrapper"
            style={{ height: selectionHeight }}
            onTransitionEnd={() => {
              if (isSelectionClosing && selectionHeight === "0px") {
                setIsSelectionClosing(false);
                onClearSelection?.();
              }
            }}
          >
            {(selection || isSelectionClosing) && (
              <div className="selection-context">
                <div className="selection-context-content">
                  <p className="selection-context-text">
                    {selection?.sheet}!{selection?.range} selected
                  </p>
                  {onClearSelection && (
                    <button
                      onClick={() => setIsSelectionClosing(true)}
                      className="selection-context-dismiss"
                      aria-label="Dismiss"
                      type="button"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" viewBox="0 0 256 256">
                        <path d="M205.66,194.34a8,8,0,0,1-11.32,11.32L128,139.31,61.66,205.66a8,8,0,0,1-11.32-11.32L116.69,128,50.34,61.66A8,8,0,0,1,61.66,50.34L128,116.69l66.34-66.35a8,8,0,0,1,11.32,11.32L139.31,128Z" />
                      </svg>
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Input container */}
        <div className={`input-container ${(selection || isSelectionClosing) ? "input-layer" : ""}`}>

          {/* Attached files */}
          {attachedFiles && attachedFiles.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", padding: "6px 12px 0" }}>
              {attachedFiles.map((f) => (
                <span key={f.file_id} className={f.thumbnailUrl ? "attached-image-chip" : "attached-file-chip"}>
                  {f.thumbnailUrl ? (
                    <img src={f.thumbnailUrl} alt={f.filename} className="attached-thumb" />
                  ) : (
                    <PaperclipIcon />
                  )}
                  <span className="attached-name">{f.filename}</span>
                  {onRemoveFile && (
                    <button onClick={() => onRemoveFile(f.file_id)} className="attached-remove">×</button>
                  )}
                </span>
              ))}
            </div>
          )}

          {/* Portfolio context indicator */}
          {selectedPortfolioId && portfolios && portfolios.length > 0 && (() => {
            const p = portfolios.find((x) => x.id === selectedPortfolioId);
            return p ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", padding: "6px 12px 0" }}>
                <span style={{
                  display: "inline-flex", alignItems: "center", gap: "4px",
                  background: "#dbeafe", borderRadius: "6px", padding: "2px 8px",
                  fontSize: "11px", color: "#1d4ed8",
                }}>
                  <BriefcaseIcon /> {p.name} ({p.tickers.length} tickers)
                  <button onClick={() => onPortfolioChange?.(null)} style={{
                    background: "none", border: "none", cursor: "pointer", padding: "0 2px",
                    color: "#93c5fd", fontSize: "11px", lineHeight: 1,
                  }}>×</button>
                </span>
              </div>
            ) : null;
          })()}

          {/* Input */}
          <div className="input-field-wrapper">
            <ChatInput
              ref={inputRef}
              value={input}
              onChange={setInput}
              onSubmit={handleSend}
              placeholder={disabled ? "Agent is working..." : "Ask about patterns, improvements..."}
              disabled={disabled}
            />
          </div>

          {/* Toolbar */}
          <div className="input-toolbar" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 0.625rem 0.625rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "2px" }}>
              <PlusMenu
                onFileUploadClick={() => fileInputRef.current?.click()}
                webSearchEnabled={webSearchEnabled}
                onWebSearchToggle={() => setWebSearchEnabled(!webSearchEnabled)}
                bloombergEnabled={bloombergEnabled}
                onBloombergToggle={onBloombergToggle}
                portfolios={portfolios}
                selectedPortfolioId={selectedPortfolioId}
                onPortfolioChange={onPortfolioChange}
                showMemory={memory.showMemory}
                onToggleMemory={memory.toggleMemory}
              />
              <input
                ref={fileInputRef}
                type="file"
                style={{ display: "none" }}
                accept=".csv,.xlsx,.xls,.pdf,.txt,.json,.md,.docx,image/*"
                onChange={handleFileSelect}
              />
              <ModeMenu mode={mode} onModeChange={onModeChange} />
              <EditModeMenu editApprovalMode={editApprovalMode} onEditApprovalModeChange={onEditApprovalModeChange} />

              {onExportConversation && (
                <button
                  onClick={onExportConversation}
                  style={{
                    padding: "2px 6px", fontSize: "10px", fontWeight: 600,
                    color: "#9333ea", background: "#faf5ff",
                    border: "1px solid #e9d5ff", borderRadius: "4px",
                    cursor: "pointer", display: "flex", alignItems: "center", gap: "3px",
                    marginLeft: "4px",
                  }}
                  title="Export conversation state (dev)"
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
                  </svg>
                  Dev
                </button>
              )}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <ModelMenu selectedModel={selectedModel} onModelChange={onModelChange} />

              {isLoading ? (
                <Tooltip label="Stop" side="top">
                  <button
                    onClick={onStop}
                    className="btn btn-ghost"
                    style={{ width: "32px", height: "32px", borderRadius: "6px", color: "hsl(var(--text-300))" }}
                    aria-label="Stop"
                  >
                    <StopCircle />
                  </button>
                </Tooltip>
              ) : (
                <button
                  onClick={handleSend}
                  disabled={!input.trim()}
                  className="btn btn-primary btn-primary-send"
                  style={{
                    width: "32px", height: "32px", borderRadius: "6px",
                    background: "hsl(var(--accent-main-000))",
                    color: "hsl(var(--oncolor-100))",
                    boxShadow: input.trim() ? "0 1px 2px rgba(0,0,0,0.1)" : "none",
                    opacity: input.trim() ? 1 : 0.55,
                  }}
                  aria-label="Send message"
                >
                  <ArrowUp />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Permission Dialog */}
      {pendingOperation && (
        <PermissionDialog
          actionDescription={pendingOperation.description}
          toolLabel={pendingOperation.toolLabel}
          onDeny={() => onDenyOperation?.()}
          onAlwaysAllow={() => onAlwaysAllow?.()}
          onAllowOnce={() => onAllowOnce?.()}
        />
      )}

      {/* Edit Message Confirmation */}
      {pendingEditSend && (
        <div className="confirm-dialog-overlay" role="dialog" aria-modal="true" aria-labelledby="confirm-edit-title">
          <div className="confirm-dialog" role="document">
            <div className="confirm-dialog-body">
              <h3 id="confirm-edit-title">Resend from here?</h3>
              <p>Messages after this point will be cleared.{pendingEditSend.checkpointId ? " You can also revert the workbook to its state before this message." : ""}</p>
              <div className="confirm-dialog-buttons">
                <button
                  type="button"
                  className="confirm-dialog-btn confirm-dialog-btn-secondary"
                  onClick={() => setPendingEditSend(null)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="confirm-dialog-btn confirm-dialog-btn-secondary"
                  onClick={() => {
                    const { index, content } = pendingEditSend;
                    setPendingEditSend(null);
                    setEditingMessageIndex(null);
                    setEditText("");
                    onEditMessage?.(index, content, false);
                  }}
                >
                  Continue
                </button>
                {pendingEditSend.checkpointId && (
                  <button
                    type="button"
                    className="confirm-dialog-btn confirm-dialog-btn-danger"
                    onClick={() => {
                      const { index, content } = pendingEditSend;
                      setPendingEditSend(null);
                      setEditingMessageIndex(null);
                      setEditText("");
                      onEditMessage?.(index, content, true);
                    }}
                  >
                    Continue &amp; revert
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Checkpoint Restore Confirmation */}
      {pendingCheckpointRestore && (
        <div className="confirm-dialog-overlay" role="dialog" aria-modal="true" aria-labelledby="confirm-restore-title">
          <div className="confirm-dialog" role="document">
            <div className="confirm-dialog-body">
              <h3 id="confirm-restore-title">Restore workbook?</h3>
              <p>This will revert the workbook to the state it was in at this point in the conversation. Any changes made after this point will be lost.</p>
              <div className="confirm-dialog-buttons">
                <button
                  type="button"
                  className="confirm-dialog-btn confirm-dialog-btn-secondary"
                  onClick={() => setPendingCheckpointRestore(null)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="confirm-dialog-btn confirm-dialog-btn-danger"
                  onClick={() => {
                    onRestoreCheckpoint?.(pendingCheckpointRestore);
                    setPendingCheckpointRestore(null);
                  }}
                >
                  Restore
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
