"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { queueApi, tasksApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatDateTime, isExpired, timeUntil, TASK_TYPE_COLORS, TASK_TYPE_LABELS } from "@/lib/utils";
import { Clock } from "lucide-react";

function AssignmentCard({ assignment }: { assignment: Awaited<ReturnType<typeof queueApi.mine>>[number] }) {
  const { data: task } = useQuery({
    queryKey: ["tasks", assignment.task_id],
    queryFn: () => tasksApi.get(assignment.task_id),
  });
  const expired = isExpired(assignment.expires_at);

  return (
    <Card className={cn(expired && "opacity-60 border-destructive/30")}>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-semibold line-clamp-2">
            {task?.title ?? <span className="text-muted-foreground">Loading…</span>}
          </CardTitle>
          {task && (
            <span className={cn("shrink-0 text-xs rounded-full px-2 py-0.5 font-medium", TASK_TYPE_COLORS[task.task_type])}>
              {TASK_TYPE_LABELS[task.task_type]}
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent className="pb-2">
        <p className="text-sm text-muted-foreground line-clamp-2">{task?.prompt}</p>
      </CardContent>
      <CardFooter className="pt-0 flex items-center justify-between">
        <span className={cn("flex items-center gap-1 text-xs", expired ? "text-destructive font-medium" : "text-muted-foreground")}>
          <Clock className="h-3 w-3" />
          {expired ? "Expired" : `${timeUntil(assignment.expires_at)} left`}
          <span className="mx-1">·</span>
          Claimed {formatDateTime(assignment.claimed_at)}
        </span>
        {!expired && (
          <Button size="sm" asChild>
            <Link href={`/annotator/workspace/${assignment.id}`}>Continue</Link>
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}

export default function MyTasksPage() {
  const { data: assignments, isLoading } = useQuery({
    queryKey: ["my-tasks"],
    queryFn: queueApi.mine,
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">My Tasks</h1>
        <p className="text-muted-foreground text-sm mt-1">Your in-progress assignments. Complete them before they expire.</p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-40 w-full rounded-lg" />)}
        </div>
      ) : assignments?.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-muted-foreground">No active assignments.</p>
          <Button className="mt-4" asChild>
            <Link href="/annotator/queue">Browse Queue</Link>
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {assignments?.map((a) => <AssignmentCard key={a.id} assignment={a} />)}
        </div>
      )}
    </div>
  );
}
