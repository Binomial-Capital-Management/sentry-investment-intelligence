import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Loader2, Check, X, Brain, Activity, Search,
  Zap, Database, FileText, Image as ImageIcon,
  Terminal, ChevronDown, ArrowRight, Cpu, Globe,
} from 'lucide-react';
import type { ToolEvent } from '@/types';

// Helper function to get appropriate icon for tool type
const getToolIcon = (event: ToolEvent, isStreaming: boolean) => {
  const iconProps = { size: 13, strokeWidth: 1.5 };

  if (!isStreaming && event.status === 'completed') {
    return <Check {...iconProps} className="text-emerald-600" />;
  }
  if (!isStreaming && event.status === 'failed') {
    return <X {...iconProps} className="text-red-600" />;
  }

  const toolName = (event.toolName || '').toLowerCase();
  const toolType = event.toolType;

  // Default color for icons
  const defaultClass = 'text-gray-500';

  if (toolType === 'code_interpreter' || toolName.includes('code') || toolName.includes('python')) {
    return <Terminal {...iconProps} className={defaultClass} />;
  }
  if (toolType === 'file_search' || toolName.includes('file search')) {
    return <Search {...iconProps} className={defaultClass} />;
  }
  if (toolType === 'web_search' || toolName.includes('web') || toolName.includes('search')) {
    return <Globe {...iconProps} className={defaultClass} />;
  }
  if (toolName.includes('data') || toolName.includes('fetch') || toolName.includes('query')) {
    return <Database {...iconProps} className={defaultClass} />;
  }
  if (toolName.includes('file') || toolName.includes('document')) {
    return <FileText {...iconProps} className={defaultClass} />;
  }
  if (toolType === 'mcp_call') {
    return <Cpu {...iconProps} className={defaultClass} />;
  }
  if (toolType === 'custom_tool_call') {
    return <Zap {...iconProps} className={defaultClass} />;
  }
  if (toolType === 'image_generation') {
    return <ImageIcon {...iconProps} className={defaultClass} />;
  }

  return <Activity {...iconProps} className={defaultClass} />;
};

// Helper function to get contextual status message
const getToolStatusMessage = (event: ToolEvent): string => {
  const { toolType, status, toolName } = event;
  const nameLower = (toolName || '').toLowerCase();

  const isDone = status === 'completed' || status === 'failed';

  // MCP calls
  if (toolType === 'mcp_call') {
    if (nameLower.includes('stock') || nameLower.includes('price')) {
      return isDone ? 'Market Data' : 'Fetching market data';
    }
    if (nameLower.includes('filing') || nameLower.includes('sec')) {
      return isDone ? 'SEC Filings' : 'Retrieving filings';
    }
    if (nameLower.includes('news')) {
      return isDone ? 'News Search' : 'Searching news';
    }
  }

  // Code Interpreter
  if (toolType === 'code_interpreter') {
    if (status === 'in_progress') return 'Preparing Environment';
    if (status === 'interpreting' || status === 'code_delta') return 'Executing Python';
    return 'Code Execution';
  }

  if (isDone) return toolName || 'Task';

  // Fallbacks for in-progress
  if (status === 'in_progress') return `Running ${toolName}`;
  if (status === 'searching') return 'Searching';
  if (status === 'generating') return 'Generating';

  return toolName || 'Processing';
};

interface StreamingProgressProps {
  toolEvents?: ToolEvent[];
  reasoningStreaming?: boolean;
  reasoningText?: string;
  isComplete?: boolean;
}

