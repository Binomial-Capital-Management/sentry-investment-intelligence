/**
 * MarkdownViewer - Renders SEC filing Markdown with pagination
 */

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { MarkdownPage } from './types';

interface MarkdownViewerProps {
  content: string;
  pages: MarkdownPage[];
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  expanded?: boolean;
}

// Shared markdown component config
const markdownComponents = (expanded: boolean) => ({
  table: ({ children }: { children: React.ReactNode }) => (
    <table style={{ 
      borderCollapse: 'collapse', 
      margin: expanded ? '1.5em 0' : '1em 0', 
      fontSize: expanded ? '13px' : '12px', 
      width: '100%' 
    }}>
      {children}
    </table>
  ),
  th: ({ children }: { children: React.ReactNode }) => (
    <th style={{ 
      padding: expanded ? '10px 14px' : '8px 12px', 
      textAlign: 'left', 
      borderBottom: '2px solid #ddd', 
      fontWeight: 600, 
      background: '#f9f9f9' 
    }}>
      {children}
    </th>
  ),
  td: ({ children }: { children: React.ReactNode }) => (
    <td style={{ 
      padding: expanded ? '8px 14px' : '6px 12px', 
      borderBottom: '1px solid #eee' 
    }}>
      {children}
    </td>
  ),
  h1: ({ children }: { children: React.ReactNode }) => (
    <h1 style={{ 
      fontSize: expanded ? '1.8em' : '1.5em', 
      marginTop: '1.5em', 
      marginBottom: '0.5em', 
      color: '#111',
      borderBottom: expanded ? '1px solid #eee' : 'none',
      paddingBottom: expanded ? '0.3em' : 0,
    }}>
      {children}
    </h1>
  ),
  h2: ({ children }: { children: React.ReactNode }) => (
    <h2 style={{ 
      fontSize: expanded ? '1.5em' : '1.3em', 
      marginTop: '1.3em', 
      marginBottom: '0.5em', 
      color: '#222' 
    }}>
      {children}
    </h2>
  ),
  h3: ({ children }: { children: React.ReactNode }) => (
    <h3 style={{ 
      fontSize: expanded ? '1.2em' : '1.1em', 
      marginTop: '1.2em', 
      marginBottom: '0.4em', 
      color: '#333' 
    }}>
      {children}
    </h3>
  ),
  p: ({ children }: { children: React.ReactNode }) => (
    <p style={{ margin: expanded ? '1em 0' : '0.75em 0' }}>{children}</p>
  ),
  a: ({ href, children }: { href?: string; children: React.ReactNode }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: '#1976d2' }}>
      {children}
    </a>
  ),
  ul: ({ children }: { children: React.ReactNode }) => (
    <ul style={{ paddingLeft: '1.5em', margin: '0.75em 0' }}>{children}</ul>
  ),
  ol: ({ children }: { children: React.ReactNode }) => (
    <ol style={{ paddingLeft: '1.5em', margin: '0.75em 0' }}>{children}</ol>
  ),
  li: ({ children }: { children: React.ReactNode }) => (
    <li style={{ margin: '0.3em 0' }}>{children}</li>
  ),
  blockquote: ({ children }: { children: React.ReactNode }) => (
    <blockquote style={{ 
      borderLeft: '3px solid #ddd', 
      paddingLeft: '1em', 
      margin: '1em 0', 
      color: '#555' 
    }}>
      {children}
    </blockquote>
  ),
});

export const MarkdownViewer: React.FC<MarkdownViewerProps> = ({
  content,
  pages,
  currentPage,
  totalPages,
  onPageChange,
  expanded = false,
}) => {
  const displayContent = pages.length > 0 && pages[currentPage - 1] 
    ? pages[currentPage - 1].content 
    : content;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Pagination bar */}
      {totalPages > 1 && (
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center', 
          padding: '8px', 
          borderBottom: '1px solid #eee',
          background: '#fafafa',
          gap: '8px',
        }}>
          {expanded && (
            <button
              onClick={() => onPageChange(1)}
              disabled={currentPage === 1}
              style={paginationButtonStyle(currentPage === 1)}
            >
              First
            </button>
          )}
          <button
            onClick={() => onPageChange(Math.max(1, currentPage - 1))}
            disabled={currentPage === 1}
            style={paginationButtonStyle(currentPage === 1, true)}
          >
            <ChevronLeft />
          </button>
          <span style={{ 
            fontSize: expanded ? '13px' : '11px', 
            color: expanded ? '#333' : '#666', 
            minWidth: expanded ? '100px' : '60px', 
            textAlign: 'center' 
          }}>
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage === totalPages}
            style={paginationButtonStyle(currentPage === totalPages, true)}
          >
            <ChevronRight />
          </button>
          {expanded && (
            <button
              onClick={() => onPageChange(totalPages)}
              disabled={currentPage === totalPages}
              style={paginationButtonStyle(currentPage === totalPages)}
            >
              Last
            </button>
          )}
        </div>
      )}
      
      {/* Content */}
      <div style={{ 
        flex: 1,
        overflow: 'auto', 
        padding: expanded ? '32px 48px' : '20px 28px',
        fontSize: expanded ? '14px' : '13px',
        lineHeight: expanded ? '1.7' : '1.6',
        color: '#1a1a1a',
        background: '#fff',
      }}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={markdownComponents(expanded) as any}
        >
          {displayContent}
        </ReactMarkdown>
      </div>
    </div>
  );
};

// Helper styles
const paginationButtonStyle = (disabled: boolean, isIcon = false) => ({
  background: 'none',
  border: '1px solid #ddd',
  borderRadius: '4px',
  padding: isIcon ? '4px 8px' : '4px 8px',
  cursor: disabled ? 'not-allowed' : 'pointer',
  opacity: disabled ? 0.5 : 1,
  fontSize: '12px',
  display: 'flex',
  alignItems: 'center',
});

// SVG Icons
const ChevronLeft = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M15 18l-6-6 6-6"/>
  </svg>
);

const ChevronRight = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M9 18l6-6-6-6"/>
  </svg>
);

export default MarkdownViewer;
