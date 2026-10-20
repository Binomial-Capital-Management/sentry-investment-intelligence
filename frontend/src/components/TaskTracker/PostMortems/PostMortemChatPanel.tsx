import { useState, useRef, useEffect, useMemo } from 'react';
import { X, ChevronDown, Maximize2, Minimize2, Upload, Globe, Database, GripVertical, FileText, Plus, MessageSquare, ArrowUp, Trash2, StopCircle, Copy, Check, Presentation, Sheet, Loader2, Pencil, CheckCircle2, Cloud, HelpCircle } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { getAuthToken } from '../../../services/authService';
import { MODELS } from '@/config/models';
import type { ModelId, ToolEvent } from '@/types';
import TransactionSelectorMenu from './TransactionSelectorMenu';
import TransactionCard from './TransactionCard';
import PostMortemGuidePanel from './PostMortemGuidePanel';
import StreamingProgress from '../../Chat/StreamingProgress';
import { GoogleDriveNativePicker } from '../../KnowledgeGraph/GoogleDriveNativePicker';
import { OneDriveNativePicker } from '../../KnowledgeGraph/OneDriveNativePicker';
import { uploadService, UploadedFile } from '@/services/upload';
import * as postmortemApi from '@/services/postmortemApi';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import axios from 'axios';
import { postmortemStreamingService, getPostmortemStreamEndpoint } from '@/services/postmortemStreaming';
import { chatAPI, API_BASE } from '@/services/api';
import { copyMessageContent } from '@/utils/export';
import { useAuth, useUser, useOrganization } from '@clerk/clerk-react';

interface Message {
 id: string;
 role: 'user' | 'assistant';
 content: string;
 created_at: string;
 metadata?: {
   transactions?: Array<{
     date: string;
     ticker: string;
     type: 'BUY' | 'SELL';
     quantity: number;
     price: number;
     realized_pnl?: number | null;
   }>;
 };
}

interface ChatThread {
 id: string;
 postmortem_id: string;
 title: string | null;
 created_at: string;
 updated_at: string;
}

interface Transaction {
 id: string;
 portfolio_id: string;
 portfolio_name: string;
 ticker: string;
 transaction_type: string;
 quantity: number;
 price: number;
 transaction_date: string;
 realized_gain_loss: number | null;
 total_amount: number;
}

interface PostMortemChatPanelProps {
 isOpen: boolean;
 onClose: () => void;
 postMortemTitle: string;
 transactionCount: number;
 postMortemId: string;
 transactions: Transaction[];
}

