export const TaskStatus = {
  PENDING: "PENDING",
  RUNNING: "RUNNING",
  SUCCEEDED: "SUCCEEDED",
  FAILED: "FAILED",
  CANCELLED: "CANCELLED",
} as const;

export type TaskStatus = typeof TaskStatus[keyof typeof TaskStatus];

export const EventType = {
  LOG: "LOG",
  MESSAGE: "MESSAGE",
  ERROR: "ERROR",
  RESULT: "RESULT",
  AGENT_START: "AGENT_START",
  AGENT_COMPLETE: "AGENT_COMPLETE",
} as const;

export type EventType = typeof EventType[keyof typeof EventType];

export interface Task {
  id: string;
  title: string;
  input_prompt: string;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
  result_summary: string | null;
}

export interface TaskCreate {
  title: string;
  input_prompt: string;
}

export interface TaskState {
  task_id: string;
  status: TaskStatus;
  progress: number;
  current_agent: string | null;
  last_message: string | null;
}

export interface Event {
  event_id: number;
  task_id: string;
  timestamp: string;
  agent_role: string | null;
  event_type: EventType;
  payload: string;
}

export interface EventLog {
  id: number;
  task_id: string;
  event_type: EventType;
  agent_role: string | null;
  content: string;
  created_at: string;
}

export interface TaskListResponse {
  items: Task[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

