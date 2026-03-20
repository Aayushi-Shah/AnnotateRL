"use client";

import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tasksApi, annotationsApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatDateTime, TASK_TYPE_COLORS, TASK_TYPE_LABELS } from "@/lib/utils";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

const SIGNAL_LABEL: Record<string, string> = {
  rating: "Rating",
  comparison: "Comparison",
  correction: "Correction",
  binary: "Binary",
};

function SignalSummary({ type, value }: { type: string; value: Record<string, unknown> }) {
  if (type === "rating") return <span className="font-semibold">{value.score as number}/5</span>;
  if (type === "comparison") return <span>{value.chosen as string}</span>;
  if (type === "binary") return <span>{value.accept ? "✓ Accept" : "✗ Reject"}</span>;
  return <span>Correction</span>;
}

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data: task, isLoading: taskLoading } = useQuery({
    queryKey: ["tasks", id],
    queryFn: () => tasksApi.get(id),
  });

  const { data: annotations, isLoading: annotationsLoading } = useQuery({
    queryKey: ["annotations", id],
    queryFn: () => annotationsApi.list({ task_id: id, size: 50 } as Parameters<typeof annotationsApi.list>[0]),
  });

  const { mutate: publish, isPending: publishing } = useMutation({
    mutationFn: () => tasksApi.publish(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks", id] }),
  });

  if (taskLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (!task) return <p className="text-muted-foreground">Task not found.</p>;

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/researcher/tasks"><ArrowLeft className="h-4 w-4" /></Link>
        </Button>
        <h1 className="text-xl font-bold flex-1 truncate">{task.title}</h1>
        {task.status === "draft" && (
          <Button size="sm" onClick={() => publish()} disabled={publishing}>
            {publishing ? "Publishing…" : "Publish"}
          </Button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-muted-foreground uppercase tracking-wide">Type</CardTitle>
          </CardHeader>
          <CardContent>
            <span className={cn("text-xs rounded-full px-2 py-1 font-medium", TASK_TYPE_COLORS[task.task_type])}>
              {TASK_TYPE_LABELS[task.task_type]}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-muted-foreground uppercase tracking-wide">Annotations</CardTitle>
          </CardHeader>
          <CardContent>
            <span className="text-2xl font-bold">{task.annotation_count}</span>
            <span className="text-muted-foreground text-sm"> / {task.annotations_required}</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-muted-foreground uppercase tracking-wide">Status</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant={task.status === "completed" ? "default" : "secondary"}>{task.status}</Badge>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Prompt</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <pre className="text-sm whitespace-pre-wrap font-mono bg-muted/40 rounded-md p-4">{task.prompt}</pre>
          {(task.metadata as Record<string, string>)?.ai_generation_status === "pending" && (
            <p className="text-xs text-amber-600">⏳ AI agent is generating a response for annotators…</p>
          )}
          {(task.metadata as Record<string, string>)?.ai_generation_status === "failed" && (
            <p className="text-xs text-destructive">⚠ AI response generation failed. Try republishing the task.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Annotations</CardTitle></CardHeader>
        <CardContent>
          {annotationsLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
            </div>
          ) : annotations?.items?.length === 0 ? (
            <p className="text-muted-foreground text-sm py-4">No annotations yet.</p>
          ) : (
            <div className="space-y-3">
              {annotations?.items?.map((a) => (
                <div key={a.id} className="border border-border rounded-lg p-3 flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">{formatDateTime(a.created_at)}</span>
                  <span className="flex items-center gap-2">
                    <Badge variant="outline">{SIGNAL_LABEL[a.signal_type]}</Badge>
                    <SignalSummary type={a.signal_type} value={a.signal_value} />
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
