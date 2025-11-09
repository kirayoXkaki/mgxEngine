import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTaskStore } from '@/store/taskStore';
import { TaskCard } from '@/components/TaskCard';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

export function Home() {
  const navigate = useNavigate();
  const { tasks, loading, error, fetchTasks, createTask, startTask } = useTaskStore();
  const [inputPrompt, setInputPrompt] = useState('');
  const [isRunning, setIsRunning] = useState(false);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const handleRunTask = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!inputPrompt.trim()) return;

    setIsRunning(true);
    try {
      // Create task with prompt as title
      const task = await createTask(
        inputPrompt.slice(0, 50) + (inputPrompt.length > 50 ? '...' : ''),
        inputPrompt
      );
      
      // Clear input immediately
      setInputPrompt('');
      
      // Navigate to task detail page first (so user sees the page)
      navigate(`/tasks/${task.id}`);
      
      // Start the task after navigation (non-blocking)
      startTask(task.id).catch((error) => {
        console.error('Failed to start task:', error);
        // Task is already created, so user can manually start it
      });
    } catch (error) {
      console.error('Failed to create task:', error);
      // Show error to user
      alert('Failed to create task. Please try again.');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">MGX Engine</h1>
        <p className="text-muted-foreground">Create and manage multi-agent tasks</p>
      </div>

      {/* Task Creation Form */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Create New Task</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleRunTask} className="space-y-4">
            <div>
              <Label htmlFor="prompt">Task Prompt</Label>
              <Textarea
                id="prompt"
                value={inputPrompt}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setInputPrompt(e.target.value)}
                placeholder="Describe what you want to build or create... (e.g., 'Create a REST API with user authentication')"
                rows={4}
                required
                disabled={isRunning || loading}
                className="resize-none"
              />
              <p className="text-sm text-muted-foreground mt-1">
                Enter a natural language description of what you want the agents to build.
              </p>
            </div>
            <Button type="submit" disabled={isRunning || loading || !inputPrompt.trim()} className="w-full">
              {isRunning ? 'Creating and Starting Task...' : loading ? 'Loading...' : 'Run Task'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <div className="mb-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg text-destructive">
          <p className="font-medium">Error</p>
          <p className="text-sm">
            {typeof error === 'string' 
              ? error 
              : (error as any)?.message || JSON.stringify(error) || 'Unknown error'}
          </p>
        </div>
      )}

      {/* Tasks List */}
      <div className="mb-4">
        <h2 className="text-2xl font-semibold mb-4">Tasks</h2>
        {loading && tasks.length === 0 ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            <p className="mt-4 text-muted-foreground">Loading tasks...</p>
          </div>
        ) : tasks.length === 0 ? (
          <div className="text-center py-12 border-2 border-dashed rounded-lg">
            <p className="text-muted-foreground text-lg">No tasks yet</p>
            <p className="text-muted-foreground text-sm mt-2">
              Create your first task using the form above
            </p>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {tasks.map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                onStart={startTask}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

