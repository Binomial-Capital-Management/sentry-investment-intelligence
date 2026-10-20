import React, { useState } from 'react';
import { Copy, Download, Play, FileText, Image } from 'lucide-react';
import { saveAs } from 'file-saver';
import api from '@/services/api';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { prism } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface CodeBlock {
  code: string;
  output: string;
  language: string;
}

interface GeneratedFile {
  file_id?: string;
  filename: string;
  type: string;
}

interface CodeExecutionDisplayProps {
  codeBlocks: CodeBlock[];
  generatedFiles: GeneratedFile[];
  containerId?: string;
}

const CodeExecutionDisplay: React.FC<CodeExecutionDisplayProps> = ({
  codeBlocks,
  generatedFiles,
  containerId,
}) => {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const copyToClipboard = async (text: string, index: number) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (err) {
      console.error('Failed to copy code:', err);
    }
  };

  const downloadFile = async (fileId: string, filename: string) => {
    console.log('Starting download for:', { fileId, filename, containerId });

    if (!containerId || !fileId) {
      console.error('Missing container ID or file ID for download');
      alert('Unable to download: Missing file information');
      return;
    }

    try {
      const sessionId = localStorage.getItem('session_id') || undefined;
      const params: Record<string, string> = { filename };
      if (sessionId) {
        params.session_id = sessionId;
      }

      // Use shared axios client with proper baseURL and auth
      const response = await api.get(`/v6/containers/${containerId}/files/${fileId}`, {
        params,
        responseType: 'blob',
        timeout: 30000,
      });

      console.log('Download response received:', {
        status: response.status,
        blobSize: response.data.size,
        blobType: response.data.type,
        filename,
      });

      // response.data is already a blob when responseType is 'blob'
      // Use FileSaver to download directly
      saveAs(response.data, filename);
      console.log('saveAs called for:', filename);
    } catch (error) {
      console.error('Failed to download file:', error);
      const errorMessage = error instanceof Error ? error.message : String(error);
      alert(`Failed to download file: ${errorMessage}`);
    }
  };

  const getFileIcon = (type: string) => {
    if (type === 'image') {
      return <Image size={16} className="text-blue-500" />;
    }
    return <FileText size={16} className="text-gray-500" />;
  };

  if (codeBlocks.length === 0 && generatedFiles.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4 my-4">
      {/* Expiration Warning - Only show when files are present */}
      {generatedFiles.length > 0 && (
        <div
          style={{
            padding: '12px 16px',
            background: '#fff3cd',
            border: '1px solid #ffc107',
            borderRadius: '8px',
            fontSize: '13px',
            color: '#856404',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span style={{ fontSize: '16px' }}>⚠️</span>
          <span>
            <strong>Note:</strong> Generated files expire after 10 minutes. Download them to save permanently.
          </span>
        </div>
      )}

      {/* Code Blocks */}
      {codeBlocks.map((block, index) => (
        <div key={index} className="code-execution-block" style={{
          border: 'none',
          borderRadius: '8px',
          overflow: 'hidden',
        }}>
          {/* Code Header */}
          <div
            className="flex items-center justify-between px-4 py-2 text-sm"
            style={{
              background: '#e9f2ff',
              color: '#495057',
            }}
          >
            <div className="flex items-center gap-2">
              <Play size={14} />
              <span style={{ fontWeight: 500 }}>Python</span>
            </div>
            <button
              onClick={() => copyToClipboard(block.code, index)}
              className="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-200 transition-colors"
              style={{ fontSize: '12px' }}
            >
              <Copy size={12} />
              {copiedIndex === index ? 'Copied!' : 'Copy'}
            </button>
          </div>

          {/* Code Content */}
          <div
            style={{
              background: '#e9f2ff',
              fontFamily: '"Source Code Pro", "Monaco", "Menlo", monospace',
              fontSize: '13px',  // Reduced from 14px
              lineHeight: '1.5',
              padding: '16px',
              overflow: 'auto',
            }}
          >
            <SyntaxHighlighter
              language="python"
              style={prism}
              customStyle={{
                margin: 0,
                padding: 0,
                background: 'transparent',
                fontSize: '13px',
                lineHeight: '1.5',
              }}
              wrapLongLines={true}
            >
              {block.code}
            </SyntaxHighlighter>
          </div>

          {/* Output */}
          {block.output && (
            <div
              style={{
                background: '#e9f2ff',
                fontFamily: '"Source Code Pro", "Monaco", "Menlo", monospace',
                fontSize: '13px',
                color: '#495057',
              }}
            >
              <div
                style={{
                  padding: '8px 16px',
                  borderTop: '1px solid #d1d9e0',
                  borderBottom: '1px solid #e9ecef',
                  fontSize: '12px',
                  fontWeight: 500,
                  color: '#6c757d',
                }}
              >
                Output:
              </div>
              <pre
                style={{
                  margin: 0,
                  padding: '12px 16px',
                  overflow: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  maxHeight: '300px',
                }}
              >
                {block.output}
              </pre>
            </div>
          )}
        </div>
      ))}

      {/* Generated Files */}
      {generatedFiles.length > 0 && (
        <div
          className="generated-files"
        >
          <div
            style={{
              fontSize: '14px',
              fontWeight: 500,
              color: '#495057',
              marginBottom: '8px',
            }}
          >
            Generated Files:
          </div>
          <div className="flex flex-wrap gap-2">
            {generatedFiles.map((file, index) => (
              <div
                key={index}
                className="flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors hover:bg-gray-50"
                style={{
                  fontSize: '13px',
                  border: '1px solid #e9ecef',
                  background: '#fff',
                }}
              >
                {getFileIcon(file.type)}
                <span style={{ fontWeight: 500, cursor: 'default' }}>{file.filename}</span>
                {file.file_id && containerId && (
                  <button
                    type="button"
                    onClick={async (e) => {
                      e.preventDefault();
                      const fid = file.file_id!;
                      const fname = file.filename;
                      console.log('Download button clicked for:', fname, 'file_id:', fid, 'container_id:', containerId);
                      // Call download directly
                      await downloadFile(fid, fname);
                    }}
                    className="flex items-center gap-1 text-blue-600 hover:text-blue-800 transition-colors"
                    style={{ fontSize: '12px', cursor: 'pointer' }}
                  >
                    <Download size={12} />
                    Download
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default CodeExecutionDisplay;
