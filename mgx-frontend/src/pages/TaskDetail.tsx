import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTaskStore } from '@/store/taskStore';
import { EventStream } from '@/components/EventStream';
import { connectTaskWebSocket } from '@/api/websocket';
import type { Event, TaskState } from '@/types/task';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { TaskStatus } from '@/types/task';
import { format } from 'date-fns';
import { ArrowLeft, Loader2, RotateCcw, CheckCircle2, XCircle, Clock } from 'lucide-react';

const statusColors: Record<TaskStatus, string> = {
  [TaskStatus.PENDING]: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  [TaskStatus.RUNNING]: 'bg-blue-100 text-blue-800 border-blue-300',
  [TaskStatus.SUCCEEDED]: 'bg-green-100 text-green-800 border-green-300',
  [TaskStatus.FAILED]: 'bg-red-100 text-red-800 border-red-300',
  [TaskStatus.CANCELLED]: 'bg-gray-100 text-gray-800 border-gray-300',
};

const statusIcons: Record<TaskStatus, React.ReactNode> = {
  [TaskStatus.PENDING]: <Clock className="h-4 w-4" />,
  [TaskStatus.RUNNING]: <Loader2 className="h-4 w-4 animate-spin" />,
  [TaskStatus.SUCCEEDED]: <CheckCircle2 className="h-4 w-4" />,
  [TaskStatus.FAILED]: <XCircle className="h-4 w-4" />,
  [TaskStatus.CANCELLED]: <XCircle className="h-4 w-4" />,
};

const getProgressColor = (status: TaskStatus): string => {
  switch (status) {
    case TaskStatus.RUNNING:
      return 'bg-blue-500';
    case TaskStatus.SUCCEEDED:
      return 'bg-green-500';
    case TaskStatus.FAILED:
      return 'bg-red-500';
    default:
      return 'bg-gray-500';
  }
};

