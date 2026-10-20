import { memo, useState, useRef, useEffect, useCallback } from 'react';
import type { ToolEvent } from '@/types';

interface ThinkingCollapsibleProps {
  reasoningEvents: ToolEvent[];
  isActive: boolean;
}

export const ThinkingCollapsible = memo(function ThinkingCollapsible({
  reasoningEvents,
  isActive,
}: ThinkingCollapsibleProps) {
  const [expanded, setExpanded] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const userScrolledUpRef = useRef(false);
  const [thinkingScrolledFromTop, setThinkingScrolledFromTop] = useState(false);

  const content = reasoningEvents.map((e) => e.result || '').join('\n');
  const startTime = reasoningEvents.length > 0
    ? Math.min(...reasoningEvents.map((e) => e.startTime))
    : Date.now();

  const durationFromEvents = !isActive && reasoningEvents.length > 0
    ? reasoningEvents.reduce((max, e) => {
        const end = e.endTime ?? e.startTime;
        return end > max ? end : max;
      }, 0)
    : 0;

  const [elapsedSecs, setElapsedSecs] = useState(0);
  const finalSecsRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isActive) {
      if (finalSecsRef.current === null) {
        const end = durationFromEvents || Date.now();
        finalSecsRef.current = Math.round((end - startTime) / 1000);
        setElapsedSecs(finalSecsRef.current);
      }
      return;
    }
    finalSecsRef.current = null;
    const update = () => setElapsedSecs(Math.round((Date.now() - startTime) / 1000));
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [isActive, startTime, durationFromEvents]);

  const titleBase = isActive ? 'Thinking' : 'Thought';
  const titleSuffix = !isActive ? ` for ${elapsedSecs}s` : '';

  const toggle = useCallback(() => {
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
      userScrolledUpRef.current = false;
      requestAnimationFrame(() => {
        el.style.height = '0px';
        el.style.opacity = '0';
        el.style.overflow = 'hidden';
        el.offsetHeight;
        el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
        el.style.opacity = '1';
      });
    }
  }, [expanded]);

  const handleTransitionEnd = useCallback(
    (e: React.TransitionEvent<HTMLDivElement>) => {
      if (e.propertyName !== 'height' || !wrapperRef.current) return;
      if (expanded) {
        wrapperRef.current.style.height = 'auto';
        wrapperRef.current.style.overflowY = 'auto';
      }
    },
    [expanded],
  );

  useEffect(() => {
    const el = wrapperRef.current;
    if (!el || !expanded || !isActive) return;
    el.style.overflowY = 'auto';
    if (!userScrolledUpRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [content, expanded, isActive]);

  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const onScroll = () => {
      const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
      userScrolledUpRef.current = !atBottom;
    };
    el.addEventListener('scroll', onScroll);
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  const handleThinkingScroll = useCallback(() => {
    const el = wrapperRef.current;
    if (!el) return;
    setThinkingScrolledFromTop(el.scrollTop > 4);
  }, []);

  if (reasoningEvents.length === 0) return null;

  return (
    <div style={{ paddingLeft: '4px' }}>
      <button className="thinking-outer-header" onClick={toggle}>
        <div className="thinking-outer-title-group">
          <span className={`thinking-outer-label${isActive ? ' timeline-label-shimmer' : ''}`}>
            {titleBase}
            {titleSuffix && <span style={{ opacity: 0.72 }}>{titleSuffix}</span>}
          </span>
          {content && (
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{
                transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s ease',
                flexShrink: 0,
                opacity: 0.5,
              }}
            >
              <polyline points="9 18 15 12 9 6" />
            </svg>
          )}
        </div>
      </button>
      <div style={{ position: 'relative' }}>
        {expanded && thinkingScrolledFromTop && <div className="thinking-fade-top" />}
        <div
          ref={wrapperRef}
          className="thinking-content-wrapper"
          onTransitionEnd={handleTransitionEnd}
          onScroll={handleThinkingScroll}
          style={expanded ? undefined : { height: 0, opacity: 0, overflow: 'hidden' }}
        >
          <div className="thinking-raw-content">{content}</div>
        </div>
      </div>
    </div>
  );
});
