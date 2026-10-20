import React from "react";
import { MemoryNoteInfo } from "../../../hooks/useMemoryNotebook";
import { TrashIcon } from "../shared";

interface MemoryPanelProps {
  memoryNotes: MemoryNoteInfo[];
  memoryLoading: boolean;
  newNoteText: string;
  setNewNoteText: (text: string) => void;
  addNote: () => void;
  removeNote: (noteId: string) => void;
}

export const MemoryPanel: React.FC<MemoryPanelProps> = ({
  memoryNotes,
  memoryLoading,
  newNoteText,
  setNewNoteText,
  addNote,
  removeNote,
}) => (
  <div style={{
    borderBottom: "1px solid #e5e7eb", background: "#fff",
    padding: "8px 12px", maxHeight: "200px", overflowY: "auto", flexShrink: 0,
  }}>
    <div style={{ fontSize: "11px", fontWeight: 600, color: "#374151", marginBottom: "6px" }}>
      Memory Notebook
    </div>
    {memoryLoading ? (
      <div style={{ fontSize: "11px", color: "#9ca3af" }}>Loading...</div>
    ) : memoryNotes.length === 0 ? (
      <div style={{ fontSize: "11px", color: "#9ca3af" }}>No notes saved yet.</div>
    ) : (
      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        {memoryNotes.map((note) => (
          <div key={note.id} style={{
            display: "flex", alignItems: "flex-start", gap: "6px",
            background: "#f9fafb", borderRadius: "4px", padding: "4px 8px",
          }}>
            <span style={{
              fontSize: "9px", fontWeight: 600, color: "#6b7280",
              background: "#e5e7eb", borderRadius: "3px", padding: "1px 4px",
              whiteSpace: "nowrap", marginTop: "1px",
            }}>{note.section}</span>
            <span style={{ fontSize: "11px", color: "#374151", flex: 1 }}>{note.content}</span>
            <button onClick={() => removeNote(note.id)} style={{
              background: "none", border: "none", cursor: "pointer", padding: "0",
              color: "#d1d5db", flexShrink: 0,
            }}
              onMouseEnter={(e) => { e.currentTarget.style.color = "#ef4444"; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = "#d1d5db"; }}>
              <TrashIcon />
            </button>
          </div>
        ))}
      </div>
    )}
    <div style={{ display: "flex", gap: "4px", marginTop: "6px" }}>
      <input
        value={newNoteText}
        onChange={(e) => setNewNoteText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") addNote(); }}
        placeholder="Add a note..."
        style={{
          flex: 1, fontSize: "11px", padding: "4px 8px",
          border: "1px solid #e5e7eb", borderRadius: "4px", outline: "none",
        }}
      />
      <button onClick={addNote} disabled={!newNoteText.trim()} style={{
        fontSize: "11px", padding: "4px 8px", background: newNoteText.trim() ? "#111827" : "#e5e7eb",
        color: newNoteText.trim() ? "#fff" : "#9ca3af", border: "none", borderRadius: "4px",
        cursor: newNoteText.trim() ? "pointer" : "default",
      }}>Save</button>
    </div>
  </div>
);
