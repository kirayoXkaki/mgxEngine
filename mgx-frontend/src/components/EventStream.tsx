import { useEffect, useRef, useState, useMemo } from 'react';
import type { Event, TaskState } from '@/types/task';
import { TaskStatus } from '@/types/task';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { format } from 'date-fns';
import { Brain, Puzzle, Cog } from 'lucide-react';

interface EventStreamProps {
  events: Event[];
  connectionStatus?: 'connecting' | 'connected' | 'reconnecting' | 'disconnected';
  taskState?: TaskState | null;
}

// Agent role configuration with icons and colors
const agentConfigMap: Record<string, { icon: React.ReactNode; emoji: string; color: string; bgColor: string }> = {
  ProductManager: {
    icon: <Brain className="h-4 w-4" />,
    emoji: '🧠',
    color: 'text-blue-600',
    bgColor: 'bg-blue-50 border-blue-200',
  },
  Architect: {
    icon: <Puzzle className="h-4 w-4" />,
    emoji: '🧩',
    color: 'text-purple-600',
    bgColor: 'bg-purple-50 border-purple-200',
  },
  Engineer: {
    icon: <Cog className="h-4 w-4" />,
    emoji: '⚙️',
    color: 'text-green-600',
    bgColor: 'bg-green-50 border-green-200',
  },
};

const getAgentConfig = (agentRole: string | null) => {
  if (!agentRole) {
    return {
      icon: null,
      emoji: '',
      color: 'text-gray-600',
      bgColor: 'bg-gray-50 border-gray-200',
    };
  }
  return agentConfigMap[agentRole] || {
    icon: null,
    emoji: '',
    color: 'text-gray-600',
    bgColor: 'bg-gray-50 border-gray-200',
  };
};

const formatEventContent = (payload: string | null | undefined): string => {
  // Handle null, undefined, or empty payload
  if (!payload) return '';
  
  // If payload is already a string, check if it's JSON
  if (typeof payload === 'string') {
    try {
      // Try to parse as JSON
      const parsed = JSON.parse(payload);
      if (typeof parsed === 'string') {
        return parsed;
      }
      // If it's an object, try to extract meaningful content
      if (typeof parsed === 'object' && parsed !== null) {
        // If object has a message field, prefer that
        if ('message' in parsed && typeof parsed.message === 'string') {
          return parsed.message;
        }
        return JSON.stringify(parsed, null, 2);
      }
      return String(parsed);
    } catch {
      // If not JSON, return as-is
      return payload;
    }
  }
  
  // If payload is an object (shouldn't happen, but handle it)
  if (typeof payload === 'object' && payload !== null) {
    const payloadObj = payload as Record<string, any>;
    if ('message' in payloadObj && typeof payloadObj.message === 'string') {
      return payloadObj.message;
    }
    return JSON.stringify(payload, null, 2);
  }
  
  // Fallback: convert to string
  return String(payload);
};

// Group events by agent role
const groupEventsByRole = (events: Event[]): Array<{ role: string | null; events: Event[] }> => {
  const groups: Map<string | null, Event[]> = new Map();
  
  events.forEach((event) => {
    const role = event.agent_role || 'System';
    if (!groups.has(role)) {
      groups.set(role, []);
    }
    groups.get(role)!.push(event);
  });
  
  return Array.from(groups.entries()).map(([role, events]) => ({
    role: role === 'System' ? null : role,
    events,
  }));
};

