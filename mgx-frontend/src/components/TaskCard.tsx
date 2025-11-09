import { Link } from 'react-router-dom';
import type { Task } from '@/types/task';
import { TaskStatus } from '@/types/task';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { format } from 'date-fns';

interface TaskCardProps {
  task: Task;
  onStart?: (id: string) => void;
}

const statusColors: Record<TaskStatus, string> = {
  [TaskStatus.PENDING]: 'bg-yellow-100 text-yellow-800',
  [TaskStatus.RUNNING]: 'bg-blue-100 text-blue-800',
  [TaskStatus.SUCCEEDED]: 'bg-green-100 text-green-800',
  [TaskStatus.FAILED]: 'bg-red-100 text-red-800',
  [TaskStatus.CANCELLED]: 'bg-gray-100 text-gray-800',
};

export function TaskCard({ task, onStart }: TaskCardProps) {
  const handleCardClick = () => {
    // Navigation is handled by the Link in the button
  };

  return (
    <Card 
      className="hover:shadow-lg transition-all cursor-pointer hover:border-primary/50"
      onClick={handleCardClick}
    >
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-lg flex-1 line-clamp-2">{task.title}</CardTitle>
          <Badge 
            className={`${statusColors[task.status]} shrink-0`}
            variant="outline"
          >
            {task.status}
          </Badge>
        </div>
        <CardDescription className="line-clamp-3 mt-2">
          {task.input_prompt}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="text-sm text-muted-foreground space-y-1">
          <p className="text-xs">
            Created: {format(new Date(task.created_at), 'MMM d, yyyy HH:mm')}
          </p>
          {task.result_summary && (
            <div className="mt-2 p-2 bg-muted rounded text-xs line-clamp-2">
              {task.result_summary}
            </div>
          )}
        </div>
      </CardContent>
      <CardFooter className="flex gap-2 pt-4">
        <Button variant="outline" className="flex-1" asChild>
          <Link to={`/tasks/${task.id}`} onClick={(e) => e.stopPropagation()}>
            View Details
          </Link>
        </Button>
        {task.status === TaskStatus.PENDING && onStart && (
          <Button 
            onClick={(e) => {
              e.stopPropagation();
              onStart(task.id);
            }}
            size="sm"
          >
            Start
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}

