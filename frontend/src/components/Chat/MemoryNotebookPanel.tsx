/**
 * Memory Notebook Side Panel
 * A persistent side panel for viewing and editing memory notes (like Analyst Mode)
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Plus, Trash2, Edit3, Check, Loader2, 
  Bold, Italic, List, ListOrdered, FileText, ChevronDown, ChevronUp,
  Database, X, Cloud
} from 'lucide-react';
import MemoryIcon from '@/components/Icons/MemoryIcon';
import sentryLogo from '@/assets/binomial-icon-logo.png';
import memoryApiService from '@/services/memoryApi';
import { uploadService } from '@/services/upload';
import type { MemoryNote, MemoryNoteCreate, ContextTokenStats } from '@/types/memory';
import { useChatStore } from '@stores/chatStore';
import toast from 'react-hot-toast';
import { GoogleDriveNativePicker } from '@/components/KnowledgeGraph/GoogleDriveNativePicker';
import { OneDriveNativePicker } from '@/components/KnowledgeGraph/OneDriveNativePicker';
import { ensureOneDriveConnection } from '@/utils/onedrive';
import googleDriveIcon from '@/assets/connector-logos/google-drive.png';
import oneDriveIcon from '@/assets/connector-logos/one-drive.png';

const TRUNCATE_LENGTH = 200;

interface MemoryNotebookPanelProps {
  sessionId: string;
  onClose?: () => void;
}

// Compact Rich Text Editor
const CompactEditor = ({
  value,
  onChange,
  placeholder,
  autoFocus = false,
}: {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
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

  const updateActiveFormats = useCallback(() => {
    const formats = new Set<string>();
    if (document.queryCommandState('bold')) formats.add('bold');
    if (document.queryCommandState('italic')) formats.add('italic');
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

  const execCommand = (command: string) => {
    document.execCommand(command, false);
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

  return (
    <div className="border border-gray-200 rounded bg-gray-50 overflow-hidden">
      {/* Compact toolbar */}
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-gray-200 bg-white">
        <button
          type="button"
          onClick={() => execCommand('bold')}
          className={`p-1 rounded ${activeFormats.has('bold') ? 'bg-gray-200 text-blue-600' : 'hover:bg-gray-100'}`}
          title="Bold (⌘B)"
        >
          <Bold size={14} />
        </button>
        <button
          type="button"
          onClick={() => execCommand('italic')}
          className={`p-1 rounded ${activeFormats.has('italic') ? 'bg-gray-200 text-blue-600' : 'hover:bg-gray-100'}`}
          title="Italic (⌘I)"
        >
          <Italic size={14} />
        </button>
        <button
          type="button"
          onClick={() => execCommand('insertUnorderedList')}
          className="p-1 rounded hover:bg-gray-100"
          title="Bullet List"
        >
          <List size={14} />
        </button>
        <button
          type="button"
          onClick={() => execCommand('insertOrderedList')}
          className="p-1 rounded hover:bg-gray-100"
          title="Numbered List"
        >
          <ListOrdered size={14} />
        </button>
      </div>
      
      {/* Editor area */}
      <div className="relative">
        <div
          ref={editorRef}
          contentEditable
          onInput={handleInput}
          onKeyDown={handleKeyDown}
          className="min-h-[60px] max-h-[120px] overflow-y-auto p-2 text-sm outline-none"
          suppressContentEditableWarning
        />
        {isEmpty && (
          <div className="absolute top-2 left-2 text-gray-400 text-sm pointer-events-none">
            {placeholder}
          </div>
        )}
      </div>
    </div>
  );
};

