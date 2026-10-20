import type { EventProps } from 'react-big-calendar';
import type { Task } from '@/types/task.types';

export function CalendarEvent({ event }: EventProps) {
  const task = event.resource as Task;

  return (
    <div className="flex items-center gap-1.5 px-0.5 overflow-hidden h-full">
      <span className="truncate font-semibold text-xs leading-none">{task.title}</span>
    </div>
  );
}
