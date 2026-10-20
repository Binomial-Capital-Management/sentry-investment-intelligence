import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useChat } from '@/hooks/useChat';
import { Paperclip, ArrowUp, Loader2, Compass, Square, Brain, Code, Folder, Columns, Plus, ChevronRight, ChevronDown, FileText, X, Quote } from 'lucide-react';
import MemoryIcon from '@/components/Icons/MemoryIcon';
import { useChatStore } from '@stores/chatStore';
import { usePortfolioStore } from '@stores/portfolioStore';
import { useUIStore } from '@stores/uiStore';
import { useMessageQueueStore, QueuedMessage } from '@/stores/messageQueueStore';
import AgentModeSelector from './AgentModeSelector';
import ToolPrioritySelector from './ToolPrioritySelector';
import PortfolioSelector from './PortfolioSelector';
import QueuedMessages from './QueuedMessages';
import TickerMention, { MentionedTicker } from './TickerMention';
import { uploadService, UploadedFile } from '@services/upload';
import { GoogleDriveNativePicker } from '@/components/KnowledgeGraph/GoogleDriveNativePicker';
import { OneDriveNativePicker } from '@/components/KnowledgeGraph/OneDriveNativePicker';
import { getModelById } from '@/config/models';
import TokenUsageRing from './TokenUsageRing';
import memoryApiService from '@/services/memoryApi';
import toast from 'react-hot-toast';
import googleDriveIcon from '@/assets/connector-logos/google-drive.png';
import oneDriveIcon from '@/assets/connector-logos/one-drive.png';
const sharepointIcon = '/connector-logos/sharepoint-logo.png';
import { ensureOneDriveConnection } from '@/utils/onedrive';

// Logo.dev token for company logos
const logoDevToken = (import.meta as any).env?.VITE_LOGODEV_TOKEN;

const getCompanyLogoUrl = (symbol: string) => {
  if (!logoDevToken) {
    return `https://logo.clearbit.com/${symbol.toLowerCase()}.com`;
  }
  return `https://img.logo.dev/ticker/${symbol.toUpperCase()}?token=${logoDevToken}`;
};

interface InputAreaProps {
  externalInput?: string;
  onInputChange?: (value: string) => void;
}

const MAX_ATTACHMENTS = 5;