export function TaskDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { 
    currentTask, 
    loading, 
    error, 
    fetchTask, 
    startTask,
  } = useTaskStore();

  // WebSocket state
  const [events, setEvents] = useState<Event[]>([]);
  const [taskState, setTaskState] = useState<TaskState | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const isTaskCompletedRef = useRef(false); // Track task completion across re-renders

  // Fetch task on mount
  useEffect(() => {
    if (id) {
      // Only fetch if we don't already have this task loaded
      // This prevents unnecessary API calls and white screen
      if (!currentTask || currentTask.id !== id) {
        fetchTask(id);
      }
    }
  }, [id, fetchTask, currentTask]);

  // Connect WebSocket on mount
  useEffect(() => {
    if (!id) return;

    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const cleanup = connectTaskWebSocket(id, (msg) => {
      // Check if task is completed - if so, ignore all messages to prevent re-renders
      // But don't close the connection, so it can still reconnect if needed
      if (isTaskCompletedRef.current) {
        return;
      }

      switch (msg.type) {
        case 'connected':
          setIsConnected(true);
          setIsReconnecting(false);
          // Reset task completed flag on reconnect (in case task was restarted)
          isTaskCompletedRef.current = false;
          break;
        case 'event':
          setEvents((prev) => [...prev, msg.data]);
          break;
        case 'state':
          const newState = msg.data;
          setTaskState(newState);
          // Check if task is completed and stop processing future messages
          // But keep the connection open for potential reconnects
          if (newState.status === TaskStatus.SUCCEEDED || 
              newState.status === TaskStatus.FAILED || 
              newState.status === TaskStatus.CANCELLED) {
            isTaskCompletedRef.current = true;
            // Don't close the connection - just stop processing messages
            // This allows reconnection if the task is restarted or if connection drops
          }
          break;
        case 'error':
          console.error('WebSocket error:', msg.message);
          setIsConnected(false);
          // Show reconnecting status after a delay
          reconnectTimeout = setTimeout(() => {
            setIsReconnecting(true);
          }, 1000);
          break;
      }
    });

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      // Only close WebSocket when component unmounts
      cleanup();
    };
  }, [id]);

  const handleStart = async () => {
    if (id) {
      await startTask(id);
    }
  };

  const handleRestart = async () => {
    if (id) {
      setEvents([]);
      setTaskState(null);
      setIsReconnecting(false);
      // Reset task completion state - WebSocket will continue to work
      isTaskCompletedRef.current = false;
      await startTask(id);
    }
  };

  // Priority 1: If we have currentTask with matching ID, show it immediately
  // This prevents white screen when navigating from create page
  // Even if loading is true (for background operations), show the task
  if (currentTask && currentTask.id === id) {
    // Continue to render - we have the task data
  }
  // Priority 2: Show loading state only if we don't have currentTask AND we're loading
  else if (loading && !currentTask) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
          <p className="text-muted-foreground">Loading task...</p>
        </div>
      </div>
    );
  }
  // Priority 3: Show error state if task not found or error occurred
  else if (error && !currentTask) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <div className="text-red-600 mb-4">
            <p className="text-lg font-semibold mb-2">Error</p>
            <p className="text-sm">
              {typeof error === 'string' 
                ? error 
                : (error as any)?.message || JSON.stringify(error) || 'Task not found'}
            </p>
          </div>
          <Button onClick={() => navigate('/')} className="mt-4">
            Back to Home
          </Button>
        </div>
      </div>
    );
  }
  // Priority 4: If no task and not loading, show error
  else if (!currentTask && !loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <div className="text-muted-foreground mb-4">
            <p className="text-lg font-semibold mb-2">Task not found</p>
            <p className="text-sm">The task you're looking for doesn't exist or has been deleted.</p>
          </div>
          <Button onClick={() => navigate('/')} className="mt-4">
            Back to Home
          </Button>
        </div>
      </div>
    );
  }
  // Fallback: This should never happen, but TypeScript needs it
  else if (!currentTask) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  const displayStatus = taskState?.status || currentTask.status;
  const displayProgress = taskState?.progress ?? 0;
  const connectionStatus = isReconnecting 
    ? 'reconnecting' 
    : isConnected 
    ? 'connected' 
    : 'connecting';

  return (
    <div className="min-h-screen bg-background">
      {/* Top Bar */}
      <div className="border-b bg-card sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4 max-w-7xl">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-4 flex-1 min-w-0">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/')}
                className="shrink-0"
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
              <Separator orientation="vertical" className="h-6" />
              <div className="flex-1 min-w-0">
                <h1 className="text-lg font-semibold truncate">{currentTask.title}</h1>
                <p className="text-sm text-muted-foreground truncate">
                  {currentTask.input_prompt}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <Badge 
                className={`${statusColors[displayStatus as TaskStatus]} flex items-center gap-1.5 px-3 py-1.5`}
                variant="outline"
              >
                {statusIcons[displayStatus as TaskStatus]}
                <span>{displayStatus}</span>
                {displayStatus === TaskStatus.SUCCEEDED && '✅'}
              </Badge>
              {(displayStatus === TaskStatus.SUCCEEDED || displayStatus === TaskStatus.FAILED) && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRestart}
                  disabled={loading}
                >
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Restart
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Connection Status Banner */}
      {isReconnecting && (
        <div className="bg-orange-50 border-b border-orange-200 px-4 py-2">
          <div className="container mx-auto max-w-7xl">
            <div className="flex items-center gap-2 text-sm text-orange-800">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Reconnecting to WebSocket...</span>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="container mx-auto px-4 py-6 max-w-7xl">
        <div className="grid gap-6">

          {/* Progress Indicator */}
          <Card>
            <CardContent className="pt-6">
              {displayProgress > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium">Progress</p>
                      {taskState?.current_agent && (
                        <Badge variant="outline" className="text-xs">
                          {typeof taskState.current_agent === 'string' 
                            ? taskState.current_agent 
                            : String(taskState.current_agent)}
                        </Badge>
                      )}
                    </div>
                    <span className="text-sm font-semibold text-muted-foreground">
                      {(displayProgress * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="w-full bg-secondary rounded-full h-3 overflow-hidden relative">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${getProgressColor(displayStatus as TaskStatus)}`}
                      style={{ width: `${displayProgress * 100}%` }}
                    />
                    {displayStatus === TaskStatus.RUNNING && (
                      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Task Details */}
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Task Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-sm font-medium">Created</p>
                  <p className="text-sm text-muted-foreground">
                    {format(new Date(currentTask.created_at), 'PPpp')}
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium">Updated</p>
                  <p className="text-sm text-muted-foreground">
                    {format(new Date(currentTask.updated_at), 'PPpp')}
                  </p>
                </div>
                {taskState?.current_agent && (
                  <div>
                    <p className="text-sm font-medium">Current Agent</p>
                    <p className="text-sm text-muted-foreground">
                      {typeof taskState.current_agent === 'string' 
                        ? taskState.current_agent 
                        : String(taskState.current_agent)}
                    </p>
                  </div>
                )}
                {currentTask.status === TaskStatus.PENDING && (
                  <Button onClick={handleStart} disabled={loading} className="w-full">
                    {loading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Starting...
                      </>
                    ) : (
                      'Start Task'
                    )}
                  </Button>
                )}
              </CardContent>
            </Card>

            {currentTask.result_summary && (
              <Card>
                <CardHeader>
                  <CardTitle>Result Summary</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="p-3 bg-muted rounded-lg">
                    <p className="text-sm whitespace-pre-wrap">
                      {currentTask.result_summary}
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Event Stream - Full Width */}
          <div className="lg:h-[calc(100vh-300px)] min-h-[500px]">
            <EventStream 
              events={events} 
              connectionStatus={connectionStatus} 
              taskState={taskState}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
