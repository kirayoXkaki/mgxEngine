import { create } from 'zustand';
import type { Task, Event, TaskState } from '@/types/task';
import { TaskStatus } from '@/types/task';
import { apiClient } from '@/api/client';

interface TaskStore {
  tasks: Task[];
  currentTask: Task | null;
  taskState: TaskState | null;
  events: Event[];
  loading: boolean;
  error: string | null;

  // Actions
  fetchTasks: () => Promise<void>;
  fetchTask: (id: string) => Promise<void>;
  createTask: (title: string, input_prompt: string) => Promise<Task>;
  startTask: (id: string) => Promise<void>;
  fetchTaskState: (id: string) => Promise<void>;
  fetchEvents: (id: string) => Promise<void>;
  addEvent: (event: Event) => void;
  updateTaskState: (state: TaskState) => void;
  setCurrentTask: (task: Task | null) => void;
  clearEvents: () => void;
}

export const useTaskStore = create<TaskStore>((set) => ({
  tasks: [],
  currentTask: null,
  taskState: null,
  events: [],
  loading: false,
  error: null,

  fetchTasks: async () => {
    set({ loading: true, error: null });
    try {
      const response = await apiClient.get('/api/tasks');
      set({ 
        tasks: response.data.items || response.data || [], 
        loading: false 
      });
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || 'Failed to fetch tasks';
      set({ 
        error: typeof errorMessage === 'string' ? errorMessage : String(errorMessage),
        loading: false 
      });
    }
  },

  fetchTask: async (id: string) => {
    set({ loading: true, error: null });
    try {
      const response = await apiClient.get(`/api/tasks/${id}`);
      set({ currentTask: response.data, loading: false, error: null });
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || 'Failed to fetch task';
      set({ 
        error: typeof errorMessage === 'string' ? errorMessage : String(errorMessage),
        loading: false,
        currentTask: null
      });
      console.error('Failed to fetch task:', error);
    }
  },

  createTask: async (title: string, input_prompt: string) => {
    set({ loading: true, error: null });
    try {
      const response = await apiClient.post('/api/tasks', {
        title,
        input_prompt,
      });
      const newTask = response.data;
      set((state) => ({
        tasks: [newTask, ...state.tasks],
        currentTask: newTask,
        loading: false,
        error: null,
      }));
      return newTask;
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || 'Failed to create task';
      set({ 
        error: typeof errorMessage === 'string' ? errorMessage : String(errorMessage),
        loading: false 
      });
      throw error;
    }
  },

  startTask: async (id: string) => {
    // Don't set loading to true for startTask - it's a background operation
    // This prevents white screen when starting task from detail page
    set({ error: null });
    try {
      await apiClient.post(`/api/tasks/${id}/run`);
      // Optionally update currentTask status if it matches
      set((state) => {
        if (state.currentTask && state.currentTask.id === id) {
          return {
            currentTask: {
              ...state.currentTask,
              status: TaskStatus.RUNNING,
            },
          };
        }
        return {};
      });
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || 'Failed to start task';
      set({ 
        error: typeof errorMessage === 'string' ? errorMessage : String(errorMessage),
      });
      console.error('Failed to start task:', error);
    }
  },

  fetchTaskState: async (id: string) => {
    try {
      const response = await apiClient.get(`/api/tasks/${id}/state`);
      set({ taskState: response.data });
    } catch (error: any) {
      console.error('Failed to fetch task state:', error);
    }
  },

  fetchEvents: async (id: string) => {
    try {
      const response = await apiClient.get(`/api/tasks/${id}/events`);
      set({ events: response.data.items || [] });
    } catch (error: any) {
      console.error('Failed to fetch events:', error);
    }
  },

  addEvent: (event: Event) => {
    set((state) => ({
      events: [...state.events, event],
    }));
  },

  updateTaskState: (state: TaskState) => {
    set({ taskState: state });
    // Also update the current task status if it matches
    set((store) => {
      if (store.currentTask && store.currentTask.id === state.task_id) {
        return {
          currentTask: {
            ...store.currentTask,
            status: state.status as TaskStatus,
          },
        };
      }
      return {};
    });
  },

  setCurrentTask: (task: Task | null) => {
    set({ currentTask: task, events: [] });
  },

  clearEvents: () => {
    set({ events: [] });
  },
}));

