/**
 * Root React component for the Sentry Excel task pane.
 * No auth gate in dev — goes straight to agent UI.
 * Chat persistence: auto-loads last thread, auto-saves on completion.
 */

import React, { useState, useCallback } from "react";
import { useAgentLoop } from "./hooks/useAgentLoop";
import { useSelectionContext } from "./hooks/useSelectionContext";
import { ChatPanel } from "./components/chat/ChatPanel";
import { AgentProgress } from "./components/AgentProgress";
import { IndexStatus } from "./components/IndexStatus";
import { ChatCircle, Clock, PlusIcon } from "@phosphor-icons/react";
import { Tooltip } from "./components/Tooltip";

const TrashSmall = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
  </svg>
);

const App: React.FC = () => {
  const agent = useAgentLoop();
  const { selection, clearSelection } = useSelectionContext();
  const [showHistory, setShowHistory] = useState(false);

  const currentChatTitle = agent.chatThreads.find(t => t.id === agent.threadId)?.title || null;

  const handleSend = useCallback((message: string) => {
    agent.runAgent(message, selection ? {
      range: selection.range,
      sheet: selection.sheet,
      values: selection.values,
      rowCount: selection.rowCount,
      colCount: selection.colCount,
      headers: selection.headers,
    } : undefined);
    clearSelection();
  }, [agent.runAgent, selection, clearSelection]);

  const isBusy =
    agent.status !== "idle" &&
    agent.status !== "done" &&
    agent.status !== "error" &&
    agent.status !== "awaiting_approval";

  const toggleHistory = useCallback(() => {
    if (!showHistory) {
      // Refresh thread list when opening
      agent.refreshThreads();
    }
    setShowHistory((prev) => !prev);
  }, [showHistory, agent.refreshThreads]);

  const handleLoadThread = useCallback((threadId: string) => {
    agent.loadThread(threadId);
    setShowHistory(false);
  }, [agent.loadThread]);

  const handleDeleteThread = useCallback((e: React.MouseEvent, threadId: string) => {
    e.stopPropagation();
    agent.deleteThread(threadId);
  }, [agent.deleteThread]);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "";
    try {
      const d = new Date(dateStr);
      const now = new Date();
      const diffMs = now.getTime() - d.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      if (diffMins < 1) return "Just now";
      if (diffMins < 60) return `${diffMins}m ago`;
      const diffHrs = Math.floor(diffMins / 60);
      if (diffHrs < 24) return `${diffHrs}h ago`;
      const diffDays = Math.floor(diffHrs / 24);
      if (diffDays < 7) return `${diffDays}d ago`;
      return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    } catch {
      return "";
    }
  };

  return (
    <div className="claude-container" style={styles.root}>
      <div className="claude-panel">
        {/* Header */}
        <div className="claude-header">
          <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
            <img src="/assets/icon-32.png" alt="" style={{ width: "20px", height: "20px", flexShrink: 0 }} />
            {currentChatTitle && (
              <>
                <span style={{ color: "hsl(var(--border-300) / 40%)", fontSize: "11px" }}>|</span>
                <span className="font-small truncate" style={{ maxWidth: "120px", fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif', fontWeight: 600 }} title={currentChatTitle}>
                  {currentChatTitle}
                </span>
              </>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Tooltip label="New chat" side="bottom">
                <button
                  onClick={agent.newChat}
                  disabled={isBusy}
                  aria-label="New chat"
                  className="btn btn-ghost btn-sm"
                  style={{
                    opacity: isBusy ? 0.4 : 1,
                    cursor: isBusy ? "not-allowed" : "pointer",
                    padding: "4px",
                    color: "hsl(var(--text-300))",
                  }}
                >
                  <span style={{ position: "relative", display: "inline-flex" }}>
                    <ChatCircle size={16} weight="regular" />
                    <PlusIcon size={8} weight="bold" style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)" }} />
                  </span>
                </button>
              </Tooltip>
            {/* History button */}
            <Tooltip label="Chat history" side="bottom">
              <button
                onClick={toggleHistory}
                aria-label="Chat history"
                className={`btn btn-ghost btn-sm ${showHistory ? "selected" : ""}`}
                style={{
                  cursor: "pointer",
                  padding: "4px",
                  color: "hsl(var(--text-300))",
                  background: showHistory ? "hsl(var(--bg-300))" : undefined,
                }}
              >
                <Clock size={16} weight="regular" />
              </button>
            </Tooltip>
            <IndexStatus status={agent.status} workbookId={agent.workbookId} />
          </div>
        </div>

        {/* Chat history panel — slides down from header */}
        {showHistory && (
          <>
            {/* Backdrop */}
            <div className="dropdown-backdrop" onClick={() => setShowHistory(false)} />
            <div className="dropdown-menu" style={{
              position: "fixed", top: "60px", right: "1rem", left: "auto",
              width: "220px", bottom: "auto", maxHeight: "none", overflowY: "visible",
            }}>
              <div className="font-caption" style={{ padding: "8px 12px 4px", color: "hsl(var(--text-400))" }}>
                Recent Chats
              </div>
              {agent.chatThreads.length === 0 ? (
                <div className="font-small" style={{ padding: "16px 12px", textAlign: "center", color: "hsl(var(--text-400))" }}>
                  No previous chats
                </div>
              ) : (
                <div style={{ maxHeight: "280px", overflowY: "auto" }}>
                  {agent.chatThreads.map((thread) => {
                    const isActive = thread.id === agent.threadId;
                    return (
                      <button
                        key={thread.id}
                        onClick={() => handleLoadThread(thread.id)}
                        disabled={isBusy}
                        className={`dropdown-item ${isActive ? "selected" : ""}`}
                        style={{ opacity: isBusy ? 0.5 : 1, cursor: isBusy ? "not-allowed" : "pointer" }}
                      >
                        <div style={{ flex: 1, minWidth: 0, textAlign: "left" }}>
                          <div className={`font-small truncate`} style={{ fontWeight: isActive ? 500 : 400 }}>
                            {thread.title || "Untitled chat"}
                          </div>
                          <div className="font-caption">
                            {thread.message_count} msgs{" "}
                            {thread.updated_at && <span>· {formatDate(thread.updated_at)}</span>}
                          </div>
                        </div>
                        <button
                          onClick={(e) => handleDeleteThread(e, thread.id)}
                          disabled={isBusy}
                          title="Delete chat"
                          className="btn btn-ghost btn-sm"
                          style={{ opacity: isBusy ? 0.5 : 1 }}
                        >
                          <TrashSmall />
                        </button>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </>
        )}

        {/* Messages + inline plan cards */}
        <div style={styles.body}>
          <ChatPanel
            messages={agent.messages}
            onSend={handleSend}
            disabled={isBusy}
            status={agent.status}
            workbookId={agent.workbookId}
            chatTitle={currentChatTitle}
            selectedModel={agent.selectedModel}
            onModelChange={agent.setModel}
            mode={agent.mode}
            onModeChange={agent.setMode}
            onBuildPlan={agent.buildPlan}
            onUndoPlan={agent.undoPlan}
            onRejectPlan={agent.rejectPlan}
            onStop={agent.stopAgent}
            onFileUpload={agent.onFileUpload}
            attachedFiles={agent.attachedFiles}
            onRemoveFile={agent.onRemoveFile}
            memorySessionId={agent.threadId}
            portfolios={agent.portfolios}
            selectedPortfolioId={agent.selectedPortfolioId}
            onPortfolioChange={agent.selectPortfolio}
            bloombergEnabled={agent.bloombergEnabled}
            onBloombergToggle={agent.setBloombergEnabled}
            onToggleActivity={agent.toggleActivityCollapsed}
            onExportConversation={process.env.NODE_ENV === "development" ? agent.exportConversation : undefined}
            selection={selection}
            onClearSelection={clearSelection}
            editApprovalMode={agent.editApprovalMode}
            onEditApprovalModeChange={agent.setEditApprovalMode}
            pendingOperation={agent.pendingOperation}
            onAllowOnce={agent.allowOnce}
            onAlwaysAllow={agent.alwaysAllow}
            onDenyOperation={agent.denyOperation}
            onRestoreCheckpoint={agent.restoreCheckpoint}
            onEditMessage={agent.editMessage}
          />
        </div>

        <AgentProgress
          plan={agent.currentPlan}
          currentStep={agent.currentStep}
          status={agent.status}
        />
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  root: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    position: "relative",
  },
  body: {
    flex: 1,
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
  },
};

export default App;
