"use client";

import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tasksApi, annotationsApi, metricsApi, finetuneApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { cn, formatDateTime, TASK_TYPE_COLORS, TASK_TYPE_LABELS } from "@/lib/utils";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

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

function qualityLabel(type: string, value: Record<string, unknown>): "accepted" | "negative" | "pending" {
  if (type === "rating") {
    const score = value.score as number;
    if (score >= 4) return "accepted";
    if (score < 3) return "negative";
    return "pending";
  }
  if (type === "binary") return value.accept ? "accepted" : "negative";
  if (type === "comparison") return "accepted"; // both sides chosen; task-level evaluation decides
  return "pending";
}

const QUALITY_COLORS: Record<string, string> = {
  accepted: "bg-green-100 text-green-700",
  negative: "bg-red-100 text-red-700",
  pending: "bg-gray-100 text-gray-500",
};
const QUALITY_LABELS: Record<string, string> = {
  accepted: "Accepted",
  negative: "Negative",
  pending: "Pending",
};

const KAPPA_COLOR = (k: number) =>
  k >= 0.6 ? "text-green-600" : k >= 0.4 ? "text-amber-600" : "text-red-600";

function ScoreWidget({ defaultPrompt }: { defaultPrompt: string }) {
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [response, setResponse] = useState("");

  const { mutate: score, data: scoreResult, isPending: scoring, reset } = useMutation({
    mutationFn: () => finetuneApi.scoreResponse(prompt, response),
  });

  function scoreColor(s: number) {
    if (s >= 4) return "text-green-600";
    if (s >= 3) return "text-amber-600";
    return "text-red-600";
  }

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <p className="text-xs text-muted-foreground uppercase tracking-wide">Prompt</p>
        <Textarea
          value={prompt}
          onChange={(e) => { setPrompt(e.target.value); reset(); }}
          className="min-h-[60px] text-sm"
        />
      </div>
      <div className="space-y-1.5">
        <p className="text-xs text-muted-foreground uppercase tracking-wide">Response to score</p>
        <Textarea
          value={response}
          onChange={(e) => { setResponse(e.target.value); reset(); }}
          placeholder="Paste any response here to get its predicted quality score"
          className="min-h-[80px] font-mono text-sm"
        />
      </div>
      <div className="flex items-center gap-4">
        <Button
          size="sm"
          variant="outline"
          onClick={() => score()}
          disabled={scoring || !response.trim()}
        >
          {scoring ? "Scoring…" : "Score Response"}
        </Button>
        {scoreResult && (
          <div className="flex items-center gap-3 text-sm">
            <span className={`text-2xl font-bold ${scoreColor(scoreResult.score)}`}>
              {scoreResult.score.toFixed(1)}
            </span>
            <span className="text-muted-foreground">/ 5</span>
            <span className="text-xs text-muted-foreground">
              {(scoreResult.confidence * 100).toFixed(0)}% confidence
              {" · "}{scoreResult.source === "model" ? "fine-tuned model" : "DB similarity"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
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

  const { data: iaa } = useQuery({
    queryKey: ["iaa", id],
    queryFn: () => metricsApi.taskIAA(id),
    enabled: !!task && task.annotations_required > 1,
  });

  const { mutate: publish, isPending: publishing } = useMutation({
    mutationFn: () => tasksApi.publish(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks", id] }),
  });

  const currentRlaif = !!(task?.metadata as Record<string, unknown>)?.rlaif;

  const { mutate: updateRlaif, isPending: togglingRlaif } = useMutation({
    mutationFn: (enabled: boolean) =>
      tasksApi.update(id, {
        metadata: { ...(task?.metadata as object), rlaif: enabled },
      }),
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
          <>
            {task.task_type !== "correction" && (
              <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={currentRlaif}
                  onChange={(e) => updateRlaif(e.target.checked)}
                  disabled={togglingRlaif}
                  className="h-4 w-4 rounded border-border accent-primary"
                />
                RLAIF
              </label>
            )}
            <Button size="sm" onClick={() => publish()} disabled={publishing}>
              {publishing ? "Publishing…" : "Publish"}
            </Button>
          </>
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

      {task.annotations_required > 1 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Inter-Annotator Agreement</CardTitle>
          </CardHeader>
          <CardContent>
            {!iaa ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : iaa.annotation_count < 2 ? (
              <p className="text-sm text-muted-foreground">
                Not enough annotations yet ({iaa.annotation_count} / {iaa.annotations_required} collected).
              </p>
            ) : iaa.signal_type === "correction" ? (
              <p className="text-sm text-muted-foreground">IAA not applicable for correction tasks.</p>
            ) : iaa.agreement && iaa.signal_type === "rating" ? (
              <div className="flex items-center gap-6 text-sm">
                <span>Mean: <strong>{iaa.agreement.mean}/5</strong> ± {iaa.agreement.std}</span>
                <span>Within-1 agreement: <strong>{((iaa.agreement.within_1_rate ?? 0) * 100).toFixed(0)}%</strong></span>
              </div>
            ) : iaa.agreement?.kappa !== undefined ? (
              <div className="flex items-center gap-4 text-sm">
                <span>
                  κ = <strong className={KAPPA_COLOR(iaa.agreement.kappa)}>{iaa.agreement.kappa.toFixed(2)}</strong>
                </span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  iaa.agreement.kappa >= 0.6 ? "bg-green-100 text-green-700" :
                  iaa.agreement.kappa >= 0.4 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"
                }`}>
                  {iaa.agreement.interpretation}
                </span>
                <span className="text-muted-foreground">
                  Agreement: {((iaa.agreement.percent_agreement ?? 0) * 100).toFixed(0)}%
                </span>
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

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
              {annotations?.items?.map((a) => {
                const ql = qualityLabel(a.signal_type, a.signal_value);
                return (
                  <div key={a.id} className="border border-border rounded-lg p-3 flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">{formatDateTime(a.created_at)}</span>
                    <span className="flex items-center gap-2">
                      {a.source === "ai" && (
                        <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-purple-100 text-purple-700">
                          AI
                        </span>
                      )}
                      <Badge variant="outline">{SIGNAL_LABEL[a.signal_type]}</Badge>
                      <SignalSummary type={a.signal_type} value={a.signal_value} />
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${QUALITY_COLORS[ql]}`}>
                        {QUALITY_LABELS[ql]}
                      </span>
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Score a Response</CardTitle>
        </CardHeader>
        <CardContent>
          <ScoreWidget defaultPrompt={task.prompt} />
        </CardContent>
      </Card>
    </div>
  );
}
