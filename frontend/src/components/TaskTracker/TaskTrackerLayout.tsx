import { useState, useMemo, useCallback } from 'react';

import { ReviewContext } from './mosaic/ReviewContext';
import { PostMortemsPanel } from './PostMortems/PostMortemsPanel';
import { TaskDetailModal } from './Shared/TaskDetailModal';
import { useTaskData } from './hooks/useTaskData';
import type { Task } from '@/types/task.types';

export function TaskTrackerLayout() {
  const { data: tasks = [], isLoading, error } = useTaskData();

  const [searchTerm,     setSearchTerm]     = useState('');
  const [priorityFilter, setPriorityFilter] = useState<string | null>(null);
  const [statusFilter,   setStatusFilter]   = useState<string | null>(null);
  const [selectedTask,   setSelectedTask]   = useState<Task | null>(null);
  const [isCreating,     setIsCreating]     = useState(false);
  const [createStatusId, setCreateStatusId] = useState<string | null>(null);

  const filteredTasks = useMemo(() => tasks.filter((t) => {
    if (searchTerm) {
      const s = searchTerm.toLowerCase();
      if (!t.title.toLowerCase().includes(s) && !t.description?.toLowerCase().includes(s) && !t.ticker?.toLowerCase().includes(s)) return false;
    }
    if (priorityFilter && t.priority !== priorityFilter) return false;
    if (statusFilter   && t.statusId !== statusFilter)   return false;
    return true;
  }), [tasks, searchTerm, priorityFilter, statusFilter]);

  const onTaskClick  = useCallback((t: Task) => setSelectedTask(t), []);
  const onCreateTask = useCallback((sid: string) => { setCreateStatusId(sid); setIsCreating(true); }, []);
  const onCloseModal = useCallback(() => { setSelectedTask(null); setIsCreating(false); setCreateStatusId(null); }, []);

  if (isLoading) return <div className="flex h-full items-center justify-center"><div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>;
  if (error)     return <div className="flex h-full items-center justify-center text-red-500">Error loading tasks</div>;

  return (
    <ReviewContext.Provider value={{
      tasks, filteredTasks, searchTerm, setSearchTerm,
      priorityFilter, setPriorityFilter, statusFilter, setStatusFilter,
      onTaskClick, onCreateTask,
    }}>
      <div className="h-full overflow-hidden">
        <PostMortemsPanel tasks={filteredTasks} viewMode="post_mortems" onViewChange={() => {}} />
      </div>

      {(selectedTask || isCreating) && (
        <TaskDetailModal task={selectedTask} isOpen={true} onClose={onCloseModal} defaultStatusId={createStatusId} />
      )}
    </ReviewContext.Provider>
  );
}
