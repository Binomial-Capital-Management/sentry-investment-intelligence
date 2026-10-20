import { Plus, Wrench } from 'lucide-react';
import { useDataWorkspaceStore } from '../stores/dataWorkspaceStore';

export default function EmptyState() {
  const setFieldPickerOpen = useDataWorkspaceStore(s => s.setFieldPickerOpen);

  return (
    <div className="flex-1 flex items-center justify-center bg-white">
      <div className="text-center max-w-xs">
        <div className="w-10 h-10 mx-auto mb-3 rounded-full bg-slate-50 flex items-center justify-center">
          <Plus className="w-5 h-5 text-slate-300" />
        </div>
        <h3 className="text-sm font-medium text-slate-700 mb-1">No datasets configured</h3>
        <p className="text-xs text-slate-400 mb-4">Add datasets using the form above</p>
        <button
          onClick={() => setFieldPickerOpen(true)}
          className="px-4 py-2 text-xs font-medium bg-slate-900 text-white rounded-lg hover:bg-slate-800 transition-colors"
        >
          Open Sources
        </button>
      </div>
    </div>
  );
}

export function ToolEmptyState() {
  return (
    <div className="flex-1 flex items-center justify-center bg-white">
      <div className="text-center max-w-xs">
        <div className="w-10 h-10 mx-auto mb-3 rounded-full bg-slate-50 flex items-center justify-center">
          <Wrench className="w-5 h-5 text-slate-300" />
        </div>
        <h3 className="text-sm font-medium text-slate-700 mb-1">Configure and run a tool</h3>
        <p className="text-xs text-slate-400">Select a tool, add inputs, and click Run</p>
      </div>
    </div>
  );
}
