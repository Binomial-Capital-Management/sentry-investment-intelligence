import { useEffect, useMemo, useState } from 'react';
import { Loader2, Search, X } from 'lucide-react';
import toast from 'react-hot-toast';
import onedriveService, { OneDriveFile } from '@/services/onedrive';

interface OneDriveFilePickerProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (file: OneDriveFile) => Promise<void> | void;
  allowedMimeTypes?: string[];
  title?: string;
}

function matchesMimeType(mimeType: string | undefined, allowed: string[]): boolean {
  if (!mimeType) return false;
  return allowed.some((pattern) => {
    if (pattern.endsWith('*')) {
      const prefix = pattern.slice(0, -1);
      return mimeType.startsWith(prefix);
    }
    return mimeType === pattern;
  });
}

export default function OneDriveFilePicker({
  isOpen,
  onClose,
  onSelect,
  allowedMimeTypes,
  title = 'Select a OneDrive file',
}: OneDriveFilePickerProps) {
  const [files, setFiles] = useState<OneDriveFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [nextToken, setNextToken] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectingId, setSelectingId] = useState<string | null>(null);

  const filteredFiles = useMemo(() => {
    if (!allowedMimeTypes?.length) {
      return files;
    }
    return files.filter((file) => matchesMimeType(file.mimeType, allowedMimeTypes));
  }, [files, allowedMimeTypes]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setFiles([]);
    setNextToken(null);
    setSearchTerm('');
    loadFiles();
  }, [isOpen]);

  const loadFiles = async (query?: string, pageToken?: string, append = false) => {
    try {
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      const response = await onedriveService.listFiles({
        query,
        pageToken,
        pageSize: 50,
      });

      const driveFiles = response.files || [];
      setFiles((prev) => (append ? [...prev, ...driveFiles] : driveFiles));
      setNextToken(response.next_page_token ?? null);
    } catch (error) {
      console.error('Failed to load OneDrive files', error);
      toast.error('Failed to load OneDrive files');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  const handleSearch = (event: React.FormEvent) => {
    event.preventDefault();
    loadFiles(searchTerm || undefined);
  };

  const handleSelect = async (file: OneDriveFile) => {
    try {
      setSelectingId(file.id);
      await onSelect(file);
    } catch (error) {
      console.error('Failed to attach OneDrive file', error);
      toast.error('Failed to attach OneDrive file');
    } finally {
      setSelectingId(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(17, 24, 39, 0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 2000,
        padding: '24px',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 'min(720px, 95vw)',
          maxHeight: '85vh',
          background: '#FFFFFF',
          borderRadius: '16px',
          boxShadow: '0 20px 45px rgba(15, 23, 42, 0.25)',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid #E5E7EB',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#111827' }}>{title}</h2>
            <p style={{ fontSize: '13px', color: '#6B7280', marginTop: '4px' }}>
              Select a file from your connected OneDrive account.
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '8px',
            }}
            aria-label="Close"
          >
            <X size={18} color="#6B7280" />
          </button>
        </div>

        <div style={{ padding: '16px 24px', borderBottom: '1px solid #F3F4F6' }}>
          <form
            onSubmit={handleSearch}
            style={{
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <div style={{ position: 'relative', flex: 1 }}>
              <Search
                size={16}
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#9CA3AF',
                }}
              />
              <input
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search files"
                style={{
                  width: '100%',
                  padding: '10px 12px 10px 38px',
                  borderRadius: '10px',
                  border: '1px solid #D1D5DB',
                  fontSize: '14px',
                  color: '#111827',
                }}
              />
            </div>
            <button
              type="submit"
              style={{
                padding: '10px 16px',
                borderRadius: '10px',
                border: 'none',
                background: '#2563EB',
                color: '#FFFFFF',
                fontSize: '14px',
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              Search
            </button>
          </form>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {loading ? (
            <div style={{ padding: '40px 0', display: 'flex', justifyContent: 'center' }}>
              <Loader2 className="animate-spin" size={28} color="#2563EB" />
            </div>
          ) : filteredFiles.length === 0 ? (
            <div style={{ padding: '36px 24px', textAlign: 'center', color: '#6B7280', fontSize: '14px' }}>
              No files found. Try adjusting your search or upload a new file in OneDrive.
            </div>
          ) : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {filteredFiles.map((file) => (
                <li
                  key={file.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '14px 24px',
                    borderBottom: '1px solid #F3F4F6',
                    gap: '16px',
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '14px', fontWeight: 500, color: '#111827' }}>{file.name}</div>
                    <div style={{ fontSize: '12px', color: '#6B7280', marginTop: '4px' }}>
                      {file.mimeType || (file.isFolder ? 'Folder' : 'Unknown type')}
                      {file.modifiedTime ? ` • Updated ${new Date(file.modifiedTime).toLocaleString()}` : ''}
                      {typeof file.size === 'number' ? ` • ${(Number(file.size) / (1024 * 1024)).toFixed(2)} MB` : ''}
                    </div>
                  </div>
                  <button
                    onClick={() => handleSelect(file)}
                    disabled={selectingId === file.id}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '999px',
                      border: 'none',
                      background: selectingId === file.id ? '#9CA3AF' : '#2563EB',
                      color: '#FFFFFF',
                      fontSize: '13px',
                      fontWeight: 500,
                      cursor: selectingId === file.id ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {selectingId === file.id ? (
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Loader2 size={14} className="animate-spin" />
                        Attaching...
                      </span>
                    ) : (
                      'Attach'
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {nextToken && (
          <div style={{ padding: '12px 24px', borderTop: '1px solid #F3F4F6', textAlign: 'center' }}>
            <button
              onClick={() => loadFiles(searchTerm || undefined, nextToken, true)}
              disabled={loadingMore}
              style={{
                padding: '8px 18px',
                borderRadius: '999px',
                border: '1px solid #D1D5DB',
                background: '#FFFFFF',
                color: '#111827',
                fontSize: '13px',
                cursor: loadingMore ? 'not-allowed' : 'pointer',
              }}
            >
              {loadingMore ? 'Loading…' : 'Load more'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
