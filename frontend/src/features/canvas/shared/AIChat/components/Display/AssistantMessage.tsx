import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import type { ToolEvent } from '@/types';
import type { Message } from '../../types';
import { LoadingIndicator, ToolEventIndicator, ThinkingCollapsible } from '../Indicators';
import { ExportButtons } from '../Interactive';

interface AssistantMessageProps {
  message: Message;
  isLoading: boolean;
  isLastMessage: boolean;
  reasoningStreaming: boolean;
  reasoningText: string;
  statusMessage: string;
  markdownComponents: Partial<Components>;
  toolEvents: ToolEvent[];
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
}

const isInProgress = (status: ToolEvent['status']) => {
  return !['completed', 'failed'].includes(status);
};

type EventSegment =
  | { type: 'reasoning'; events: ToolEvent[] }
  | { type: 'tools'; events: ToolEvent[] };

function segmentToolEvents(toolEvents: ToolEvent[]): EventSegment[] {
  const segments: EventSegment[] = [];
  for (const event of toolEvents) {
    const segType = event.toolType === 'reasoning' ? 'reasoning' : 'tools';
    const last = segments[segments.length - 1];
    if (last && last.type === segType) {
      last.events.push(event);
    } else {
      segments.push({ type: segType, events: [event] });
    }
  }
  return segments;
}

export function AssistantMessage({
  message,
  isLoading,
  isLastMessage,
  reasoningStreaming,
  reasoningText,
  statusMessage,
  markdownComponents,
  toolEvents,
  exportState,
}: AssistantMessageProps) {
  const segments = useMemo(() => segmentToolEvents(toolEvents), [toolEvents]);

  const hasAnyEvents = toolEvents.length > 0;
  const hasReasoning = toolEvents.some((e) => e.toolType === 'reasoning');
  const showLoadingIndicator =
    isLoading &&
    isLastMessage &&
    !message.content &&
    !reasoningStreaming &&
    !reasoningText &&
    !hasReasoning &&
    !hasAnyEvents;
  const showExportButtons = !isLoading && isLastMessage;

  const contentStyle: React.CSSProperties = {
    fontFamily: 'var(--cc-font-response)',
    fontSize: '0.875rem',
    lineHeight: 1.625,
    color: 'hsl(var(--cc-text-100))',
    wordBreak: 'break-word',
    overflowWrap: 'anywhere',
  };

  const renderSegments = () =>
    segments.map((seg, i) => {
      if (seg.type === 'reasoning') {
        const isLastSeg = i === segments.length - 1;
        const isActive =
          isLoading && isLastMessage && isLastSeg && seg.events.some((e) => isInProgress(e.status));
        return (
          <ThinkingCollapsible key={`seg-${i}`} reasoningEvents={seg.events} isActive={isActive} />
        );
      }
      return <ToolEventIndicator key={`seg-${i}`} toolEvents={seg.events} />;
    });

  const renderContent = () => {
    const nonReasoningEvents = toolEvents.filter((e) => e.toolType !== 'reasoning');
    const getContentPosition = (te: ToolEvent): number | undefined => {
      const pos = te.details?.contentPosition;
      return typeof pos === 'number' ? pos : undefined;
    };

    const eventsWithPosition = nonReasoningEvents.filter(
      (te) => getContentPosition(te) !== undefined,
    );

    if (eventsWithPosition.length === 0) {
      return (
        <div style={contentStyle}>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {message.content}
          </ReactMarkdown>
        </div>
      );
    }

    const content = message.content;
    const sortedEvents = [...eventsWithPosition].sort(
      (a, b) => (getContentPosition(a) || 0) - (getContentPosition(b) || 0),
    );
    const splitPosition = getContentPosition(sortedEvents[0]) || 0;

    if (splitPosition === 0 || splitPosition >= content.length) {
      return content ? (
        <div style={contentStyle}>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {content}
          </ReactMarkdown>
        </div>
      ) : null;
    }

    const beforeTools = content.slice(0, splitPosition);
    const afterTools = content.slice(splitPosition);

    return (
      <>
        {beforeTools && (
          <div style={contentStyle}>
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {beforeTools}
            </ReactMarkdown>
          </div>
        )}
        {afterTools && (
          <div style={contentStyle}>
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {afterTools}
            </ReactMarkdown>
          </div>
        )}
      </>
    );
  };

  return (
    <div style={{ marginBottom: '1rem', animation: 'fadeSlideIn 0.25s ease-out' }}>
      {showLoadingIndicator && <LoadingIndicator statusMessage={statusMessage} />}

      {renderSegments()}

      {renderContent()}

      {showExportButtons && (
        <div style={{ display: 'flex', gap: '0.125rem', marginTop: '0.5rem' }}>
          <ExportButtons
            message={message}
            copyFeedback={exportState.copyFeedback}
            exportingPdf={exportState.exportingPdf}
            exportingPpt={exportState.exportingPpt}
            exportingWorkbook={exportState.exportingWorkbook}
            showStyleSelector={exportState.showStyleSelector}
            availableStyles={exportState.availableStyles}
            selectedStyleName={exportState.selectedStyleName}
            styleSelectorRef={exportState.styleSelectorRef}
            setShowStyleSelector={exportState.setShowStyleSelector}
            setSelectedStyleName={exportState.setSelectedStyleName}
            onCopy={() => exportState.handleCopy(message)}
            onPDFExport={() => exportState.handlePDFExport(message)}
            onPPTExport={() => exportState.handlePPTExport(message)}
            onWorkbookExport={() => exportState.handleWorkbookExport(message)}
          />
        </div>
      )}
    </div>
  );
}
