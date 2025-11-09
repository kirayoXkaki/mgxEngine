import type { Event, TaskState } from '@/types/task';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL = API_URL.replace(/^http/, 'ws');

export type WebSocketMessage = 
  | { type: 'connected'; message: string }
  | { type: 'event'; data: Event }
  | { type: 'state'; data: TaskState }
  | { type: 'error'; message: string };

/**
 * Connect to task WebSocket and handle messages
 * @param taskId - Task ID to connect to
 * @param onMessage - Callback for received messages
 * @returns Cleanup function to disconnect
 */
export function connectTaskWebSocket(
  taskId: string,
  onMessage: (msg: WebSocketMessage) => void
): () => void {
  const url = `${WS_URL}/ws/tasks/${taskId}`;
  let ws: WebSocket | null = null;
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;
  const reconnectDelay = 1000;
  let isManualClose = false;

  const connect = () => {
    try {
      ws = new WebSocket(url);

      ws.onopen = () => {
        console.log('WebSocket connected for task:', taskId);
        reconnectAttempts = 0;
        onMessage({ type: 'connected', message: 'Connected' });
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WebSocketMessage;
          onMessage(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
          onMessage({ type: 'error', message: 'Failed to parse message' });
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        onMessage({ type: 'error', message: 'WebSocket connection error' });
      };

      ws.onclose = () => {
        console.log('WebSocket closed for task:', taskId);
        
        // Attempt to reconnect if not manually closed
        if (!isManualClose && reconnectAttempts < maxReconnectAttempts) {
          reconnectAttempts++;
          reconnectTimeout = setTimeout(() => {
            console.log(`Reconnecting... (attempt ${reconnectAttempts})`);
            connect();
          }, reconnectDelay * reconnectAttempts);
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      onMessage({ type: 'error', message: 'Failed to create WebSocket connection' });
    }
  };

  connect();

  // Return cleanup function
  return () => {
    isManualClose = true;
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
    }
    if (ws) {
      ws.close();
      ws = null;
    }
  };
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private taskId: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  constructor(taskId: string) {
    this.taskId = taskId;
  }

  connect(
    onMessage: (message: WebSocketMessage) => void,
    onError?: (error: globalThis.Event) => void,
    onClose?: () => void
  ): void {
    const url = `${WS_URL}/ws/tasks/${this.taskId}`;
    
    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
      };

      this.ws.onmessage = (wsEvent) => {
        try {
          const data = JSON.parse(wsEvent.data) as WebSocketMessage;
          onMessage(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        if (onError) {
          onError(error);
        }
      };

      this.ws.onclose = () => {
        console.log('WebSocket closed');
        if (onClose) {
          onClose();
        }
        
        // Attempt to reconnect if not a normal closure
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          setTimeout(() => {
            console.log(`Reconnecting... (attempt ${this.reconnectAttempts})`);
            this.connect(onMessage, onError, onClose);
          }, this.reconnectDelay * this.reconnectAttempts);
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      if (onError) {
        onError(error as globalThis.Event);
      }
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

