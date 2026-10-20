import { useMemo, useState } from 'react';
import { useChatStore } from '@stores/chatStore';
import PlotlyChart from '@components/Charts/PlotlyChart';
import type { ToolEvent } from '@/types';
import {
  ChevronDown,
  ChevronRight,
  Check,
  Copy,
  ExternalLink,
} from 'lucide-react';

const ResultsPanel = () => {
  const thread = useChatStore((s) => s.threads.find(t => t.id === s.currentThreadId));
  const lastAssistant = thread?.messages.slice().reverse().find(m => m.role === 'assistant');
  const [active, setActive] = useState<'charts' | 'reasoning' | 'tools' | 'sources' | 'data' | 'json'>('charts');
  const [expandedTools, setExpandedTools] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState(false);

  if (!lastAssistant) {
    return (
      <div className="h-full flex flex-col p-4 space-y-4">
        <div className="h-24 bg-gray-50 border border-gray-100 rounded-sm w-full" />
        <div className="h-40 bg-gray-50 border border-gray-100 rounded-sm w-full" />
        <div className="h-full bg-gray-50 border border-gray-100 rounded-sm w-full" />
      </div>
    );
  }

  const hasCharts = Array.isArray(lastAssistant.charts) && lastAssistant.charts.length > 0;
  const hasSources = Array.isArray(lastAssistant.sources) && lastAssistant.sources.length > 0;
  const hasToolEvents = Array.isArray(lastAssistant.toolEvents) && lastAssistant.toolEvents.length > 0;
  const hasReasoning = !!lastAssistant.reasoningText;
  const hasData = lastAssistant.extras && Object.keys(lastAssistant.extras).length > 0;

  const toggleTool = (id: string) => {
    setExpandedTools(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const formatDuration = (startTime: number, endTime?: number) => {
    if (!endTime) return 'Running...';
    const ms = endTime - startTime;
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-emerald-500';
      case 'failed': return 'bg-red-500';
      case 'in_progress': return 'bg-amber-500';
      default: return 'bg-gray-300';
    }
  };

  const groupedTools = useMemo(() => {
    if (!hasToolEvents) return {};
    const groups: Record<string, ToolEvent[]> = {};
    lastAssistant.toolEvents!.forEach(tool => {
      const type = tool.toolType || 'General';
      if (!groups[type]) groups[type] = [];
      groups[type].push(tool);
    });
    return groups;
  }, [lastAssistant.toolEvents, hasToolEvents]);

  const copyJSON = () => {
    const text = JSON.stringify({
      content: lastAssistant.content,
      sources: lastAssistant.sources,
      charts: lastAssistant.charts,
      toolEvents: lastAssistant.toolEvents,
      reasoningText: lastAssistant.reasoningText,
      extras: lastAssistant.extras,
    }, null, 2);

    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const tabs = [
    { id: 'charts', label: 'Charts', disabled: !hasCharts },
    { id: 'reasoning', label: 'Reasoning', disabled: !hasReasoning },
    { id: 'tools', label: 'Execution', disabled: !hasToolEvents },
    { id: 'sources', label: 'Sources', disabled: !hasSources },
    { id: 'data', label: 'Data', disabled: !hasData },
    { id: 'json', label: 'JSON', disabled: false },
  ] as const;

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200 font-sans text-sm">
      {/* Minimalist Tab Bar */}
      <div className="flex items-center border-b border-gray-200 px-4">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => !tab.disabled && setActive(tab.id as any)}
            disabled={tab.disabled}
            className={`
              relative py-3 px-4 text-xs font-semibold uppercase tracking-wider transition-colors
              ${active === tab.id
                ? 'text-gray-900'
                : tab.disabled
                  ? 'text-gray-300 cursor-not-allowed'
                  : 'text-gray-500 hover:text-gray-700'
              }
            `}
          >
            {tab.label}
            {active === tab.id && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gray-900" />
            )}
          </button>
        ))}
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto bg-gray-50/30">
        <div className="p-0">
          {active === 'charts' && hasCharts && (
            <div className="divide-y divide-gray-100">
              {lastAssistant.charts!.map((c) => (
                <div key={c.id} className="bg-white p-4">
                  <div className="mb-2 text-xs font-medium text-gray-500 uppercase tracking-wide">{c.title || 'Analysis Chart'}</div>
                  <div className="border border-gray-100 rounded-sm bg-white p-1">
                    <PlotlyChart chart={c} />
                  </div>
                </div>
              ))}
            </div>
          )}

          {active === 'reasoning' && hasReasoning && (
            <div className="p-6 max-w-none">
              <div className="prose prose-sm prose-gray max-w-none">
                <div className="whitespace-pre-wrap font-serif text-gray-800 leading-relaxed">
                  {lastAssistant.reasoningText}
                </div>
              </div>
            </div>
          )}

          {active === 'tools' && hasToolEvents && (
            <div className="divide-y divide-gray-200 border-b border-gray-200">
              {Object.entries(groupedTools).map(([type, tools]) => (
                <div key={type} className="bg-white">
                  <div className="bg-gray-50 px-4 py-2 border-b border-gray-100">
                    <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">{type.replace(/_/g, ' ')}</span>
                  </div>
                  <div className="divide-y divide-gray-100">
                    {tools.map((tool) => {
                      const isExpanded = expandedTools.has(tool.id);
                      return (
                        <div key={tool.id} className="group">
                          <button
                            onClick={() => toggleTool(tool.id)}
                            className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 text-left transition-colors"
                          >
                            <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${getStatusColor(tool.status)}`} />
                            <span className="flex-1 font-mono text-xs text-gray-700 truncate">{tool.toolName}</span>
                            <span className="text-xs text-gray-400 font-mono flex-shrink-0 tabular-nums">
                              {formatDuration(tool.startTime, tool.endTime)}
                            </span>
                            {isExpanded ? (
                              <ChevronDown className="w-3 h-3 text-gray-400" />
                            ) : (
                              <ChevronRight className="w-3 h-3 text-gray-400" />
                            )}
                          </button>

                          {isExpanded && (
                            <div className="px-4 py-3 bg-gray-50/50 border-t border-gray-100 space-y-3">
                              {tool.arguments && (
                                <div>
                                  <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Input</div>
                                  <pre className="text-xs font-mono text-gray-600 bg-white border border-gray-200 p-2 rounded-sm overflow-x-auto">
                                    {typeof tool.arguments === 'string' ? tool.arguments : JSON.stringify(tool.arguments, null, 2)}
                                  </pre>
                                </div>
                              )}
                              {tool.result && (
                                <div>
                                  <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Output</div>
                                  <pre className="text-xs font-mono text-gray-600 bg-white border border-gray-200 p-2 rounded-sm overflow-x-auto max-h-60">
                                    {typeof tool.result === 'string' ? tool.result : JSON.stringify(tool.result, null, 2)}
                                  </pre>
                                </div>
                              )}
                              {tool.error && (
                                <div className="text-xs text-red-600 bg-red-50 border border-red-100 p-2 rounded-sm font-mono">
                                  {tool.error}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}

          {active === 'sources' && hasSources && (
            <div className="divide-y divide-gray-100">
              {lastAssistant.sources!.map((s) => (
                <a
                  key={s.id}
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                  className="block p-4 hover:bg-gray-50 group transition-colors"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h4 className="text-sm font-medium text-gray-900 group-hover:text-blue-700 leading-snug mb-1">
                        {s.title}
                      </h4>
                      <div className="flex items-center gap-2 text-xs text-gray-500">
                        <span>{new URL(s.url).hostname.replace('www.', '')}</span>
                      </div>
                    </div>
                    <ExternalLink className="w-3 h-3 text-gray-300 group-hover:text-blue-400 flex-shrink-0 mt-1" />
                  </div>
                </a>
              ))}
            </div>
          )}

          {active === 'data' && hasData && (
            <div className="bg-white">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="py-2 px-4 font-semibold text-gray-500 uppercase tracking-wider w-1/3">Field</th>
                    <th className="py-2 px-4 font-semibold text-gray-500 uppercase tracking-wider">Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {Object.entries(lastAssistant.extras!).map(([k, v]) => (
                    <tr key={k} className="hover:bg-gray-50">
                      <td className="py-2 px-4 text-gray-600 font-medium border-r border-gray-50">{k}</td>
                      <td className="py-2 px-4 text-gray-900 font-mono break-all">{String(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {active === 'json' && (
            <div className="h-full flex flex-col">
              <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
                <span className="text-xs font-mono text-gray-500">raw_response.json</span>
                <button
                  onClick={copyJSON}
                  className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded-sm transition-colors"
                >
                  {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
              <div className="flex-1 overflow-auto p-4 bg-white">
                <pre className="text-xs font-mono text-gray-700 leading-relaxed whitespace-pre-wrap break-words">
                  {JSON.stringify({
                    content: lastAssistant.content,
                    sources: lastAssistant.sources,
                    charts: lastAssistant.charts,
                    toolEvents: lastAssistant.toolEvents,
                    reasoningText: lastAssistant.reasoningText,
                    extras: lastAssistant.extras,
                  }, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ResultsPanel;
