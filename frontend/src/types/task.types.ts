export interface Task {
  id: string;
  boardId: string;
  statusId: string;
  title: string;
  description?: string;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  type: 'research' | 'meeting' | 'filing' | 'committee' | 'task';
  ticker?: string;
  tags?: string[];
  dueDate?: string;
  startTime?: string; // For calendar items that have a time
  endTime?: string;
  assignee?: {
    id: string;
    name: string;
    avatar?: string;
  };
  createdAt: string;
  updatedAt: string;
}

export interface TaskStatus {
  id: string;
  name: string;
  color: string;
  position: number;
}

export interface TaskBoard {
  id: string;
  name: string;
  description?: string;
  statuses: TaskStatus[];
  createdAt: string;
  updatedAt: string;
}

export interface CreateTaskInput {
  boardId: string;
  statusId: string;
  title: string;
  description?: string;
  priority?: Task['priority'];
  type?: Task['type'];
  ticker?: string;
  dueDate?: string;
  assigneeId?: string;
}

export interface UpdateTaskInput {
  title?: string;
  description?: string;
  statusId?: string;
  priority?: Task['priority'];
  type?: Task['type'];
  ticker?: string;
  dueDate?: string;
  assigneeId?: string;
}

export type ViewMode = 'board' | 'calendar' | 'post_mortems';
