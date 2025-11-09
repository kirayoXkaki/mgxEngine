import axios from 'axios';
import type { Task, TaskListResponse, TaskCreate } from '@/types/task';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response) {
      // Server responded with error
      console.error('API Error:', error.response.data);
    } else if (error.request) {
      // Request made but no response
      console.error('Network Error:', error.request);
    } else {
      // Something else happened
      console.error('Error:', error.message);
    }
    return Promise.reject(error);
  }
);

// Task API methods
export const taskApi = {
  /**
   * Get all tasks with pagination
   */
  getTasks: async (page: number = 1, pageSize: number = 10): Promise<TaskListResponse> => {
    const response = await apiClient.get<TaskListResponse>('/api/tasks', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  /**
   * Get a single task by ID
   */
  getTaskById: async (id: string): Promise<Task> => {
    const response = await apiClient.get<Task>(`/api/tasks/${id}`);
    return response.data;
  },

  /**
   * Create a new task
   */
  createTask: async (data: TaskCreate): Promise<Task> => {
    const response = await apiClient.post<Task>('/api/tasks', data);
    return response.data;
  },
};

