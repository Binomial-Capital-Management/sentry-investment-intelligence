import { useState, useCallback, useEffect } from "react";

export interface MemoryNoteInfo {
  id: string;
  section: string;
  content: string;
  priority: number;
  created_at: string;
}

export interface UseMemoryNotebookReturn {
  showMemory: boolean;
  toggleMemory: () => void;
  memoryNotes: MemoryNoteInfo[];
  memoryLoading: boolean;
  newNoteText: string;
  setNewNoteText: (text: string) => void;
  addNote: () => Promise<void>;
  removeNote: (noteId: string) => Promise<void>;
}

export function useMemoryNotebook(memorySessionId?: string | null): UseMemoryNotebookReturn {
  const [showMemory, setShowMemory] = useState(false);
  const [memoryNotes, setMemoryNotes] = useState<MemoryNoteInfo[]>([]);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [newNoteText, setNewNoteText] = useState("");

  const loadMemory = useCallback(async () => {
    if (!memorySessionId) return;
    setMemoryLoading(true);
    try {
      const { getMemoryNotes } = await import("../utils/sentry-api");
      const notes = await getMemoryNotes(memorySessionId);
      setMemoryNotes(notes);
    } catch {
      setMemoryNotes([]);
    } finally {
      setMemoryLoading(false);
    }
  }, [memorySessionId]);

  const addNote = useCallback(async () => {
    if (!memorySessionId || !newNoteText.trim()) return;
    try {
      const { createMemoryNote } = await import("../utils/sentry-api");
      await createMemoryNote(memorySessionId, newNoteText.trim());
      setNewNoteText("");
      loadMemory();
    } catch {
      // silent
    }
  }, [memorySessionId, newNoteText, loadMemory]);

  const removeNote = useCallback(async (noteId: string) => {
    if (!memorySessionId) return;
    try {
      const { deleteMemoryNote } = await import("../utils/sentry-api");
      await deleteMemoryNote(memorySessionId, noteId);
      setMemoryNotes((prev) => prev.filter((n) => n.id !== noteId));
    } catch {
      // silent
    }
  }, [memorySessionId]);

  const toggleMemory = useCallback(() => {
    setShowMemory((prev) => !prev);
  }, []);

  useEffect(() => {
    if (showMemory) loadMemory();
  }, [showMemory, loadMemory]);

  return {
    showMemory,
    toggleMemory,
    memoryNotes,
    memoryLoading,
    newNoteText,
    setNewNoteText,
    addNote,
    removeNote,
  };
}
