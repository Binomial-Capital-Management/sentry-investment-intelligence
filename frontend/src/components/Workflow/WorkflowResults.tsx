import WorkingContentRenderer from '../Chat/WorkingContentRenderer';
import CodeExecutionDisplay from '../Chat/CodeExecutionDisplay';
import { API_BASE } from '@/services/api';

interface WorkflowResultsProps {
  results: any;
}

export function WorkflowResults({ results }: WorkflowResultsProps) {

  if (!results) {
    console.log('[WorkflowResults] No results provided');
    return null;
  }

  console.log('[WorkflowResults] Rendering with results:', results);

  const copyToClipboard = (content: string) => {
    navigator.clipboard.writeText(content);
  };


  // Check if this is a file download result (PDF/PPT)
  const isFileDownload = results && typeof results === 'object' &&
    (results.type === 'pdf' || results.type === 'ppt' || results.type === 'presentation') &&
    results.download_url;

  console.log('[WorkflowResults] isFileDownload:', isFileDownload, 'type:', results.type);

  // Extract code execution data from results
  const getCodeExecutionData = () => {
    // Direct access
    if (results?.code_execution_data) {
      return results.code_execution_data;
    }

    // Nested in content object
    if (results?.content && typeof results.content === 'object' && results.content.code_execution_data) {
      return results.content.code_execution_data;
    }

    return null;
  };

  // Get the actual content from the results
  const getContent = () => {
    // Handle nested object structures from workflow
    if (results && typeof results === 'object' && !Array.isArray(results)) {
      const contentData = results.content;

      // Handle nested content structure: {type:"text", content:{charts:[], content:"...", sources:[]}}
      if (contentData && typeof contentData === 'object' && !Array.isArray(contentData)) {
        // Extract string content from nested object
        if ('content' in contentData && typeof contentData.content === 'string') {
          return contentData.content;
        }
        // If it's an object but not the nested structure, stringify it
        return JSON.stringify(contentData, null, 2);
      }

      // Content is already a string
      if (typeof contentData === 'string') {
        return contentData;
      }
    }

    // Handle array of results
    if (Array.isArray(results)) {
      const contents = [];
      for (const item of results) {
        if (item && item.content) {
          // Handle nested content in array items
          if (typeof item.content === 'object' && 'content' in item.content) {
            contents.push(item.content.content);
          } else if (typeof item.content === 'string') {
            contents.push(item.content);
          }
        } else if (item && item.summary) {
          contents.push(item.summary);
        } else if (typeof item === 'string') {
          contents.push(item);
        }
      }
      if (contents.length > 0) {
        return contents.join('\n\n');
      }
    }

    // Other fallbacks
    if (results && results.summary) return results.summary;
    if (results && results.output) return results.output;
    if (results && results.message) return results.message;

    // If it's just a string
    if (typeof results === 'string') return results;

    // Default message
    return 'No workflow results available.';
  };

  const getDownloadUrl = () => {
    const url = results?.download_url;
    if (!url) return '#';
    if (/^https?:\/\//i.test(url)) {
      return url;
    }
    const base = (API_BASE || '').replace(/\/$/, '');
    const normalizedPath = url.startsWith('/') ? url : `/${url}`;
    return base ? `${base}${normalizedPath}` : normalizedPath;
  };

  // If this is a file download, show a download card instead of text
  if (isFileDownload) {
    const fileType = results.type === 'pdf' ? 'PDF' : results.type === 'ppt' || results.type === 'presentation' ? 'PowerPoint' : 'Document';
    const fileIcon = results.type === 'pdf' ? (
      <svg className="w-16 h-16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 3v6a1 1 0 001 1h6M9 13h6M9 17h6" />
      </svg>
    ) : (
      <svg className="w-16 h-16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 3v6a1 1 0 001 1h6" />
      </svg>
    );

    return (
      <div className="workflow-results h-full flex items-center justify-center p-8">
        <div className="max-w-2xl w-full">
          <div className="bg-gradient-to-br from-white to-gray-50 dark:from-gray-900 dark:to-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
            {/* Success indicator */}
            <div className="bg-gradient-to-r from-green-500 to-emerald-500 px-6 py-3">
              <div className="flex items-center gap-2 text-white">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span className="font-semibold text-sm uppercase tracking-wide">Completed</span>
              </div>
            </div>

            {/* Main content */}
            <div className="p-12 text-center">
              <div className="flex justify-center mb-6 text-blue-600 dark:text-blue-400">
                {fileIcon}
              </div>
              <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">
                {results.title || `${fileType} Report Generated`}
              </h3>
              <p className="text-gray-600 dark:text-gray-400 mb-8 text-lg">
                Your {fileType.toLowerCase()} report has been generated successfully and is ready for download.
              </p>

              {/* Download button with enhanced styling */}
              <a
                href={getDownloadUrl()}
                download={results.pdf_filename || results.ppt_filename}
                className="inline-flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                <span>Download {fileType}</span>
              </a>

              {/* File info */}
              {results.pdf_filename || results.ppt_filename ? (
                <p className="mt-6 text-sm text-gray-500 dark:text-gray-400 font-mono">
                  {results.pdf_filename || results.ppt_filename}
                </p>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Otherwise show the text results
  return (
    <div className="workflow-results h-full">
      <div className="h-full flex flex-col bg-white dark:bg-gray-900 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        {/* Header with gradient and actions */}
        <div className="flex justify-between items-center px-6 py-4 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-gray-800 dark:to-gray-900 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white dark:bg-gray-800 rounded-lg shadow-sm">
              <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">Workflow Results</h3>
          </div>
          <button
            onClick={() => copyToClipboard(getContent())}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white bg-white hover:bg-gray-50 dark:bg-gray-800 dark:hover:bg-gray-700 rounded-lg shadow-sm border border-gray-200 dark:border-gray-600 transition-all duration-200 hover:shadow-md"
            title="Copy to clipboard"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <span>Copy</span>
          </button>
        </div>

        {/* Content Area - Markdown rendered like chat interface */}
        <div className="flex-1 overflow-y-auto p-6 bg-gradient-to-br from-gray-50 to-white dark:from-gray-900 dark:to-gray-800">
          <div className="max-w-4xl mx-auto">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <WorkingContentRenderer content={getContent()} />

              {/* Code Execution Display - Show code blocks and generated files */}
              {(() => {
                const codeData = getCodeExecutionData();
                if (codeData) {
                  return (
                    <CodeExecutionDisplay
                      codeBlocks={codeData.code_blocks || []}
                      generatedFiles={codeData.generated_files || []}
                      containerId={codeData.container_id}
                    />
                  );
                }
                return null;
              })()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
