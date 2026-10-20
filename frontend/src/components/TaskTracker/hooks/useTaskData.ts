import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import type { Task } from '@/types/task.types';
import { API_BASE } from '@/services/api';

const USE_MOCK_DATA = true; // Set to false when backend is ready

// Mock data for development
const MOCK_TASKS: Task[] = [
  {
    id: '1',
    boardId: 'default',
    statusId: 'idea-generation',
    title: 'Review Q4 Portfolio Performance',
    description: 'Analyze returns, risk metrics, and rebalancing opportunities against benchmark.',
    priority: 'high',
    type: 'research',
    ticker: 'PORT',
    dueDate: '2025-11-25',
    createdAt: '2025-11-15T10:00:00Z',
    updatedAt: '2025-11-15T10:00:00Z',
  },
  {
    id: '2',
    boardId: 'default',
    statusId: 'due-diligence',
    title: 'Deep Dive: NVIDIA Corp',
    description: 'Analyze Blackwell architecture impact on margin structure.',
    priority: 'urgent',
    type: 'research',
    ticker: 'NVDA',
    dueDate: '2025-11-20',
    createdAt: '2025-11-15T11:00:00Z',
    updatedAt: '2025-11-15T11:00:00Z',
  },
  {
    id: '3',
    boardId: 'default',
    statusId: 'ic-review',
    title: 'Investment Committee: MSFT Position',
    description: 'Decision meeting on overweighting Microsoft allocated funds.',
    priority: 'high',
    type: 'committee',
    ticker: 'MSFT',
    dueDate: '2025-11-22',
    assignee: {
      id: 'user1',
      name: 'Sarah Chen',
    },
    createdAt: '2025-11-14T09:00:00Z',
    updatedAt: '2025-11-16T15:00:00Z',
  },
  {
    id: '4',
    boardId: 'default',
    statusId: 'idea-generation',
    title: 'Sector Rotation: Semiconductor to Energy',
    description: 'Research rotation opportunities given macro headwinds.',
    priority: 'medium',
    type: 'research',
    dueDate: '2025-11-28',
    createdAt: '2025-11-13T14:00:00Z',
    updatedAt: '2025-11-15T10:00:00Z',
  },
  {
    id: '5',
    boardId: 'default',
    statusId: 'portfolio',
    title: 'Client Report: Institutional Fund A',
    description: 'Prepare quarterly performance summary for institutional client.',
    priority: 'high',
    type: 'task',
    dueDate: '2025-11-19',
    assignee: {
      id: 'user2',
      name: 'David Miller',
    },
    createdAt: '2025-11-10T08:00:00Z',
    updatedAt: '2025-11-17T12:00:00Z',
  },
  {
    id: '6',
    boardId: 'default',
    statusId: 'due-diligence',
    title: 'Earnings Call: Tesla Q3',
    description: 'Attend call and update valuation model.',
    priority: 'medium',
    type: 'filing',
    ticker: 'TSLA',
    dueDate: '2025-11-24',
    createdAt: '2025-11-12T16:00:00Z',
    updatedAt: '2025-11-16T09:00:00Z',
  },
  {
    id: '7',
    boardId: 'default',
    statusId: 'ic-review',
    title: 'IC Memo: Amazon Valuation',
    description: 'Finalize memo for committee review next week.',
    priority: 'urgent',
    type: 'committee',
    ticker: 'AMZN',
    dueDate: '2025-11-21',
    assignee: {
      id: 'user3',
      name: 'Jessica Wu',
    },
    createdAt: '2025-11-05T10:00:00Z',
    updatedAt: '2025-11-15T17:00:00Z',
  },
  {
    id: '8',
    boardId: 'default',
    statusId: 'portfolio',
    title: 'ESG Screening Implementation',
    description: 'Apply ESG filters to portfolio holdings.',
    priority: 'medium',
    type: 'task',
    dueDate: '2025-11-18',
    createdAt: '2025-11-08T11:00:00Z',
    updatedAt: '2025-11-18T14:00:00Z',
  },
];

interface UseTaskDataOptions {
  boardId?: string;
  enabled?: boolean;
}

export function useTaskData(options: UseTaskDataOptions = {}) {
  const { boardId, enabled = true } = options;

  return useQuery({
    queryKey: ['planning', boardId],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        // Simulate API delay
        await new Promise((resolve) => setTimeout(resolve, 300));
        return MOCK_TASKS;
      }

      const { data } = await axios.get<Task[]>(`${API_BASE}/v6/planning`, {
        params: { boardId },
        headers: {
          Authorization: `Bearer ${localStorage.getItem('clerk_session_token')}`,
        },
      });
      return data;
    },
    enabled,
    refetchInterval: USE_MOCK_DATA ? false : 30000, // Don't poll with mock data
    staleTime: 10000,
  });
}