const MemoryNotebookPanel: React.FC<MemoryNotebookPanelProps> = ({ sessionId, onClose }) => {
  const [notes, setNotes] = useState<MemoryNote[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newNoteHtml, setNewNoteHtml] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editHtml, setEditHtml] = useState('');
  const [tokenStats, setTokenStats] = useState<ContextTokenStats | null>(null);
  const [isPinningFile, setIsPinningFile] = useState(false);
  const [expandedNotes, setExpandedNotes] = useState<Set<string>>(new Set());
  const [useLongDocMode, setUseLongDocMode] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Cloud picker state
  const [showGoogleDrivePicker, setShowGoogleDrivePicker] = useState(false);
  const [showOneDrivePicker, setShowOneDrivePicker] = useState(false);
  const [oneDriveAccountType, setOneDriveAccountType] = useState<'personal' | 'business' | 'sharepoint'>('personal');
  const [isPinningCloudFile, setIsPinningCloudFile] = useState(false);
  const [showCloudMenu, setShowCloudMenu] = useState(false);
  const cloudMenuRef = useRef<HTMLDivElement>(null);

  const getCurrentThreadModel = useChatStore((s) => s.getCurrentThreadModel);
  const currentModel = getCurrentThreadModel?.() || 'gpt-6.1-sol';

  const loadTokenStats = useCallback(async () => {
    if (!sessionId) return;
    try {
      const stats = await memoryApiService.getTokenStats(sessionId, currentModel);
      setTokenStats(stats);
    } catch (err) {
      console.error('[MemoryPanel] Failed to load token stats:', err);
    }
  }, [sessionId, currentModel]);

  const loadNotes = useCallback(async () => {
    if (!sessionId) return;
    setIsLoading(true);
    try {
      const data = await memoryApiService.getNotes(sessionId);
      setNotes(data.notes || []);
    } catch (err) {
      console.error('[MemoryPanel] Failed to load:', err);
      setNotes([]);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (sessionId) {
      loadNotes();
      loadTokenStats();
    }
  }, [sessionId, loadNotes, loadTokenStats]);

  const getTextContent = (html: string): string => {
    const div = document.createElement('div');
    div.innerHTML = html;
    return div.textContent || '';
  };

  const needsTruncation = (content: string): boolean => {
    const text = getTextContent(content);
    return text.length > TRUNCATE_LENGTH;
  };

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

  const getTruncatedHtml = (html: string): string => {
    const text = getTextContent(html);
    if (text.length <= TRUNCATE_LENGTH) return html;
    const truncated = text.slice(0, TRUNCATE_LENGTH);
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
      loadTokenStats();
    } catch (err) {
      console.error('[MemoryPanel] Failed to add note:', err);
      toast.error('Failed to add note');
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
      console.error('[MemoryPanel] Failed to update:', err);
      toast.error('Failed to update note');
    }
  };

  const handleDeleteNote = async (id: string) => {
    try {
      await memoryApiService.deleteNote(sessionId, id);
      setNotes(prev => prev.filter(n => n.id !== id));
      loadTokenStats();
    } catch (err) {
      console.error('[MemoryPanel] Failed to delete:', err);
      toast.error('Failed to delete note');
    }
  };

  const handleFilePinClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    setIsPinningFile(true);
    const toastId = `pin-file-${Date.now()}`;
    toast.loading(`Processing "${file.name}"...`, { id: toastId });

    try {
      const uploadedFiles = await uploadService.uploadFiles([file]);
      if (!uploadedFiles || uploadedFiles.length === 0) {
        throw new Error('Failed to upload file');
      }

      const uploadedFile = uploadedFiles[0];
      toast.loading(`Extracting & indexing "${file.name}"...`, { id: toastId });
      
      const newNote = await memoryApiService.pinFileToMemory(sessionId, uploadedFile.id, {
        extractionMode: useLongDocMode ? 'text' : undefined,
        index: true,
      });
      
      setNotes(prev => [newNote, ...prev]);
      loadTokenStats();
      
      const chunkCount = newNote.reference_metadata?.chunk_count;
      if (chunkCount) {
        toast.success(`"${file.name}" indexed (${chunkCount} chunks)`, { id: toastId });
      } else {
        toast.success(`"${file.name}" pinned to memory`, { id: toastId });
      }
    } catch (err: any) {
      console.error('[MemoryPanel] Failed to pin file:', err);
      toast.error(err?.response?.data?.detail || 'Failed to pin file', { id: toastId });
    } finally {
      setIsPinningFile(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // Handle Google Drive file selection
  const handleGoogleDriveSelect = async (file: File) => {
    setShowGoogleDrivePicker(false);
    setIsPinningCloudFile(true);
    const toastId = `pin-gdrive-${Date.now()}`;
    toast.loading(`Processing "${file.name}" from Google Drive...`, { id: toastId });

    try {
      // First upload the file to our server
      const uploadedFiles = await uploadService.uploadFiles([file]);
      if (!uploadedFiles || uploadedFiles.length === 0) {
        throw new Error('Failed to upload file from Google Drive');
      }

      const uploadedFile = uploadedFiles[0];
      toast.loading(`Extracting & indexing "${file.name}"...`, { id: toastId });
      
      const newNote = await memoryApiService.pinFileToMemory(sessionId, uploadedFile.id, {
        extractionMode: useLongDocMode ? 'text' : undefined,
        index: true,
      });
      
      setNotes(prev => [newNote, ...prev]);
      loadTokenStats();
      
      const chunkCount = newNote.reference_metadata?.chunk_count;
      if (chunkCount) {
        toast.success(`"${file.name}" indexed (${chunkCount} chunks)`, { id: toastId });
      } else {
        toast.success(`"${file.name}" pinned to memory`, { id: toastId });
      }
    } catch (err: any) {
      console.error('[MemoryPanel] Failed to pin Google Drive file:', err);
      toast.error(err?.response?.data?.detail || 'Failed to pin Google Drive file', { id: toastId });
    } finally {
      setIsPinningCloudFile(false);
    }
  };

  // Handle OneDrive file selection
  const handleOneDriveSelect = async (file: File) => {
    setShowOneDrivePicker(false);
    setIsPinningCloudFile(true);
    const toastId = `pin-onedrive-${Date.now()}`;
    toast.loading(`Processing "${file.name}" from OneDrive...`, { id: toastId });

    try {
      // First upload the file to our server
      const uploadedFiles = await uploadService.uploadFiles([file]);
      if (!uploadedFiles || uploadedFiles.length === 0) {
        throw new Error('Failed to upload file from OneDrive');
      }

      const uploadedFile = uploadedFiles[0];
      toast.loading(`Extracting & indexing "${file.name}"...`, { id: toastId });
      
      const newNote = await memoryApiService.pinFileToMemory(sessionId, uploadedFile.id, {
        extractionMode: useLongDocMode ? 'text' : undefined,
        index: true,
      });
      
      setNotes(prev => [newNote, ...prev]);
      loadTokenStats();
      
      const chunkCount = newNote.reference_metadata?.chunk_count;
      if (chunkCount) {
        toast.success(`"${file.name}" indexed (${chunkCount} chunks)`, { id: toastId });
      } else {
        toast.success(`"${file.name}" pinned to memory`, { id: toastId });
      }
    } catch (err: any) {
      console.error('[MemoryPanel] Failed to pin OneDrive file:', err);
      toast.error(err?.response?.data?.detail || 'Failed to pin OneDrive file', { id: toastId });
    } finally {
      setIsPinningCloudFile(false);
    }
  };

  // Open OneDrive picker with connection check
  const handleOpenOneDrivePicker = async (accountType: 'personal' | 'business' | 'sharepoint') => {
    setShowCloudMenu(false);
    try {
      const { connected } = await ensureOneDriveConnection();
      if (!connected) {
        return;
      }
      setOneDriveAccountType(accountType);
      setShowOneDrivePicker(true);
    } catch (err) {
      console.error('[MemoryPanel] OneDrive connection error:', err);
      toast.error('Failed to connect to OneDrive');
    }
  };

  // Close cloud menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (cloudMenuRef.current && !cloudMenuRef.current.contains(event.target as Node)) {
        setShowCloudMenu(false);
      }
    };
    if (showCloudMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showCloudMenu]);

  // Token usage bar
  const tokenUsagePercent = tokenStats ? Math.min(100, tokenStats.usage_percent) : 0;
  const pressureColor = tokenStats?.pressure_level === 'critical' ? 'bg-red-500' :
    tokenStats?.pressure_level === 'high' ? 'bg-orange-500' :
    tokenStats?.pressure_level === 'medium' ? 'bg-yellow-500' : 'bg-green-500';

  return (
    <div className="flex flex-col h-full bg-white font-sans text-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center gap-2">
          <MemoryIcon size={16} className="text-gray-600" />
          <span className="font-semibold text-gray-800">Memory Notebook</span>
          <span className="text-xs text-gray-500">({notes.length})</span>
        </div>
        {onClose && (
          <button onClick={onClose} className="p-1 hover:bg-gray-200 rounded">
            <X size={16} className="text-gray-500" />
          </button>
        )}
      </div>

      {/* Token Usage Bar */}
      {tokenStats && (
        <div className="px-4 py-2 border-b border-gray-100 bg-gray-50">
          <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
            <span>Context: {tokenStats.total_used.toLocaleString()} / {tokenStats.context_limit.toLocaleString()}</span>
            <span className={tokenStats.pressure_level === 'critical' ? 'text-red-600 font-medium' : ''}>
              {tokenUsagePercent.toFixed(1)}%
            </span>
          </div>
          <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className={`h-full ${pressureColor} transition-all duration-300`}
              style={{ width: `${tokenUsagePercent}%` }}
            />
          </div>
          <div className="flex justify-between text-[10px] text-gray-500 mt-1">
            <span>Notes: {tokenStats.memory_notebook_tokens}</span>
            <span>History: {tokenStats.message_history_tokens}</span>
          </div>
        </div>
      )}

      {/* Add Note Section */}
      <div className="p-3 border-b border-gray-100">
        <CompactEditor
          value={newNoteHtml}
          onChange={setNewNoteHtml}
          placeholder="Add a note..."
          autoFocus={false}
        />
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.csv,.xlsx,.xls,.txt,.json,.png,.jpg,.jpeg"
              onChange={handleFileSelected}
              className="hidden"
            />
            {/* Pin local file */}
            <button
              onClick={handleFilePinClick}
              disabled={isPinningFile || isPinningCloudFile}
              className="flex items-center gap-1 px-2 py-1 text-xs text-gray-600 hover:bg-gray-100 rounded border border-gray-200 disabled:opacity-50"
              title="Pin a local file"
            >
              {isPinningFile ? <Loader2 size={12} className="animate-spin" /> : <FileText size={12} />}
              File
            </button>
            
            {/* Cloud menu dropdown */}
            <div className="relative" ref={cloudMenuRef}>
              <button
                onClick={() => setShowCloudMenu(!showCloudMenu)}
                disabled={isPinningFile || isPinningCloudFile}
                className="flex items-center gap-1 px-2 py-1 text-xs text-gray-600 hover:bg-gray-100 rounded border border-gray-200 disabled:opacity-50"
                title="Pin from cloud storage"
              >
                {isPinningCloudFile ? <Loader2 size={12} className="animate-spin" /> : <Cloud size={12} />}
                Cloud
                <ChevronDown size={10} />
              </button>
              
              {showCloudMenu && (
                <div className="absolute left-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 min-w-[160px] py-1">
                  {/* Google Drive */}
                  <button
                    onClick={() => {
                      setShowCloudMenu(false);
                      setShowGoogleDrivePicker(true);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-700 hover:bg-gray-50"
                  >
                    <img src={googleDriveIcon} alt="Google Drive" className="w-3.5 h-2.5" />
                    Google Drive
                  </button>
                  
                  {/* OneDrive Personal */}
                  <button
                    onClick={() => handleOpenOneDrivePicker('personal')}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-700 hover:bg-gray-50"
                  >
                    <img src={oneDriveIcon} alt="OneDrive" className="w-3.5 h-2.5" />
                    OneDrive
                  </button>
                  
                  {/* OneDrive Business / SharePoint */}
                  <button
                    onClick={() => handleOpenOneDrivePicker('business')}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-700 hover:bg-gray-50"
                  >
                    <img src={oneDriveIcon} alt="OneDrive Business" className="w-3.5 h-2.5" />
                    OneDrive Business
                  </button>
                </div>
              )}
            </div>
            
            <label className="flex items-center gap-1 text-[10px] text-gray-500 cursor-pointer ml-1">
              <input
                type="checkbox"
                checked={useLongDocMode}
                onChange={(e) => setUseLongDocMode(e.target.checked)}
                className="w-3 h-3"
              />
              Long doc
            </label>
          </div>
          <button
            onClick={handleAddNote}
            disabled={!getTextContent(newNoteHtml).trim()}
            className="flex items-center gap-1 px-3 py-1 text-xs font-medium text-white bg-blue-600 rounded disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            <Plus size={12} />
            Add
          </button>
        </div>
      </div>

      {/* Notes List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={20} className="animate-spin text-gray-400" />
          </div>
        ) : notes.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <MemoryIcon size={24} className="mx-auto mb-2" color="#D1D5DB" />
            <p className="text-xs">No notes yet</p>
          </div>
        ) : (
          <div className="p-2 space-y-2">
            <AnimatePresence>
              {notes.map((note) => (
                <motion.div
                  key={note.id}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                  className={`bg-white border rounded p-2 ${editingId === note.id ? 'border-blue-400' : 'border-gray-200'}`}
                >
                  {editingId === note.id ? (
                    <div>
                      <CompactEditor
                        value={editHtml}
                        onChange={setEditHtml}
                        autoFocus
                      />
                      <div className="flex justify-end gap-1 mt-2">
                        <button
                          onClick={() => { setEditingId(null); setEditHtml(''); }}
                          className="px-2 py-1 text-xs text-gray-600 hover:bg-gray-100 rounded"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => handleUpdateNote(note.id)}
                          disabled={!getTextContent(editHtml).trim()}
                          className="flex items-center gap-1 px-2 py-1 text-xs text-white bg-blue-600 rounded disabled:bg-gray-300"
                        >
                          <Check size={10} />
                          Save
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <div className="flex justify-between items-start gap-2">
                        <div
                          className="note-content text-xs text-gray-700 leading-relaxed flex-1"
                          dangerouslySetInnerHTML={{ 
                            __html: expandedNotes.has(note.id) || !needsTruncation(note.content) 
                              ? note.content 
                              : getTruncatedHtml(note.content) 
                          }}
                        />
                        <div className="flex gap-0.5 flex-shrink-0">
                          <button
                            onClick={() => { setEditingId(note.id); setEditHtml(note.content); }}
                            className="p-1 hover:bg-gray-100 rounded"
                            title="Edit"
                          >
                            <Edit3 size={12} className="text-gray-400" />
                          </button>
                          <button
                            onClick={() => handleDeleteNote(note.id)}
                            className="p-1 hover:bg-gray-100 rounded"
                            title="Delete"
                          >
                            <Trash2 size={12} className="text-gray-400" />
                          </button>
                        </div>
                      </div>
                      
                      {needsTruncation(note.content) && (
                        <button
                          onClick={() => toggleNoteExpansion(note.id)}
                          className="flex items-center gap-1 mt-1 text-[10px] text-blue-600 hover:underline"
                        >
                          {expandedNotes.has(note.id) ? (
                            <>
                              <ChevronUp size={10} />
                              Less
                            </>
                          ) : (
                            <>
                              <ChevronDown size={10} />
                              More
                            </>
                          )}
                        </button>
                      )}
                      
                      {/* Footer */}
                      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-100 text-[10px] text-gray-400">
                        <span className="flex items-center gap-1">
                          {note.source === 'ai' ? (
                            <>
                              <img src={sentryLogo} alt="" className="w-3 h-3" />
                              Sentry
                            </>
                          ) : note.source === 'tool' ? (
                            <>
                              <FileText size={10} />
                              File
                            </>
                          ) : 'You'}
                        </span>
                        <span>
                          {new Date(note.created_at).toLocaleDateString(undefined, {
                            month: 'short',
                            day: 'numeric',
                          })}
                        </span>
                        {(note.is_chunked || note.reference_metadata?.indexed) && (
                          <span className="flex items-center gap-0.5 px-1 py-0.5 bg-green-100 text-green-700 rounded text-[9px]">
                            <Database size={8} />
                            Indexed
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* Footer hint */}
      <div className="px-3 py-2 border-t border-gray-100 bg-gray-50 text-[10px] text-gray-500 text-center">
        Notes persist for this chat • ⌘B bold • ⌘I italic
      </div>

      {/* Styles for note content */}
      <style>{`
        .note-content ul, .note-content ol {
          margin: 4px 0;
          padding-left: 16px;
        }
        .note-content ul { list-style-type: disc; }
        .note-content ol { list-style-type: decimal; }
        .note-content li { margin: 2px 0; }
      `}</style>

      {/* Google Drive Picker */}
      {showGoogleDrivePicker && (
        <GoogleDriveNativePicker
          onSelect={handleGoogleDriveSelect}
          onClose={() => setShowGoogleDrivePicker(false)}
          allowAllFileTypes={true}
        />
      )}

      {/* OneDrive Picker */}
      {showOneDrivePicker && (
        <OneDriveNativePicker
          onSelect={handleOneDriveSelect}
          onClose={() => setShowOneDrivePicker(false)}
          accountType={oneDriveAccountType}
          allowAllFileTypes={true}
        />
      )}
    </div>
  );
};

export default MemoryNotebookPanel;

