import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { TaskCard } from './TaskCard';
import type { Task, TaskStatus } from '@/types/task.types';

interface KanbanColumnProps {
  status: TaskStatus;
  tasks: Task[];
  onTaskClick: (task: Task) => void;
  onCreateTask: (statusId: string) => void;
}

export function KanbanColumn({
  status,
  tasks,
  onTaskClick,
  onCreateTask,
}: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: status.id });

  return (
    <div
      className={`
        flex-shrink-0 w-[300px] flex flex-col h-full max-h-full rounded-2xl
        transition-colors duration-200
        ${isOver ? 'bg-gray-50/80' : 'bg-transparent'}
      `}
    >
      {/* Header */}
      <div className="px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <h3 className="text-sm font-semibold text-gray-700">{status.name}</h3>
          <span className="bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full text-xs font-medium min-w-[20px] text-center">
            {tasks.length}
          </span>
        </div>

        <button
          onClick={() => onCreateTask(status.id)}
          className="w-6 h-6 flex items-center justify-center rounded-full hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-all"
          title="Add task"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        </button>
      </div>

      {/* Task List - transparent background for the track */}
      <div
        ref={setNodeRef}
        className="flex-1 px-2 pb-2 space-y-3 overflow-y-auto custom-scrollbar"
      >
        <SortableContext
          items={tasks.map((t) => t.id)}
          strategy={verticalListSortingStrategy}
        >
          {tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onClick={() => onTaskClick(task)}
            />
          ))}

          {/* Subtle empty state */}
          {tasks.length === 0 && (
             <div className="h-32 flex flex-col items-center justify-center text-gray-400/50 border-2 border-dashed border-gray-100 rounded-xl m-1">
                <span className="text-xs font-medium">Drop here</span>
             </div>
          )}
        </SortableContext>
      </div>
    </div>
  );
}