const InputArea = ({ externalInput, onInputChange }: InputAreaProps = {}) => {
  // Enable all features (cloud connectors, portfolios, etc.)
  const disabled = false;

  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLDivElement>(null);
  const portfolioDropdownRef = useRef<HTMLDivElement>(null);

  const { sendMessage, cancelMessage } = useChat();
  const { addToQueue } = useMessageQueueStore();
  const {
    currentThreadId,
    setAgentMode,
    getCurrentThreadModel,
    getCurrentThreadAgentMode,
    selectedChatPortfolioId,
    setSelectedChatPortfolioId,
    threads,
    deepAnalysisMode,
    setDeepAnalysisMode,
    prioritizedTools,
    setPrioritizedTools,
    draftMessages,
    setDraftMessage,
  } = useChatStore();
  const { savedPortfolios, loadPortfolios } = usePortfolioStore();
  const { analystMode, toggleAnalystMode } = useUIStore();

  // Get per-thread model selection
  const selectedModel = getCurrentThreadModel();

  // Get per-thread agent mode (not global)
  const currentAgentMode = getCurrentThreadAgentMode();

  // File attachments with proper typing
  const [attachedFiles, setAttachedFiles] = useState<UploadedFile[]>([]);
  const [attachedFileIds, setAttachedFileIds] = useState<string[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState(false);
  const [searchMode, setSearchMode] = useState(false);
  const [showPortfolioDropdown, setShowPortfolioDropdown] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [showOptionsMenu, setShowOptionsMenu] = useState(false);
  const [showConnectorsMenu, setShowConnectorsMenu] = useState(false);
  const [showDrivePicker, setShowDrivePicker] = useState(false);
  const [showOneDrivePicker, setShowOneDrivePicker] = useState(false);
  const [oneDriveAccountType, setOneDriveAccountType] = useState<'personal' | 'business' | 'sharepoint' | null>(null);
  const [isCompassHovered, setIsCompassHovered] = useState(false);
  const toggleMemoryPanel = useUIStore((s: any) => s.toggleMemoryPanel);
  const setStudioPanelOpen = useUIStore((s: any) => s.setStudioPanelOpen);
  // Ticker mention state - use both state and ref for immediate access
  const [mentionedTickers, setMentionedTickers] = useState<MentionedTicker[]>([]);
  const mentionedTickersRef = useRef<MentionedTicker[]>([]);
  const [cursorPosition, setCursorPosition] = useState(0);
  const optionsMenuRef = useRef<HTMLDivElement>(null);
  const inputContainerRef = useRef<HTMLDivElement>(null);
  const connectorsMenuTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const backgroundOverlayRef = useRef<HTMLDivElement>(null);

  // Undo/redo history
  const historyRef = useRef<string[]>([]);
  const historyIndexRef = useRef(-1);
  const isUndoRedoRef = useRef(false);

  // Sources count state
  const [sourcesCount, setSourcesCount] = useState(0);
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const memoryPanelOpen = useUIStore((s: any) => s.memoryPanelOpen);
  
  // Filing citations from sidebar
  const filingCitations = useUIStore((s: any) => s.filingCitations);
  const removeFilingCitation = useUIStore((s: any) => s.removeFilingCitation);
  const clearFilingCitations = useUIStore((s: any) => s.clearFilingCitations);

  // Fetch sources count when thread changes
  useEffect(() => {
    const fetchSourcesCount = async () => {
      if (!currentThreadId) {
        setSourcesCount(0);
        return;
      }
      try {
        const response = await memoryApiService.getNotes(currentThreadId);
        setSourcesCount(response.notes?.length || 0);
      } catch {
        setSourcesCount(0);
      }
    };
    fetchSourcesCount();
    // Refetch when memory panel closes (in case sources changed)
  }, [currentThreadId, memoryPanelOpen]);

  // Check if any search model (Perplexity) is selected
  const currentModel = getModelById(selectedModel);
  const isPerplexity = currentModel?.category === 'search';
  const isDeepSeek = selectedModel ? selectedModel.includes('deepseek') : false;

  // Auto-enable search mode for Perplexity models
  const effectiveSearchMode = !isDeepSeek && (isPerplexity || searchMode);

  // Check if any message is currently streaming
  const currentThread = threads.find(t => t.id === currentThreadId);
  const isStreaming = currentThread?.messages.some(m => m.isStreaming) || false;

  // Dynamic placeholder text
  const placeholderText = isPerplexity ? 'Search the web with Perplexity...' :
                         (!isDeepSeek && searchMode) ? 'Search portfolios, calculations, market data...' :
                         'How can I help you?';

  useEffect(() => {
    if (isDeepSeek && searchMode) {
      setSearchMode(false);
    }
  }, [isDeepSeek, searchMode]);

  // Simple debounce function
  const debounce = useCallback((func: Function, wait: number) => {
    let timeout: NodeJS.Timeout;
    return (...args: any[]) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(null, args), wait);
    };
  }, []);

  // Save to history (called on input changes)
  const saveToHistory = useCallback((text: string) => {
    if (isUndoRedoRef.current) {
      // Don't save if we're in the middle of undo/redo
      return;
    }

    // Remove any future history if we're not at the end
    if (historyIndexRef.current < historyRef.current.length - 1) {
      historyRef.current = historyRef.current.slice(0, historyIndexRef.current + 1);
    }

    // Add to history
    historyRef.current.push(text);
    historyIndexRef.current = historyRef.current.length - 1;

    // Limit history size to 50 entries
    if (historyRef.current.length > 50) {
      historyRef.current.shift();
      historyIndexRef.current--;
    }
  }, []);

  // Debounced history save (500ms delay to avoid saving every keystroke)
  const debouncedSaveToHistory = useMemo(
    () => debounce(saveToHistory, 500),
    [debounce, saveToHistory],
  );

  // Debounced draft saving
  const saveDraft = useCallback(
    debounce((threadId: string, message: string) => {
      if (threadId) {
        setDraftMessage(threadId, message);
      }
    }, 500),
    [setDraftMessage, debounce],
  );

  // Handle external input updates (from PromptLibrary)
  useEffect(() => {
    if (externalInput !== undefined && externalInput !== '' && externalInput !== input) {
      setInput(externalInput);
      if (textareaRef.current) {
        textareaRef.current.textContent = externalInput;
        // Focus the input and move cursor to end
        textareaRef.current.focus();
        const range = document.createRange();
        const sel = window.getSelection();
        range.selectNodeContents(textareaRef.current);
        range.collapse(false);
        sel?.removeAllRanges();
        sel?.addRange(range);
      }
      // Notify parent of change
      onInputChange?.(externalInput);
    }
  }, [externalInput]);

  // Track previous thread ID to detect actual thread switches
  const prevThreadIdRef = useRef<string | null>(null);

  // Restore draft when switching threads - ONLY clear mentioned tickers on actual thread switch
  useEffect(() => {
    const isThreadSwitch = prevThreadIdRef.current !== null && prevThreadIdRef.current !== currentThreadId;

    if (isThreadSwitch) {
      // Clear undo history and mentioned tickers ONLY when actually switching threads
      historyRef.current = [];
      historyIndexRef.current = -1;
      mentionedTickersRef.current = [];
      setMentionedTickers([]);
    }

    prevThreadIdRef.current = currentThreadId;

    if (currentThreadId && draftMessages[currentThreadId]) {
      const draftMessage = draftMessages[currentThreadId];
      // Only restore draft on actual thread switch, not on every draftMessages change
      if (isThreadSwitch || !input) {
        setInput(draftMessage);
        if (textareaRef.current && textareaRef.current.textContent !== draftMessage) {
          textareaRef.current.textContent = draftMessage;
        }
        historyRef.current = [draftMessage];
        historyIndexRef.current = 0;
      }
    } else if (isThreadSwitch && (!externalInput || externalInput === '')) {
      setInput('');
      if (textareaRef.current && textareaRef.current.textContent !== '') {
        textareaRef.current.textContent = '';
      }
    }
  }, [currentThreadId, draftMessages, externalInput]);


  // Save draft when input changes
  useEffect(() => {
    if (currentThreadId) {
      saveDraft(currentThreadId, input);
    }
  }, [input, currentThreadId, saveDraft]);

  // Initialize history with initial input value
  useEffect(() => {
    if (historyRef.current.length === 0 && input) {
      historyRef.current = [input];
      historyIndexRef.current = 0;
    }
  }, [input]);

  // Load portfolios on mount
  useEffect(() => {
    loadPortfolios();
  }, [loadPortfolios]);

  // Undo function
  const handleUndo = useCallback(() => {
    if (historyIndexRef.current > 0) {
      isUndoRedoRef.current = true;
      historyIndexRef.current--;
      const previousText = historyRef.current[historyIndexRef.current];
      setInput(previousText);
      if (textareaRef.current) {
        textareaRef.current.textContent = previousText;
      }
      setTimeout(() => {
        isUndoRedoRef.current = false;
      }, 0);
    }
  }, []);

  // Redo function
  const handleRedo = useCallback(() => {
    if (historyIndexRef.current < historyRef.current.length - 1) {
      isUndoRedoRef.current = true;
      historyIndexRef.current++;
      const nextText = historyRef.current[historyIndexRef.current];
      setInput(nextText);
      if (textareaRef.current) {
        textareaRef.current.textContent = nextText;
      }
      setTimeout(() => {
        isUndoRedoRef.current = false;
      }, 0);
    }
  }, []);

  // Track cursor position for ticker mentions - improved calculation
  const updateCursorPosition = useCallback(() => {
    if (!textareaRef.current) return;

    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;

    try {
      const range = selection.getRangeAt(0);
      const textContent = textareaRef.current.textContent || '';

      // Create a range from start to cursor
      const preCaretRange = range.cloneRange();
      preCaretRange.selectNodeContents(textareaRef.current);
      preCaretRange.setEnd(range.endContainer, range.endOffset);

      // Use textContent length for accurate position
      const position = preCaretRange.toString().length;

      // Clamp position to valid range
      const clampedPosition = Math.min(Math.max(0, position), textContent.length);
      setCursorPosition(clampedPosition);
    } catch (error) {
      console.warn('Error calculating cursor position:', error);
      // Fallback to end of text
      setCursorPosition((textareaRef.current.textContent || '').length);
    }
  }, []);

  // Handle ticker selection from mention dropdown
  const handleTickerSelect = useCallback((ticker: MentionedTicker, startIndex: number, endIndex: number) => {
    // Add to confirmed tickers list (for highlighting) - update ref FIRST for immediate access
    let newTickers = mentionedTickersRef.current;
    if (!newTickers.find(t => t.symbol === ticker.symbol)) {
      newTickers = [...newTickers, ticker];
      mentionedTickersRef.current = newTickers;
      setMentionedTickers(newTickers);
    }

    // Replace @query with @SYMBOL (keeps it in text but confirmed)
    const newInput = input.slice(0, startIndex) + `@${ticker.symbol} ` + input.slice(endIndex);

    // Update both the contenteditable and state
    if (textareaRef.current) {
      textareaRef.current.textContent = newInput;
    }
    setInput(newInput);

    // Move cursor after the inserted ticker + space
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        const range = document.createRange();
        const sel = window.getSelection();
        const textNode = textareaRef.current.firstChild || textareaRef.current;
        const pos = Math.min(startIndex + ticker.symbol.length + 2, (textNode.textContent || '').length);
        if (textNode.nodeType === Node.TEXT_NODE) {
          range.setStart(textNode, pos);
          range.setEnd(textNode, pos);
        } else {
          range.selectNodeContents(textareaRef.current);
          range.collapse(false);
        }
        sel?.removeAllRanges();
        sel?.addRange(range);
      }
    }, 20);
  }, [input]);

  // Remove a mentioned ticker
  const removeMentionedTicker = useCallback((symbol: string) => {
    mentionedTickersRef.current = mentionedTickersRef.current.filter(t => t.symbol !== symbol);
    setMentionedTickers(mentionedTickersRef.current);
  }, []);

  // Sync mentioned tickers with input - remove tickers that were deleted from text
  useEffect(() => {
    if (mentionedTickersRef.current.length === 0) return;

    const remainingTickers = mentionedTickersRef.current.filter(ticker => {
      const regex = new RegExp(`@${ticker.symbol}(?=\\s|$)`, 'i');
      return regex.test(input);
    });

    if (remainingTickers.length !== mentionedTickersRef.current.length) {
      mentionedTickersRef.current = remainingTickers;
      setMentionedTickers(remainingTickers);
    }
  }, [input]);

  // Close portfolio dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (portfolioDropdownRef.current && !portfolioDropdownRef.current.contains(event.target as Node)) {
        setShowPortfolioDropdown(false);
      }
      if (optionsMenuRef.current && !optionsMenuRef.current.contains(event.target as Node)) {
        setShowOptionsMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();

    if (!input.trim() && mentionedTickers.length === 0) return;

    let message = input.trim();

    // Prepend mentioned tickers to message for context
    if (mentionedTickers.length > 0) {
      const tickerList = mentionedTickers.map(t => t.symbol).join(', ');
      message = `[Tickers: ${tickerList}] ${message}`;
    }

    // Append filing citations as hidden context (full text, hidden in UI via regex)
    if (filingCitations && filingCitations.length > 0) {
      const citationBlocks = filingCitations.map((c: any) => 
        `<!-- CITATION:${c.ticker || ''}:${c.formType || ''} -->\n${c.text}\n<!-- /CITATION -->`
      ).join('\n');
      message = `${message}\n\n${citationBlocks}`;
      clearFilingCitations();
    }

    // Prepend search command if in search mode (including Perplexity)
    if (effectiveSearchMode) {
      message = `/search ${message}`;
      // Only reset manual search mode, not Perplexity-triggered search
      if (!isPerplexity) {
        setSearchMode(false);
      }
    }

    setInput('');

    // Clear the contentEditable div content and reset height
    if (textareaRef.current) {
      textareaRef.current.innerHTML = '';  // Clear the HTML content
      textareaRef.current.textContent = ''; // Ensure text is also cleared
      textareaRef.current.style.height = 'auto';
      // Keep focus for better UX
      textareaRef.current.focus();
    }

    // Clear draft for current thread
    if (currentThreadId) {
      setDraftMessage(currentThreadId, '');
    }

    // Clear undo history
    historyRef.current = [];
    historyIndexRef.current = -1;

    // If streaming is active, queue the message instead of sending directly
    if (isStreaming && currentThreadId) {
      addToQueue(currentThreadId, message, attachedFileIds, selectedChatPortfolioId, attachedFiles);
      // Clear files and mentioned tickers after queueing
      setAttachedFiles([]);
      setAttachedFileIds([]);
      mentionedTickersRef.current = [];
      setMentionedTickers([]);
      return;
    }

    // Send message with file IDs and optional portfolio ID (pass attachments for display)
    await sendMessage(message, true, attachedFileIds, selectedChatPortfolioId, attachedFiles);
    // Clear files and mentioned tickers after successful send
    setAttachedFiles([]);
    setAttachedFileIds([]);
    mentionedTickersRef.current = [];
    setMentionedTickers([]);
  };

  // Handle "Send Now" from queue - cancels current stream and sends immediately
  const handleSendNow = useCallback(async (queuedMessage: QueuedMessage) => {
    if (!currentThreadId) return;
    
    // Cancel the current streaming response and add "send_now" artifact
    if (isStreaming) {
      const store = useChatStore.getState();
      const thread = store.threads.find((t) => t.id === currentThreadId);
      const streamingMessage = thread?.messages.find((m) => m.isStreaming);
      
      // Add artifact to show this was skipped for a priority message
      if (streamingMessage) {
        store.addArtifact(currentThreadId, {
          id: `${currentThreadId}-sendnow-${Date.now()}`,
          type: 'cancelled',
          createdAt: new Date(),
          data: {
            reason: 'send_now',
            partialContent: streamingMessage.content,
          },
        });
      }
      
      if (cancelMessage) {
        cancelMessage();
      }
      // Brief delay to let cancellation take effect
      await new Promise(resolve => setTimeout(resolve, 150));
    }
    
    // Send the queued message immediately
    await sendMessage(
      queuedMessage.content,
      true,
      queuedMessage.fileIds || [],
      queuedMessage.portfolioId,
      queuedMessage.attachments
    );
  }, [currentThreadId, isStreaming, cancelMessage, sendMessage]);

  // Handle file uploads (shared logic for drag-drop and click)
  const handleFileUpload = async (files: File[]) => {
    if (files.length === 0) return;

    const remainingSlots = MAX_ATTACHMENTS - attachedFiles.length;
    if (files.length > remainingSlots) {
      toast.error(`Only ${remainingSlots} more file(s) can be attached (${MAX_ATTACHMENTS} max)`);
      files = files.slice(0, remainingSlots);
    }

    setUploadingFiles(true);
    try {
      const uploadedFiles = await uploadService.uploadFiles(files);
      setAttachedFiles(prev => [...prev, ...uploadedFiles]);
      const newFileIds = uploadedFiles.map(f => f.id);
      setAttachedFileIds(prev => [...prev, ...newFileIds]);
      toast.success(`Uploaded ${uploadedFiles.length} file(s)`);
    } catch (err) {
      console.error('Failed to upload files:', err);
      toast.error('Failed to upload files');
    } finally {
      setUploadingFiles(false);
    }
  };

  const handleOpenDrivePicker = () => {
    setShowOptionsMenu(false);
    if (attachedFiles.length >= MAX_ATTACHMENTS) {
      toast.error(`Maximum ${MAX_ATTACHMENTS} files allowed per message`);
      return;
    }
    setShowDrivePicker(true);
  };

  const handleOpenOneDrivePicker = async () => {
    setShowOptionsMenu(false);
    if (attachedFiles.length >= MAX_ATTACHMENTS) {
      toast.error(`Maximum ${MAX_ATTACHMENTS} files allowed per message`);
      return;
    }
    const { connected } = await ensureOneDriveConnection();
    if (!connected) {
      return;
    }
    setShowOneDrivePicker(true);
  };

  // Drag and drop handlers
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // Only set dragging to false if we're leaving the drop zone container
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX;
    const y = e.clientY;

    // Check if mouse is outside the container bounds
    if (x <= rect.left || x >= rect.right || y <= rect.top || y >= rect.bottom) {
      setIsDragging(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (attachedFiles.length >= MAX_ATTACHMENTS) {
      toast.error(`Maximum ${MAX_ATTACHMENTS} files allowed per message`);
      return;
    }

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      await handleFileUpload(files);
    }
  };

  return (
    <div style={{ background: '#FFFFFF' }}>
      <style>
        {`
          [contenteditable="true"]:empty:before {
            content: attr(data-placeholder);
            color: #9ca3af;
            pointer-events: none;
          }
        `}
      </style>

      <div style={{ padding: '20px 0' }}>
        <div style={{ maxWidth: 'min(60rem, 95vw)', margin: '0 auto', padding: '0 16px' }}>
          {/* Queued Messages Display */}
          <QueuedMessages threadId={currentThreadId} onSendNow={handleSendNow} />
          
          {/* Sources indicator - expandable */}
          {sourcesCount > 0 && (
            <div style={{ marginBottom: '6px', paddingLeft: '4px' }}>
              <button
                type="button"
                onClick={() => setSourcesExpanded(!sourcesExpanded)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: '2px 4px',
                  borderRadius: '4px',
                  fontSize: '12px',
                  color: '#6b7280',
                }}
              >
                {sourcesExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                <span style={{ fontWeight: 500 }}>{sourcesCount} Files</span>
              </button>
              {sourcesExpanded && (
                <div style={{ 
                  display: 'flex', 
                  flexDirection: 'column',
                  gap: '2px', 
                  marginTop: '4px',
                  marginLeft: '20px',
                  fontSize: '11px',
                }}>
                  <span 
                    style={{ color: '#6b7280', cursor: 'pointer' }}
                    onClick={() => toggleMemoryPanel()}
                  >
                    Memory notes
                  </span>
                  <span 
                    style={{ color: '#6b7280', cursor: 'pointer' }}
                    onClick={() => toggleMemoryPanel()}
                  >
                    SEC filings
                  </span>
                  <span 
                    style={{ color: '#6b7280', cursor: 'pointer' }}
                    onClick={() => toggleMemoryPanel()}
                  >
                    Datasets
                  </span>
                  <span 
                    style={{ color: '#9ca3af', textDecoration: 'underline', cursor: 'pointer', marginTop: '2px' }}
                    onClick={() => toggleMemoryPanel()}
                  >
                    Review
                  </span>
                </div>
              )}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div style={{ position: 'relative' }}>

              {/* Clean input area with rounded corners and subtle border */}
              <div
                ref={inputContainerRef}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                style={{
                  display: 'flex',
                  flexDirection: (selectedChatPortfolioId || attachedFiles.length > 0 || (filingCitations && filingCitations.length > 0)) ? 'column' : 'row',
                  alignItems: (selectedChatPortfolioId || attachedFiles.length > 0 || (filingCitations && filingCitations.length > 0)) ? 'stretch' : 'center',
                  background: isDragging ? '#eff6ff' : '#FFFFFF',
                  border: isDragging ? '2px dashed #3b82f6' : '1px solid #d1d5db',
                  borderRadius: '24px',
                  padding: (selectedChatPortfolioId || attachedFiles.length > 0 || (filingCitations && filingCitations.length > 0)) ? '14px 18px' : '12px 12px 12px 18px',
                  minHeight: (selectedChatPortfolioId || attachedFiles.length > 0 || (filingCitations && filingCitations.length > 0)) ? '80px' : '52px',
                  gap: (selectedChatPortfolioId || attachedFiles.length > 0 || (filingCitations && filingCitations.length > 0)) ? '8px' : '8px',
                  boxShadow: isDragging ? '0 4px 12px rgba(59, 130, 246, 0.15)' : '0 1px 2px rgba(0, 0, 0, 0.05)',
                  transition: 'all 0.2s',
                  position: 'relative',
                }}
              >
                {/* Drag overlay */}
                {isDragging && (
                  <div style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'rgba(59, 130, 246, 0.05)',
                    borderRadius: '24px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    pointerEvents: 'none',
                    zIndex: 10,
                  }}>
                    <div style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '8px',
                    }}>
                      <Paperclip size={32} style={{ color: '#3b82f6' }} />
                      <span style={{
                        fontSize: '14px',
                        fontWeight: 500,
                        color: '#3b82f6',
                      }}>
                        Drop files here
                      </span>
                    </div>
                  </div>
                )}

                {/* Attachments, Citations, and Portfolio selector - appears at top when present */}
                {(attachedFiles.length > 0 || selectedChatPortfolioId || (filingCitations && filingCitations.length > 0)) && (
                  <div style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '8px',
                    alignItems: 'flex-start',
                  }}>
                    {/* Filing citations - inline with attachments */}
                    {filingCitations && filingCitations.map((citation: any) => (
                      <div
                        key={citation.id}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '4px 8px',
                          background: '#fef3c7',
                          border: '1px solid #fcd34d',
                          borderRadius: '12px',
                          fontSize: '12px',
                          color: '#92400e',
                          maxWidth: '200px',
                        }}
                        title={citation.text}
                      >
                        <Quote size={11} style={{ flexShrink: 0 }} />
                        <span style={{ 
                          overflow: 'hidden', 
                          textOverflow: 'ellipsis', 
                          whiteSpace: 'nowrap',
                        }}>
                          {citation.ticker || citation.formType || 'cite'}_{citation.id.slice(-6)}
                        </span>
                        <button
                          type="button"
                          onClick={() => removeFilingCitation(citation.id)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: '2px',
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            color: '#b45309',
                            borderRadius: '4px',
                            flexShrink: 0,
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.background = '#fde68a'}
                          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ))}
                    {/* File attachments display */}
                    {attachedFiles.map((file, idx) => (
                      <div key={idx} style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '4px 8px',
                        background: '#f3f4f6',
                        border: '1px solid #d1d5db',
                        borderRadius: '12px',
                        fontSize: '14px',
                        color: '#6b7280',
                        maxWidth: '240px',
                      }}>
                        {file.source === 'google_drive' ? (
                          <img src={googleDriveIcon} alt="Google Drive" style={{ width: '14px', height: 'auto' }} />
                        ) : file.source === 'onedrive' ? (
                          <img src={oneDriveIcon} alt="OneDrive" style={{ width: '14px', height: 'auto' }} />
                        ) : (
                          <Paperclip size={12} />
                        )}
                        <span style={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}>{file.original_name}</span>
                        {/* Pin to Memory button */}
                        {currentThreadId && (
                          <button
                            type="button"
                            onClick={async () => {
                              try {
                                toast.loading('Extracting file content...', { id: `pin-${file.id}` });
                                await memoryApiService.pinFileToMemory(currentThreadId, file.id);
                                toast.success('File pinned to memory', { id: `pin-${file.id}` });
                              } catch (err) {
                                console.error('Failed to pin file to memory:', err);
                                toast.error('Failed to pin file', { id: `pin-${file.id}` });
                              }
                            }}
                            style={{
                              background: 'transparent',
                              border: 'none',
                              cursor: 'pointer',
                              padding: '2px',
                              marginLeft: '2px',
                              color: '#6b7280',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              borderRadius: '4px',
                              transition: 'all 0.15s',
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.background = '#e5e7eb';
                              e.currentTarget.style.color = '#0078D4';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = 'transparent';
                              e.currentTarget.style.color = '#6b7280';
                            }}
                            title="Pin to Memory Notebook"
                          >
                            <MemoryIcon size={12} />
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={async () => {
                            try {
                              await uploadService.deleteFile(file.id);
                              setAttachedFiles(attachedFiles.filter((_, i) => i !== idx));
                              const fileIdToRemove = file.id;
                              setAttachedFileIds(attachedFileIds.filter(id => id !== fileIdToRemove));
                            } catch (err) {
                              console.error('Failed to delete file:', err);
                              setAttachedFiles(attachedFiles.filter((_, i) => i !== idx));
                              const fileIdToRemove = file.id;
                              setAttachedFileIds(attachedFileIds.filter(id => id !== fileIdToRemove));
                            }
                          }}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            cursor: 'pointer',
                            padding: '0',
                            marginLeft: '4px',
                            color: '#6b7280',
                            fontSize: '16px',
                            lineHeight: '1',
                          }}
                        >
                          ×
                        </button>
                      </div>
                    ))}

                    {/* Portfolio selector - only show here */}
                    <PortfolioSelector />
                  </div>
                )}

                {/* Bottom row with all controls */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  flex: 1,
                }}>
                  {/* Options menu button - LEFTMOST */}
                  <div ref={optionsMenuRef} style={{ position: 'relative' }}>
                    <button
                      type="button"
                      onClick={() => setShowOptionsMenu(!showOptionsMenu)}
                      style={{
                        padding: '8px',
                        background: showOptionsMenu ? '#f3f4f6' : 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: '50%',
                        transition: 'background 0.2s',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = '#f3f4f6';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = showOptionsMenu ? '#f3f4f6' : 'transparent';
                      }}
                      title="Options"
                    >
                      <Plus size={20} style={{ color: deepAnalysisMode ? '#3b82f6' : '#6b7280' }} />
                    </button>

                    {/* Options menu */}
                    {showOptionsMenu && (
                      <div style={{
                        position: 'absolute',
                        bottom: '100%',
                        left: 0,
                        marginBottom: '0.5rem',
                        background: '#FFFFFF',
                        border: '0.0625rem solid #d1d5db',
                        borderRadius: '0.5rem',
                        boxShadow: '0 0.125rem 0.5rem rgba(0, 0, 0, 0.12)',
                        zIndex: 1000,
                        minWidth: '17.5rem',
                        padding: '0.25rem',
                      }}>
                        {/* Multi-Agent toggle */}
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '0.5rem 0.75rem',
                          borderRadius: '0.375rem',
                          cursor: 'pointer',
                        }}
                        onClick={() => {
                          const newValue = !deepAnalysisMode;
                          setDeepAnalysisMode(newValue);
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = '#f9fafb';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = 'transparent';
                        }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <Brain size={18} style={{ color: deepAnalysisMode ? '#8b5cf6' : '#6b7280' }} />
                            <div>
                              <div style={{
                                fontSize: '0.875rem',
                                fontWeight: 500,
                                color: '#111827',
                              }}>
                                Multi-Agent Mode
                              </div>
                              <div style={{
                                fontSize: '0.75rem',
                                color: '#6b7280',
                                marginTop: '0.0625rem',
                              }}>
                                Collaborative agent analysis
                              </div>
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              const newValue = !deepAnalysisMode;
                              setDeepAnalysisMode(newValue);
                            }}
                            style={{
                              position: 'relative',
                              width: '2rem',
                              height: '1.125rem',
                              background: deepAnalysisMode ? '#8b5cf6' : '#d1d5db',
                              border: 'none',
                              borderRadius: '0.5625rem',
                              cursor: 'pointer',
                              transition: 'background 0.3s',
                              padding: 0,
                            }}
                          >
                            <div style={{
                              position: 'absolute',
                              top: '0.125rem',
                              left: deepAnalysisMode ? '1rem' : '0.125rem',
                              width: '0.875rem',
                              height: '0.875rem',
                              background: '#FFFFFF',
                              borderRadius: '50%',
                              transition: 'left 0.3s',
                              boxShadow: '0 0.0625rem 0.1875rem rgba(0, 0, 0, 0.2)',
                            }} />
                          </button>
                        </div>

                        {/* Analyst Mode toggle */}
                        <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '0.5rem 0.75rem',
                          borderRadius: '0.375rem',
                          cursor: 'pointer',
                          marginTop: '0.25rem',
                        }}
                        onClick={() => {
                          toggleAnalystMode();
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = '#f9fafb';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = 'transparent';
                        }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <Columns size={18} style={{ color: analystMode ? '#0078D4' : '#6b7280' }} />
                            <div>
                              <div style={{
                                fontSize: '0.875rem',
                                fontWeight: 500,
                                color: '#111827',
                              }}>
                                Analyst Mode
                              </div>
                              <div style={{
                                fontSize: '0.75rem',
                                color: '#6b7280',
                                marginTop: '0.0625rem',
                              }}>
                                Split-screen with charts & data
                              </div>
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleAnalystMode();
                            }}
                            style={{
                              position: 'relative',
                              width: '2rem',
                              height: '1.125rem',
                              background: analystMode ? '#0078D4' : '#d1d5db',
                              border: 'none',
                              borderRadius: '0.5625rem',
                              cursor: 'pointer',
                              transition: 'background 0.3s',
                              padding: 0,
                            }}
                          >
                            <div style={{
                              position: 'absolute',
                              top: '0.125rem',
                              left: analystMode ? '1rem' : '0.125rem',
                              width: '0.875rem',
                              height: '0.875rem',
                              background: '#FFFFFF',
                              borderRadius: '50%',
                              transition: 'left 0.3s',
                              boxShadow: '0 0.0625rem 0.1875rem rgba(0, 0, 0, 0.2)',
                            }} />
                          </button>
                        </div>

                        {/* Divider */}
                        <div style={{ height: '1px', background: '#e5e7eb', margin: '0.25rem 0' }} />

                        {/* Memory Notebook button */}
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            padding: '0.5rem 0.75rem',
                            borderRadius: '0.375rem',
                            cursor: currentThreadId ? 'pointer' : 'not-allowed',
                            opacity: currentThreadId ? 1 : 0.5,
                          }}
                          onClick={() => {
                            if (currentThreadId) {
                              // Close Studio mode first if open, then open Memory Notebook
                              setStudioPanelOpen(false);
                              toggleMemoryPanel();
                              setShowOptionsMenu(false);
                            }
                          }}
                          onMouseEnter={(e) => {
                            if (currentThreadId) e.currentTarget.style.background = '#f9fafb';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'transparent';
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <MemoryIcon size={18} color="#6b7280" />
                            <div>
                              <div style={{
                                fontSize: '0.875rem',
                                fontWeight: 500,
                                color: '#111827',
                              }}>
                                Memory Notebook
                              </div>
                              <div style={{
                                fontSize: '0.75rem',
                                color: '#6b7280',
                                marginTop: '0.0625rem',
                              }}>
                                Pin important context
                              </div>
                            </div>
                          </div>
                        </div>

                      </div>
                    )}
                  </div>

                  {/* Attach button on the left */}
                  <button
                  type="button"
                  onClick={() => {
                    if (attachedFiles.length >= 10) {
                      toast.error('Maximum 10 files allowed per message');
                      return;
                    }

                    const input = document.createElement('input');
                    input.type = 'file';
                    input.multiple = true;
                    input.accept = '.pdf,.doc,.docx,.csv,.xlsx,.xls,.txt,.json,.png,.jpg,.jpeg';
                    input.onchange = async (e: any) => {
                      const files = Array.from(e.target.files || []) as File[];
                      await handleFileUpload(files);
                    };
                    input.click();
                  }}
                  disabled={uploadingFiles || attachedFiles.length >= 10}
                  style={{
                    padding: '8px',
                    background: 'transparent',
                    border: 'none',
                    cursor: (uploadingFiles || attachedFiles.length >= 10) ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    opacity: attachedFiles.length >= 10 ? 0.5 : 1,
                    borderRadius: '50%',
                    transition: 'background 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    if (!uploadingFiles && attachedFiles.length < 10) {
                      e.currentTarget.style.background = '#f3f4f6';
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                  title={attachedFiles.length >= 10 ? 'Maximum 10 files reached' : 'Attach files or drag and drop'}
                >
                  {uploadingFiles ? (
                    <Loader2 size={20} className="animate-spin" style={{ color: '#6b7280' }} />
                  ) : (
                    <Paperclip size={20} style={{ color: '#6b7280' }} />
                  )}
                  </button>

                  {/* Cloud Connectors button */}
                  <div
                    style={{
                      position: 'relative',
                    }}
                    onMouseEnter={() => {
                      if (connectorsMenuTimeoutRef.current) {
                        clearTimeout(connectorsMenuTimeoutRef.current);
                        connectorsMenuTimeoutRef.current = null;
                      }
                      setShowConnectorsMenu(true);
                    }}
                    onMouseLeave={() => {
                      connectorsMenuTimeoutRef.current = setTimeout(() => {
                        setShowConnectorsMenu(false);
                      }, 200);
                    }}
                  >
                    <button
                      type="button"
                      style={{
                        padding: '8px',
                        background: showConnectorsMenu ? '#f3f4f6' : 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: '50%',
                        transition: 'background 0.2s',
                      }}
                      title="Connect to cloud storage"
                    >
                      <svg
                        width="20"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        style={{ color: '#6b7280' }}
                      >
                        <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
                      </svg>
                    </button>

                    {showConnectorsMenu && (
                      <div
                        style={{
                          position: 'absolute',
                          bottom: '100%',
                          left: 0,
                          marginBottom: '0.5rem',
                          backgroundColor: '#ffffff',
                          borderRadius: '0.5rem',
                          boxShadow: '0 0.125rem 0.5rem rgba(0, 0, 0, 0.12)',
                          padding: '0.25rem',
                          minWidth: 'max-content',
                          maxWidth: 'min(17.5rem, 90vw)',
                          zIndex: 1000,
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            padding: '0.5rem 0.75rem',
                            borderRadius: '0.375rem',
                            cursor: 'pointer',
                            transition: 'background-color 0.15s ease',
                            backgroundColor: 'transparent',
                          }}
                          onClick={handleOpenDrivePicker}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = '#f3f4f6';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                        >
                          <img src={googleDriveIcon} alt="Google Drive" style={{ width: '1.125rem', height: 'auto', flexShrink: 0, objectFit: 'contain' }} />
                          <span style={{
                            fontSize: '0.875rem',
                            fontWeight: 400,
                            color: '#111827',
                            whiteSpace: 'nowrap',
                          }}>
                            Add from Google Drive {disabled && '🔒'}
                          </span>
                        </div>

                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            padding: '0.5rem 0.75rem',
                            borderRadius: '0.375rem',
                            cursor: 'pointer',
                            transition: 'background-color 0.15s ease',
                            backgroundColor: 'transparent',
                          }}
                          onClick={() => {
                            setOneDriveAccountType('personal');
                            handleOpenOneDrivePicker();
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = '#f3f4f6';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                        >
                          <img src={oneDriveIcon} alt="OneDrive Personal" style={{ width: '1.125rem', height: 'auto', flexShrink: 0, objectFit: 'contain' }} />
                          <span style={{
                            fontSize: '0.875rem',
                            fontWeight: 400,
                            color: '#111827',
                            whiteSpace: 'nowrap',
                          }}>
                            Add from OneDrive {disabled && '🔒'}
                          </span>
                        </div>

                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            padding: '0.5rem 0.75rem',
                            borderRadius: '0.375rem',
                            cursor: 'pointer',
                            transition: 'background-color 0.15s ease',
                            backgroundColor: 'transparent',
                          }}
                          onClick={() => {
                            setOneDriveAccountType('business');
                            handleOpenOneDrivePicker();
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = '#f3f4f6';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                        >
                          <img src={oneDriveIcon} alt="OneDrive Business" style={{ width: '1.125rem', height: 'auto', flexShrink: 0, objectFit: 'contain' }} />
                          <span style={{
                            fontSize: '0.875rem',
                            fontWeight: 400,
                            color: '#111827',
                            whiteSpace: 'nowrap',
                          }}>
                            Add from OneDrive Business {disabled && '🔒'}
                          </span>
                        </div>

                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            padding: '0.5rem 0.75rem',
                            borderRadius: '0.375rem',
                            cursor: disabled ? 'not-allowed' : 'pointer',
                            opacity: disabled ? 0.5 : 1,
                            transition: 'background-color 0.15s ease',
                            backgroundColor: 'transparent',
                          }}
                          onClick={() => {
                            setOneDriveAccountType('sharepoint');
                            handleOpenOneDrivePicker();
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = '#f3f4f6';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                        >
                          <img src={sharepointIcon} alt="SharePoint" style={{ width: '1.125rem', height: 'auto', flexShrink: 0, objectFit: 'contain' }} />
                          <span style={{
                            fontSize: '0.875rem',
                            fontWeight: 400,
                            color: '#111827',
                            whiteSpace: 'nowrap',
                          }}>
                            Add from SharePoint {disabled && '🔒'}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Portfolio button - only show when no portfolio selected */}
                  {!selectedChatPortfolioId && (
                    <div ref={portfolioDropdownRef} style={{ position: 'relative' }}>
                      <button
                        type="button"
                        onClick={() => setShowPortfolioDropdown(!showPortfolioDropdown)}
                        style={{
                          padding: '8px',
                          background: 'transparent',
                          border: 'none',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          borderRadius: '50%',
                          transition: 'background 0.2s',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = '#f3f4f6';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = 'transparent';
                        }}
                        title="Add portfolio"
                      >
                        <Folder size={18} style={{ color: '#6b7280' }} />
                      </button>

                      {showPortfolioDropdown && (
                        <div style={{
                          position: 'absolute',
                          bottom: '100%',
                          left: 0,
                          marginBottom: '0.5rem',
                          backgroundColor: '#ffffff',
                          borderRadius: '0.5rem',
                          boxShadow: '0 0.125rem 0.5rem rgba(0, 0, 0, 0.12)',
                          padding: '0.25rem',
                          width: 'clamp(15rem, 17.5rem, 90vw)',
                          maxHeight: '20rem',
                          overflowY: 'auto',
                          zIndex: 1000,
                        }}>
                          {(disabled ? [
                            { id: 'demo-1', name: 'Tech Growth Portfolio', tickers: ['AAPL', 'MSFT', 'GOOGL', 'NVDA'], is_default: true },
                            { id: 'demo-2', name: 'Value Stocks', tickers: ['BRK.B', 'JPM', 'JNJ'], is_default: false },
                            { id: 'demo-3', name: 'Dividend Income', tickers: ['KO', 'PG', 'MCD', 'VZ', 'T'], is_default: false },
                          ] : savedPortfolios).map((portfolio) => {
                            return (
                              <button
                                key={portfolio.id}
                                onClick={() => {
                                  if (disabled) {
                                    alert('Demo Mode - Sign up to use portfolios');
                                  } else {
                                    setSelectedChatPortfolioId(portfolio.id);
                                  }
                                  setShowPortfolioDropdown(false);
                                }}
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                  width: '100%',
                                  padding: '0.5rem 0.75rem',
                                  backgroundColor: 'transparent',
                                  border: 'none',
                                  borderRadius: '0.375rem',
                                  fontSize: '0.875rem',
                                  fontWeight: 600,
                                  color: '#111827',
                                  cursor: disabled ? 'not-allowed' : 'pointer',
                                  transition: 'background-color 0.15s ease',
                                  textAlign: 'left',
                                  opacity: disabled ? 0.5 : 1,
                                }}
                                onMouseEnter={(e) => {
                                  if (!disabled) e.currentTarget.style.backgroundColor = '#f3f4f6';
                                }}
                                onMouseLeave={(e) => {
                                  if (!disabled) e.currentTarget.style.backgroundColor = 'transparent';
                                }}
                              >
                                <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                  {portfolio.name} {disabled && '🔒'}
                                </span>
                                {portfolio.is_default && (
                                  <span style={{
                                    fontSize: '0.625rem',
                                    padding: '0.125rem 0.375rem',
                                    backgroundColor: '#fef3c7',
                                    color: '#92400e',
                                    borderRadius: '0.25rem',
                                    marginLeft: '0.5rem',
                                    fontWeight: 500,
                                    flexShrink: 0,
                                  }}>
                                    Default
                                  </span>
                                )}
                              </button>
                            );
                          })}

                          {!disabled && savedPortfolios.length === 0 && (
                            <div style={{
                              padding: '1rem 0.75rem',
                              textAlign: 'center',
                              color: '#9ca3af',
                              fontSize: '0.8125rem',
                            }}>
                              No portfolios saved yet
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Input field - overlay highlighter approach */}
                  <div style={{ position: 'relative', flex: 1 }}>
                    {/* Ticker Mention Dropdown - always rendered, handles its own visibility */}
                    <TickerMention
                      inputText={input}
                      cursorPosition={cursorPosition}
                      onSelect={handleTickerSelect}
                      onClose={() => setCursorPosition(-1)}
                      anchorRef={inputContainerRef}
                    />
                    {/* Background overlay with colored text */}
                    <div
                      ref={backgroundOverlayRef}
                      aria-hidden="true"
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        fontSize: '16px',
                        lineHeight: '24px',
                        padding: '4px 0',
                        margin: 0,
                        border: 'none',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        overflowWrap: 'break-word',
                        pointerEvents: 'none',
                        color: '#111827',
                        fontFamily: 'inherit',
                        letterSpacing: 'normal',
                        wordSpacing: 'normal',
                        textAlign: 'left',
                        minHeight: '24px',
                        maxHeight: '300px',
                        overflowY: 'auto',
                        overflowX: 'hidden',
                      }}
                      dangerouslySetInnerHTML={{
                        __html: (() => {
                          if (!input.trim()) {
                            return `<span style="color: #9ca3af;">${placeholderText}</span>`;
                          }

                          let html = input
                            .replace(/&/g, '&amp;')
                            .replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;');

                          // Highlight confirmed ticker mentions as inline pills (use ref for immediate access)
                          const tickers = mentionedTickersRef.current;
                          tickers.forEach(ticker => {
                            const regex = new RegExp(`@${ticker.symbol}(?=\\s|$)`, 'gi');
                            html = html.replace(regex,
                              '<span style="display: inline-flex; align-items: center; gap: 3px; padding: 1px 5px; background: #dbeafe; border-radius: 3px; font-size: 13px; font-weight: 500; color: #1d4ed8;">' +
                              `<img src="${getCompanyLogoUrl(ticker.symbol)}" style="width: 12px; height: 12px; object-fit: contain; mix-blend-mode: multiply;" onerror="this.style.display='none'"/>` +
                              `${ticker.symbol}</span>`,
                            );
                          });

                          // Agent highlights
                          html = html
                            .replace(/\b(quant-agent)\b/gi, '<span style="color: #ec4899; font-weight: bold;">$1</span>')
                            .replace(/\b(document-analyst)\b/gi, '<span style="color: #8b5cf6; font-weight: bold;">$1</span>')
                            .replace(/\b(chart-analyst)\b/gi, '<span style="color: #06b6d4; font-weight: bold;">$1</span>')
                            .replace(/\b(comparables-agent)\b/gi, '<span style="color: #8b5cf6; font-weight: bold;">$1</span>')
                            .replace(/\b(dcf-agent)\b/gi, '<span style="color: #059669; font-weight: bold;">$1</span>')
                            .replace(/\b(alternatives-agent)\b/gi, '<span style="color: #f59e0b; font-weight: bold;">$1</span>')
                            .replace(/\b(institutional-agent)\b/gi, '<span style="color: #8b5cf6; font-weight: bold;">$1</span>')
                            .replace(/\b(generalist-agent)\b/gi, '<span style="color: #3b82f6; font-weight: bold;">$1</span>')
                            .replace(/\b(risk-agent)\b/gi, '<span style="color: #ef4444; font-weight: bold;">$1</span>')
                            .replace(/\b(options-agent)\b/gi, '<span style="color: #f97316; font-weight: bold;">$1</span>')
                            .replace(/\b(structuring-agent)\b/gi, '<span style="color: #6366f1; font-weight: bold;">$1</span>')
                            .replace(/\b(screener-agent)\b/gi, '<span style="color: #3b82f6; font-weight: bold;">$1</span>')
                            .replace(/\b(funds-agent)\b/gi, '<span style="color: #10b981; font-weight: bold;">$1</span>')
                            .replace(/\b(prediction-agent)\b/gi, '<span style="color: #06b6d4; font-weight: bold;">$1</span>')
                            .replace(/\b(private-markets-agent)\b/gi, '<span style="color: #7c3aed; font-weight: bold;">$1</span>');

                          return html;
                        })(),
                      }}
                    />

                    {/* Transparent editable layer */}
                    <div
                      ref={textareaRef}
                      contentEditable
                      suppressContentEditableWarning={true}
                      onInput={(e) => {
                        const text = e.currentTarget.textContent || '';
                        setInput(text);
                        // Save to undo history (debounced)
                        debouncedSaveToHistory(text);
                        // Track cursor for @mentions - use requestAnimationFrame for better timing
                        requestAnimationFrame(() => updateCursorPosition());
                      }}
                      onClick={() => requestAnimationFrame(() => updateCursorPosition())}
                      onSelect={() => requestAnimationFrame(() => updateCursorPosition())}
                      onKeyDown={(e) => {
                        // Check if @ mention is active (dropdown open)
                        const textBeforeCursor = input.slice(0, cursorPosition);
                        const isAtMentionActive = /@[A-Za-z0-9.]*$/.test(textBeforeCursor);

                        // If ticker mention dropdown is open, let it handle navigation
                        if (isAtMentionActive && (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Tab')) {
                          // Let TickerMention handle these via document event listener
                          return;
                        }

                        // If @ mention active and Enter pressed, let dropdown handle selection
                        if (isAtMentionActive && e.key === 'Enter') {
                          // Let TickerMention handle selection
                          return;
                        }

                        // Handle Enter to submit
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleSubmit();
                          return;
                        }

                        // Handle Command+Z (undo) and Command+Shift+Z (redo) on Mac
                        // Handle Ctrl+Z (undo) and Ctrl+Y (redo) on Windows
                        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') {
                          e.preventDefault();
                          if (e.shiftKey) {
                            // Redo (Command+Shift+Z or Ctrl+Shift+Z)
                            handleRedo();
                          } else {
                            // Undo (Command+Z or Ctrl+Z)
                            handleUndo();
                          }
                          return;
                        }

                        // Handle Ctrl+Y for redo on Windows
                        if (e.ctrlKey && e.key.toLowerCase() === 'y') {
                          e.preventDefault();
                          handleRedo();
                          return;
                        }
                      }}
                      onKeyUp={(e) => {
                        // Update cursor position after navigation keys
                        if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(e.key)) {
                          requestAnimationFrame(() => updateCursorPosition());
                        }
                      }}
                      onScroll={(e) => {
                        // Sync scroll position to background overlay
                        if (backgroundOverlayRef.current) {
                          backgroundOverlayRef.current.scrollTop = e.currentTarget.scrollTop;
                          backgroundOverlayRef.current.scrollLeft = e.currentTarget.scrollLeft;
                        }
                      }}
                      onPaste={(e) => {
                        e.preventDefault();
                        const text = e.clipboardData.getData('text/plain');

                        // Modern approach using Selection API
                        const selection = window.getSelection();
                        if (selection?.rangeCount) {
                          const range = selection.getRangeAt(0);
                          range.deleteContents();
                          range.insertNode(document.createTextNode(text));
                          range.collapse(false);

                          // Update our state
                          const currentText = e.currentTarget.textContent || '';
                          setInput(currentText);
                        }
                      }}
                      style={{
                        position: 'relative',
                        background: 'transparent',
                        border: 'none',
                        outline: 'none',
                        fontSize: '16px',
                        lineHeight: '24px',
                        padding: '4px 0',
                        margin: 0,
                        color: 'transparent',
                        WebkitTextFillColor: 'transparent',
                        caretColor: '#111827',
                        minHeight: '24px',
                        maxHeight: '300px',
                        overflowY: 'auto',
                        overflowX: 'hidden',
                        fontFamily: 'inherit',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        overflowWrap: 'break-word',
                        letterSpacing: 'normal',
                        wordSpacing: 'normal',
                        textAlign: 'left',
                      }}
                    />
                  </div>

                  {/* Right side controls */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: 'auto', paddingRight: '8px' }}>
                    {/* Agent Mode selector */}
                    <AgentModeSelector
                      mode={currentAgentMode}
                      onModeChange={setAgentMode}
                      disabled={false}
                      direction="up"
                    />

                    {/* Tool Priority selector */}
                    <ToolPrioritySelector
                      agentMode={currentAgentMode}
                      selectedTools={prioritizedTools}
                      onToolsChange={setPrioritizedTools}
                      disabled={false}
                      direction="up"
                    />

                    {/* Search button */}
                    <button
                      type="button"
                      onClick={() => {
                        if (!isPerplexity && !isDeepSeek) {
                          setSearchMode(!searchMode);
                        }
                      }}
                      disabled={isPerplexity || isDeepSeek}
                      style={{
                        width: '32px',
                        height: '32px',
                        padding: 0,
                        background: effectiveSearchMode ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                        border: 'none',
                        borderRadius: '50%',
                        cursor: (isPerplexity || isDeepSeek) ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        opacity: (isPerplexity || isDeepSeek) ? 0.5 : 1,
                        transition: 'all 0.2s',
                      }}
                      onMouseEnter={(e) => {
                        if (!isPerplexity && !isDeepSeek) {
                          setIsCompassHovered(true);
                          if (!effectiveSearchMode) e.currentTarget.style.background = '#f3f4f6';
                        }
                      }}
                      onMouseLeave={(e) => {
                        setIsCompassHovered(false);
                        if (!effectiveSearchMode) e.currentTarget.style.background = 'transparent';
                      }}
                      title={
                        isPerplexity ? 'Search active with Perplexity' :
                        isDeepSeek ? 'Web search disabled for DeepSeek' :
                        searchMode ? 'Exit search mode' : 'Web search'
                      }
                    >
                      <Compass size={20} style={{
                        color: (effectiveSearchMode || isCompassHovered) ? '#3b82f6' : '#6b7280',
                        transition: 'color 0.2s',
                      }} />
                    </button>

                    {/* Token usage ring */}
                    {currentThreadId && (
                      <div style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <TokenUsageRing size={24} />
                      </div>
                    )}

                    {/* Send/Cancel button */}
                    {isStreaming ? (
                      <button
                        type="button"
                        onClick={() => {
                          if (cancelMessage) {
                            cancelMessage();
                          }
                        }}
                        style={{
                          width: '32px',
                          height: '32px',
                          padding: 0,
                          background: '#f3f4f6',
                          border: 'none',
                          borderRadius: '50%',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          transition: 'background 0.2s',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = '#e5e7eb';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = '#f3f4f6';
                        }}
                        title="Stop generating"
                      >
                        <Square size={12} fill="#0051cc" style={{ color: '#0051cc' }} />
                      </button>
                    ) : (
                      <button
                        type="submit"
                        disabled={!input.trim()}
                        style={{
                          width: '32px',
                          height: '32px',
                          padding: 0,
                          background: input.trim() ? '#0051cc' : '#e5e7eb',
                          border: 'none',
                          borderRadius: '50%',
                          cursor: !input.trim() ? 'default' : 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          transition: 'all 0.2s',
                        }}
                        onMouseEnter={(e) => {
                          if (input.trim()) {
                            e.currentTarget.style.background = '#003d99';
                          }
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = input.trim() ? '#0051cc' : '#e5e7eb';
                        }}
                        title="Send message"
                      >
                        <ArrowUp size={16} strokeWidth={2.5} style={{ color: '#FFFFFF' }} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </form>
        </div>
      </div>

      {showDrivePicker && (
        <GoogleDriveNativePicker
          onSelect={async (file: File) => {
            setShowDrivePicker(false);
            if (attachedFiles.length >= MAX_ATTACHMENTS) {
              toast.error(`Maximum ${MAX_ATTACHMENTS} files allowed per message`);
              return;
            }
            setUploadingFiles(true);
            try {
              const uploadedFiles = await uploadService.uploadFiles([file]);
              if (uploadedFiles && uploadedFiles[0]) {
                const driveFile = { ...uploadedFiles[0], source: 'google_drive' };
                setAttachedFiles(prev => [...prev, driveFile]);
                setAttachedFileIds(prev => [...prev, driveFile.id]);
                toast.success(`Attached ${file.name} from Google Drive`);
              }
            } catch (error) {
              console.error('Failed to upload file from Google Drive', error);
              toast.error('Failed to upload file from Google Drive');
            } finally {
              setUploadingFiles(false);
            }
          }}
          onClose={() => setShowDrivePicker(false)}
          allowAllFileTypes={true}
        />
      )}

      {showOneDrivePicker && (
        <OneDriveNativePicker
          onSelect={async (file: File) => {
            setShowOneDrivePicker(false);
            if (attachedFiles.length >= MAX_ATTACHMENTS) {
              toast.error(`Maximum ${MAX_ATTACHMENTS} files allowed per message`);
              return;
            }
            setUploadingFiles(true);
            try {
              const uploadedFiles = await uploadService.uploadFiles([file]);
              if (uploadedFiles && uploadedFiles[0]) {
                const driveFile = { ...uploadedFiles[0], source: 'onedrive' };
                setAttachedFiles(prev => [...prev, driveFile]);
                setAttachedFileIds(prev => [...prev, driveFile.id]);
                toast.success(`Attached ${file.name} from OneDrive`);
              }
            } catch (error) {
              console.error('Failed to upload file from OneDrive', error);
              toast.error('Failed to upload file from OneDrive');
            } finally {
              setUploadingFiles(false);
            }
          }}
          onClose={() => setShowOneDrivePicker(false)}
          allowAllFileTypes={true}
          accountType={oneDriveAccountType || 'personal'}
        />
      )}

    </div>
  );
};

export default InputArea;
