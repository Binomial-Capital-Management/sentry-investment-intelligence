import { useEffect } from 'react';
import { Upload } from 'lucide-react';
import type { UploadedFile } from '@/services/upload';
import type { SavedProcess } from '../../types';
import { AttachedFiles } from '../Display/AttachedFiles';

interface ChatInputAreaProps {
  inputRef: React.RefObject<HTMLTextAreaElement>;
  input: string;
  setInput: (value: string) => void;
  isLoading: boolean;
  process: SavedProcess | null;
  attachedFiles: UploadedFile[];
  isDraggingFiles: boolean;
  onSend: () => void;
  onCancel: () => void;
  onRemoveFile: (fileId: string) => void;
  dragHandlers: {
    onDragEnter: (e: React.DragEvent) => void;
    onDragLeave: (e: React.DragEvent) => void;
    onDragOver: (e: React.DragEvent) => void;
    onDrop: (e: React.DragEvent) => void;
  };
  children?: React.ReactNode;
}

const MIN_HEIGHT = 24;
const MAX_HEIGHT = 200;

export function ChatInputArea({
  inputRef,
  input,
  setInput,
  isLoading,
  process,
  attachedFiles,
  isDraggingFiles,
  onSend,
  onCancel,
  onRemoveFile,
  dragHandlers,
  children,
}: ChatInputAreaProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  useEffect(() => {
    const textarea = inputRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    const newHeight = Math.min(Math.max(textarea.scrollHeight, MIN_HEIGHT), MAX_HEIGHT);
    textarea.style.height = `${newHeight}px`;
  }, [input, inputRef]);

  return (
    <div
      style={{
        backgroundColor: 'hsl(var(--cc-bg-000))',
        border: '1px solid hsl(var(--cc-border-300) / 15%)',
        borderRadius: 16,
        boxShadow: '0px 4px 20px 0px rgba(0, 0, 0, 0.04)',
        position: 'relative',
        zIndex: 30,
        overflow: 'visible',
        transition: 'border-color 0.15s ease',
      }}
      onDragEnter={dragHandlers.onDragEnter}
      onDragLeave={dragHandlers.onDragLeave}
      onDragOver={dragHandlers.onDragOver}
      onDrop={dragHandlers.onDrop}
    >
      {/* Drag-and-Drop Overlay */}
      {isDraggingFiles && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'hsla(var(--cc-accent-main-100) / 8%)',
          backdropFilter: 'blur(4px)',
          borderRadius: 16,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          pointerEvents: 'none',
          zIndex: 50,
        }}>
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 8,
          }}>
            <Upload size={28} style={{ color: 'hsl(var(--cc-accent-main-000))' }} />
            <span style={{
              fontFamily: 'var(--cc-font-ui)',
              fontSize: '0.75rem',
              fontWeight: 500,
              color: 'hsl(var(--cc-accent-main-000))',
            }}>
              Drop files here
            </span>
          </div>
        </div>
      )}

      {/* Attached Files Display */}
      <AttachedFiles files={attachedFiles} onRemoveFile={onRemoveFile} />

      {/* Input field wrapper */}
      <div style={{ padding: '0.75rem 1rem 0' }}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={process ? "Ask about this analysis..." : "Reply"}
          disabled={isLoading}
          rows={1}
          style={{
            width: '100%',
            fontFamily: 'var(--cc-font-ui)',
            fontSize: '0.875rem',
            color: 'hsl(var(--cc-text-100))',
            backgroundColor: 'transparent',
            border: 'none',
            outline: 'none',
            resize: 'none',
            overflowY: 'auto',
            lineHeight: 1.5,
            minHeight: `${MIN_HEIGHT}px`,
            maxHeight: `${MAX_HEIGHT}px`,
            opacity: isLoading ? 0.5 : 1,
          }}
        />
      </div>

      {/* Toolbar (ChatControls rendered as children) */}
      {children && (
        <div style={{
          padding: '0 0.625rem 0.625rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          {children}
        </div>
      )}
    </div>
  );
}
