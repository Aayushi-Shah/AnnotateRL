"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { finetuneApi } from "@/lib/api";
import type { FineTuningJob, ModelVersion } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime } from "@/lib/utils";
import { Play, Zap, CheckCircle2 } from "lucide-react";

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

function ActiveModelCard({ models }: { models: ModelVersion[] }) {
  const active = models.find((m) => m.is_active);

  if (!active) {
    return (
      <Card>
        <CardContent className="p-4">
          <p className="text-sm text-muted-foreground">
            No active model version. AI generation uses the default base model.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-green-200 bg-green-50/50">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-2">
          <Zap className="h-4 w-4 text-green-600" />
          <span className="font-medium text-green-800">Active Model</span>
        </div>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">Version</p>
            <p className="font-mono font-medium">{active.version_tag}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Base Model</p>
            <p className="font-mono">{active.base_model}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Fine-tuned ID</p>
            <p className="font-mono text-xs truncate">{active.finetuned_model_id ?? "—"}</p>
          </div>
        </div>
      </CardContent>
    </Card>
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
      qc.invalidateQueries({ queryKey: ["finetune-models"] });
    },
  });

  const isLoading = jobsLoading || modelsLoading;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Fine-tuning</h1>
        <Button onClick={() => triggerJob()} disabled={triggering}>
          <Play className="h-4 w-4 mr-1" />
          {triggering ? "Triggering…" : "Trigger Fine-tune"}
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-20 w-full" />)}
        </div>
      ) : (
        <>
          {/* Active model */}
          {models && <ActiveModelCard models={models} />}

          {/* Jobs */}
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
                  {jobs.map((job: FineTuningJob) => (
                    <div key={job.id} className="flex items-center justify-between border border-border rounded-lg p-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <JobStatusBadge status={job.status} />
                          <span className="text-xs font-mono text-muted-foreground">{job.id.slice(0, 8)}</span>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                          <span>Rows: {job.training_data_rows ?? "—"}</span>
                          <span>Provider: {String(job.config?.provider ?? "—")}</span>
                          <span>{formatDateTime(job.created_at)}</span>
                        </div>
                        {job.error_message && (
                          <p className="text-xs text-red-600 mt-1">{job.error_message}</p>
                        )}
                      </div>
                      {job.external_job_id && (
                        <span className="text-xs font-mono text-muted-foreground truncate max-w-[180px]">
                          {job.external_job_id}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Model versions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Model Versions</CardTitle>
            </CardHeader>
            <CardContent>
              {!models || models.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  No model versions yet. They are created automatically when fine-tuning completes.
                </p>
              ) : (
                <div className="space-y-2">
                  {models.map((v: ModelVersion) => (
                    <div key={v.id} className="flex items-center justify-between border border-border rounded-lg p-3">
                      <div className="flex items-center gap-3">
                        <span className="font-mono font-medium text-sm">{v.version_tag}</span>
                        {v.is_active && (
                          <Badge variant="outline" className="border-green-300 text-green-700 text-xs">
                            <CheckCircle2 className="h-3 w-3 mr-1" /> Active
                          </Badge>
                        )}
                        <span className="text-xs text-muted-foreground">{v.base_model}</span>
                        <span className="text-xs font-mono text-muted-foreground truncate max-w-[160px]">
                          {v.finetuned_model_id ?? "—"}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">{formatDateTime(v.created_at)}</span>
                        {!v.is_active && (
                          <Button size="sm" variant="outline" onClick={() => activateModel(v.id)}>
                            Activate
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