const StreamingProgress = ({
  toolEvents = [],
  reasoningStreaming = false,
  reasoningText = '',
  isComplete = false,
}: StreamingProgressProps) => {
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const [autoExpanded, setAutoExpanded] = useState<string | null>(null);

  // Auto-expand active tools/reasoning
  useEffect(() => {
    if (isComplete) {
      setExpandedItem(null);
      return;
    }

    if (reasoningStreaming) {
      setAutoExpanded('reasoning');
    } else {
      const activeEvent = toolEvents.find(e =>
        e.status === 'in_progress' ||
        e.status === 'searching' ||
        e.status === 'interpreting' ||
        e.status === 'generating',
      );
      if (activeEvent) {
        setAutoExpanded(activeEvent.id);
      }
    }
  }, [reasoningStreaming, toolEvents, isComplete]);

  if (isComplete) return null;
  const showReasoning = reasoningStreaming || reasoningText;
  if (toolEvents.length === 0 && !showReasoning) return null;

  const activeId = expandedItem !== null ? expandedItem : autoExpanded;

  const transition = { duration: 0.2, ease: 'easeInOut' };

  return (
    <div className="flex flex-col gap-0.5 my-2 pl-1 select-none font-sans text-[11px]">
      <AnimatePresence initial={false} mode="sync">
        {/* Reasoning Node */}
        {showReasoning && (
          <motion.div
            layout
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={transition}
            className="relative group"
          >
            {/* Timeline connector */}
             <div className="absolute left-[9px] top-[20px] bottom-[-2px] w-[1px] bg-gray-100 group-last:hidden" />

            <div className="flex flex-col pb-0.5">
              <button
                onClick={() => setExpandedItem(expandedItem === 'reasoning' ? null : 'reasoning')}
                className={`
                  relative z-10 flex items-center gap-3 py-1.5 pr-3 pl-0.5 rounded-sm transition-colors w-full
                  hover:bg-gray-50/50
                `}
              >
                <div className={`
                  w-[18px] h-[18px] rounded-[2px] flex items-center justify-center border transition-colors
                  ${reasoningStreaming
                    ? 'bg-white border-gray-300 text-gray-700'
                    : 'bg-white border-gray-200 text-gray-400'}
                `}>
                  {reasoningStreaming ? (
                    <Loader2 size={10} className="animate-spin" />
                  ) : (
                    <Brain size={10} />
                  )}
                </div>

                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <span className={`font-medium tracking-tight ${reasoningStreaming ? 'text-gray-900' : 'text-gray-600'}`}>
                    Reasoning
                  </span>
                </div>

                <ChevronDown
                  size={10}
                  className={`text-gray-400 transition-transform duration-200 ${activeId === 'reasoning' ? 'rotate-180' : ''}`}
                />
              </button>

              {/* Expanded Reasoning Content */}
              <AnimatePresence>
                {activeId === 'reasoning' && reasoningText && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={transition}
                    className="ml-[19px] pl-3 overflow-hidden"
                  >
                    <div className="relative pb-2">
                      <div className="absolute left-0 top-0 bottom-0 w-[1px] bg-gray-100" />
                      <div className="text-gray-600 font-mono leading-relaxed whitespace-pre-wrap bg-gray-50 p-2 rounded-sm border border-gray-100 text-[10px]">
                        {reasoningText}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        )}

        {/* Tool Events */}
        {toolEvents.map((event, index) => {
          const isActive = event.status === 'in_progress' ||
                          event.status === 'searching' ||
                          event.status === 'interpreting' ||
                          event.status === 'generating' ||
                          event.status === 'code_delta';

          const isFailed = event.status === 'failed';
          const isCompleted = event.status === 'completed';

          return (
            <motion.div
              layout
              key={event.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={transition}
              className="relative group"
            >
              {/* Timeline connector */}
              {index < toolEvents.length - 1 && (
                <div className="absolute left-[9px] top-[20px] bottom-[-2px] w-[1px] bg-gray-100" />
              )}

              <div className="flex flex-col pb-0.5">
                <button
                  onClick={() => setExpandedItem(expandedItem === event.id ? null : event.id)}
                  className={`
                    relative z-10 flex items-center gap-3 py-1.5 pr-3 pl-0.5 rounded-sm transition-colors w-full
                    hover:bg-gray-50/50
                  `}
                >
                  {/* Status Icon Box */}
                  <div className={`
                    w-[18px] h-[18px] rounded-[2px] flex items-center justify-center border transition-colors z-10
                    ${isActive
                      ? 'bg-white border-gray-300 text-gray-900'
                      : isFailed
                        ? 'bg-white border-red-200 text-red-600'
                        : 'bg-white border-gray-200 text-gray-400'}
                  `}>
                     {isActive ? (
                       <Loader2 size={10} className="animate-spin" />
                     ) : (
                       getToolIcon(event, isActive)
                     )}
                  </div>

                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className={`font-medium tracking-tight truncate ${
                      isActive ? 'text-gray-900' :
                      isFailed ? 'text-red-700' :
                      'text-gray-600'
                    }`}>
                      {getToolStatusMessage(event)}
                    </span>
                  </div>

                  <ChevronDown
                    size={10}
                    className={`text-gray-400 transition-transform duration-200 ${activeId === event.id ? 'rotate-180' : ''}`}
                  />
                </button>

                {/* Details Pane */}
                <AnimatePresence>
                  {activeId === event.id && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={transition}
                      className="ml-[19px] pl-3 overflow-hidden"
                    >
                      <div className="relative pb-2">
                        {/* Guide line for nested content */}
                        <div className="absolute left-0 top-0 bottom-0 w-[1px] bg-gray-100" />

                        <div className="bg-white rounded-sm border border-gray-200 overflow-hidden">
                          {/* Code View */}
                          {event.toolType === 'code_interpreter' && event.details?.code && (
                            <div className="bg-gray-900 border-l-2 border-gray-600">
                              <div className="flex items-center justify-between px-3 py-1.5 border-b border-gray-800 bg-gray-900">
                                <div className="flex items-center gap-2">
                                  <Terminal size={10} className="text-gray-400" />
                                  <span className="text-[9px] font-mono uppercase tracking-wider text-gray-400">Python</span>
                                </div>
                              </div>
                              <div className="p-2.5 overflow-x-auto custom-scrollbar">
                                <pre className="font-mono text-[10px] leading-relaxed text-gray-300">
                                  {String(event.details.code)}
                                </pre>
                              </div>
                            </div>
                          )}

                          {/* Arguments View */}
                          {event.arguments && event.toolType !== 'code_interpreter' && (
                            <div className="p-2 border-b border-gray-100 last:border-0 bg-gray-50/50">
                              <div className="flex items-center gap-1.5 mb-1.5 text-gray-500">
                                <ArrowRight size={10} />
                                <span className="text-[9px] font-semibold uppercase tracking-wider">Input</span>
                              </div>
                              <pre className="text-gray-600 font-mono whitespace-pre-wrap break-words text-[10px] bg-white p-2 rounded-sm border border-gray-200">
                                {event.arguments.length > 300 ? event.arguments.slice(0, 300) + '...' : event.arguments}
                              </pre>
                            </div>
                          )}

                          {/* Result View */}
                          {event.result && isCompleted && (
                            <div className="p-2 bg-emerald-50/30 border-l-2 border-emerald-500/20">
                               <div className="flex items-center gap-1.5 mb-1.5 text-emerald-700/80">
                                 <Check size={10} />
                                 <span className="text-[9px] font-bold uppercase tracking-wider">Output</span>
                               </div>
                               <pre className="text-gray-600 font-mono whitespace-pre-wrap break-words max-h-40 overflow-y-auto custom-scrollbar text-[10px]">
                                 {event.result.length > 200 ? event.result.slice(0, 200) + '...' : event.result}
                               </pre>
                            </div>
                          )}

                          {/* Error View */}
                          {event.error && (
                            <div className="p-2 bg-red-50/30 text-red-700 border-t border-red-100 border-l-2 border-red-500/30">
                               <div className="flex items-center gap-1.5 mb-1.5 opacity-80">
                                 <X size={10} />
                                 <span className="text-[9px] font-bold uppercase tracking-wider">Error</span>
                               </div>
                               <span className="text-[10px] font-mono">{event.error}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
};

export default StreamingProgress;
