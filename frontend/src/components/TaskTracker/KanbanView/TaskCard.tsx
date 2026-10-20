import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { PriorityBadge } from '../Shared/PriorityBadge';
import type { Task } from '@/types/task.types';

interface TaskCardProps {
  task: Task;
  isDragging?: boolean;
  onClick?: () => void;
}

export function TaskCard({ task, isDragging, onClick }: TaskCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging: isSortableDragging,
  } = useSortable({ id: task.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isSortableDragging ? 0.4 : 1,
  };

  const dueDate = task.dueDate ? new Date(task.dueDate) : null;
  const isOverdue = dueDate && dueDate < new Date();

  // Type badge colors
  const getTypeColor = (type?: Task['type']) => {
    switch (type) {
      case 'research': return 'bg-blue-50 text-blue-700 border-blue-100';
      case 'meeting': return 'bg-purple-50 text-purple-700 border-purple-100';
      case 'committee': return 'bg-amber-50 text-amber-700 border-amber-100';
      case 'filing': return 'bg-gray-100 text-gray-700 border-gray-200';
      default: return 'bg-gray-50 text-gray-600 border-gray-100';
    }
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={onClick}
      className={`
        group relative bg-white p-4 rounded-xl border border-gray-100 cursor-pointer
        shadow-[0_2px_8px_-2px_rgba(0,0,0,0.05)] hover:shadow-[0_4px_12px_-4px_rgba(0,0,0,0.1)] 
        hover:border-blue-200 transition-all duration-200 ease-out
        ${isDragging ? 'shadow-2xl ring-2 ring-blue-500/20 rotate-1 z-50' : ''}
      `}
    >
      {/* Header Tags */}
      <div className="flex items-center gap-2 mb-2">
        {task.ticker && (
          <span className="px-1.5 py-0.5 text-[10px] font-bold text-gray-700 bg-gray-100 rounded border border-gray-200 font-mono">
            {task.ticker}
          </span>
        )}
        {task.type && (
           <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded border ${getTypeColor(task.type)} uppercase tracking-wider`}>
             {task.type}
           </span>
        )}
      </div>

      {/* Title */}
      <div className="mb-3">
        <h4 className="text-[14px] font-medium text-gray-800 leading-relaxed group-hover:text-blue-600 transition-colors line-clamp-2">
          {task.title}
        </h4>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-50">
        <div className="flex items-center gap-2">
           <PriorityBadge priority={task.priority} size="sm" />

           {dueDate && (
            <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1 ${isOverdue ? 'bg-red-50 text-red-600' : 'bg-gray-50 text-gray-500'}`}>
              {/* Simple clock icon */}
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
              {dueDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
           )}
        </div>

        {/* Assignee Avatar */}
        {task.assignee ? (
            <div className="w-6 h-6 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center text-[10px] font-bold border border-indigo-100 shadow-sm" title={task.assignee.name}>
                {task.assignee.name.charAt(0)}
            </div>
        ) : (
            <div className="w-6 h-6 rounded-full bg-gray-50 text-gray-400 border border-gray-100 flex items-center justify-center text-[10px] shadow-sm">
                <span className="sr-only">Unassigned</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            </div>
        )}
      </div>
    </div>
  );
}