export function EventStream({ events, connectionStatus = 'connected', taskState }: EventStreamProps) {
  const eventsEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const scrollBlockedRef = useRef(false); // Additional flag to block scrolling
  const [highlightedEventId, setHighlightedEventId] = useState<number | null>(null);
  const [previousEventCount, setPreviousEventCount] = useState(0);
  const [userHasScrolled, setUserHasScrolled] = useState(false);
  const isTaskCompletedRef = useRef(false);
  const stableEventsRef = useRef<Event[]>([]);
  
  // Check if task is completed (not running) - MUST be defined before useMemo
  const isTaskCompleted = taskState?.status === TaskStatus.SUCCEEDED || 
                          taskState?.status === TaskStatus.FAILED || 
                          taskState?.status === TaskStatus.CANCELLED;
  
  // Stabilize events array reference when task is completed to prevent re-renders
  useEffect(() => {
    if (isTaskCompleted || isTaskCompletedRef.current) {
      // When task is completed, freeze the events array to prevent re-renders
      if (stableEventsRef.current.length !== events.length) {
        stableEventsRef.current = [...events];
      }
    } else {
      stableEventsRef.current = events;
    }
  }, [events, isTaskCompleted]);

  // Memoize groupedEvents using stable events reference when task is completed
  const groupedEvents = useMemo(() => {
    const eventsToUse = (isTaskCompleted || isTaskCompletedRef.current) 
      ? stableEventsRef.current 
      : events;
    return groupEventsByRole(eventsToUse);
  }, [events, isTaskCompleted]);
  
  // Update ref to track completion status (avoids closure issues)
  useEffect(() => {
    isTaskCompletedRef.current = isTaskCompleted;
  }, [isTaskCompleted]);

  // Track user scroll to detect manual scrolling - DISABLED when task is completed
  useEffect(() => {
    // Don't set up scroll listener if task is completed
    if (isTaskCompletedRef.current || isTaskCompleted || scrollBlockedRef.current) {
      return;
    }

    // Wait for ScrollArea to render
    const timer = setTimeout(() => {
      const scrollContainer = scrollAreaRef.current?.querySelector('[data-radix-scroll-area-viewport]');
      if (!scrollContainer) return;

      let scrollTimeout: ReturnType<typeof setTimeout> | null = null;

      const handleScroll = () => {
        // If task is completed, don't do anything - check FIRST
        if (isTaskCompletedRef.current || scrollBlockedRef.current) {
          return;
        }

        // Debounce scroll events to avoid excessive updates
        if (scrollTimeout) {
          clearTimeout(scrollTimeout);
        }
        
        scrollTimeout = setTimeout(() => {
          // Double check - if task is completed, don't do anything
          if (isTaskCompletedRef.current || scrollBlockedRef.current) {
            return;
          }
          
          // Check if user scrolled away from bottom
          const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
          const isAtBottom = scrollHeight - scrollTop - clientHeight < 50; // 50px threshold
          
          // If user scrolled away from bottom, mark as user scroll
          if (!isAtBottom) {
            setUserHasScrolled(true);
          } else if (isAtBottom && userHasScrolled && !isTaskCompletedRef.current && !scrollBlockedRef.current) {
            // If user scrolled back to bottom, reset the flag (only if task not completed)
            setUserHasScrolled(false);
          }
        }, 100);
      };

      scrollContainer.addEventListener('scroll', handleScroll, { passive: true });
      return () => {
        if (scrollTimeout) clearTimeout(scrollTimeout);
        scrollContainer.removeEventListener('scroll', handleScroll);
      };
    }, 100);

    return () => clearTimeout(timer);
  }, [userHasScrolled, isTaskCompleted]);

  // Auto-scroll to bottom only when:
  // 1. New events arrive (event count increases)
  // 2. Task is still running (not completed)
  // 3. User hasn't manually scrolled away from bottom
  useEffect(() => {
    // CRITICAL: Skip if task is completed - never auto-scroll after completion
    // Use ref to avoid closure issues - check FIRST before anything else
    // Check ALL conditions before doing ANY work
    if (isTaskCompletedRef.current || isTaskCompleted || scrollBlockedRef.current) {
      // Update count but NEVER scroll, even if events array changes
      // Don't even check events.length if task is completed
      const currentCount = events.length;
      if (currentCount !== previousEventCount) {
        setPreviousEventCount(currentCount);
      }
      return; // Early return - no scrolling logic at all, no DOM access
    }

    // If we reach here, task is NOT completed AND scrolling is NOT blocked
    const currentEventCount = events.length;
    const hasNewEvents = currentEventCount > previousEventCount;
    
    // Only auto-scroll if:
    // - There are new events (count increased)
    // - User hasn't manually scrolled away
    // - Task is NOT completed (triple check with ref)
    // - Scrolling is NOT blocked
    // - eventsEndRef is still attached (not cleared)
    if (hasNewEvents && !userHasScrolled && !isTaskCompletedRef.current && !scrollBlockedRef.current && eventsEndRef.current) {
      // Use requestAnimationFrame to ensure DOM is updated
      requestAnimationFrame(() => {
        // Final check before scrolling - use ref for latest state
        // Check ALL conditions again inside requestAnimationFrame
        // Also verify ref is still valid
        if (!isTaskCompletedRef.current && !scrollBlockedRef.current && eventsEndRef.current) {
          try {
            eventsEndRef.current.scrollIntoView({ behavior: 'smooth' });
          } catch (error) {
            // Silently fail if scroll fails (e.g., element removed)
            console.warn('Scroll failed:', error);
          }
        }
      });
      setPreviousEventCount(currentEventCount);
    } else if (currentEventCount !== previousEventCount) {
      // Update count even if not scrolling
      setPreviousEventCount(currentEventCount);
    }
  }, [events.length, previousEventCount, isTaskCompleted, userHasScrolled]); // Use events.length instead of events to avoid unnecessary triggers

  // When task completes, disable auto-scroll permanently
  useEffect(() => {
    if (isTaskCompleted) {
      // Permanently disable auto-scroll - set ALL flags IMMEDIATELY
      isTaskCompletedRef.current = true;
      scrollBlockedRef.current = true; // Block all scrolling FIRST
      setUserHasScrolled(true); // Set to true to prevent any auto-scroll
      // Also update previousEventCount to current to prevent any scroll triggers
      setPreviousEventCount(events.length);
      // Clear the ref to prevent any scrollIntoView calls
      if (eventsEndRef.current) {
        eventsEndRef.current = null;
      }
      console.log('Task completed - auto-scroll permanently disabled');
    } else {
      // Reset scroll block when task is not completed (e.g., restart)
      scrollBlockedRef.current = false;
      isTaskCompletedRef.current = false;
    }
  }, [isTaskCompleted, events.length]);

  // Highlight the latest event temporarily - DISABLED when task is completed
  useEffect(() => {
    // Don't update highlight if task is completed
    if (isTaskCompletedRef.current || isTaskCompleted || scrollBlockedRef.current) {
      return;
    }
    
    if (events.length > 0) {
      const latestEvent = events[events.length - 1];
      setHighlightedEventId(latestEvent.event_id);
      const timer = setTimeout(() => {
        setHighlightedEventId(null);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [events.length, isTaskCompleted]);

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle>Real-time Event Stream</CardTitle>
          {connectionStatus === 'connected' && (
            <span className="text-xs text-green-600 flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              Connected ✅
            </span>
          )}
          {connectionStatus === 'connecting' && (
            <span className="text-xs text-yellow-600 flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-yellow-500 animate-pulse" />
              Connecting...
            </span>
          )}
          {connectionStatus === 'reconnecting' && (
            <span className="text-xs text-orange-600 flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-orange-500 animate-pulse" />
              Reconnecting...
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden p-0">
        <div ref={scrollAreaRef} className="h-full">
          <ScrollArea className="h-full px-4 pb-4">
            <div className="space-y-4">
            {events.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <p>No events yet...</p>
                <p className="text-sm mt-2">Waiting for task to start...</p>
              </div>
            ) : (
              groupedEvents.map((group, groupIndex) => {
                const agentConfig = getAgentConfig(group.role);
                
                return (
                  <div key={group.role || 'system'} className="space-y-2">
                    {group.role && (
                      <>
                        <div className="flex items-center gap-2 py-2">
                          <div className={`flex items-center gap-2 ${agentConfig.color}`}>
                            {agentConfig.icon}
                            <span className="text-sm font-semibold">
                              {group.role} {agentConfig.emoji}
                            </span>
                          </div>
                          <Separator className="flex-1" />
                        </div>
                      </>
                    )}
                    <div className="space-y-2">
                      {group.events.map((event) => {
                        const content = formatEventContent(event.payload);
                        const isHighlighted = highlightedEventId === event.event_id;

                        return (
                          <div
                            key={event.event_id}
                            className={`p-3 border rounded-lg ${agentConfig.bgColor} ${
                              // Disable animations when task is completed to prevent re-renders
                              !isTaskCompleted && !scrollBlockedRef.current
                                ? 'transition-all duration-300 animate-in'
                                : ''
                            } ${
                              isHighlighted && !isTaskCompleted && !scrollBlockedRef.current
                                ? 'ring-2 ring-primary shadow-md scale-[1.02]' 
                                : ''
                            }`}
                          >
                            <div className="flex items-start gap-2">
                              {agentConfig.icon && (
                                <div className={`mt-0.5 ${agentConfig.color} shrink-0`}>
                                  {agentConfig.icon}
                                </div>
                              )}
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between mb-1">
                                  <span className="text-xs text-muted-foreground">
                                    {format(new Date(event.timestamp), 'HH:mm:ss')}
                                  </span>
                                </div>
                                {content && (
                                  <p className="text-sm mt-1 whitespace-pre-wrap break-words text-foreground">
                                    {typeof content === 'string' ? content : String(content)}
                                  </p>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    {groupIndex < groupedEvents.length - 1 && (
                      <Separator className="my-4" />
                    )}
                  </div>
                );
              })
            )}
              {/* Scroll anchor - conditionally attach ref only when task is running */}
              <div 
                ref={(!isTaskCompleted && !scrollBlockedRef.current) ? eventsEndRef : null}
              />
            </div>
          </ScrollArea>
        </div>
      </CardContent>
    </Card>
  );
}
