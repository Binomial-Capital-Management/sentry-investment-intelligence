/**
 * MermaidRenderer - Renders Mermaid diagrams from code blocks
 * 
 * Usage:
 * - Pass mermaid code as children
 * - Renders as SVG in the DOM
 * - For PDF export, call renderToSvg() to get static SVG string
 * 
 * Features:
 * - Debounced rendering to handle streaming content
 * - Syntax validation before render attempts
 * - Graceful fallback to code display on errors
 */

import React, { useEffect, useRef, useState, useId, useCallback } from 'react';
import mermaid from 'mermaid';

// Custom theme variables for better colors
const themeVariables = {
  // Primary colors
  primaryColor: '#4f46e5',      // Indigo
  primaryTextColor: '#ffffff',
  primaryBorderColor: '#3730a3',
  
  // Secondary colors  
  secondaryColor: '#10b981',    // Emerald
  secondaryTextColor: '#ffffff',
  secondaryBorderColor: '#059669',
  
  // Tertiary colors
  tertiaryColor: '#f59e0b',     // Amber
  tertiaryTextColor: '#1f2937',
  tertiaryBorderColor: '#d97706',
  
  // Background
  background: '#ffffff',
  mainBkg: '#f3f4f6',
  
  // Lines and borders
  lineColor: '#6b7280',
  
  // Text
  textColor: '#1f2937',
  
  // Node colors
  nodeBorder: '#d1d5db',
  nodeTextColor: '#1f2937',
  
  // Special nodes
  criticalColor: '#ef4444',
  criticalBorderColor: '#dc2626',
  criticalTextColor: '#ffffff',
  
  doneColor: '#22c55e',
  doneBorderColor: '#16a34a',
  
  activeColor: '#3b82f6',
  activeBorderColor: '#2563eb',
  activeTextColor: '#ffffff',
};

// Initialize mermaid with enhanced config supporting colors
mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  themeVariables,
  securityLevel: 'loose',
  suppressErrorRendering: true,  // Don't render error SVGs
  logLevel: 'fatal',  // Only log fatal errors (suppresses syntax errors)
  fontFamily: 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  flowchart: {
    htmlLabels: true,
    curve: 'basis',
    padding: 15,
    nodeSpacing: 50,
    rankSpacing: 50,
  },
  sequence: {
    diagramMarginX: 50,
    diagramMarginY: 10,
    actorMargin: 50,
    width: 150,
    height: 65,
    boxMargin: 10,
    boxTextMargin: 5,
    noteMargin: 10,
    messageMargin: 35,
  },
  gantt: {
    titleTopMargin: 25,
    barHeight: 20,
    barGap: 4,
    topPadding: 50,
    leftPadding: 75,
    gridLineStartPadding: 35,
    fontSize: 11,
  },
  pie: {
    textPosition: 0.75,
  },
});

interface MermaidRendererProps {
  children: string;
  className?: string;
  isStreaming?: boolean;
}

// Debounce delay for streaming content (ms)
const RENDER_DEBOUNCE_MS = 150;
const RENDER_DEBOUNCE_STREAMING_MS = 500; // Longer delay when actively streaming

/**
 * Check if mermaid code looks complete enough to render
 * Helps avoid rendering partial streaming content
 */