export default function PostMortemChatPanel({
 isOpen,
 onClose,
 postMortemTitle,
 transactionCount,
 postMortemId,
 transactions,
}: PostMortemChatPanelProps) {
 const [messages, setMessages] = useState<Message[]>([]);
 const [input, setInput] = useState('');
 const [isLoading, setIsLoading] = useState(false);
 const messagesEndRef = useRef<HTMLDivElement>(null);
 const inputRef = useRef<HTMLTextAreaElement>(null);
 const [selectedModel, setSelectedModel] = useState<ModelId>('gpt-6.1-sol');
 const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
 const [panelWidth, setPanelWidth] = useState(480);
 const [isDragging, setIsDragging] = useState(false);
 const [isWebSearchEnabled, setIsWebSearchEnabled] = useState(false);
 const [selectedTransactionIds, setSelectedTransactionIds] = useState<Set<string>>(new Set());
 const [isTransactionMenuOpen, setIsTransactionMenuOpen] = useState(false);
 const [attachedFiles, setAttachedFiles] = useState<UploadedFile[]>([]);
 const [uploadingFiles, setUploadingFiles] = useState(false);
 const [toolEvents, setToolEvents] = useState<ToolEvent[]>([]);
 const [reasoningStreaming, setReasoningStreaming] = useState(false);
 const [reasoningText, setReasoningText] = useState('');
 const [statusMessage, setStatusMessage] = useState<string>('');
 const assistantMessageIndexRef = useRef<number>(-1);

 // Thread management state
 const [threads, setThreads] = useState<ChatThread[]>([]);
 const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
 const [isThreadMenuOpen, setIsThreadMenuOpen] = useState(false);
 const [loadingThreads, setLoadingThreads] = useState(false);

 // Export state management (per-message tracking)
 const [copyFeedback, setCopyFeedback] = useState<Record<string, boolean>>({});
 const [exportingPdf, setExportingPdf] = useState<Record<string, boolean>>({});
 const [exportingPpt, setExportingPpt] = useState<Record<string, boolean>>({});
 const [exportingWorkbook, setExportingWorkbook] = useState<Record<string, boolean>>({});
 const [showStyleSelector, setShowStyleSelector] = useState(false);
 const [availableStyles, setAvailableStyles] = useState<Array<{style_name: string, is_default: boolean}>>([]);
 const [selectedStyleName, setSelectedStyleName] = useState<string | null>(null);
 const styleSelectorRef = useRef<HTMLDivElement>(null);
 const { getToken, isLoaded } = useAuth();
 const { user } = useUser();
 const { organization } = useOrganization();

 // Cloud integration state
 const [showDrivePicker, setShowDrivePicker] = useState(false);
 const [showOneDrivePicker, setShowOneDrivePicker] = useState(false);
 const [oneDriveAccountType, setOneDriveAccountType] = useState<'personal' | 'business' | 'sharepoint'>('personal');
const [showCloudMenu, setShowCloudMenu] = useState(false);
  const cloudMenuTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [guideOpen, setGuideOpen] = useState(false);

 // Non-stream analysis uses simple loading flag

 // Initialize selected transaction IDs when transactions load
 useEffect(() => {
   // Ensure transactions is an array before accessing length
   const txs = transactions || [];
   if (txs.length > 0 && selectedTransactionIds.size === 0) {
     setSelectedTransactionIds(new Set(txs.map(t => t.id)));
   }
 }, [transactions]);

 // Get current model info
 const currentModel = MODELS[selectedModel];

 // Handle resizing
 useEffect(() => {
   const handleMouseMove = (e: MouseEvent) => {
     if (!isDragging) return;
     const newWidth = window.innerWidth - e.clientX;
     // Clamp width between 300px and 90% of screen width
     const clampedWidth = Math.max(300, Math.min(newWidth, window.innerWidth * 0.9));
     setPanelWidth(clampedWidth);
   };

   const handleMouseUp = () => {
     setIsDragging(false);
     document.body.style.cursor = 'default';
   };

   if (isDragging) {
     window.addEventListener('mousemove', handleMouseMove);
     window.addEventListener('mouseup', handleMouseUp);
     document.body.style.cursor = 'ew-resize';
   }

   return () => {
     window.removeEventListener('mousemove', handleMouseMove);
     window.removeEventListener('mouseup', handleMouseUp);
     document.body.style.cursor = 'default';
   };
 }, [isDragging]);

 useEffect(() => {
   if (isOpen && inputRef.current) {
     inputRef.current.focus();
   }
 }, [isOpen]);

 useEffect(() => {
   messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
 }, [messages]);

 // Load export styles when auth is ready
 useEffect(() => {
   if (!isLoaded) return;
   const loadStyles = async () => {
     try {
       const token = await getToken();
       const response = await fetch(`${API_BASE}/api/user-settings/export-styles`, {
         headers: { Authorization: `Bearer ${token}` },
       });
       const data = await response.json();
       setAvailableStyles(data.styles || []);
       const defaultStyle = data.styles?.find((s: any) => s.is_default);
       if (defaultStyle) {
         setSelectedStyleName(defaultStyle.style_name);
       }
     } catch (error) {
       console.error('Failed to load export styles:', error);
     }
   };
   loadStyles();
 }, [isLoaded]);

 // Handle clicks outside style selector dropdown
 useEffect(() => {
   const handleClickOutside = (event: MouseEvent) => {
     if (styleSelectorRef.current && !styleSelectorRef.current.contains(event.target as Node)) {
       setShowStyleSelector(false);
     }
   };
   if (showStyleSelector) {
     document.addEventListener('mousedown', handleClickOutside);
     return () => document.removeEventListener('mousedown', handleClickOutside);
   }
 }, [showStyleSelector]);

 // Load threads when panel opens (after auth is ready)
 useEffect(() => {
   if (isOpen && postMortemId && isLoaded) {
     loadThreads();
   }
 }, [isOpen, postMortemId, isLoaded]);

 // Cleanup streaming on unmount
 useEffect(() => {
   return () => {
     postmortemStreamingService.close(true);
   };
 }, []);

 // Load messages when thread changes
 useEffect(() => {
   if (currentThreadId) {
     loadThreadMessages(currentThreadId);
   }
 }, [currentThreadId]);

 const loadThreads = async () => {
   setLoadingThreads(true);
   try {
     const token = await getAuthToken();
     const response = await axios.get(`${API_BASE}/api/postmortem/${postMortemId}/threads`, {
       headers: { Authorization: `Bearer ${token}` },
     });
     setThreads(response.data.threads);

     // Auto-select first thread if exists
     if (response.data.threads.length > 0 && !currentThreadId) {
       setCurrentThreadId(response.data.threads[0].id);
     }
   } catch (error) {
     console.error('Failed to load threads:', error);
     toast.error('Failed to load chat history');
   } finally {
     setLoadingThreads(false);
   }
 };

 const loadThreadMessages = async (threadId: string) => {
   try {
     const token = await getAuthToken();
     const response = await axios.get(`${API_BASE}/api/postmortem/threads/${threadId}/messages`, {
       headers: { Authorization: `Bearer ${token}` },
     });
     setMessages(response.data.messages);
   } catch (error) {
     console.error('Failed to load messages:', error);
     toast.error('Failed to load messages');
   }
 };

 const createNewThread = async (): Promise<string | null> => {
   try {
     const token = await getAuthToken();
     const response = await axios.post(
       `/api/postmortem/${postMortemId}/threads`,
       { title: `Analysis - ${new Date().toLocaleString()}` },
       { headers: { Authorization: `Bearer ${token}` } },
     );

     const newThread: ChatThread = {
       id: response.data.thread_id,
       postmortem_id: postMortemId,
       title: response.data.title,
       created_at: new Date().toISOString(),
       updated_at: new Date().toISOString(),
     };

     setThreads(prev => [newThread, ...prev]);
     setCurrentThreadId(newThread.id);
     setMessages([]);
     toast.success('New chat thread created');
     return newThread.id;
   } catch (error) {
     console.error('Failed to create thread:', error);
     toast.error('Failed to create new thread');
     return null;
   }
 };

 const handleSendMessage = async (messageText?: string, isInitial = false) => {
   const text = (messageText || input).trim();
   if (isLoading || !text) return;

   // Clear input immediately
   setInput('');
   setIsLoading(true);

   // Append user message immediately so it renders in the thread
   const userMessage: Message = {
     id: `user-${Date.now()}`,
     role: 'user',
     content: text,
     created_at: new Date().toISOString(),
   };
   setMessages((prev) => [...prev, userMessage]);

   // Clear previous streaming progress state
   setToolEvents([]);
   setReasoningStreaming(false);
   setReasoningText('');
   setStatusMessage('');

   // Create placeholder for streaming assistant response
   const assistantMessage: Message = {
     id: `temp-assistant-${Date.now()}`,
     role: 'assistant',
     content: '',
     created_at: new Date().toISOString(),
   };
   setMessages((prev) => {
     const next = [...prev, assistantMessage];
     assistantMessageIndexRef.current = next.length - 1;
     return next;
   });

   const endpoint = getPostmortemStreamEndpoint(postMortemId);

   const handleStreamMessage = (data: any) => {
     const type = data?.type;

     switch (type) {
       case 'start': {
         // Backend sends thread_id directly in data for postmortem
         if (data?.thread_id) {
           setCurrentThreadId(data.thread_id);
         }
         break;
       }

       case 'content': {
         // Simple content event - data.content is the chunk
         const chunk = (data as any).content ?? '';
         if (!chunk) return;
         setMessages((prev) => {
           const updated = [...prev];
           const idx = assistantMessageIndexRef.current;
           if (idx >= 0 && idx < updated.length) {
             updated[idx] = {
               ...updated[idx],
               content: (updated[idx].content || '') + chunk,
             };
           }
           return updated;
         });
         break;
       }

       case 'output_text_delta':
       case 'response.output_text.delta': {
         // Structured streaming - extract payload (support both underscore and dot notation)
         const payload = (data as any).event ?? data;
         const delta = typeof payload?.delta === 'string' ? payload.delta : '';
         if (!delta) return;
         setMessages((prev) => {
           const updated = [...prev];
           const idx = assistantMessageIndexRef.current;
           if (idx >= 0 && idx < updated.length) {
             updated[idx] = {
               ...updated[idx],
               content: (updated[idx].content || '') + delta,
             };
           }
           return updated;
         });
         break;
       }

       case 'output_text_done':
       case 'response.output_text.done': {
         const payload = (data as any).event ?? data;
         const text = typeof payload?.text === 'string' ? payload.text : '';
         if (text) {
           setMessages((prev) => {
             const updated = [...prev];
             const idx = assistantMessageIndexRef.current;
             if (idx >= 0 && idx < updated.length) {
               updated[idx] = {
                 ...updated[idx],
                 content: text,
               };
             }
             return updated;
           });
         }
         break;
       }

       case 'tool_call_started': {
         const payload = (data as any).event ?? data;
         const callId = payload?.item_id ?? payload?.id ?? `tool_${Date.now()}`;
         const toolName = payload?.tool_name ?? payload?.name ?? 'Tool Call';
         const tn = (toolName || '').toLowerCase();

         // Enhanced tool type inference from tool name with better pattern matching
         let toolType: 'function_call' | 'mcp_call' | 'code_interpreter' | 'file_search' | 'web_search' = 'function_call';

         // Code Interpreter patterns
         if (tn.includes('code') || tn.includes('interpreter') || tn.includes('python') || tn.includes('execute')) {
           toolType = 'code_interpreter';
         }
         // File Search patterns
         else if ((tn.includes('file') && tn.includes('search')) || tn.includes('filesearch')) {
           toolType = 'file_search';
         }
         // Web Search patterns (broader matching)
         else if (tn.includes('web') || tn.includes('search') || tn.includes('google') || tn.includes('bing')) {
           toolType = 'web_search';
         }
         // MCP Server patterns (comprehensive matching for all data providers)
         else if (
           tn.startsWith('mcp') ||
           tn.includes('mcp_') ||
           tn.includes('fmp') ||
           tn.includes('yahoo') ||
           tn.includes('fred') ||
           tn.includes('sec') ||
           tn.includes('market') ||
           tn.includes('financial') ||
           tn.includes('data_') ||
           tn.includes('get_') ||
           tn.includes('fetch_') ||
           tn.includes('discover_')
         ) {
           toolType = 'mcp_call';
         }
         // Function calls - anything that looks like a function pattern
         else if (tn.match(/^[a-z_]+$/)) {
           toolType = 'function_call';
         }

         setToolEvents((prev) => [...prev, {
           id: callId,
           toolType,
           toolName,
           status: 'in_progress' as const,
           startTime: Date.now(),
         }]);
         break;
       }

       case 'tool_call_output': {
         const payload = (data as any).event ?? data;
         const callId = payload?.item_id ?? payload?.id ?? 'tool_call';
         const out = payload?.output;
         const resultText = typeof out === 'string' ? out : (out ? JSON.stringify(out, null, 2) : undefined);

         setToolEvents((prev) => prev.map((e) =>
           e.id === callId ? {
             ...e,
             status: 'completed' as const,
             endTime: Date.now(),
             result: resultText ?? e.result,
           } : e,
         ));
         break;
       }

       case 'web_search_in_progress':
       case 'file_search_in_progress':
       case 'mcp_call_in_progress':
       case 'code_interpreter_in_progress': {
         const payload = (data as any).event ?? data;
         const callId = payload?.item_id ?? payload?.id ?? `tool_${Date.now()}`;
         const toolName = payload?.tool_name ?? payload?.name ?? type.replace(/_in_progress$/, '');
         const toolType = type.includes('web_search') ? 'web_search'
           : type.includes('file_search') ? 'file_search'
           : type.includes('code_interpreter') ? 'code_interpreter'
           : 'mcp_call';

         setToolEvents((prev) => {
           const existing = prev.find(e => e.id === callId);
           if (existing) return prev;
           return [...prev, {
             id: callId,
             toolType,
             toolName,
             status: 'in_progress' as const,
             startTime: Date.now(),
           }];
         });
         break;
       }

       case 'web_search_completed':
       case 'file_search_completed':
       case 'mcp_call_completed':
       case 'code_interpreter_completed': {
         const payload = (data as any).event ?? data;
         const callId = payload?.item_id ?? payload?.id ?? 'tool_call';
         const output = payload?.output ?? payload?.results ?? '';

         setToolEvents((prev) => prev.map((e) =>
           e.id === callId ? {
             ...e,
             status: 'completed' as const,
             endTime: Date.now(),
             result: typeof output === 'string' ? output : JSON.stringify(output),
           } : e,
         ));
         break;
       }

       case 'code_interpreter_code_delta': {
         const payload = (data as any).event ?? data;
         const code = payload?.code ?? payload?.delta ?? '';
         if (code) {
           console.log('[PostMortem] Code delta:', code);
         }
         break;
       }

       case 'function_call.arguments_delta':
       case 'mcp_call.arguments_delta': {
         // Function/MCP call arguments are being streamed
         // We can log or display this if needed, but typically not shown to user
         const payload = (data as any).event ?? data;
         const delta = payload?.delta ?? '';
         if (delta) {
           console.log('[PostMortem] Function arguments delta:', delta);
         }
         break;
       }

       case 'function_call.arguments_done':
       case 'mcp_call.arguments_done': {
         // Function/MCP call arguments finished streaming
         const payload = (data as any).event ?? data;
         const args = payload?.arguments ?? '';
         if (args) {
           console.log('[PostMortem] Function arguments done:', args);
         }
         break;
       }

       case 'reasoning_delta': {
         const payload = (data as any).event ?? data;
         const delta = typeof payload?.delta === 'string' ? payload.delta : '';
         if (delta) {
           setReasoningStreaming(true);
           setReasoningText((prev) => prev + delta);
         }
         break;
       }

       case 'reasoning_summary_part': {
         const payload = (data as any).event ?? data;
         const delta = typeof payload?.part?.text === 'string' ? payload.part.text : (typeof payload?.text === 'string' ? payload.text : '');
         if (delta) {
           setReasoningStreaming(true);
           setReasoningText((prev) => prev + delta);
         }
         break;
       }

       case 'reasoning_done':
       case 'reasoning_summary_done': {
         setReasoningStreaming(false);
         break;
       }

       case 'agent_updated': {
         const payload = (data as any).event ?? data;
         const agentName = payload?.agent_name;
         console.log('[PostMortem] Agent updated:', agentName);
         break;
       }

       case 'done':
       case 'response_completed':
       case 'response.completed': {
         console.log('[PostMortem] Stream completed, isLoading -> false');
         setIsLoading(false);
         setReasoningStreaming(false);
         setStatusMessage('');
         loadThreads();
         assistantMessageIndexRef.current = -1;
         break;
       }

      case 'stream_error':
      case 'response_failed':
      case 'error': {
        const payload = (data as any).event ?? data;
        const errMsg = payload?.error ?? data?.error ?? payload?.message ?? data?.message ?? 'Analysis failed';
        const isFatal = payload?.fatal ?? data?.fatal ?? false;
        console.error('[PostMortem] Stream error:', errMsg, isFatal ? '(FATAL - no retry)' : '');
        toast.error(errMsg);
        setIsLoading(false);
        setReasoningStreaming(false);
        setStatusMessage('');
        assistantMessageIndexRef.current = -1;

        // If fatal error, force close the stream to prevent reconnection attempts
        if (isFatal) {
          console.log('[PostMortem] Fatal error - closing stream to prevent retries');
          postmortemStreamingService.close();
        }
        break;
      }

       // Handle status events for non-streaming models (simulated streaming)
       case 'status':
       case 'progress': {
         // Status events are sent periodically during non-streaming execution
         // Update status message to show in loading indicator
         const statusMsg = (data as any).message ?? (data as any).status ?? 'Analyzing...';
         console.log('[PostMortem] Status update:', statusMsg);
         setStatusMessage(statusMsg);
         break;
       }

       default:
         console.log('[PostMortem] Unhandled event type:', type, data);
         break;
     }
   };

   console.log('[PostMortem] Starting stream with endpoint:', endpoint);
   console.log('[PostMortem] Stream context:', {
     postmortem_id: postMortemId,
     thread_id: currentThreadId,
     selected_transaction_ids: Array.from(selectedTransactionIds),
     message: text,
   });

  // Build cancel endpoint for this postmortem (include thread_id if available)
  const cancelEndpoint = currentThreadId
    ? `${API_BASE}/api/postmortem/${postMortemId}/analyze/cancel?thread_id=${currentThreadId}`
    : `${API_BASE}/api/postmortem/${postMortemId}/analyze/cancel`;

  postmortemStreamingService.startStream(
    text,
    {
      onMessage: handleStreamMessage,
      onError: (err) => {
        console.error('[PostMortem] Stream error callback triggered:', err);
        toast.error('Failed to start analysis');
        setIsLoading(false);
        setReasoningStreaming(false);
        assistantMessageIndexRef.current = -1;
      },
      onComplete: () => {
        console.log('[PostMortem] Stream onComplete callback triggered');
        setIsLoading(false);
        setReasoningStreaming(false);
        loadThreads();
        assistantMessageIndexRef.current = -1;
      },
    },
    {
      selectedModel,
      fileIds: attachedFiles.map(f => f.id),
      // Pass cancel endpoint so StreamingService uses it instead of /v6/chat/cancel
      cancelEndpoint,
      extraParams: {
        postmortem_id: postMortemId,
        ...(currentThreadId ? { thread_id: currentThreadId } : {}),
        ...(selectedTransactionIds.size ? { selected_transaction_ids: Array.from(selectedTransactionIds).join(',') } : {}),
        ...(isWebSearchEnabled ? { web_search: 'true', force_web_search: 'true' } : {}),
      },
    },
    endpoint,
  );
 };

 // Markdown components for rendering
 const markdownComponents: Partial<Components> = useMemo(() => ({
   code({ node, inline, className, children, ...props }: any) {
     const match = /language-(\w+)/.exec(className || '');
     return !inline && match ? (
       <SyntaxHighlighter
         style={oneDark}
         language={match[1]}
         PreTag="div"
         {...props}
       >
         {String(children).replace(/\n$/, '')}
       </SyntaxHighlighter>
     ) : (
       <code className="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono" {...props}>
         {children}
       </code>
     );
   },
   p({ children }) {
     return <p className="mb-2">{children}</p>;
   },
   ul({ children }) {
     return <ul className="list-disc ml-5 mb-2">{children}</ul>;
   },
   ol({ children }) {
     return <ol className="list-decimal ml-5 mb-2">{children}</ol>;
   },
   li({ children }) {
     return <li className="mb-1">{children}</li>;
   },
   h1({ children }) {
     return <h1 className="text-xl font-bold mb-2">{children}</h1>;
   },
   h2({ children }) {
     return <h2 className="text-lg font-bold mb-2">{children}</h2>;
   },
   h3({ children }) {
     return <h3 className="text-base font-bold mb-2">{children}</h3>;
   },
   strong({ children }) {
     return <strong className="font-bold">{children}</strong>;
   },
   a({ href, children }) {
     return (
       <a
         href={href}
         target="_blank"
         rel="noopener noreferrer"
         className="text-blue-600 hover:underline"
       >
         {children}
       </a>
     );
   },
 }), []);

 const handleFileUpload = async (files: File[]) => {
   if (files.length === 0) return;

   const MAX_ATTACHMENTS = 10;
   const remainingSlots = MAX_ATTACHMENTS - attachedFiles.length;
   if (files.length > remainingSlots) {
     toast.error(`Maximum ${MAX_ATTACHMENTS} files. You can attach ${remainingSlots} more.`);
     files = files.slice(0, remainingSlots);
   }

   setUploadingFiles(true);
   try {
     const uploadedFiles = await uploadService.uploadFiles(files);
     setAttachedFiles(prev => [...prev, ...uploadedFiles]);
     toast.success(`Uploaded ${uploadedFiles.length} file(s)`);
   } catch (error: any) {
     console.error('File upload failed:', error);
     toast.error(error.message || 'Failed to upload files');
   } finally {
     setUploadingFiles(false);
   }
 };

 const handleFileUploadClick = () => {
   const input = document.createElement('input');
   input.type = 'file';
   input.multiple = true;
   input.accept = '.pdf,.doc,.docx,.csv,.xlsx,.xls,.txt,.json,.png,.jpg,.jpeg';
   input.onchange = async (e: any) => {
     const files = Array.from(e.target.files || []) as File[];
     await handleFileUpload(files);
   };
   input.click();
 };

 // Drag-and-drop handlers
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

   const MAX_ATTACHMENTS = 10;
   if (attachedFiles.length >= MAX_ATTACHMENTS) {
     toast.error(`Maximum ${MAX_ATTACHMENTS} files allowed per message`);
     return;
   }

   const files = Array.from(e.dataTransfer.files);
   if (files.length > 0) {
     await handleFileUpload(files);
   }
 };

 const handleRemoveFile = async (fileId: string) => {
   try {
     await uploadService.deleteFile(fileId);
     setAttachedFiles(prev => prev.filter(f => f.id !== fileId));
     toast.success('File removed');
   } catch (error) {
     console.error('Failed to remove file:', error);
     toast.error('Failed to remove file');
   }
 };

 // Cloud file selection handlers
 const handleGoogleDriveSelect = async (files: any[]) => {
   if (files.length === 0) return;

   const MAX_ATTACHMENTS = 10;
   const remainingSlots = MAX_ATTACHMENTS - attachedFiles.length;
   if (files.length > remainingSlots) {
     toast.error(`Maximum ${MAX_ATTACHMENTS} files. You can attach ${remainingSlots} more.`);
     files = files.slice(0, remainingSlots);
   }

   setUploadingFiles(true);
   try {
     const uploadedFiles = await uploadService.uploadFiles(files);
     setAttachedFiles(prev => [...prev, ...uploadedFiles]);
     toast.success(`Added ${uploadedFiles.length} file(s) from Google Drive`);
   } catch (error: any) {
     console.error('Google Drive upload failed:', error);
     toast.error(error.message || 'Failed to upload files from Google Drive');
   } finally {
     setUploadingFiles(false);
     setShowDrivePicker(false);
   }
 };

 const handleOneDriveSelect = async (file: File) => {
   setShowOneDrivePicker(false);
   const MAX_ATTACHMENTS = 10;
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
       toast.success(`Attached ${file.name} from OneDrive`);
     }
   } catch (error: any) {
     console.error('Failed to upload file from OneDrive', error);
     toast.error('Failed to upload file from OneDrive');
   } finally {
     setUploadingFiles(false);
   }
 };

 if (!isOpen) return null;

 return (
   <>
     <div
       className="h-full bg-[#f5f5f5] flex flex-col relative"
       style={{
         width: `${panelWidth}px`,
         transition: isDragging ? 'none' : 'width 75ms ease-out',
       }}
     >
       {/* Resize Handle - On the Left */}
       <div
         className="absolute left-0 top-0 bottom-0 w-1 cursor-ew-resize hover:bg-blue-400 transition-colors z-[80]"
         onMouseDown={() => setIsDragging(true)}
       />

       {/* Unified Header with Thread Selector and Buttons */}
       <div className="flex items-center justify-between px-4 py-2 bg-[#f5f5f5] shrink-0">
         <div className="flex items-center gap-2 min-w-0 flex-1">
           <span className="text-sm text-gray-700 font-normal truncate">{postMortemTitle}</span>
           <span className="text-xs text-gray-400 shrink-0 whitespace-nowrap">• {transactionCount} trades</span>
         </div>

         <div className="flex items-center gap-1 shrink-0">
           {/* Thread Selector Button */}
           <div className="relative">
             <button
               onClick={() => setIsThreadMenuOpen(!isThreadMenuOpen)}
               className="p-1.5 text-gray-500 hover:text-gray-700 transition-colors"
               title="Chat history"
             >
               <MessageSquare className="h-4 w-4" />
             </button>

             {isThreadMenuOpen && (
               <>
                 <div
                   className="fixed inset-0 z-10"
                   onClick={() => setIsThreadMenuOpen(false)}
                 />
                 <div className="absolute top-full right-0 mt-1 w-72 bg-white rounded-lg shadow-xl border border-gray-200 z-20 max-h-64 overflow-y-auto py-1">
                   {threads.length === 0 ? (
                     <div className="px-3 py-2 text-sm text-gray-400">No history</div>
                   ) : (
                     threads.map((thread) => (
                       <div
                         key={thread.id}
                         className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center justify-between gap-2 transition-colors group ${
                           currentThreadId === thread.id ? 'bg-gray-100 text-gray-900' : 'text-gray-700'
                         }`}
                       >
                         <button
                           onClick={() => {
                             setCurrentThreadId(thread.id);
                             setIsThreadMenuOpen(false);
                           }}
                           className="flex-1 flex items-center justify-between gap-2 min-w-0"
                         >
                           <span className="truncate">{thread.title || 'Untitled'}</span>
                           <span className="text-xs text-gray-400 shrink-0">
                             {new Date(thread.updated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                           </span>
                         </button>
                         <button
                           onClick={async (e) => {
                             e.stopPropagation();
                             if (confirm('Delete this conversation?')) {
                               try {
                                 await postmortemApi.deleteThread(thread.id);
                                 // Refresh threads list
                                 if (postMortemId) {
                                   const data = await postmortemApi.listThreads(postMortemId);
                                   setThreads(data.threads);
                                   // If deleted current thread, switch to new thread
                                   if (currentThreadId === thread.id) {
                                     if (data.threads.length > 0) {
                                       setCurrentThreadId(data.threads[0].id);
                                     } else {
                                       createNewThread();
                                     }
                                   }
                                 }
                               } catch (error) {
                                 console.error('Failed to delete thread:', error);
                               }
                             }
                           }}
                           className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-600 transition-all"
                           title="Delete conversation"
                         >
                           <Trash2 className="h-3 w-3" />
                         </button>
                       </div>
                     ))
                   )}
                 </div>
               </>
             )}
           </div>

{/* New Thread Button */}
          <button
            onClick={createNewThread}
            className="p-1.5 text-gray-500 hover:text-gray-700 transition-colors"
            title="New conversation"
          >
            <Plus className="h-4 w-4" />
          </button>

          {/* Help Button */}
          <button
            onClick={() => setGuideOpen(true)}
            className="p-1.5 text-gray-500 hover:text-gray-700 transition-colors"
            title="Open Post Mortem Guide"
          >
            <HelpCircle className="h-4 w-4" />
          </button>

          {/* Close Button */}
           <button
             onClick={onClose}
             className="p-1.5 text-gray-500 hover:text-gray-700 transition-colors"
             title="Close"
           >
             <X className="h-4 w-4" />
           </button>
         </div>
       </div>

       {/* Messages */}
       <div className="flex-1 overflow-y-auto px-3 py-3 relative bg-[#f5f5f5]">
         <div className="space-y-3">
             {messages.map((message, index) => (
               <div key={index}>
                 {/* User Message */}
                 {message.role === 'user' && (
                   <div className="mb-2">
                     {/* Transaction card (if metadata contains transactions) */}
                     {message.metadata?.transactions && (
                       <div className="mb-2">
                         <TransactionCard transactions={message.metadata.transactions} />
                       </div>
                     )}
                     {/* User message bubble */}
                     <div className="flex justify-end">
                       <div className="bg-[#ebebeb] text-gray-800 text-sm px-4 py-2.5 rounded-2xl rounded-tr-sm max-w-[85%] leading-relaxed whitespace-pre-wrap">
                         {message.content}
                       </div>
                     </div>
                   </div>
                 )}

                 {/* Assistant Message */}
                 {message.role === 'assistant' && (
                   <div className="mb-4">
                     <div className="flex items-center gap-2 mb-1.5">
                       <div className="w-5 h-5 rounded-full bg-blue-100 flex items-center justify-center">
                         <span className="text-[10px] font-bold text-blue-600">AI</span>
                       </div>
                       <span className="text-xs font-medium text-gray-500">Assistant</span>
                     </div>

                     {/* Show reasoning ABOVE content when streaming the last message */}
                     {isLoading && index === messages.length - 1 && (reasoningStreaming || reasoningText) && (
                       <div className="mb-2 pl-7">
                         <div className="flex items-center gap-1.5 mb-1">
                           <div className="w-3 h-3 flex items-center justify-center">
                             {reasoningStreaming ? (
                               <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-pulse" />
                             ) : (
                               <span className="text-[9px]">💭</span>
                             )}
                           </div>
                           <span className="text-[10px] font-medium text-gray-500">Reasoning</span>
                         </div>
                         {reasoningText && (
                           <div className="text-sm text-gray-800 opacity-60 leading-relaxed pl-5">
                             {(() => {
                               const lines = reasoningText.split('\n');
                               const lastThreeLines = lines.slice(-3);
                               return lastThreeLines.join('\n');
                             })()}
                           </div>
                         )}
                       </div>
                     )}

                     {/* Show tool events ABOVE content when streaming the last message */}
                     {isLoading && index === messages.length - 1 && toolEvents.length > 0 && (
                       <div className="flex flex-col gap-0.5 mb-2 pl-7">
                         {toolEvents.slice(-3).map((event) => (
                           <div key={event.id} className="flex items-center gap-1.5 text-[11px]">
                             <div className={`w-3 h-3 rounded flex items-center justify-center ${
                               event.status === 'completed'
                                 ? 'bg-emerald-100 text-emerald-600'
                                 : event.status === 'failed'
                                 ? 'bg-red-100 text-red-600'
                                 : 'bg-blue-100 text-blue-600'
                             }`}>
                               {event.status === 'completed' ? (
                                 <span className="text-[8px]">✓</span>
                               ) : event.status === 'failed' ? (
                                 <span className="text-[8px]">✗</span>
                               ) : (
                                 <div className="w-1 h-1 bg-blue-600 rounded-full animate-pulse" />
                               )}
                             </div>
                             <span className={`${
                               event.status === 'completed' ? 'text-gray-500' : 'text-gray-700'
                             }`}>
                               {event.toolName || 'Processing'}
                             </span>
                           </div>
                         ))}
                       </div>
                     )}

                     {/* Show generic loading indicator for non-streaming models (no reasoning/tool events) */}
                     {isLoading && index === messages.length - 1 && !message.content && !reasoningStreaming && !reasoningText && toolEvents.length === 0 && (
                       <div className="flex items-center gap-1.5 mb-2 pl-7">
                         <div className="flex gap-0.5">
                           <div className="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                           <div className="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                           <div className="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                         </div>
                         <span className="text-xs text-gray-500">{statusMessage || 'Analyzing...'}</span>
                       </div>
                     )}

                     <div className="text-sm text-gray-800 leading-relaxed pl-7 prose prose-sm max-w-none">
                       <ReactMarkdown
                         remarkPlugins={[remarkGfm]}
                         components={markdownComponents}
                       >
                         {message.content}
                       </ReactMarkdown>
                     </div>

                     {/* Export buttons row - only show for completed messages */}
                     {(!isLoading || index < messages.length - 1) && (
                     <div className="flex items-center gap-1.5 mt-2 pl-7">
                       {/* Copy */}
                       <button
                         onClick={async () => {
                           const messageDiv = document.createElement('div');
                           messageDiv.innerHTML = message.content;
                           const success = await copyMessageContent(messageDiv);
                           if (success) {
                             setCopyFeedback(prev => ({ ...prev, [message.id]: true }));
                             setTimeout(() => setCopyFeedback(prev => ({ ...prev, [message.id]: false })), 2000);
                             toast.success('Copied to clipboard');
                           }
                         }}
                         title="Copy message"
                         className="p-1 hover:bg-gray-100 rounded transition-colors"
                       >
                         {copyFeedback[message.id] ? (
                           <Check size={13} color="#10B981" strokeWidth={2.5} />
                         ) : (
                           <Copy size={13} color="#000000" strokeWidth={2} />
                         )}
                       </button>

                       {/* PDF (Gamma) */}
                       <button
                         onClick={async () => {
                           if (exportingPdf[message.id]) return;

                           try {
                             setExportingPdf(prev => ({ ...prev, [message.id]: true }));
                             const payload = {
                               mode: 'postmortem',
                               content: message.content,
                               metadata: {
                                 postmortem_id: postMortemId,
                                 thread_id: currentThreadId,
                                 transactions: Array.from(selectedTransactionIds),
                               },
                             };

                             const blob = await chatAPI.exportPdf(payload, 'gamma_pdf', selectedStyleName || undefined);

                             const url = URL.createObjectURL(blob);
                             const a = document.createElement('a');
                             a.href = url;
                             a.download = `postmortem_${postMortemId.substring(0, 8)}_${new Date().toISOString().split('T')[0]}.pdf`;
                             a.click();
                             URL.revokeObjectURL(url);
                             toast.success('PDF exported successfully');
                           } catch (error) {
                             console.error('Gamma PDF export failed:', error);
                             toast.error('Export failed. Please try again.');
                           } finally {
                             setExportingPdf(prev => ({ ...prev, [message.id]: false }));
                           }
                         }}
                         title={exportingPdf[message.id] ? 'Generating PDF...' : 'Export as PDF'}
                         disabled={exportingPdf[message.id]}
                         className="p-1 hover:bg-gray-100 rounded transition-colors disabled:opacity-50 disabled:cursor-wait"
                       >
                         {exportingPdf[message.id] ? (
                           <Loader2 size={13} color="#000000" strokeWidth={2.5} className="animate-spin" />
                         ) : (
                           <FileText size={13} color="#000000" strokeWidth={2} />
                         )}
                       </button>

                       {/* PowerPoint (Gamma) */}
                       <button
                         onClick={async () => {
                           if (exportingPpt[message.id]) return;

                           try {
                             setExportingPpt(prev => ({ ...prev, [message.id]: true }));
                             const payload = {
                               mode: 'postmortem',
                               content: message.content,
                               metadata: {
                                 postmortem_id: postMortemId,
                                 thread_id: currentThreadId,
                                 transactions: Array.from(selectedTransactionIds),
                               },
                             };

                             const blob = await chatAPI.exportPowerpoint(payload, 'gamma_pptx', selectedStyleName || undefined);

                             const url = URL.createObjectURL(blob);
                             const a = document.createElement('a');
                             a.href = url;
                             a.download = `postmortem_${postMortemId.substring(0, 8)}_${new Date().toISOString().split('T')[0]}.pptx`;
                             a.click();
                             URL.revokeObjectURL(url);
                             toast.success('PowerPoint exported successfully');
                           } catch (error) {
                             console.error('PowerPoint export failed:', error);
                             toast.error('Export failed. Please try again.');
                           } finally {
                             setExportingPpt(prev => ({ ...prev, [message.id]: false }));
                           }
                         }}
                         title={exportingPpt[message.id] ? 'Generating presentation...' : 'Export as PowerPoint'}
                         disabled={exportingPpt[message.id]}
                         className="p-1 hover:bg-gray-100 rounded transition-colors disabled:opacity-50 disabled:cursor-wait"
                       >
                         {exportingPpt[message.id] ? (
                           <Loader2 size={13} color="#000000" strokeWidth={2.5} className="animate-spin" />
                         ) : (
                           <Presentation size={13} color="#000000" strokeWidth={2} />
                         )}
                       </button>

                       {/* Excel/CSV Workbook */}
                       <button
                         onClick={async () => {
                           if (exportingWorkbook[message.id]) return;

                           try {
                             setExportingWorkbook(prev => ({ ...prev, [message.id]: true }));
                             const payload = {
                               message_id: message.id,
                               content: message.content,
                               metadata: {
                                 postmortem_id: postMortemId,
                                 thread_id: currentThreadId,
                                 transactions: Array.from(selectedTransactionIds),
                               },
                             };

                             const blob = await chatAPI.exportWorkbook(payload);

                             const url = URL.createObjectURL(blob);
                             const a = document.createElement('a');
                             a.href = url;
                             a.download = `postmortem_workbooks_${message.id.substring(0, 8)}_${new Date().toISOString().split('T')[0]}.zip`;
                             a.click();
                             URL.revokeObjectURL(url);
                             toast.success('Workbook exported successfully');
                           } catch (error) {
                             console.error('Workbook export failed:', error);
                             toast.error('Failed to generate workbook. Please try again.');
                           } finally {
                             setExportingWorkbook(prev => ({ ...prev, [message.id]: false }));
                           }
                         }}
                         title={exportingWorkbook[message.id] ? 'Generating workbooks... (~30-60 seconds)' : 'Export as Excel/CSV'}
                         disabled={exportingWorkbook[message.id]}
                         className="p-1 hover:bg-gray-100 rounded transition-colors disabled:opacity-50 disabled:cursor-wait"
                       >
                         {exportingWorkbook[message.id] ? (
                           <Loader2 size={13} color="#000000" strokeWidth={2.5} className="animate-spin" />
                         ) : (
                           <Sheet size={13} color="#000000" strokeWidth={2} />
                         )}
                       </button>

                       {/* Export Style Selector (Pencil Button) */}
                       <div className="relative" ref={styleSelectorRef}>
                         <button
                           onClick={() => setShowStyleSelector(!showStyleSelector)}
                           title="Select export style"
                           className="p-1 hover:bg-gray-100 rounded transition-colors"
                         >
                           <Pencil size={13} color="#000000" strokeWidth={2} />
                         </button>

                         {/* Style Selector Dropdown */}
                         {showStyleSelector && (
                           <div className="absolute left-0 bottom-full mb-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-80 overflow-y-auto">
                             <div className="p-2 border-b border-gray-100">
                               <div className="text-xs font-medium text-gray-700">Export Style</div>
                               <div className="text-[10px] text-gray-500 mt-0.5">
                                 Choose a custom style for PDF/PowerPoint exports
                               </div>
                             </div>
                             <div className="py-1">
                               {availableStyles.length === 0 ? (
                                 <div className="px-3 py-2 text-xs text-gray-500 text-center">
                                   No custom styles available
                                 </div>
                               ) : (
                                 availableStyles.map((style) => (
                                   <button
                                     key={style.style_name}
                                     onClick={() => {
                                       setSelectedStyleName(style.style_name);
                                       setShowStyleSelector(false);
                                       toast.success(`Style set to: ${style.style_name}`);
                                     }}
                                     className="w-full px-3 py-2 text-left text-xs hover:bg-gray-50 flex items-center justify-between group"
                                   >
                                     <span className="font-medium text-gray-700 group-hover:text-gray-900">
                                       {style.style_name}
                                     </span>
                                     {selectedStyleName === style.style_name && (
                                       <CheckCircle2 size={14} className="text-blue-600" />
                                     )}
                                     {style.is_default && (
                                       <span className="text-[10px] text-gray-400 ml-2">(default)</span>
                                     )}
                                   </button>
                                 ))
                               )}
                             </div>
                           </div>
                         )}
                       </div>
                     </div>
                     )}
                   </div>
                 )}
               </div>
             ))}

           {/* Fallback loading indicator when no messages yet */}
           {isLoading && messages.length === 0 && (
             <div className="pl-1">
               <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1.5">Assistant</div>
               <div className="flex items-center gap-1.5 text-xs text-gray-400">
                 <div className="flex gap-0.5">
                   <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                   <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                   <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                 </div>
                 <span>Analyzing...</span>
               </div>
             </div>
           )}
         </div>

         <div ref={messagesEndRef} />
       </div>

       {/* Input + Controls at Bottom */}
       <div className="p-4 shrink-0 z-20 relative">
         <div
           className="bg-white rounded-xl overflow-visible relative z-30"
           onDragEnter={handleDragEnter}
           onDragLeave={handleDragLeave}
           onDragOver={handleDragOver}
           onDrop={handleDrop}
         >
           {/* Drag-and-Drop Overlay */}
           {isDragging && (
             <div style={{
               position: 'absolute',
               top: 0,
               left: 0,
               right: 0,
               bottom: 0,
               background: 'rgba(59, 130, 246, 0.05)',
               borderRadius: '12px',
               display: 'flex',
               alignItems: 'center',
               justifyContent: 'center',
               pointerEvents: 'none',
               zIndex: 50,
             }}>
               <div style={{
                 display: 'flex',
                 flexDirection: 'column',
                 alignItems: 'center',
                 gap: '8px',
               }}>
                 <Upload size={32} style={{ color: '#3b82f6' }} />
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

           {/* Attached Files Display */}
           {attachedFiles.length > 0 && (
             <div className="px-3 pt-2 pb-1 border-b border-gray-100">
               <div className="flex flex-wrap gap-2">
                 {attachedFiles.map((file) => (
                   <div
                     key={file.id}
                     className="flex items-center gap-1.5 px-2 py-1 bg-blue-50 border border-blue-200 rounded-md text-xs relative"
                   >
                     {/* Cloud source badge */}
                     {file.source === 'google_drive' && (
                       <div className="absolute -top-1 -left-1 w-3.5 h-3.5 bg-white rounded-full border border-blue-200 flex items-center justify-center">
                         <svg className="w-2 h-2" viewBox="0 0 24 24" fill="none">
                           <path d="M12.545 2.26a2.024 2.024 0 00-1.09 0L2.8 5.55C1.804 5.96 1 6.96 1 8.077v7.846c0 1.117.804 2.117 1.8 2.527l8.655 3.29c.345.135.745.135 1.09 0l8.655-3.29C22.196 17.94 23 16.94 23 15.823V8.077c0-1.117-.804-2.117-1.8-2.527L12.545 2.26z" fill="#4285F4"/>
                         </svg>
                       </div>
                     )}
                     {file.source === 'onedrive' && (
                       <div className="absolute -top-1 -left-1 w-3.5 h-3.5 bg-white rounded-full border border-blue-200 flex items-center justify-center">
                         <svg className="w-2 h-2" viewBox="0 0 24 24" fill="none">
                           <path d="M9.5 8.5a5.5 5.5 0 1011 0 5.5 5.5 0 00-11 0z" fill="#0364B8"/>
                           <path d="M3 14.5a5.5 5.5 0 1011 0 5.5 5.5 0 00-11 0z" fill="#0078D4"/>
                           <path d="M14 14.5a5.5 5.5 0 11-11 0 5.5 5.5 0 0111 0z" fill="#28A8EA"/>
                         </svg>
                       </div>
                     )}
                     <FileText className="h-3 w-3 text-blue-600 shrink-0" />
                     <span className="text-blue-700 font-medium truncate max-w-[120px]">
                       {file.original_name}
                     </span>
                     <button
                       onClick={() => handleRemoveFile(file.id)}
                       className="text-blue-500 hover:text-blue-700 transition-colors ml-0.5"
                       title="Remove file"
                     >
                       <X className="h-3 w-3" />
                     </button>
                   </div>
                 ))}
               </div>
             </div>
           )}

           <div className="flex items-end gap-2 px-3 py-2">
             <textarea
               ref={inputRef}
               value={input}
               onChange={(e) => setInput(e.target.value)}
               onKeyDown={(e) => {
                 if (e.key === 'Enter' && !e.shiftKey) {
                   e.preventDefault();
                   handleSendMessage();
                 }
               }}
               placeholder="Ask about patterns, improvements..."
               disabled={isLoading}
               rows={1}
               className="flex-1 text-sm text-gray-800 placeholder:text-gray-400 bg-transparent focus:outline-none disabled:opacity-50 resize-none max-h-[120px]"
             />

            {/* Send / Cancel Button */}
            {isLoading ? (
              <button
                onClick={async () => {
                  try {
                    // Close the frontend stream with cancelled=true
                    // This triggers sendCancelRequest which uses the cancelEndpoint we passed
                    postmortemStreamingService.close(true);

                    // Reset UI state
                    setIsLoading(false);
                    setReasoningStreaming(false);
                    setToolEvents([]);
                    setReasoningText('');
                    assistantMessageIndexRef.current = -1;

                    toast.success('Analysis cancelled');
                  } catch (error) {
                    console.error('Failed to cancel analysis:', error);
                    toast.error('Failed to cancel analysis');
                    // Still reset UI state even if backend cancel fails
                    setIsLoading(false);
                    setReasoningStreaming(false);
                    assistantMessageIndexRef.current = -1;
                  }
                }}
                className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-colors bg-red-500 text-white hover:bg-red-600"
                title="Cancel analysis"
              >
                <StopCircle className="h-4 w-4" />
              </button>
             ) : (
               <button
                 onClick={() => handleSendMessage()}
                 disabled={!input.trim()}
                 className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                   input.trim()
                     ? 'bg-black text-white hover:bg-gray-800'
                     : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                 }`}
                 title="Send message"
               >
                 <ArrowUp className="h-4 w-4" />
               </button>
             )}
           </div>

           <div className="flex items-center justify-between px-3 pb-2">
             <div className="flex items-center gap-2">
               {/* Model Selector */}
               <div className="relative">
                 <button
                   onClick={() => setIsModelMenuOpen(!isModelMenuOpen)}
                   className="flex items-center gap-1.5 px-2 py-1 text-[11px] font-medium text-gray-600 hover:text-gray-900 transition-colors"
                 >
                   {currentModel?.logo && (
                     <img src={currentModel.logo} alt="" className="w-3 h-3 object-contain" />
                   )}
                   <span className="truncate max-w-[100px]">{currentModel?.name || 'Select Model'}</span>
                   <ChevronDown className="h-3 w-3 opacity-50" />
                 </button>

                 {/* Model Dropdown Menu - Fixed Positioning via CSS or Portal ideally, but absolute with z-index works if container allows overflow */}
                 {isModelMenuOpen && (
                   <>
                     <div className="fixed inset-0 z-40" onClick={() => setIsModelMenuOpen(false)} />
                     <div className="absolute bottom-full left-0 mb-1 w-48 bg-white border border-gray-200 rounded-md shadow-xl z-50 py-1 max-h-60 overflow-y-auto">
                       {Object.values(MODELS).filter(m => m.available).map((model) => (
                         <button
                           key={model.id}
                           onClick={() => {
                             setSelectedModel(model.id);
                             setIsModelMenuOpen(false);
                           }}
                           className={`w-full text-left px-2.5 py-1.5 text-[11px] hover:bg-gray-50 flex items-center gap-2 ${
                             selectedModel === model.id ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-700'
                           }`}
                         >
                           {model.logo && (
                             <img src={model.logo} alt="" className="w-3.5 h-3.5 object-contain shrink-0" />
                           )}
                           <span className="truncate">{model.name}</span>
                         </button>
                       ))}
                     </div>
                   </>
                 )}
               </div>

               {/* Context & Tools Buttons */}
               <div className="h-4 w-px bg-gray-200 mx-0.5" />

               <div className="relative">
                 <button
                   onClick={() => setIsTransactionMenuOpen(!isTransactionMenuOpen)}
                   className="p-1.5 text-gray-500 hover:text-gray-900 transition-colors relative"
                   title={`${selectedTransactionIds.size} transactions selected`}
                 >
                   <Database className="h-3.5 w-3.5" />
                   {/* Transaction count badge */}
                   {selectedTransactionIds.size > 0 && (
                     <span className="absolute -top-0.5 -right-0.5 bg-blue-600 text-white text-[8px] font-bold rounded-full w-3 h-3 flex items-center justify-center">
                       {selectedTransactionIds.size}
                     </span>
                   )}
                 </button>

                 <TransactionSelectorMenu
                   isOpen={isTransactionMenuOpen}
                   onClose={() => setIsTransactionMenuOpen(false)}
                   transactions={transactions}
                   selectedIds={selectedTransactionIds}
                   onSelectionChange={setSelectedTransactionIds}
                 />
               </div>

               <button
                 onClick={() => setIsWebSearchEnabled(!isWebSearchEnabled)}
                 className={`p-1.5 rounded transition-all ${
                   isWebSearchEnabled
                     ? 'bg-blue-100 text-blue-600 ring-1 ring-blue-200'
                     : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'
                 }`}
                 title={isWebSearchEnabled ? 'Web search enabled (forced)' : 'Enable web search'}
               >
                 <Globe className="h-3.5 w-3.5" />
               </button>

               {/* Cloud Connectors Hover Menu */}
               <div
                 className="relative"
                 onMouseEnter={() => {
                   if (cloudMenuTimeoutRef.current) {
                     clearTimeout(cloudMenuTimeoutRef.current);
                     cloudMenuTimeoutRef.current = null;
                   }
                   setShowCloudMenu(true);
                 }}
                 onMouseLeave={() => {
                   cloudMenuTimeoutRef.current = setTimeout(() => {
                     setShowCloudMenu(false);
                   }, 200);
                 }}
               >
                 <button
                   className="p-1.5 text-gray-500 hover:text-gray-900 transition-colors"
                   title="Connect cloud storage"
                 >
                   <Cloud className="h-3.5 w-3.5" />
                 </button>

                 {/* Cloud Menu Dropdown */}
                 {showCloudMenu && (
                   <div className="absolute bottom-full left-0 mb-1 w-52 bg-white border border-gray-200 rounded-md shadow-xl z-50 py-1">
                     {/* Google Drive */}
                     <button
                       onClick={() => {
                         setShowDrivePicker(true);
                         setShowCloudMenu(false);
                       }}
                       className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 flex items-center gap-2.5 text-gray-700"
                     >
                       <img src="/connector-logos/google-drive.png" alt="Google Drive" className="w-4 h-3 object-contain" />
                       <span className="font-medium">Google Drive</span>
                     </button>

                     {/* OneDrive Personal */}
                     <button
                       onClick={() => {
                         setOneDriveAccountType('personal');
                         setShowOneDrivePicker(true);
                         setShowCloudMenu(false);
                       }}
                       className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 flex items-center gap-2.5 text-gray-700"
                     >
                       <img src="/connector-logos/one-drive.png" alt="OneDrive" className="w-4 h-3 object-contain" />
                       <span className="font-medium">OneDrive Personal</span>
                     </button>

                     {/* OneDrive Business */}
                     <button
                       onClick={() => {
                         setOneDriveAccountType('business');
                         setShowOneDrivePicker(true);
                         setShowCloudMenu(false);
                       }}
                       className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 flex items-center gap-2.5 text-gray-700"
                     >
                       <img src="/connector-logos/one-drive.png" alt="OneDrive Business" className="w-4 h-3 object-contain" />
                       <span className="font-medium">OneDrive Business</span>
                     </button>

                     {/* SharePoint */}
                     <button
                       onClick={() => {
                         setOneDriveAccountType('business');
                         setShowOneDrivePicker(true);
                         setShowCloudMenu(false);
                       }}
                       className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 flex items-center gap-2.5 text-gray-700"
                     >
                       <img src="/connector-logos/sharepoint-logo.png" alt="SharePoint" className="w-4 h-3 object-contain" />
                       <span className="font-medium">SharePoint</span>
                     </button>
                   </div>
                 )}
               </div>

               <button
                 onClick={handleFileUploadClick}
                 disabled={uploadingFiles}
                 className={`p-1.5 transition-colors ${
                   uploadingFiles
                     ? 'opacity-50 cursor-not-allowed text-gray-400'
                     : 'text-gray-500 hover:text-gray-900'
                 }`}
                 title="Upload file"
               >
                 <Upload className="h-3.5 w-3.5" />
               </button>
             </div>

             <div className="text-[10px] text-gray-400 font-medium whitespace-nowrap ml-2">
               {transactionCount} trades
             </div>
           </div>
         </div>
         <div className="text-[10px] text-gray-400 mt-2 text-center">
            AI analysis may generate inaccurate results. Verify important information.
         </div>
       </div>
     </div>

     {/* Cloud Picker Modals */}
     {showDrivePicker && (
       <GoogleDriveNativePicker
         onFilesSelected={handleGoogleDriveSelect}
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

    {/* Post Mortem Guide Panel */}
    <PostMortemGuidePanel
      isOpen={guideOpen}
      onClose={() => setGuideOpen(false)}
    />
  </>
 );
}

