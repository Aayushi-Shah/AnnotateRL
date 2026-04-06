"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { finetuneApi } from "@/lib/api";
import type { FineTuningJob, ModelVersion, TrainingStats, EvalResult } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime } from "@/lib/utils";
import { Play, Zap, CheckCircle2, Clock } from "lucide-react";

function JobStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "bg-gray-100 text-gray-700",
    preparing_data: "bg-blue-100 text-blue-700",
    training: "bg-amber-100 text-amber-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
  };
  const labels: Record<string, string> = {
    pending: "Pending",
    preparing_data: "Preparing Data",
    training: "Training",
    completed: "Completed",
    failed: "Failed",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors[status] ?? ""}`}>
      {labels[status] ?? status}
    </span>
  );
}

function joinParts(parts: string[]): string {
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return `${parts[0]} and ${parts[1]}`;
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

function TrainingDescription({ stats }: { stats: TrainingStats }) {
  const parts: string[] = [];
  if (stats.accepted > 0)
    parts.push(`${stats.accepted} approved ${stats.accepted === 1 ? "response" : "responses"}`);
  if (stats.negative_examples > 0)
    parts.push(`${stats.negative_examples} rejected ${stats.negative_examples === 1 ? "response" : "responses"}`);
  if (stats.dpo_pairs > 0)
    parts.push(`${stats.dpo_pairs} preference ${stats.dpo_pairs === 1 ? "pair" : "pairs"}`);

  const skipped = stats.skipped_low_iaa + stats.skipped_ambiguous + stats.skipped_correction;
  const skippedTooltip = `Ambiguous quality: ${stats.skipped_ambiguous}, Low annotator agreement: ${stats.skipped_low_iaa}, Correction tasks: ${stats.skipped_correction}`;

  return (
    <div className="text-xs mt-1.5 space-y-0.5">
      <p className="text-foreground">
        {parts.length > 0 ? `Trained on ${joinParts(parts)}.` : "No usable training examples found."}
      </p>
      {skipped > 0 && (
        <p className="text-muted-foreground cursor-help" title={skippedTooltip}>
          {skipped} {skipped === 1 ? "example" : "examples"} excluded — hover for details
        </p>
      )}
    </div>
  );
}

function EvalBadge({ eval: ev }: { eval: EvalResult | null }) {
  if (!ev) return null;
  if (ev.status === "pending" || ev.status === "running") {
    return (
      <span className="text-xs text-muted-foreground animate-pulse">Evaluating…</span>
    );
  }
  if (ev.status === "failed") {
    return <span className="text-xs text-red-500" title={ev.error_message ?? ""}>Eval failed</span>;
  }
  if (ev.win_rate !== null) {
    const pct = Math.round(ev.win_rate * 100);
    return (
      <span className={`text-xs font-medium ${pct >= 50 ? "text-green-600" : "text-amber-600"}`}
        title="Win rate vs current active model">
        {pct}% win rate
      </span>
    );
  }
  return null;
}

function ModelVersionSection({
  version,
  onActivate,
  onRunEval,
  runningEval,
}: {
  version: ModelVersion | undefined;
  onActivate: (id: string) => void;
  onRunEval: (id: string) => void;
  runningEval: boolean;
}) {
  return (
    <div className="mt-2 pt-2 border-t border-border/60 flex items-center justify-between min-h-[28px]">
      {version ? (
        <>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-medium">{version.version_tag}</span>
            {version.is_active ? (
              <Badge variant="outline" className="border-green-300 text-green-700 text-xs">
                <CheckCircle2 className="h-3 w-3 mr-1" /> Active
              </Badge>
            ) : (
              <Badge variant="outline" className="border-amber-300 text-amber-700 text-xs">
                <Clock className="h-3 w-3 mr-1" /> Candidate
              </Badge>
            )}
            <span className="text-xs text-muted-foreground">{version.base_model}</span>
            <span className="text-xs font-mono text-muted-foreground truncate max-w-[160px]">
              {version.finetuned_model_id ?? "—"}
            </span>
            <EvalBadge eval={version.latest_eval} />
          </div>
          {!version.is_active && (
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => onRunEval(version.id)}
                disabled={runningEval || version.latest_eval?.status === "running" || version.latest_eval?.status === "pending"}
              >
                {version.latest_eval?.status === "running" || version.latest_eval?.status === "pending"
                  ? "Evaluating…"
                  : "Run Eval"}
              </Button>
              <Button size="sm" variant="outline" onClick={() => onActivate(version.id)}>
                Activate
              </Button>
            </div>
          )}
        </>
      ) : (
        <p className="text-xs text-muted-foreground italic">
          Model version will appear here when training completes.
        </p>
      )}
    </div>
  );
}

export default function FinetunePage() {
  const qc = useQueryClient();

  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ["finetune-jobs"],
    queryFn: finetuneApi.listJobs,
    refetchInterval: (q) =>
      q.state.data?.some((j: FineTuningJob) =>
        ["pending", "preparing_data", "training"].includes(j.status)
      )
        ? 3000
        : false,
  });

  const { data: models, isLoading: modelsLoading } = useQuery({
    queryKey: ["finetune-models"],
    queryFn: finetuneApi.listModels,
    refetchInterval: (q) =>
      q.state.data?.some((m: ModelVersion) =>
        ["pending", "running"].includes(m.latest_eval?.status ?? "")
      )
        ? 3000
        : false,
  });

  const { mutate: triggerJob, isPending: triggering } = useMutation({
    mutationFn: () => finetuneApi.triggerManual(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finetune-jobs"] });
      qc.invalidateQueries({ queryKey: ["finetune-models"] });
    },
  });

  const { mutate: activateModel } = useMutation({
    mutationFn: (id: string) => finetuneApi.activateModel(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finetune-jobs"] });
      qc.invalidateQueries({ queryKey: ["finetune-models"] });
    },
  });

  const { mutate: runEval, isPending: runningEval } = useMutation({
    mutationFn: (id: string) => finetuneApi.runEval(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finetune-models"] }),
  });

  const isLoading = jobsLoading || modelsLoading;
  const activeModel = models?.find((m: ModelVersion) => m.is_active);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Fine-tuning</h1>
          {!isLoading && (
            activeModel ? (
              <p className="text-sm text-muted-foreground mt-0.5">
                <Zap className="h-3.5 w-3.5 inline mr-1 text-green-600" />
                Active model: <span className="font-mono font-medium">{activeModel.version_tag}</span>
              </p>
            ) : (
              <p className="text-sm text-muted-foreground mt-0.5">
                No active model — using base model for AI generation.
              </p>
            )
          )}
        </div>
        <Button onClick={() => triggerJob()} disabled={triggering}>
          <Play className="h-4 w-4 mr-1" />
          {triggering ? "Triggering…" : "Trigger Fine-tune"}
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Fine-tuning Jobs</CardTitle>
          </CardHeader>
          <CardContent>
            {!jobs || jobs.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No fine-tuning jobs yet. Complete some annotations to trigger the RLHF loop, or trigger one manually.
              </p>
            ) : (
              <div className="space-y-3">
                {jobs.map((job: FineTuningJob) => {
                  const modelVersion = models?.find((m: ModelVersion) => m.training_job_id === job.id);
                  return (
                    <div key={job.id} className="border border-border rounded-lg p-3">
                      <div className="flex items-center justify-between mb-1">
                        <JobStatusBadge status={job.status} />
                        <span className="text-xs text-muted-foreground">{formatDateTime(job.created_at)}</span>
                      </div>
                      {job.training_stats ? (
                        <TrainingDescription stats={job.training_stats} />
                      ) : (
                        <p className="text-xs text-muted-foreground mt-1.5">
                          {job.status === "preparing_data" ? "Preparing training data…" :
                           job.status === "training" ? "Training in progress…" :
                           job.status === "pending" ? "Waiting to start…" : ""}
                        </p>
                      )}
                      {job.error_message && (
                        <p className="text-xs text-red-600 mt-1">{job.error_message}</p>
                      )}
                      <ModelVersionSection
                        version={modelVersion}
                        onActivate={activateModel}
                        onRunEval={runEval}
                        runningEval={runningEval}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
