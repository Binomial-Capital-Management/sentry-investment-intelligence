import { X, FileText } from 'lucide-react';
import type { UploadedFile } from '@/services/upload';

interface AttachedFilesProps {
  files: UploadedFile[];
  onRemoveFile: (fileId: string) => void;
}

export function AttachedFiles({ files, onRemoveFile }: AttachedFilesProps) {
  if (files.length === 0) return null;

  return (
    <div style={{
      padding: '0.5rem 0.75rem 0.25rem',
      borderBottom: '1px solid hsl(var(--cc-border-300) / 10%)',
    }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
        {files.map((file) => (
          <div
            key={file.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.375rem',
              padding: '0.25rem 0.5rem',
              backgroundColor: 'hsl(var(--cc-bg-200))',
              borderRadius: 6,
              fontFamily: 'var(--cc-font-ui)',
              fontSize: '0.688rem',
              color: 'hsl(var(--cc-text-300))',
              position: 'relative',
            }}
          >
            {file.source === 'google_drive' && (
              <div style={{
                position: 'absolute',
                top: -4,
                left: -4,
                width: 14,
                height: 14,
                backgroundColor: 'hsl(var(--cc-bg-000))',
                borderRadius: '50%',
                border: '1px solid hsl(var(--cc-border-300) / 15%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <svg style={{ width: 8, height: 8 }} viewBox="0 0 24 24" fill="none">
                  <path d="M12.545 2.26a2.024 2.024 0 00-1.09 0L2.8 5.55C1.804 5.96 1 6.96 1 8.077v7.846c0 1.117.804 2.117 1.8 2.527l8.655 3.29c.345.135.745.135 1.09 0l8.655-3.29C22.196 17.94 23 16.94 23 15.823V8.077c0-1.117-.804-2.117-1.8-2.527L12.545 2.26z" fill="#4285F4"/>
                </svg>
              </div>
            )}
            {file.source === 'onedrive' && (
              <div style={{
                position: 'absolute',
                top: -4,
                left: -4,
                width: 14,
                height: 14,
                backgroundColor: 'hsl(var(--cc-bg-000))',
                borderRadius: '50%',
                border: '1px solid hsl(var(--cc-border-300) / 15%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <svg style={{ width: 8, height: 8 }} viewBox="0 0 24 24" fill="none">
                  <path d="M9.5 8.5a5.5 5.5 0 1011 0 5.5 5.5 0 00-11 0z" fill="#0364B8"/>
                  <path d="M3 14.5a5.5 5.5 0 1011 0 5.5 5.5 0 00-11 0z" fill="#0078D4"/>
                  <path d="M14 14.5a5.5 5.5 0 11-11 0 5.5 5.5 0 0111 0z" fill="#28A8EA"/>
                </svg>
              </div>
            )}
            <FileText style={{ width: 12, height: 12, color: 'hsl(var(--cc-text-400))', flexShrink: 0 }} />
            <span style={{
              fontWeight: 500,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              maxWidth: 120,
            }}>
              {file.original_name}
            </span>
            <button
              onClick={() => onRemoveFile(file.id)}
              className="cc-btn-ghost"
              title="Remove file"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 16,
                height: 16,
                background: 'transparent',
                border: 'none',
                borderRadius: 'var(--cc-radius-sm)',
                color: 'hsl(var(--cc-text-400))',
                cursor: 'pointer',
                marginLeft: '0.125rem',
              }}
            >
              <X style={{ width: 10, height: 10 }} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