function looksComplete(code: string): boolean {
  const trimmed = code.trim();
  
  // Must have at least a diagram type declaration
  if (!isMermaidCode(trimmed)) return false;
  
  // Check for common incomplete patterns
  const incompletePatterns = [
    /-->\s*$/,           // Ends with arrow
    /---\s*$/,           // Ends with link
    /\[\s*$/,            // Unclosed bracket
    /\(\s*$/,            // Unclosed paren  
    /\{\s*$/,            // Unclosed brace
    /"\s*$/,             // Unclosed quote
    /style\s+\w*\s*$/,   // Incomplete style statement
    /classDef\s+\w*\s*$/,// Incomplete classDef
  ];
  
  if (incompletePatterns.some(p => p.test(trimmed))) {
    return false;
  }
  
  // For flowcharts, should have at least one complete node definition
  if (trimmed.startsWith('flowchart') || trimmed.startsWith('graph')) {
    // Should have at least one node with brackets
    if (!/\w+\s*[\[\(\{]/.test(trimmed)) return false;
  }
  
  return true;
}

const MermaidRenderer: React.FC<MermaidRendererProps> = ({ children, className = '', isStreaming = false }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showSource, setShowSource] = useState(false);
  const uniqueId = useId().replace(/:/g, '-');
  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  const lastContentRef = useRef<string>('');
  const isStreamingRef = useRef(isStreaming);
  
  // Keep streaming ref in sync
  isStreamingRef.current = isStreaming;

  const renderDiagram = useCallback(async (code: string) => {
    if (!code?.trim()) {
      setError('No diagram content provided');
      setIsLoading(false);
      return;
    }

    const trimmedCode = code.trim();

    // Skip rendering if content looks incomplete (streaming)
    if (!looksComplete(trimmedCode)) {
      // Show loading state while streaming
      setIsLoading(true);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      // Generate unique ID for this render
      const id = `mermaid-${uniqueId}-${Date.now()}`;
      
      // Render the diagram
      const { svg: renderedSvg } = await mermaid.render(id, trimmedCode);
      setSvg(renderedSvg);
      setError(null);
    } catch (err: any) {
      // Silently handle - this is expected for non-mermaid content that was incorrectly detected
      // Just fall back to code display without logging errors
      setError('invalid');
    } finally {
      setIsLoading(false);
    }
  }, [uniqueId]);

  useEffect(() => {
    // Clear any pending debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    // Skip if content hasn't changed
    if (children === lastContentRef.current && svg) {
      return;
    }
    lastContentRef.current = children;

    // Use longer debounce when actively streaming
    const debounceMs = isStreamingRef.current ? RENDER_DEBOUNCE_STREAMING_MS : RENDER_DEBOUNCE_MS;

    // Debounce to handle streaming content
    debounceRef.current = setTimeout(() => {
      renderDiagram(children);
    }, debounceMs);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [children, renderDiagram, svg, isStreaming]);

  if (isLoading) {
    return (
      <div className={`mermaid-artifact my-4 ${className}`}>
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden shadow-sm">
          {/* Header */}
          <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
            <svg className="w-4 h-4 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
            </svg>
            <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Diagram</span>
          </div>
          {/* Loading content */}
          <div className="flex items-center justify-center py-8 bg-white dark:bg-gray-900">
            <div className="flex items-center gap-2 text-gray-400 dark:text-gray-500">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span className="text-sm">{isStreaming ? 'Building diagram...' : 'Rendering...'}</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    // Silently fall back to a simple code block - no ugly error UI
    // This handles cases where content was incorrectly detected as mermaid
    return (
      <pre className="my-4 p-3 text-xs text-gray-700 dark:text-gray-300 overflow-x-auto font-mono leading-relaxed bg-gray-100 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 max-h-64">
        <code>{children}</code>
      </pre>
    );
  }

  return (
    <div className={`mermaid-artifact my-4 ${className}`}>
      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden shadow-sm">
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
            </svg>
            <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Diagram</span>
          </div>
          <button
            onClick={() => {
              // Copy SVG to clipboard
              navigator.clipboard.writeText(svg);
            }}
            className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 flex items-center gap-1"
            title="Copy SVG"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </button>
        </div>
        
        {/* Diagram content */}
        <div 
          ref={containerRef}
          className="p-4 flex justify-center overflow-x-auto bg-white dark:bg-gray-900"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>
    </div>
  );
};

/**
 * Utility function to render Mermaid to SVG string (for PDF export)
 * This can be called before generating PDF to convert all Mermaid blocks to static SVG
 */
export async function renderMermaidToSvg(code: string): Promise<string> {
  try {
    const id = `mermaid-export-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const { svg } = await mermaid.render(id, code.trim());
    return svg;
  } catch (err) {
    console.error('[renderMermaidToSvg] Failed:', err);
    throw err;
  }
}

/**
 * Check if a string is valid Mermaid syntax
 * More strict detection to avoid false positives on regular text
 */
export function isMermaidCode(code: string): boolean {
  const trimmed = code.trim();
  
  // Must match exact mermaid patterns with direction indicators or specific syntax
  const strictMermaidPatterns = [
    /^graph\s+(TB|BT|LR|RL|TD)\b/i,           // graph TB, graph LR, etc.
    /^flowchart\s+(TB|BT|LR|RL|TD)\b/i,       // flowchart TB, flowchart LR, etc.
    /^sequenceDiagram\s*$/im,                  // sequenceDiagram on its own line
    /^sequenceDiagram\s*\n/i,                  // sequenceDiagram followed by newline
    /^classDiagram\s*$/im,
    /^classDiagram\s*\n/i,
    /^stateDiagram(-v2)?\s*$/im,
    /^stateDiagram(-v2)?\s*\n/i,
    /^erDiagram\s*$/im,
    /^erDiagram\s*\n/i,
    /^gantt\s*$/im,
    /^gantt\s*\n/i,
    /^pie(\s+showData)?\s*$/im,
    /^pie(\s+showData)?\s*\n/i,
    /^journey\s*$/im,
    /^journey\s*\n/i,
    /^gitGraph\s*$/im,
    /^gitGraph\s*\n/i,
    /^mindmap\s*$/im,
    /^mindmap\s*\n/i,
    /^timeline\s*$/im,
    /^timeline\s*\n/i,
    /^quadrantChart\s*$/im,
    /^quadrantChart\s*\n/i,
    /^sankey-beta\s*$/im,
    /^sankey-beta\s*\n/i,
    /^xychart-beta\s*$/im,
    /^xychart-beta\s*\n/i,
    /^block-beta\s*$/im,
    /^block-beta\s*\n/i,
  ];
  
  return strictMermaidPatterns.some(pattern => pattern.test(trimmed));
}

export default MermaidRenderer;
