import { useState } from 'react';
import { DragEndEvent, DragStartEvent } from '@dnd-kit/core';
import { useTaskMutations } from './useTaskMutations';
import type { Task } from '@/types/task.types';

export function useDragAndDrop() {
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const { updateTask } = useTaskMutations();

  const handleDragStart = (event: DragStartEvent) => {
    // Store the task being dragged
    const taskData = event.active.data.current;
    if (taskData) {
      setActiveTask(taskData as Task);
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (!over) {
      setActiveTask(null);
      return;
    }

    const taskId = active.id as string;
    const newStatusId = over.id as string;

    // Only update if status changed
    if (activeTask && activeTask.statusId !== newStatusId) {
      // Optimistic update - UI updates immediately
      updateTask.mutate({
        id: taskId,
        updates: { statusId: newStatusId },
      });
    }

    setActiveTask(null);
  };

  return {
    activeTask,
    handleDragStart,
    handleDragEnd,
  };
}
