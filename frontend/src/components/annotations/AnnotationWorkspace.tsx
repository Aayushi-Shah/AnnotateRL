"use client";

import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { annotationsApi, queueApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { cn, isExpired, timeUntil, TASK_TYPE_COLORS, TASK_TYPE_LABELS } from "@/lib/utils";
import { RatingSignal, ratingValid } from "./RatingSignal";
import { ComparisonSignal, comparisonValid } from "./ComparisonSignal";
import { BinarySignal, binaryValid } from "./BinarySignal";
import { CorrectionSignal, correctionValid } from "./CorrectionSignal";
import { AlertTriangle, Clock, Loader2 } from "lucide-react";
import type { Task, TaskAssignment } from "@/lib/types";

interface Props {
  task: Task;
  assignment: TaskAssignment;
  onComplete: () => void;
  onAbandon: () => void;
}

// Map task_type → default signal_type
const DEFAULT_SIGNAL: Record<string, string> = {
  coding: "rating",
  reasoning: "rating",
  comparison: "comparison",
  correction: "correction",
};

export function AnnotationWorkspace({ task, assignment, onComplete, onAbandon }: Props) {
  const qc = useQueryClient();
  const modelResponse = (task.metadata as Record<string, string>)?.model_response ?? "";
  const [response, setResponse] = useState(
    // Correction: pre-fill with AI response from context (annotator edits it)
    // Rating tasks: pre-fill with model_response (submitted as-is; annotator only rates)
    task.task_type === "correction" ? (task.context ?? "") : modelResponse
  );
  const [tick, setTick] = useState(0);
  const [confirmAbandon, setConfirmAbandon] = useState(false);
  const [submitError, setSubmitError] = useState("");

  // Rating state
  const [ratingScore, setRatingScore] = useState<number | null>(null);
  const [ratingJustification, setRatingJustification] = useState("");

  // Comparison state
  const [chosen, setChosen] = useState<"A" | "B" | null>(null);
  const [rationale, setRationale] = useState("");

  // Binary state
  const [accept, setAccept] = useState<boolean | null>(null);
  const [binaryJustification, setBinaryJustification] = useState("");

  // Correction state — response IS the edited text
  // (response is pre-filled above)

  // Countdown timer
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 10_000);
    return () => clearInterval(id);
  }, []);

  const signalType = DEFAULT_SIGNAL[task.task_type] ?? "rating";
  const expired = isExpired(assignment.expires_at);
  const timeLeft = timeUntil(assignment.expires_at);

  const metadata = task.metadata as Record<string, string>;
  const genPending = metadata?.ai_generation_status === "pending";

  function buildSignalValue(): Record<string, unknown> {
    if (signalType === "rating") return { score: ratingScore, justification: ratingJustification };
    if (signalType === "comparison") return { chosen, rationale };
    if (signalType === "binary") return { accept, justification: binaryJustification };
    if (signalType === "correction") return { edited: response };
    return {};
  }

  function isValid(): boolean {
    // rating: response comes from model_response (always set); only validate the signal
    if (signalType === "rating") return ratingValid(ratingScore, ratingJustification);
    if (signalType === "comparison") return comparisonValid(chosen);
    if (signalType === "binary") return binaryValid(accept);
    if (signalType === "correction") return correctionValid(task.context ?? "", response);
    return false;
  }

  const { mutate: submit, isPending: submitting } = useMutation({
    mutationFn: () =>
      annotationsApi.submit({
        assignment_id: assignment.id,
        response,
        signal_type: signalType,
        signal_value: buildSignalValue(),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-tasks"] });
      qc.invalidateQueries({ queryKey: ["queue"] });
      onComplete();
    },
    onError: (err: Error) => setSubmitError(err.message),
  });

  const { mutate: abandon, isPending: abandoning } = useMutation({
    mutationFn: () => queueApi.abandon(assignment.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-tasks"] });
      qc.invalidateQueries({ queryKey: ["queue"] });
      onAbandon();
    },
  });

  return (
    <div className="flex gap-6 h-full min-h-0">
      {/* Left: Task Info */}
      <div className="w-2/5 flex flex-col gap-4 overflow-y-auto">
        <div className="flex items-center justify-between">
          <span className={cn("text-xs rounded-full px-2.5 py-1 font-medium", TASK_TYPE_COLORS[task.task_type])}>
            {TASK_TYPE_LABELS[task.task_type]}
          </span>
          <span
            className={cn(
              "flex items-center gap-1 text-xs font-medium",
              expired ? "text-destructive" : timeLeft.includes("m") && !timeLeft.includes("h") ? "text-amber-600" : "text-muted-foreground"
            )}
          >
            <Clock className="h-3.5 w-3.5" />
            {expired ? "Expired" : timeLeft + " remaining"}
          </span>
        </div>

        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-2">Task</p>
          <p className="font-semibold text-sm leading-relaxed">{task.title}</p>
        </div>

        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-2">Prompt</p>
          <pre className="text-sm whitespace-pre-wrap font-mono bg-muted/40 rounded-lg p-3 leading-relaxed">
            {task.prompt}
          </pre>
        </div>

        {task.context && signalType !== "correction" && (
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground mb-2">Context</p>
            <pre className="text-sm whitespace-pre-wrap font-mono bg-muted/40 rounded-lg p-3 leading-relaxed">
              {task.context}
            </pre>
          </div>
        )}
      </div>

      {/* Right: Annotation Form */}
      <div className="flex-1 flex flex-col gap-4 overflow-y-auto">
        {expired && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            This assignment has expired. You can no longer submit. Abandon to return it to the queue.
          </div>
        )}

        {/* AI Response — shown read-only for rating tasks */}
        {signalType === "rating" && (
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">AI Response</p>
            {genPending ? (
              <div className="flex items-center gap-2 p-4 rounded-lg border border-border bg-muted/20 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin shrink-0" />
                Claude is generating the AI response. Refresh in a moment.
              </div>
            ) : (
              <pre
                className={cn(
                  "text-sm whitespace-pre-wrap rounded-lg border border-border bg-muted/30 p-3 leading-relaxed max-h-64 overflow-y-auto",
                  task.task_type === "coding" && "font-mono"
                )}
              >
                {modelResponse || <span className="text-muted-foreground italic">No model response provided.</span>}
              </pre>
            )}
          </div>
        )}

        {/* Signal */}
        <div className="border border-border rounded-lg p-4 max-h-[32rem] overflow-y-auto">
          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-4">Evaluation</p>

          {signalType === "rating" && (
            <RatingSignal
              score={ratingScore}
              justification={ratingJustification}
              onChange={(score, justification) => { setRatingScore(score); setRatingJustification(justification); }}
            />
          )}
          {signalType === "comparison" && (
            <ComparisonSignal
              responseA={metadata.response_a ?? ""}
              responseB={metadata.response_b ?? ""}
              chosen={chosen}
              rationale={rationale}
              onChange={(c, r) => { setChosen(c); setRationale(r); }}
            />
          )}
          {signalType === "binary" && (
            <BinarySignal
              accept={accept}
              justification={binaryJustification}
              onChange={(a, j) => { setAccept(a); setBinaryJustification(j); }}
            />
          )}
          {signalType === "correction" && (
            <CorrectionSignal
              original={task.context ?? ""}
              edited={response}
              onChange={setResponse}
            />
          )}
        </div>

        {submitError && (
          <p className="text-sm text-destructive">{submitError}</p>
        )}

        <div className="flex items-center justify-between pt-2">
          {confirmAbandon ? (
            <div className="flex items-center gap-3">
              <p className="text-sm text-muted-foreground">Abandon this task?</p>
              <Button variant="destructive" size="sm" onClick={() => abandon()} disabled={abandoning}>
                Yes, abandon
              </Button>
              <Button variant="outline" size="sm" onClick={() => setConfirmAbandon(false)}>
                Cancel
              </Button>
            </div>
          ) : (
            <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={() => setConfirmAbandon(true)}>
              Abandon task
            </Button>
          )}

          <Button
            onClick={() => submit()}
            disabled={!isValid() || expired || submitting || (signalType === "rating" && genPending)}
            size="lg"
          >
            {submitting ? "Submitting…" : "Submit Annotation"}
          </Button>
        </div>
      </div>
    </div>
  );
}
