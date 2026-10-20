import { DndContext, DragOverlay, closestCorners, PointerSensor, useSensor, useSensors, defaultDropAnimationSideEffects } from '@dnd-kit/core';
import { KanbanColumn } from './KanbanColumn';
import { TaskCard } from './TaskCard';
import { useDragAndDrop } from '../hooks/useDragAndDrop';
import type { Task, TaskStatus } from '@/types/task.types';

interface KanbanBoardProps {
  tasks: Task[];
  onTaskClick: (task: Task) => void;
  onCreateTask: (statusId: string) => void;
}

const DEFAULT_STATUSES: TaskStatus[] = [
  { id: 'idea-generation', name: 'Idea Generation', color: '#64748b', position: 0 },
  { id: 'due-diligence', name: 'Due Diligence', color: '#3b82f6', position: 1 },
  { id: 'ic-review', name: 'IC Review', color: '#f59e0b', position: 2 },
  { id: 'portfolio', name: 'Portfolio', color: '#10b981', position: 3 },
];

export function KanbanBoard({ tasks, onTaskClick, onCreateTask }: KanbanBoardProps) {
  const { activeTask, handleDragStart, handleDragEnd } = useDragAndDrop();

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 3,
      },
    }),
  );

  const dropAnimation = {
    sideEffects: defaultDropAnimationSideEffects({
      styles: {
        active: {
          opacity: '0.5',
        },
      },
    }),
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="h-full overflow-x-auto overflow-y-hidden">
        <div className="flex h-full gap-6 px-2 pb-2 min-w-max">
          {DEFAULT_STATUSES.map((status) => {
            const statusTasks = tasks.filter((t) => t.statusId === status.id);

            return (
              <KanbanColumn
                key={status.id}
                status={status}
                tasks={statusTasks}
                onTaskClick={onTaskClick}
                onCreateTask={onCreateTask}
              />
            );
          })}
        </div>
      </div>

      <DragOverlay dropAnimation={dropAnimation}>
        {activeTask ? (
          <div className="rotate-2 cursor-grabbing scale-105">
            <TaskCard task={activeTask} isDragging />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
