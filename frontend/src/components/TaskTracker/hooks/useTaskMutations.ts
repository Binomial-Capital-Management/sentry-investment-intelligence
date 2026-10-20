import { useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import type { Task, CreateTaskInput, UpdateTaskInput } from '@/types/task.types';
import { API_BASE } from '@/services/api';

const getAuthHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem('clerk_session_token')}`,
});

export function useTaskMutations() {
  const queryClient = useQueryClient();

  const createTask = useMutation({
    mutationFn: async (input: CreateTaskInput) => {
      const { data } = await axios.post<Task>(
        `${API_BASE}/v6/planning`,
        input,
        { headers: getAuthHeaders() },
      );
      return data;
    },
    onSuccess: () => {
      // Invalidate and refetch planning items
      queryClient.invalidateQueries({ queryKey: ['planning'] });
    },
    onError: (error) => {
      console.error('Failed to create planning item:', error);
    },
  });

  const updateTask = useMutation({
    mutationFn: async ({ id, updates }: { id: string; updates: UpdateTaskInput }) => {
      const { data } = await axios.patch<Task>(
        `${API_BASE}/v6/planning/${id}`,
        updates,
        { headers: getAuthHeaders() },
      );
      return data;
    },
    onMutate: async ({ id, updates }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['planning'] });

      // Snapshot previous value
      const previousTasks = queryClient.getQueryData(['planning']);

      // Optimistically update cache
      queryClient.setQueryData<Task[]>(['planning'], (old) => {
        if (!old) return old;
        return old.map((task) =>
          task.id === id ? { ...task, ...updates } : task,
        );
      });

      return { previousTasks };
    },
    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousTasks) {
        queryClient.setQueryData(['planning'], context.previousTasks);
      }
      console.error('Failed to update planning item:', error);
    },
    onSettled: () => {
      // Refetch after error or success
      queryClient.invalidateQueries({ queryKey: ['planning'] });
    },
  });

  const deleteTask = useMutation({
    mutationFn: async (id: string) => {
      await axios.delete(`${API_BASE}/v6/planning/${id}`, {
        headers: getAuthHeaders(),
      });
      return id;
    },
    onSuccess: (deletedId) => {
      // Optimistically remove from cache
      queryClient.setQueryData<Task[]>(['planning'], (old) => {
        if (!old) return old;
        return old.filter((task) => task.id !== deletedId);
      });
    },
    onError: (error) => {
      console.error('Failed to delete planning item:', error);
      queryClient.invalidateQueries({ queryKey: ['planning'] });
    },
  });

  return {
    createTask,
    updateTask,
    deleteTask,
  };
}
