import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Plus, Trash2, Edit3, Check, Loader2, Bold, Italic, List, ListOrdered, Maximize2, Minimize2, Activity, FileText, ChevronDown, ChevronUp } from 'lucide-react';
import MemoryIcon from '@/components/Icons/MemoryIcon';
import sentryLogo from '@/assets/binomial-icon-logo.png';
import memoryApiService from '@/services/memoryApi';
import { uploadService } from '@/services/upload';
import type { MemoryNote, MemoryNoteCreate, ContextTokenStats } from '@/types/memory';
import { useChatStore } from '@stores/chatStore';
import toast from 'react-hot-toast';

// Max characters to show before truncating
const TRUNCATE_LENGTH = 300;

interface MemoryNotebookModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId: string;
}

// Rich text editor component
const RichTextEditor = ({
  value,
  onChange,
  placeholder,
  autoFocus = false,
  minHeight = '80px',
  expanded = false,
  onToggleExpand,
  showExpand = false,
}: {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
  minHeight?: string;
  expanded?: boolean;
  onToggleExpand?: () => void;
  showExpand?: boolean;
}) => {
  const editorRef = useRef<HTMLDivElement>(null);
  const [isEmpty, setIsEmpty] = useState(!value);
  const [activeFormats, setActiveFormats] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (editorRef.current && value !== editorRef.current.innerHTML) {
      editorRef.current.innerHTML = value;
      setIsEmpty(!value);
    }
  }, [value]);

  useEffect(() => {
    if (autoFocus && editorRef.current) {
      setTimeout(() => editorRef.current?.focus(), 100);
    }
  }, [autoFocus]);

  // Check active formats on selection change
  const updateActiveFormats = useCallback(() => {
    const formats = new Set<string>();
    if (document.queryCommandState('bold')) formats.add('bold');
    if (document.queryCommandState('italic')) formats.add('italic');
    if (document.queryCommandState('insertUnorderedList')) formats.add('ul');
    if (document.queryCommandState('insertOrderedList')) formats.add('ol');
    setActiveFormats(formats);
  }, []);

  useEffect(() => {
    document.addEventListener('selectionchange', updateActiveFormats);
    return () => document.removeEventListener('selectionchange', updateActiveFormats);
  }, [updateActiveFormats]);

  const handleInput = () => {
    if (editorRef.current) {
      const html = editorRef.current.innerHTML;
      const text = editorRef.current.textContent || '';
      setIsEmpty(!text.trim());
      onChange(html);
      updateActiveFormats();
    }
  };

  const execCommand = (command: string, value?: string) => {
    document.execCommand(command, false, value);
    editorRef.current?.focus();
    handleInput();
    updateActiveFormats();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
      e.preventDefault();
      execCommand('bold');
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 'i') {
      e.preventDefault();
      execCommand('italic');
    }
  };

  const ToolbarButton = ({ 
    command, 
    icon: Icon, 
    title,
    isActive,
  }: { 
    command: string; 
    icon: React.ElementType; 
    title: string;
    isActive: boolean;
  }) => (
    <button
      type="button"
      onClick={() => execCommand(command)}
      style={{
        padding: '5px 8px',
        background: isActive ? '#E1DFDD' : 'transparent',
        border: 'none',
        borderRadius: '4px',
        cursor: 'pointer',
        color: isActive ? '#0078D4' : '#323130',
        display: 'flex',
        alignItems: 'center',
        fontWeight: isActive ? 600 : 400,
        transition: 'all 0.1s ease',
      }}
      title={title}
      onMouseEnter={(e) => {
        if (!isActive) e.currentTarget.style.background = '#F3F2F1';
      }}
      onMouseLeave={(e) => {
        if (!isActive) e.currentTarget.style.background = 'transparent';
      }}
    >
      <Icon size={15} strokeWidth={isActive ? 2.5 : 2} />
    </button>
  );

  return (
    <div style={{
      border: '1px solid #E1DFDD',
      borderRadius: '6px',
      background: '#FAF9F8',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      height: expanded ? '100%' : 'auto',
    }}>
      {/* Toolbar inside the editor area */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '2px',
        padding: '6px 8px',
        borderBottom: '1px solid #E1DFDD',
        background: '#FFFFFF',
      }}>
        <div style={{ display: 'flex', gap: '2px' }}>
          <ToolbarButton 
            command="bold" 
            icon={Bold} 
            title="Bold (⌘B)" 
            isActive={activeFormats.has('bold')}
          />
          <ToolbarButton 
            command="italic" 
            icon={Italic} 
            title="Italic (⌘I)" 
            isActive={activeFormats.has('italic')}
          />
          <div style={{ width: '1px', background: '#E1DFDD', margin: '0 4px' }} />
          <ToolbarButton 
            command="insertUnorderedList" 
            icon={List} 
            title="Bullet list" 
            isActive={activeFormats.has('ul')}
          />
          <ToolbarButton 
            command="insertOrderedList" 
            icon={ListOrdered} 
            title="Numbered list" 
            isActive={activeFormats.has('ol')}
          />
        </div>
        {showExpand && onToggleExpand && (
          <button
            type="button"
            onClick={onToggleExpand}
            style={{
              padding: '4px 8px',
              background: 'transparent',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              color: '#605E5C',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '11px',
            }}
            title={expanded ? 'Collapse' : 'Expand'}
            onMouseEnter={(e) => e.currentTarget.style.background = '#F3F2F1'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
          >
            {expanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            <span>{expanded ? 'Collapse' : 'Expand'}</span>
          </button>
        )}
      </div>

      {/* Editable content area */}
      <div style={{ position: 'relative', flex: expanded ? 1 : 'none' }}>
        <div
          ref={editorRef}
          contentEditable
          onInput={handleInput}
          onKeyDown={handleKeyDown}
          onMouseUp={updateActiveFormats}
          onKeyUp={updateActiveFormats}
          style={{
            minHeight: expanded ? '100%' : minHeight,
            height: expanded ? '100%' : 'auto',
            padding: '10px 12px',
            fontSize: '13px',
            lineHeight: 1.6,
            outline: 'none',
            color: '#323130',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            overflowY: 'auto',
          }}
          suppressContentEditableWarning
        />
        {isEmpty && (
          <div style={{
            position: 'absolute',
            top: '10px',
            left: '12px',
            color: '#A19F9D',
            fontSize: '13px',
            pointerEvents: 'none',
          }}>
            {placeholder}
          </div>
        )}
      </div>
    </div>
  );
};

