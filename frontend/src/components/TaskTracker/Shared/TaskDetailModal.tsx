import { useState, useEffect } from 'react';
import { useTaskMutations } from '../hooks/useTaskMutations';
import type { Task } from '@/types/task.types';

interface TaskDetailModalProps {
  task: Task | null;
  isOpen: boolean;
  onClose: () => void;
  defaultStatusId?: string | null;
}

export function TaskDetailModal({
  task,
  isOpen,
  onClose,
  defaultStatusId,
}: TaskDetailModalProps) {
  const { createTask, updateTask, deleteTask } = useTaskMutations();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<Task['priority']>('medium');
  const [type, setType] = useState<Task['type']>('research');
  const [ticker, setTicker] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [statusId, setStatusId] = useState('idea-generation');

  useEffect(() => {
    if (task) {
      setTitle(task.title);
      setDescription(task.description || '');
      setPriority(task.priority);
      setType(task.type || 'research');
      setTicker(task.ticker || '');
      setDueDate(task.dueDate ? task.dueDate.split('T')[0] : '');
      setStatusId(task.statusId);
    } else if (defaultStatusId) {
      setStatusId(defaultStatusId);
      setTitle('');
      setDescription('');
      setPriority('medium');
      setType('research');
      setTicker('');
      setDueDate('');
    }
  }, [task, defaultStatusId]);

  const handleSave = () => {
    if (!title.trim()) return;
    const payload = {
        title,
        description: description || undefined,
        priority,
        type,
        ticker: ticker || undefined,
        dueDate: dueDate || undefined,
        statusId,
    };

    if (task) {
      updateTask.mutate({ id: task.id, updates: payload }, { onSuccess: onClose });
    } else {
      createTask.mutate({ boardId: 'default', ...payload }, { onSuccess: onClose });
    }
  };

  const handleDelete = () => {
    if (task && window.confirm('Delete this issue?')) {
      deleteTask.mutate(task.id, { onSuccess: onClose });
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-gray-900/20 backdrop-blur-sm flex items-center justify-center z-[100] p-4 transition-opacity">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col animate-in zoom-in-95 duration-200 overflow-hidden ring-1 ring-black/5">

        {/* Header */}
        <div className="flex items-center justify-between px-8 py-5 border-b border-gray-50 bg-white/50 backdrop-blur-xl sticky top-0 z-10">
          <div className="flex items-center gap-3">
             <span className="text-xs font-mono font-medium text-gray-400 tracking-wide">
                {task ? `INV-${task.id.slice(0,4).toUpperCase()}` : 'NEW ITEM'}
             </span>
             {task?.ticker && (
                <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-xs font-bold font-mono border border-gray-200">
                    {task.ticker}
                </span>
             )}
          </div>
          <div className="flex items-center gap-2">
            {task && (
                <button onClick={handleDelete} className="w-8 h-8 flex items-center justify-center rounded-full text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </button>
            )}
            <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-full text-gray-400 hover:text-gray-800 hover:bg-gray-50 transition-colors">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
          {/* Main Form */}
          <div className="flex-1 p-8 overflow-y-auto custom-scrollbar">
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Task Title"
              className="w-full text-2xl font-semibold text-gray-900 placeholder-gray-300 border-none focus:ring-0 px-0 mb-6 bg-transparent"
              autoFocus={!task}
            />

            <div className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                     <div>
                        <label className="block text-xs font-medium text-gray-400 mb-2 ml-1">Ticker</label>
                        <div className="relative">
                            <input
                                type="text"
                                value={ticker}
                                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                                placeholder="e.g. AAPL"
                                className="w-full p-2.5 text-sm font-mono text-gray-900 bg-gray-50/50 border-0 rounded-xl hover:bg-gray-50 focus:bg-white focus:ring-2 focus:ring-blue-500/20 transition-all uppercase"
                            />
                        </div>
                     </div>
                     <div>
                        <label className="block text-xs font-medium text-gray-400 mb-2 ml-1">Type</label>
                        <div className="relative">
                             <select
                                value={type}
                                onChange={(e) => setType(e.target.value as any)}
                                className="w-full p-2.5 text-sm font-medium text-gray-900 bg-gray-50/50 border-0 rounded-xl hover:bg-gray-50 focus:bg-white focus:ring-2 focus:ring-blue-500/20 transition-all cursor-pointer appearance-none"
                            >
                                <option value="research">Research</option>
                                <option value="meeting">Meeting</option>
                                <option value="committee">IC Committee</option>
                                <option value="filing">Filing Review</option>
                                <option value="task">General Task</option>
                            </select>
                        </div>
                     </div>
                </div>

                <div>
                    <label className="block text-xs font-medium text-gray-400 mb-2 ml-1">Description</label>
                    <textarea
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="Add details..."
                        rows={12}
                        className="w-full p-4 text-sm text-gray-700 bg-gray-50/50 border-0 rounded-xl hover:bg-gray-50 focus:bg-white focus:ring-2 focus:ring-blue-500/20 transition-all resize-none placeholder-gray-400"
                    />
                </div>
            </div>
          </div>

          {/* Sidebar Metadata */}
          <div className="w-full md:w-72 bg-gray-50/30 p-8 border-l border-gray-50 overflow-y-auto">
            <div className="space-y-8">
                <div className="space-y-2">
                    <label className="block text-xs font-medium text-gray-400 ml-1">Stage</label>
                    <div className="relative">
                      <select
                          value={statusId}
                          onChange={(e) => setStatusId(e.target.value)}
                          className="w-full text-sm font-medium bg-white border-0 rounded-xl px-4 py-2.5 shadow-sm ring-1 ring-gray-100 focus:ring-2 focus:ring-blue-500/20 cursor-pointer appearance-none"
                      >
                          <option value="idea-generation">Idea Generation</option>
                          <option value="due-diligence">Due Diligence</option>
                          <option value="ic-review">IC Review</option>
                          <option value="portfolio">Portfolio</option>
                      </select>
                      <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6"/></svg>
                      </div>
                    </div>
                </div>

                <div className="space-y-2">
                    <label className="block text-xs font-medium text-gray-400 ml-1">Priority</label>
                     <div className="relative">
                      <select
                          value={priority}
                          onChange={(e) => setPriority(e.target.value as any)}
                          className="w-full text-sm font-medium bg-white border-0 rounded-xl px-4 py-2.5 shadow-sm ring-1 ring-gray-100 focus:ring-2 focus:ring-blue-500/20 cursor-pointer appearance-none"
                      >
                          <option value="low">Low</option>
                          <option value="medium">Medium</option>
                          <option value="high">High</option>
                          <option value="urgent">Urgent</option>
                      </select>
                      <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6"/></svg>
                      </div>
                    </div>
                </div>

                <div className="space-y-2">
                    <label className="block text-xs font-medium text-gray-400 ml-1">Assignee</label>
                    <div className="flex items-center gap-3 p-2.5 bg-white rounded-xl ring-1 ring-gray-100 shadow-sm cursor-pointer hover:ring-gray-200 transition-all">
                        <div className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center text-[10px] text-gray-500 font-bold">?</div>
                        <span className="text-sm font-medium text-gray-600">Unassigned</span>
                    </div>
                </div>

                <div className="space-y-2">
                    <label className="block text-xs font-medium text-gray-400 ml-1">Due Date</label>
                    <input
                        type="date"
                        value={dueDate}
                        onChange={(e) => setDueDate(e.target.value)}
                        className="w-full text-sm font-medium bg-white border-0 rounded-xl px-4 py-2.5 shadow-sm ring-1 ring-gray-100 focus:ring-2 focus:ring-blue-500/20 text-gray-600"
                    />
                </div>
            </div>
          </div>
        </div>

        {/* Footer Buttons */}
        <div className="px-8 py-5 border-t border-gray-50 flex justify-end gap-3 bg-white/50 backdrop-blur-xl">
            <button
                onClick={onClose}
                className="px-5 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-50 rounded-xl transition-all"
            >
                Cancel
            </button>
            <button
                onClick={handleSave}
                className="px-5 py-2.5 text-sm font-medium text-white bg-gray-900 hover:bg-gray-800 rounded-xl shadow-lg shadow-gray-900/10 transition-all transform hover:-translate-y-0.5 active:translate-y-0"
            >
                {task ? 'Save Changes' : 'Create Task'}
            </button>
        </div>
      </div>
    </div>
  );
}
