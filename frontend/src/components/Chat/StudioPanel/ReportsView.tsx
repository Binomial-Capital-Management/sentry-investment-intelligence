/**
 * ReportsView - Displays generated reports with markdown rendering and export
 * Supports: GFM tables, math (KaTeX), Mermaid diagrams
 */

import React, { useState, useRef, useCallback, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import toast from 'react-hot-toast';
import MermaidRenderer, { isMermaidCode } from '../MermaidRenderer';

interface ReportData {
  markdown: string;
  sourceCount?: number;
}

interface ReportsViewProps {
  data: ReportData;
  title?: string;
  onBack?: () => void;
}

const ReportsView: React.FC<ReportsViewProps> = ({ data, title = 'Report', onBack }) => {
  const [copied, setCopied] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(data.markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success('Copied to clipboard');
  };

  const handleDownloadMarkdown = () => {
    const blob = new Blob([data.markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title.replace(/\s+/g, '_')}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('Downloaded .md file');
  };

  const handleDownloadPDF = useCallback(async () => {
    if (!contentRef.current) return;

    setIsExporting(true);
    const toastId = toast.loading('Preparing PDF...');

    try {
      // Wait a moment for any pending Mermaid renders to complete
      await new Promise(resolve => setTimeout(resolve, 500));

      const currentDate = new Date().toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });

      // Clone the content and clean it up for PDF
      const contentClone = contentRef.current.cloneNode(true) as HTMLElement;
      
      // Remove any loading states from Mermaid
      const loadingElements = contentClone.querySelectorAll('.mermaid-container .animate-spin');
      loadingElements.forEach(el => el.parentElement?.remove());

      // Get the cleaned HTML
      const contentHtml = contentClone.innerHTML;

      // Open print window with content
      const printWindow = window.open('', '_blank');
      if (!printWindow) {
        toast.error('Please allow popups', { id: toastId });
        setIsExporting(false);
        return;
      }

      printWindow.document.write(`
<!DOCTYPE html>
<html>
<head>
  <title>${title}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css" crossorigin="anonymous">
  <style>
    @page { margin: 0.75in; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 11pt;
      line-height: 1.6;
      color: #1a1a1a;
      padding: 0;
      margin: 0;
    }
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding-bottom: 12px;
      margin-bottom: 20px;
      border-bottom: 1px solid #ddd;
    }
    .logo { height: 32px; }
    .header-right { text-align: right; }
    .header-title { font-size: 11pt; font-weight: 600; color: #333; }
    .header-date { font-size: 10pt; color: #666; }
    h1 { font-size: 18pt; margin: 20px 0 10px; font-weight: 600; }
    h2 { font-size: 14pt; margin: 18px 0 8px; font-weight: 600; }
    h3 { font-size: 12pt; margin: 14px 0 6px; font-weight: 600; }
    p { margin: 0 0 10px; }
    ul, ol { margin: 0 0 10px; padding-left: 20px; }
    li { margin-bottom: 4px; }
    code { font-family: monospace; font-size: 9pt; background: #f5f5f5; padding: 1px 4px; border-radius: 3px; }
    pre { background: #f5f5f5; padding: 10px; margin: 10px 0; font-size: 9pt; overflow-x: auto; border-radius: 4px; }
    table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 10pt; }
    th, td { border: 1px solid #ddd; padding: 6px; text-align: left; }
    th { background: #f8f8f8; }
    /* Mermaid diagram styling for PDF */
    .mermaid-container { 
      display: flex; 
      justify-content: center; 
      margin: 16px 0;
      page-break-inside: avoid;
    }
    .mermaid-container svg { 
      max-width: 100%; 
      height: auto; 
    }
    /* KaTeX styling */
    .katex { font-size: 1em; }
    .katex-display { margin: 1em 0; overflow-x: auto; }
    .footer {
      margin-top: 24px;
      padding-top: 12px;
      border-top: 1px solid #ddd;
      font-size: 9pt;
      color: #888;
      text-align: center;
    }
    @media print {
      body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      .mermaid-container { break-inside: avoid; }
    }
  </style>
</head>
<body>
  <div class="header">
    <img src="${window.location.origin}/binomial-icon-logo.png" class="logo" />
    <div class="header-right">
      <div class="header-title">${title}</div>
      <div class="header-date">${currentDate}</div>
    </div>
  </div>
  ${contentHtml}
  <div class="footer">Generated by Sentry Investment Intelligence</div>
</body>
</html>
      `);

      printWindow.document.close();
      
      // Wait for KaTeX CSS and images to load, then print
      setTimeout(() => {
        printWindow.print();
        toast.success('Print dialog opened - save as PDF', { id: toastId });
        setIsExporting(false);
      }, 800);
    } catch (error) {
      console.error('[ReportsView] PDF export error:', error);
      toast.error('Failed to generate PDF', { id: toastId });
      setIsExporting(false);
    }
  }, [title]);

  // Pre-process markdown for math delimiters
  const processedMarkdown = useMemo(() => {
    let processed = data.markdown || '';
    
    // Escape monetary values (e.g. $100) to prevent LaTeX interpretation
    processed = processed.replace(/\$(?=\d)/g, '\\$');
    
    // Convert \[ ... \] to $$ ... $$ for block math
    processed = processed.replace(/\\\[([\s\S]*?)\\\]/g, (_, content) => `\n$$${content.trim()}$$\n`);
    
    // Convert \( ... \) to $ ... $ for inline math  
    processed = processed.replace(/\\\(([\s\S]*?)\\\)/g, (_, content) => `$${content.trim()}$`);
    
    return processed;
  }, [data.markdown]);

  // Custom code block handler for Mermaid
  const CodeBlock = useCallback(({ node, inline, className, children, ...props }: any) => {
    const match = /language-(\w+)/.exec(className || '');
    const language = match ? match[1] : '';
    const codeContent = String(children).replace(/\n$/, '');

    // Check if this is a mermaid code block
    if (!inline && (language === 'mermaid' || isMermaidCode(codeContent))) {
      return <MermaidRenderer>{codeContent}</MermaidRenderer>;
    }

    // Inline code
    if (inline) {
      return (
        <code className="px-1 py-0.5 bg-gray-100 rounded text-sm font-mono" {...props}>
          {children}
        </code>
      );
    }

    // Regular code block
    return (
      <pre className="bg-gray-50 border border-gray-200 rounded-lg p-4 overflow-x-auto my-4">
        <code className={className} {...props}>
          {children}
        </code>
      </pre>
    );
  }, []);

  const containerClass = isFullscreen 
    ? 'fixed inset-0 z-50 bg-white flex flex-col' 
    : 'flex flex-col h-full';

  return (
    <div className={containerClass}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white flex-shrink-0">
        <div className="flex items-center gap-3">
          {onBack && (
            <button onClick={onBack} className="p-1 hover:bg-gray-100 rounded">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M19 12H5M12 19l-7-7 7-7" stroke="#666" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          )}
          <div>
            <h3 className="text-sm font-medium text-gray-900">{title}</h3>
            {data.sourceCount && <p className="text-xs text-gray-500">{data.sourceCount} sources</p>}
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 border border-gray-200 rounded"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button
            onClick={handleDownloadMarkdown}
            className="px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 border border-gray-200 rounded flex items-center gap-1.5"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            .md
          </button>
          <button
            onClick={handleDownloadPDF}
            disabled={isExporting}
            className="px-3 py-1.5 text-xs text-white rounded flex items-center gap-1.5 disabled:opacity-50"
            style={{ backgroundColor: '#1a1a1a' }}
          >
            {isExporting ? (
              <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            )}
            PDF
          </button>
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-1.5 hover:bg-gray-100 rounded"
          >
            {isFullscreen ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M18 6L6 18M6 6l12 12" stroke="#666" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3" stroke="#666" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6 bg-gray-50">
        <div 
          ref={contentRef}
          className={`mx-auto bg-white rounded border border-gray-200 p-8 shadow-sm ${isFullscreen ? 'max-w-4xl' : 'max-w-3xl'}`}
        >
          <div className="prose prose-sm prose-gray max-w-none">
            <ReactMarkdown 
              remarkPlugins={[remarkGfm, remarkMath]}
              rehypePlugins={[[rehypeKatex, { strict: false, trust: true }]]}
              components={{
                code: CodeBlock,
              }}
            >
              {processedMarkdown}
            </ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportsView;
