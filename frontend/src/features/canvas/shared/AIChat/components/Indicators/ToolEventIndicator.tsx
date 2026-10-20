import { memo, useState, useRef, useCallback } from 'react';
import type { ToolEvent } from '@/types';
import { parseAndFormatJson } from '../../utils/json-highlight';

const COLLAPSED_MAX_HEIGHT = 200;

interface ToolEventIndicatorProps {
  toolEvents: ToolEvent[];
}

const isInProgress = (status: ToolEvent['status']) => {
  return !['completed', 'failed'].includes(status);
};

const getToolDisplayName = (event: ToolEvent) => {
  if (event.toolName) {
    return event.toolName
      .replace(/_/g, ' ')
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return 'Processing';
};

const ChevronIcon = ({ expanded }: { expanded: boolean }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="16"
    height="16"
    fill="currentColor"
    viewBox="0 0 256 256"
    className={`timeline-chevron ${expanded ? 'expanded' : ''}`}
  >
    <path d="M213.66,101.66l-80,80a8,8,0,0,1-11.32,0l-80-80A8,8,0,0,1,53.66,90.34L128,164.69l74.34-74.35a8,8,0,0,1,11.32,11.32Z" />
  </svg>
);

const CollapsibleCode = memo(function CollapsibleCode({ html }: { html: string }) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [showMore, setShowMore] = useState(false);
  const [needsTruncation, setNeedsTruncation] = useState(false);

  const measuredRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (node) {
        (contentRef as React.MutableRefObject<HTMLDivElement>).current = node;
        setNeedsTruncation(node.scrollHeight > COLLAPSED_MAX_HEIGHT);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [html],
  );

  return (
    <div className="timeline-code-collapsible">
      <div
        ref={measuredRef}
        className={`timeline-code-content${!showMore && needsTruncation ? ' truncated' : ''}`}
        style={!showMore && needsTruncation ? { maxHeight: COLLAPSED_MAX_HEIGHT, overflow: 'hidden' } : undefined}
      >
        <pre dangerouslySetInnerHTML={{ __html: html }} />
      </div>
      {needsTruncation && (
        <button
          type="button"
          className="timeline-show-more"
          onClick={() => setShowMore((v) => !v)}
        >
          {showMore ? 'Show less' : 'Show more'}
        </button>
      )}
    </div>
  );
});

interface TimelineItemProps {
  event: ToolEvent;
  isFirst: boolean;
  isLast: boolean;
}

const TimelineItem = memo(function TimelineItem({ event, isFirst, isLast }: TimelineItemProps) {
  const [expanded, setExpanded] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const hasContent = event.arguments || event.result || event.error;
  const isError = event.status === 'failed';
  const isRunning = isInProgress(event.status);

  const toggle = useCallback(() => {
    if (!hasContent) return;
    const el = wrapperRef.current;
    if (!el) {
      setExpanded((v) => !v);
      return;
    }

    if (expanded) {
      el.style.overflow = 'hidden';
      el.style.height = `${el.scrollHeight}px`;
      el.offsetHeight;
      el.style.height = '0px';
      el.style.opacity = '0';
      setExpanded(false);
    } else {
      setExpanded(true);
      requestAnimationFrame(() => {
        el.style.height = '0px';
        el.style.opacity = '0';
        el.style.overflow = 'hidden';
        el.offsetHeight;
        el.style.height = `${el.scrollHeight}px`;
        el.style.opacity = '1';
      });
    }
  }, [expanded, hasContent]);

  const handleTransitionEnd = useCallback(
    (e: React.TransitionEvent) => {
      if (e.propertyName !== 'height' || !wrapperRef.current) return;
      if (expanded) {
        wrapperRef.current.style.height = 'auto';
        wrapperRef.current.style.overflow = 'visible';
      }
    },
    [expanded],
  );

  const duration =
    event.status === 'completed' && event.endTime && event.startTime
      ? ((event.endTime - event.startTime) / 1000).toFixed(1)
      : null;

  return (
    <div className="timeline-item-wrapper">
      <div className="timeline-item">
        <div className="timeline-track">
          <div className={`timeline-line-top ${!isFirst ? 'visible' : ''}`} />
          <div className={`timeline-dot${isRunning ? ' timeline-dot-pending' : ''}`} />
          <div className={`timeline-line-bottom ${!isLast ? 'visible' : ''}`} />
        </div>

        <div className="timeline-content">
          <button
            type="button"
            className="timeline-header"
            onClick={toggle}
            disabled={!hasContent}
          >
            <div className="timeline-label-wrapper">
              <span
                className={`timeline-label ${isError ? 'timeline-label-error' : ''} ${isRunning ? 'timeline-label-shimmer' : ''}`}
              >
                {getToolDisplayName(event)}
              </span>
              {duration && <span className="timeline-duration">{duration}s</span>}
            </div>
            {hasContent && <ChevronIcon expanded={expanded} />}
          </button>

          {hasContent && (
            <div
              ref={wrapperRef}
              className="timeline-expanded-wrapper"
              style={{ height: 0, opacity: 0 }}
              onTransitionEnd={handleTransitionEnd}
            >
              <div className="timeline-expanded">
                <div className="timeline-sections">
                  {event.arguments && (
                    <div className="timeline-section">
                      <span className="timeline-section-label">Parameters:</span>
                      <div className="timeline-code">
                        <CollapsibleCode html={parseAndFormatJson(event.arguments)} />
                      </div>
                    </div>
                  )}

                  {isError && event.error && (
                    <div className="timeline-section">
                      <span className="timeline-section-label timeline-label-error">Error:</span>
                      <div className="timeline-error-text">{event.error}</div>
                    </div>
                  )}

                  {!isError && event.result && (
                    <div className="timeline-section">
                      <span className="timeline-section-label">Result:</span>
                      <div className="timeline-code">
                        <CollapsibleCode html={parseAndFormatJson(event.result)} />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

export function ToolEventIndicator({ toolEvents }: ToolEventIndicatorProps) {
  const nonReasoningEvents = toolEvents.filter((e) => e.toolType !== 'reasoning');

  if (nonReasoningEvents.length === 0) return null;

  return (
    <div className="tool-timeline">
      {nonReasoningEvents.map((event, idx) => (
        <TimelineItem
          key={event.id}
          event={event}
          isFirst={idx === 0}
          isLast={idx === nonReasoningEvents.length - 1}
        />
      ))}
    </div>
  );
}
