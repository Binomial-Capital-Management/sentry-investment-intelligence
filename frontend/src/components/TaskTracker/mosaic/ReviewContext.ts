import { createContext, useContext } from 'react';
import type { Task } from '@/types/task.types';

export interface ReviewContextValue {
  tasks: Task[];
  filteredTasks: Task[];
  searchTerm: string;
  setSearchTerm: (v: string) => void;
  priorityFilter: string | null;
  setPriorityFilter: (v: string | null) => void;
  statusFilter: string | null;
  setStatusFilter: (v: string | null) => void;
  onTaskClick: (t: Task) => void;
  onCreateTask: (statusId: string) => void;
}

export const ReviewContext = createContext<ReviewContextValue>({
  tasks: [],
  filteredTasks: [],
  searchTerm: '',
  setSearchTerm: () => {},
  priorityFilter: null,
  setPriorityFilter: () => {},
  statusFilter: null,
  setStatusFilter: () => {},
  onTaskClick: () => {},
  onCreateTask: () => {},
});

export function useReview() {
  return useContext(ReviewContext);
}
