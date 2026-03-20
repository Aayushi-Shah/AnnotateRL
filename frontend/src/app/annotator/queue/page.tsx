"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { queueApi } from "@/lib/api";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, TASK_TYPE_COLORS, TASK_TYPE_LABELS } from "@/lib/utils";

const TYPE_FILTERS = ["all", "coding", "reasoning", "comparison", "correction"];

export default function QueuePage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [filter, setFilter] = useState("all");
  const [claimingId, setClaimingId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const { data: tasks, isLoading } = useQuery({
    queryKey: ["queue", filter],
    queryFn: () => queueApi.list({ task_type: filter === "all" ? undefined : filter }),
    refetchInterval: 15_000,
  });

  const { mutate: claim } = useMutation({
    mutationFn: (taskId: string) => queueApi.claim(taskId),
    onMutate: (taskId) => { setClaimingId(taskId); setError(""); },
    onSuccess: (assignment) => {
      qc.invalidateQueries({ queryKey: ["queue"] });
      qc.invalidateQueries({ queryKey: ["my-tasks"] });
      router.push(`/annotator/workspace/${assignment.id}`);
    },
    onError: (err: Error) => {
      setError(err.message);
      setClaimingId(null);
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Task Queue</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Claim a task to start annotating. Tasks expire after 4 hours.
          </p>
        </div>
        {tasks && (
          <span className="text-muted-foreground text-sm">{tasks.length} available</span>
        )}
      </div>

      {/* Type filter */}
      <div className="flex gap-1 flex-wrap">
        {TYPE_FILTERS.map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={cn(
              "px-3 py-1 rounded-full text-sm font-medium transition-colors",
              filter === t
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-secondary-foreground hover:bg-secondary/70"
            )}
          >
            {t === "all" ? "All" : TASK_TYPE_LABELS[t]}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-48 w-full rounded-lg" />)}
        </div>
      ) : tasks?.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-muted-foreground">No tasks available right now.</p>
          <p className="text-sm text-muted-foreground mt-1">Check back later or try a different filter.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {tasks?.map((task) => (
            <Card key={task.id} className="flex flex-col">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-sm font-semibold leading-snug">{task.title}</CardTitle>
                  <span className={cn("shrink-0 text-xs rounded-full px-2 py-0.5 font-medium", TASK_TYPE_COLORS[task.task_type])}>
                    {TASK_TYPE_LABELS[task.task_type]}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="flex-1 pb-2">
                <p className="text-sm text-muted-foreground line-clamp-4">{task.prompt}</p>
              </CardContent>
              <CardFooter className="pt-0 justify-between items-center">
                <span className="text-xs text-muted-foreground">
                  Priority: {task.priority} · Needs {task.annotations_required}
                </span>
                <Button
                  size="sm"
                  onClick={() => claim(task.id)}
                  disabled={claimingId === task.id}
                >
                  {claimingId === task.id ? "Claiming…" : "Claim Task"}
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
