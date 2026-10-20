/**
 * GroupSelectionModal - Modal for choosing which dataset group to add datasets to
 * 
 * Shown when user adds datasets to a workspace that already has existing groups.
 * Options:
 * 1. Add to an existing group (extends the merged table)
 * 2. Create a new group (separate merged table)
 */

import { useState } from 'react';
import { Plus } from 'lucide-react';
import type { DatasetGroup, DatasetConfig } from '../../stores/types';

interface GroupOption {
  group: DatasetGroup;
  datasets: DatasetConfig[];
  endpoints: string[];
  symbols: string[];
}

interface GroupSelectionModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Existing groups with their datasets */
  groupOptions: GroupOption[];
  /** Callback when user selects an existing group */
  onSelectGroup: (groupId: string) => void;
  /** Callback when user wants to create a new group */
  onCreateGroup: (name: string) => void;
  /** Callback when user cancels */
  onCancel: () => void;
  /** Description of what's being added (e.g., "2 datasets") */
  addingDescription?: string;
}

export function GroupSelectionModal({
  isOpen,
  groupOptions,
  onSelectGroup,
  onCreateGroup,
  onCancel,
  addingDescription = 'datasets',
}: GroupSelectionModalProps) {
  const [selectedOption, setSelectedOption] = useState<'existing' | 'new'>('existing');
  const [selectedGroupId, setSelectedGroupId] = useState<string>(
    groupOptions.length > 0 ? groupOptions[0].group.id : ''
  );
  const [newGroupName, setNewGroupName] = useState('');

  // Log when modal opens/closes
  if (isOpen) {
    console.log('[GroupSelectionModal] MODAL IS OPEN:', { 
      groupOptionsCount: groupOptions.length,
      groupOptions: groupOptions.map(g => ({ id: g.group.id, name: g.group.name, datasetCount: g.datasets.length })),
      selectedOption,
      selectedGroupId,
    });
  }

  if (!isOpen) return null;

  const handleConfirm = () => {
    if (selectedOption === 'existing' && selectedGroupId) {
      onSelectGroup(selectedGroupId);
    } else if (selectedOption === 'new') {
      onCreateGroup(newGroupName.trim() || 'New Group');
    }
  };

  const canConfirm = selectedOption === 'new' || (selectedOption === 'existing' && selectedGroupId);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onCancel}
      />
      
      {/* Modal */}
      <div className="relative bg-white rounded-lg shadow-2xl w-full max-w-[260px] mx-4 overflow-hidden">
        {/* Header */}
        <div className="px-4 py-3 border-b border-slate-100">
          <h2 className="text-xs font-semibold text-slate-900">Add {addingDescription} to:</h2>
          <p className="text-[10px] text-slate-400 mt-0.5">
            Choose an existing group or create a new one
          </p>
        </div>

        {/* Content */}
        <div className="px-3 py-3 max-h-[50vh] overflow-y-auto space-y-2">
          {/* Existing Groups */}
          {groupOptions.map(({ group, datasets, endpoints, symbols }) => (
            <label
              key={group.id}
              className={`block p-2.5 rounded-lg border cursor-pointer transition-all ${
                selectedOption === 'existing' && selectedGroupId === group.id
                  ? 'border-blue-400 bg-blue-50/50'
                  : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
              }`}
            >
              <div className="flex items-start gap-2">
                <input
                  type="radio"
                  name="group-selection"
                  checked={selectedOption === 'existing' && selectedGroupId === group.id}
                  onChange={() => {
                    setSelectedOption('existing');
                    setSelectedGroupId(group.id);
                  }}
                  className="mt-0.5 w-3.5 h-3.5 text-blue-600 border-slate-300 focus:ring-blue-500"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-medium text-slate-900">{group.name}</span>
                    <span className="text-[9px] px-1 py-0 bg-slate-100 text-slate-500 rounded">
                      {datasets.length} dataset{datasets.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                  <div className="mt-0.5 text-[10px] text-slate-400 truncate">
                    {symbols.join(', ')} → {endpoints.join(', ')}
                  </div>
                </div>
              </div>
            </label>
          ))}

          {/* Create New Group */}
          <label
            className={`block p-2.5 rounded-lg border cursor-pointer transition-all ${
              selectedOption === 'new'
                ? 'border-emerald-400 bg-emerald-50/50'
                : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
            }`}
          >
            <div className="flex items-start gap-2">
              <input
                type="radio"
                name="group-selection"
                checked={selectedOption === 'new'}
                onChange={() => setSelectedOption('new')}
                className="mt-0.5 w-3.5 h-3.5 text-emerald-600 border-slate-300 focus:ring-emerald-500"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-medium text-slate-900">Create New Group</span>
                  <Plus className="w-3 h-3 text-emerald-500" />
                </div>
                <p className="mt-0.5 text-[10px] text-slate-400">
                  Separate merged table
                </p>

                {selectedOption === 'new' && (
                  <div className="mt-2">
                    <input
                      type="text"
                      placeholder="Group name (optional)"
                      value={newGroupName}
                      onChange={(e) => setNewGroupName(e.target.value)}
                      className="w-full px-2 py-1.5 text-xs border border-slate-200 rounded focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-transparent"
                      autoFocus
                    />
                  </div>
                )}
              </div>
            </div>
          </label>
        </div>

        {/* Footer */}
        <div className="px-3 py-2.5 border-t border-slate-100 flex items-center justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-xs font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!canConfirm}
            className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
              canConfirm
                ? 'bg-slate-900 text-white hover:bg-slate-800'
                : 'bg-slate-200 text-slate-400 cursor-not-allowed'
            }`}
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}

export default GroupSelectionModal;
