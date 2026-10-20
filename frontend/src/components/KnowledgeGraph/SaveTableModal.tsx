/**
 * SaveTableModal - Name and save table to database
 */

import { useState, useEffect } from 'react';
import { X, Save, AlertCircle } from 'lucide-react';

interface SaveTableModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (tableName: string, description?: string) => Promise<void>;
  defaultName?: string;
  defaultDescription?: string;
}

export default function SaveTableModal({
  isOpen,
  onClose,
  onSave,
  defaultName = '',
  defaultDescription = '',
}: SaveTableModalProps) {
  const [tableName, setTableName] = useState(defaultName);
  const [description, setDescription] = useState(defaultDescription);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen) {
      setTableName(defaultName || '');
      setDescription(defaultDescription || '');
      setError('');
    }
  }, [isOpen, defaultName, defaultDescription]);

  const handleSave = async () => {
    // Validate table name
    if (!tableName.trim()) {
      setError('Table name is required');
      return;
    }

    if (!/^[a-zA-Z0-9_\s-]+$/.test(tableName)) {
      setError('Table name can only contain letters, numbers, spaces, hyphens, and underscores');
      return;
    }

    setIsSaving(true);
    setError('');

    try {
      await onSave(tableName.trim(), description.trim() || undefined);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to save table');
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100] animate-in fade-in duration-150">
      <div className="bg-white rounded-lg shadow-2xl w-[500px] flex flex-col animate-in slide-in-from-top-4 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-300">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">Save Table</h3>
            <p className="text-sm text-slate-600 mt-0.5">Name your table to save it to the database</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-md transition-colors"
            disabled={isSaving}
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Table Name */}
          <div>
            <label className="block text-sm font-medium text-slate-900 mb-1.5">
              Table Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={tableName}
              onChange={(e) => {
                setTableName(e.target.value);
                setError('');
              }}
              placeholder="e.g., Customer_Data_2025"
              className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isSaving}
              autoFocus
            />
            <p className="text-xs text-slate-500 mt-1">
              Use letters, numbers, spaces, hyphens, or underscores
            </p>
          </div>

          {/* Description (Optional) */}
          <div>
            <label className="block text-sm font-medium text-slate-900 mb-1.5">
              Description <span className="text-slate-400">(optional)</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Add a brief description of this table..."
              rows={3}
              className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              disabled={isSaving}
            />
          </div>

          {/* Error Message */}
          {error && (
            <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-md">
              <AlertCircle size={16} className="text-red-600 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-300 bg-slate-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200 rounded-md transition-colors"
            disabled={isSaving}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving || !tableName.trim()}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
          >
            <Save size={16} />
            {isSaving ? 'Saving...' : 'Save Table'}
          </button>
        </div>
      </div>
    </div>
  );
}