const MemoryNotebookModal: React.FC<MemoryNotebookModalProps> = ({
  isOpen,
  onClose,
  sessionId,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const [notes, setNotes] = useState<MemoryNote[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newNoteHtml, setNewNoteHtml] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editHtml, setEditHtml] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);
  const [tokenStats, setTokenStats] = useState<ContextTokenStats | null>(null);
  const [isPinningFile, setIsPinningFile] = useState(false);
  const [expandedNotes, setExpandedNotes] = useState<Set<string>>(new Set());
  const [useLongDocMode, setUseLongDocMode] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Get current model from chat store
  const getCurrentThreadModel = useChatStore((s) => s.getCurrentThreadModel);
  const currentModel = getCurrentThreadModel?.() || 'gpt-6.1-sol';

  // Load token stats
  const loadTokenStats = useCallback(async () => {
    if (!sessionId) return;
    try {
      const stats = await memoryApiService.getTokenStats(sessionId, currentModel);
      setTokenStats(stats);
    } catch (err) {
      console.error('[MemoryNotebook] Failed to load token stats:', err);
    }
  }, [sessionId, currentModel]);

  // Load notes
  const loadNotes = useCallback(async () => {
    if (!sessionId) return;
    setIsLoading(true);
    try {
      const data = await memoryApiService.getNotes(sessionId);
      setNotes(data.notes || []);
    } catch (err) {
      console.error('[MemoryNotebook] Failed to load:', err);
      setNotes([]);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (isOpen && sessionId) {
      loadNotes();
      loadTokenStats();
    }
  }, [isOpen, sessionId, loadNotes, loadTokenStats]);

  // Reset states when closing
  useEffect(() => {
    if (!isOpen) {
      setIsExpanded(false);
      setExpandedNotes(new Set());
    }
  }, [isOpen]);

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
      onClose();
    }
  };

  const getTextContent = (html: string): string => {
    const div = document.createElement('div');
    div.innerHTML = html;
    return div.textContent || '';
  };

  // Check if content needs truncation
  const needsTruncation = (content: string): boolean => {
    const text = getTextContent(content);
    return text.length > TRUNCATE_LENGTH;
  };

  // Toggle note expansion
  const toggleNoteExpansion = (noteId: string) => {
    setExpandedNotes(prev => {
      const newSet = new Set(prev);
      if (newSet.has(noteId)) {
        newSet.delete(noteId);
      } else {
        newSet.add(noteId);
      }
      return newSet;
    });
  };

  // Get truncated content for display
  const getTruncatedHtml = (html: string): string => {
    const text = getTextContent(html);
    if (text.length <= TRUNCATE_LENGTH) return html;
    
    // Find a good break point (word boundary)
    let breakPoint = TRUNCATE_LENGTH;
    const spaceIndex = text.lastIndexOf(' ', TRUNCATE_LENGTH);
    if (spaceIndex > TRUNCATE_LENGTH - 50) {
      breakPoint = spaceIndex;
    }
    
    // Create truncated text and wrap in div to maintain formatting
    const truncated = text.slice(0, breakPoint);
    return `<span>${truncated.replace(/</g, '&lt;').replace(/>/g, '&gt;')}...</span>`;
  };

  const handleAddNote = async () => {
    const text = getTextContent(newNoteHtml);
    if (!text.trim()) return;
    try {
      const payload: MemoryNoteCreate = { content: newNoteHtml };
      const created = await memoryApiService.createNote(sessionId, payload);
      setNotes(prev => [created, ...prev]);
      setNewNoteHtml('');
      setIsExpanded(false); // Collapse after adding
      loadTokenStats(); // Refresh token stats
    } catch (err) {
      console.error('[MemoryNotebook] Failed to add note:', err);
    }
  };

  const handleUpdateNote = async (id: string) => {
    const text = getTextContent(editHtml);
    if (!text.trim()) return;
    try {
      const updated = await memoryApiService.updateNote(sessionId, id, { content: editHtml });
      setNotes(prev => prev.map(n => n.id === id ? updated : n));
      setEditingId(null);
      setEditHtml('');
    } catch (err) {
      console.error('[MemoryNotebook] Failed to update:', err);
    }
  };

  const handleDeleteNote = async (id: string) => {
    try {
      await memoryApiService.deleteNote(sessionId, id);
      setNotes(prev => prev.filter(n => n.id !== id));
      loadTokenStats(); // Refresh token stats
    } catch (err) {
      console.error('[MemoryNotebook] Failed to delete:', err);
    }
  };

  // Handle file upload and pin to memory
  const handleFilePinClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    setIsPinningFile(true);
    
    const toastId = `pin-file-${Date.now()}`;
    toast.loading(`Uploading and extracting "${file.name}"...`, { id: toastId });

    try {
      // First upload the file
      const uploadedFiles = await uploadService.uploadFiles([file]);
      if (!uploadedFiles || uploadedFiles.length === 0) {
        throw new Error('Failed to upload file');
      }

      const uploadedFile = uploadedFiles[0];
      
      // Then pin it to memory (extracts content)
      toast.loading(`Extracting content from "${file.name}"...`, { id: toastId });
      const newNote = await memoryApiService.pinFileToMemory(sessionId, uploadedFile.id, {
        extractionMode: useLongDocMode ? 'text' : undefined,
        index: true,
      });
      
      // Add the new note to the list
      setNotes(prev => [newNote, ...prev]);
      loadTokenStats(); // Refresh token stats
      
      toast.success(`"${file.name}" pinned to memory`, { id: toastId });
    } catch (err: any) {
      console.error('[MemoryNotebook] Failed to pin file:', err);
      toast.error(err?.response?.data?.detail || 'Failed to pin file', { id: toastId });
    } finally {
      setIsPinningFile(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-[100]"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.4)' }}
      onClick={handleBackdropClick}
    >
      <motion.div
        ref={modalRef}
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.98 }}
        transition={{ duration: 0.15 }}
        layout
        style={{
          background: '#FFFFFF',
          borderRadius: '8px',
          boxShadow: '0 4px 24px rgba(0, 0, 0, 0.15)',
          width: '100%',
          maxWidth: isExpanded ? '95vw' : '720px',
          height: isExpanded ? '90vh' : 'auto',
          maxHeight: isExpanded ? '90vh' : '85vh',
          display: 'flex',
          flexDirection: 'column',
          border: '1px solid #E1DFDD',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          transition: 'max-width 0.2s ease, height 0.2s ease',
        }}
      >
        {/* Header */}
        <div style={{
          padding: '14px 16px',
          borderBottom: '1px solid #E1DFDD',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MemoryIcon size={16} color="#605E5C" />
            <span style={{ fontSize: '14px', fontWeight: 600, color: '#323130' }}>
              Memory Notebook
            </span>
          </div>
          <button
            onClick={onClose}
            style={{
              padding: '4px',
              background: 'transparent',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              color: '#605E5C',
              display: 'flex',
            }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Add Note Input */}
        <div style={{ 
          padding: '12px 16px', 
          borderBottom: '1px solid #F3F2F1',
          flex: isExpanded ? 1 : 'none',
          display: 'flex',
          flexDirection: 'column',
          minHeight: isExpanded ? 0 : 'auto',
        }}>
          <div style={{ flex: isExpanded ? 1 : 'none', display: 'flex', flexDirection: 'column' }}>
            <RichTextEditor
              value={newNoteHtml}
              onChange={setNewNoteHtml}
              placeholder="Add a note for the AI to remember..."
              autoFocus={isOpen}
              expanded={isExpanded}
              onToggleExpand={() => setIsExpanded(!isExpanded)}
              showExpand={true}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px', flexShrink: 0 }}>
            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.csv,.xlsx,.xls,.txt,.json,.png,.jpg,.jpeg,.webp,.gif"
              onChange={handleFileSelected}
              style={{ display: 'none' }}
            />
            
            {/* Pin File section */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {/* Pin File button */}
              <button
                onClick={handleFilePinClick}
                disabled={isPinningFile}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '6px 12px',
                  fontSize: '12px',
                  fontWeight: 500,
                  color: isPinningFile ? '#A19F9D' : '#323130',
                  background: '#F3F2F1',
                  border: '1px solid #E1DFDD',
                  borderRadius: '4px',
                  cursor: isPinningFile ? 'wait' : 'pointer',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={(e) => {
                  if (!isPinningFile) {
                    e.currentTarget.style.background = '#E1DFDD';
                    e.currentTarget.style.borderColor = '#C8C6C4';
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = '#F3F2F1';
                  e.currentTarget.style.borderColor = '#E1DFDD';
                }}
                title="Upload a file and extract its content to memory"
              >
                {isPinningFile ? (
                  <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                ) : (
                  <FileText size={14} />
                )}
                {isPinningFile ? 'Extracting...' : 'Pin File'}
              </button>
              
              {/* Long document checkbox */}
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '11px',
                  color: '#605E5C',
                  cursor: 'pointer',
                  userSelect: 'none',
                }}
                title="Check this for PDFs with 4+ pages to extract full text instead of using Vision (which only processes first 5 pages)"
              >
                <input
                  type="checkbox"
                  checked={useLongDocMode}
                  onChange={(e) => setUseLongDocMode(e.target.checked)}
                  style={{
                    width: '14px',
                    height: '14px',
                    accentColor: '#0078D4',
                    cursor: 'pointer',
                  }}
                />
                Long document
              </label>
            </div>

            <button
              onClick={handleAddNote}
              disabled={!getTextContent(newNoteHtml).trim()}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: 500,
                color: getTextContent(newNoteHtml).trim() ? '#FFFFFF' : '#A19F9D',
                background: getTextContent(newNoteHtml).trim() ? '#0078D4' : '#F3F2F1',
                border: 'none',
                borderRadius: '4px',
                cursor: getTextContent(newNoteHtml).trim() ? 'pointer' : 'default',
              }}
            >
              <Plus size={14} />
              Add Note
            </button>
          </div>
        </div>

        {/* Notes List - hidden when expanded */}
        {!isExpanded && (
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '8px 16px 16px',
          }}>
            {isLoading ? (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '32px 0',
                color: '#605E5C',
              }}>
                <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
              </div>
            ) : notes.length === 0 ? (
              <div style={{
                textAlign: 'center',
                padding: '32px 16px',
                color: '#605E5C',
              }}>
                <MemoryIcon size={24} color="#C8C6C4" />
                <p style={{ fontSize: '13px', margin: 0 }}>No notes yet</p>
                <p style={{ fontSize: '12px', color: '#A19F9D', margin: '4px 0 0' }}>
                  Add notes the AI should remember
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <AnimatePresence>
                  {notes.map((note) => (
                    <motion.div
                      key={note.id}
                      layout
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.98 }}
                      style={{
                        background: '#FFFFFF',
                        border: editingId === note.id ? '1px solid #0078D4' : '1px solid #E1DFDD',
                        borderRadius: '6px',
                        padding: '12px 14px',
                      }}
                    >
                      {editingId === note.id ? (
                        <div>
                          <RichTextEditor
                            value={editHtml}
                            onChange={setEditHtml}
                            autoFocus
                            minHeight="60px"
                          />
                          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px', marginTop: '8px' }}>
                            <button
                              onClick={() => { setEditingId(null); setEditHtml(''); }}
                              style={{
                                padding: '5px 10px',
                                fontSize: '12px',
                                color: '#605E5C',
                                background: 'transparent',
                                border: '1px solid #E1DFDD',
                                borderRadius: '4px',
                                cursor: 'pointer',
                              }}
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => handleUpdateNote(note.id)}
                              disabled={!getTextContent(editHtml).trim()}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '5px 10px',
                                fontSize: '12px',
                                color: '#FFFFFF',
                                background: getTextContent(editHtml).trim() ? '#0078D4' : '#A19F9D',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: getTextContent(editHtml).trim() ? 'pointer' : 'default',
                              }}
                            >
                              <Check size={12} />
                              Save
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                            <div
                              className="note-content"
                              style={{
                                fontSize: '13px',
                                color: '#323130',
                                lineHeight: 1.6,
                                flex: 1,
                              }}
                              dangerouslySetInnerHTML={{ 
                                __html: expandedNotes.has(note.id) || !needsTruncation(note.content) 
                                  ? note.content 
                                  : getTruncatedHtml(note.content) 
                              }}
                            />
                            <div style={{ display: 'flex', gap: '2px', flexShrink: 0 }}>
                              <button
                                onClick={() => { setEditingId(note.id); setEditHtml(note.content); }}
                              style={{
                                padding: '4px',
                                background: 'transparent',
                                border: 'none',
                                borderRadius: '3px',
                                cursor: 'pointer',
                                color: '#605E5C',
                              }}
                              title="Edit"
                            >
                              <Edit3 size={13} />
                            </button>
                            <button
                              onClick={() => handleDeleteNote(note.id)}
                              style={{
                                padding: '4px',
                                background: 'transparent',
                                border: 'none',
                                borderRadius: '3px',
                                cursor: 'pointer',
                                color: '#605E5C',
                              }}
                              title="Delete"
                            >
                              <Trash2 size={13} />
                            </button>
                            </div>
                          </div>
                          {/* View more/less button for long notes */}
                          {needsTruncation(note.content) && (
                            <button
                              onClick={() => toggleNoteExpansion(note.id)}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                marginTop: '8px',
                                padding: '4px 8px',
                                fontSize: '11px',
                                fontWeight: 500,
                                color: '#0078D4',
                                background: 'transparent',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                transition: 'background 0.15s',
                              }}
                              onMouseEnter={(e) => e.currentTarget.style.background = '#F3F2F1'}
                              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                            >
                              {expandedNotes.has(note.id) ? (
                                <>
                                  <ChevronUp size={14} />
                                  View less
                                </>
                              ) : (
                                <>
                                  <ChevronDown size={14} />
                                  View more
                                </>
                              )}
                            </button>
                          )}
                        </div>
                      )}
                      {editingId !== note.id && (
                        <div style={{
                          marginTop: '8px',
                          paddingTop: '8px',
                          borderTop: '1px solid #F3F2F1',
                          fontSize: '10px',
                          color: '#A19F9D',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '12px'
                        }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          {note.source === 'ai' ? (
                            <>
                              <img src={sentryLogo} alt="Sentry" style={{ width: '12px', height: '12px' }} />
                              Sentry
                            </>
                          ) : note.source === 'tool' ? (
                            <>
                              <FileText size={12} style={{ color: '#605E5C' }} />
                              File
                            </>
                          ) : '👤 You'}
                        </span>
                          <span>{new Date(note.created_at).toLocaleDateString(undefined, {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}</span>
                          {/* Indexed badge for chunked notes */}
                          {(note.is_chunked || note.reference_metadata?.indexed) && (
                            <span style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '3px',
                              padding: '2px 6px',
                              fontSize: '9px',
                              fontWeight: 500,
                              color: '#107C10',
                              background: '#DFF6DD',
                              borderRadius: '3px',
                            }}>
                              Indexed
                            </span>
                          )}
                        </div>
                      )}
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}
          </div>
        )}

        {/* Footer with Token Stats */}
        <div style={{
          padding: '12px 16px',
          borderTop: '1px solid #E1DFDD',
          flexShrink: 0,
          background: '#FAF9F8',
        }}>
          {/* Token Usage Bar */}
          {tokenStats && (
            <div style={{ marginBottom: '8px' }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between',
                marginBottom: '4px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Activity size={12} style={{ color: '#605E5C' }} />
                  <span style={{ fontSize: '11px', color: '#323130', fontWeight: 500 }}>
                    Context Usage
                  </span>
                </div>
                <span style={{ 
                  fontSize: '10px', 
                  color: tokenStats.pressure_level === 'critical' ? '#D13438' :
                         tokenStats.pressure_level === 'high' ? '#CA5010' :
                         tokenStats.pressure_level === 'medium' ? '#8A8886' : '#107C10',
                  fontWeight: 500,
                }}>
                  {tokenStats.usage_percent.toFixed(1)}% used
                </span>
              </div>
              
              {/* Progress Bar */}
              <div style={{
                width: '100%',
                height: '6px',
                background: '#E1DFDD',
                borderRadius: '3px',
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${Math.min(100, tokenStats.usage_percent)}%`,
                  height: '100%',
                  background: tokenStats.pressure_level === 'critical' ? '#D13438' :
                              tokenStats.pressure_level === 'high' ? '#CA5010' :
                              tokenStats.pressure_level === 'medium' ? '#FFB900' : '#107C10',
                  borderRadius: '3px',
                  transition: 'width 0.3s ease',
                }} />
              </div>
              
              {/* Token Breakdown */}
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between',
                marginTop: '6px',
                fontSize: '10px',
                color: '#605E5C',
              }}>
                <span>Notes: {tokenStats.memory_notebook_tokens.toLocaleString()}</span>
                <span>History: {tokenStats.message_history_tokens.toLocaleString()}</span>
                <span>System: {tokenStats.system_prompt_tokens.toLocaleString()}</span>
                <span style={{ fontWeight: 500 }}>Total: {tokenStats.total_used.toLocaleString()}</span>
                <span style={{ color: tokenStats.pressure_level === 'critical' ? '#D13438' : tokenStats.pressure_level === 'high' ? '#CA5010' : '#107C10' }}>Left: {tokenStats.remaining.toLocaleString()}</span>
              </div>
            </div>
          )}
          
          <div style={{ 
            fontSize: '10px', 
            color: '#A19F9D', 
            textAlign: 'center',
          }}>
            Notes persist for this chat • ⌘B bold • ⌘I italic
          </div>
        </div>
      </motion.div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        [contenteditable] ul, [contenteditable] ol,
        .note-content ul, .note-content ol {
          margin: 4px 0;
          padding-left: 24px;
          list-style-position: outside;
        }
        [contenteditable] ul, .note-content ul {
          list-style-type: disc;
        }
        [contenteditable] ol, .note-content ol {
          list-style-type: decimal;
        }
        [contenteditable] li, .note-content li {
          margin: 2px 0;
          display: list-item;
        }
      `}</style>
    </div>
  );
};

export default MemoryNotebookModal;
