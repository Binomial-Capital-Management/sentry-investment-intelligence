import type { Task } from '@/types/task.types';

interface PriorityBadgeProps {
  priority: Task['priority'];
  size?: 'sm' | 'md';
}

const priorityConfig = {
  urgent: {
    label: 'Urgent',
    classes: 'bg-red-50 text-red-600',
  },
  high: {
    label: 'High',
    classes: 'bg-orange-50 text-orange-600',
  },
  medium: {
    label: 'Medium',
    classes: 'bg-blue-50 text-blue-600',
  },
  low: {
    label: 'Low',
    classes: 'bg-slate-50 text-slate-600',
  },
};

export function PriorityBadge({ priority, size = 'md' }: PriorityBadgeProps) {
  // Fallback to medium if priority is undefined or invalid
  const config = priorityConfig[priority] || priorityConfig.medium;

  const containerClasses = size === 'sm'
    ? 'px-2 py-0.5 text-[10px] font-semibold'
    : 'px-2.5 py-1 text-xs font-medium';

  return (
    <span
      className={`
        inline-flex items-center justify-center rounded-full
        ${config.classes} ${containerClasses}
      `}
    >
      {config.label}
    </span>
  );
}
