"use client";

import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const LABELS = ["", "Very Poor", "Poor", "Fair", "Good", "Excellent"];

interface Props {
  score: number | null;
  justification: string;
  onChange: (score: number, justification: string) => void;
}

export function RatingSignal({ score, justification, onChange }: Props) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Quality Rating <span className="text-destructive">*</span></Label>
        <div className="flex gap-2">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => onChange(n, justification)}
              className={cn(
                "flex-1 py-3 rounded-lg border-2 text-sm font-semibold transition-all",
                score === n
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border hover:border-primary/50 hover:bg-accent"
              )}
            >
              {n}
            </button>
          ))}
        </div>
        {score !== null && (
          <p className="text-sm text-center text-muted-foreground font-medium">
            {LABELS[score]}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="justification">
          Justification <span className="text-destructive">*</span>
          <span className="text-muted-foreground font-normal text-xs ml-1">(min 10 chars)</span>
        </Label>
        <Textarea
          id="justification"
          value={justification}
          onChange={(e) => onChange(score ?? 0, e.target.value)}
          placeholder="Explain your rating…"
          className="min-h-[80px]"
        />
      </div>
    </div>
  );
}

export function ratingValid(score: number | null, justification: string): boolean {
  return score !== null && score >= 1 && score <= 5 && justification.trim().length >= 10;
}
