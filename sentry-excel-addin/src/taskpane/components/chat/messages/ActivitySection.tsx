/**
 * ActivitySection - Renders tool calls in Claude's timeline style
 * 
 * Uses the grouped timeline structure with dots and connecting lines,
 * matching Claude's exact UI for multiple tool calls.
 */

import React, { memo, useCallback, useRef, useState } from "react";
import { ActivityGroup, ActivityItem } from "../../../../shared/types";
import { formatJsonWithSyntax, parseAndFormatJson } from "../../../utils/json-highlight";

const COLLAPSED_MAX_HEIGHT = 200;

/* ── Icons ── */

const ChevronIcon = ({ expanded }: { expanded: boolean }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="16"
    height="16"
    fill="currentColor"
    viewBox="0 0 256 256"
    className={`timeline-chevron ${expanded ? "expanded" : ""}`}
  >
    <path d="M213.66,101.66l-80,80a8,8,0,0,1-11.32,0l-80-80A8,8,0,0,1,53.66,90.34L128,164.69l74.34-74.35a8,8,0,0,1,11.32,11.32Z" />
  </svg>
);

/* ── Collapsible Code Block ── */

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
    [html],
  );

  return (
    <div className="timeline-code-collapsible">
      <div
        ref={measuredRef}
        className={`timeline-code-content${!showMore && needsTruncation ? " truncated" : ""}`}
        style={!showMore && needsTruncation ? { maxHeight: COLLAPSED_MAX_HEIGHT, overflow: "hidden" } : undefined}
      >
        <pre dangerouslySetInnerHTML={{ __html: html }} />
      </div>
      {needsTruncation && (
        <button
          type="button"
          className="timeline-show-more"
          onClick={() => setShowMore((v) => !v)}
        >
          {showMore ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
});

/* ── Timeline Item ── */

interface TimelineItemProps {
  item: ActivityItem;
  isFirst: boolean;
  isLast: boolean;
  isPending?: boolean;
}

const TimelineItem = memo(function TimelineItem({ item, isFirst, isLast, isPending }: TimelineItemProps) {
  const [expanded, setExpanded] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const hasContent = item.parameters || item.result || item.preview || item.code;
  const isError = item.status === "error";
  const isRunning = item.status === "running";

  const toggle = useCallback(() => {
    if (!hasContent) return;
    const el = wrapperRef.current;
    if (!el) {
      setExpanded((v) => !v);
      return;
    }

    if (expanded) {
      // CLOSE: lock current height in px, then collapse to 0
      el.style.overflow = "hidden";
      el.style.height = `${el.scrollHeight}px`;
      el.offsetHeight; // force reflow
      el.style.height = "0px";
      el.style.opacity = "0";
      setExpanded(false);
    } else {
      // OPEN: start from 0, expand to measured scrollHeight
      setExpanded(true);
      requestAnimationFrame(() => {
        el.style.height = "0px";
        el.style.opacity = "0";
        el.style.overflow = "hidden";
        el.offsetHeight; // force reflow
        el.style.height = `${el.scrollHeight}px`;
        el.style.opacity = "1";
      });
    }
  }, [expanded, hasContent]);

  const handleTransitionEnd = useCallback(
    (e: React.TransitionEvent) => {
      if (e.propertyName !== "height" || !wrapperRef.current) return;
      if (expanded) {
        wrapperRef.current.style.height = "auto";
        wrapperRef.current.style.overflow = "visible";
      }
    },
    [expanded],
  );

  return (
    <div className="timeline-item-wrapper">
      <div className="timeline-item">
        {/* Timeline track (dot + lines) */}
        <div className="timeline-track">
          <div className={`timeline-line-top ${!isFirst ? "visible" : ""}`} />
          <div className={`timeline-dot${isPending && isRunning ? " timeline-dot-pending" : ""}`} />
          <div className={`timeline-line-bottom ${!isLast ? "visible" : ""}`} />
        </div>

        {/* Content */}
        <div className="timeline-content">
          <button
            type="button"
            className="timeline-header"
            onClick={toggle}
            disabled={!hasContent}
          >
            <div className="timeline-label-wrapper">
              <span className={`timeline-label ${isError ? "timeline-label-error" : ""} ${isRunning ? "timeline-label-shimmer" : ""}`}>
                {item.label}
              </span>
              {process.env.NODE_ENV === "development" && item.durationMs != null && (
                <span className="timeline-duration">
                  {item.durationMs < 1000
                    ? `${item.durationMs}ms`
                    : `${(item.durationMs / 1000).toFixed(1)}s`}
                </span>
              )}
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
                  {item.code && (
                    <div className="timeline-section">
                      <span className="timeline-section-label">
                        {item.status === "running" ? "Writing code..." : "Code:"}
                      </span>
                      <div className="timeline-code">
                        <CollapsibleCode
                          html={item.code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}
                        />
                      </div>
                    </div>
                  )}

                  {item.parameters && Object.keys(item.parameters).length > 0 && (
                    <div className="timeline-section">
                      <span className="timeline-section-label">Parameters:</span>
                      <div className="timeline-code">
                        <CollapsibleCode html={formatJsonWithSyntax(item.parameters)} />
                      </div>
                    </div>
                  )}

                  {isError && item.result && "error" in item.result && (
                    <div className="timeline-section">
                      <span className="timeline-section-label timeline-label-error">Error:</span>
                      <div className="timeline-error-text">
                        {String(item.result.error)}
                      </div>
                    </div>
                  )}

                  {item.tool === "code_interpreter" && ((item.result as { output?: string })?.output || item.preview) && (
                    <div className="timeline-section">
                      <span className="timeline-section-label">Output:</span>
                      <div className="timeline-code">
                        <CollapsibleCode
                          html={(String((item.result as { output?: string })?.output ?? item.preview ?? ""))
                            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}
                        />
                      </div>
                    </div>
                  )}

                  {item.tool !== "code_interpreter" && !isError && item.result && Object.keys(item.result).length > 0 && (
                    <div className="timeline-section">
                      <span className="timeline-section-label">Result:</span>
                      <div className="timeline-code">
                        <CollapsibleCode html={formatJsonWithSyntax(item.result)} />
                      </div>
                    </div>
                  )}

                  {item.tool !== "code_interpreter" && !item.result && item.preview && (
                    <div className="timeline-section">
                      <span className="timeline-section-label">Result:</span>
                      <div className="timeline-code">
                        <CollapsibleCode html={parseAndFormatJson(item.preview)} />
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

/* ── Main Component ── */

interface ActivitySectionProps {
  activity: ActivityGroup;
  isPending?: boolean;
}

export const ActivitySection = memo(function ActivitySection({
  activity,
  isPending,
}: ActivitySectionProps) {
  const items = activity.items;

  return (
    <div className="tool-timeline">
      {items.map((item, idx) => (
        <TimelineItem
          key={`${item.tool}-${idx}`}
          item={item}
          isFirst={idx === 0}
          isLast={idx === items.length - 1}
          isPending={isPending && idx === items.length - 1}
        />
      ))}
    </div>
  );
});

export default ActivitySection;
