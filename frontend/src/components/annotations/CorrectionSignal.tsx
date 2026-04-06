"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

interface Props {
  original: string;
  critique?: string;
  critiqueAccepted: boolean | null;
  onCritiqueAcceptedChange: (v: boolean) => void;
  genPending?: boolean;
}

export function CorrectionSignal({
  original,
  critique,
  critiqueAccepted,
  onCritiqueAcceptedChange,
  genPending,
}: Props) {
  if (genPending || !critique) {
    return (
      <div className="flex items-center gap-2 p-4 rounded-lg border border-border bg-muted/20 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin shrink-0" />
        AI is evaluating the response for errors. Refresh in a moment.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        {/* Panel 1: Response under review */}
        <div className="space-y-1.5">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Response
          </p>
          <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm whitespace-pre-wrap overflow-y-auto max-h-48 font-mono leading-relaxed">
            {original || <span className="italic text-muted-foreground">No response provided</span>}
          </div>
        </div>

        {/* Panel 2: AI critique */}
        <div className="space-y-1.5">
          <p className="text-xs font-medium uppercase tracking-wide text-amber-600">
            AI Critique
          </p>
          <div className="rounded-lg border border-amber-200 bg-amber-50/60 dark:bg-amber-950/20 dark:border-amber-800 p-3 text-sm whitespace-pre-wrap overflow-y-auto max-h-48 leading-relaxed">
            {critique}
          </div>
        </div>
      </div>

      {/* Accept / Reject buttons */}
      <div className="space-y-2">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          Is this critique correct?
        </p>
        <div className="flex gap-3">
          <Button
            type="button"
            variant={critiqueAccepted === true ? "default" : "outline"}
            className={cn(
              "flex-1",
              critiqueAccepted === true && "bg-green-600 hover:bg-green-700 border-green-600"
            )}
            onClick={() => onCritiqueAcceptedChange(true)}
          >
            Accept Critique
          </Button>
          <Button
            type="button"
            variant={critiqueAccepted === false ? "destructive" : "outline"}
            className="flex-1"
            onClick={() => onCritiqueAcceptedChange(false)}
          >
            Reject Critique
          </Button>
        </div>
        {critiqueAccepted === false && (
          <p className="text-xs text-muted-foreground">
            The AI will generate a new response and critique for another annotator to review.
          </p>
        )}
      </div>
    </div>
  );
}

export function correctionValid(critiqueAccepted: boolean | null): boolean {
  return critiqueAccepted !== null;
}
