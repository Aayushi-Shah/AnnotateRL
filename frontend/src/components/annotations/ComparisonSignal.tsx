"use client";

import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface Props {
  responseA: string;
  responseB: string;
  chosen: "A" | "B" | null;
  rationale: string;
  onChange: (chosen: "A" | "B" | null, rationale: string) => void;
}

export function ComparisonSignal({ responseA, responseB, chosen, rationale, onChange }: Props) {
  return (
    <div className="space-y-4">
      <Label>Select the better response <span className="text-destructive">*</span></Label>

      <div className="grid grid-cols-2 gap-4">
        {(["A", "B"] as const).map((side) => {
          const text = side === "A" ? responseA : responseB;
          const selected = chosen === side;
          return (
            <button
              key={side}
              type="button"
              onClick={() => onChange(side, rationale)}
              className={cn(
                "text-left rounded-lg border-2 p-4 transition-all space-y-3",
                selected
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/40 hover:bg-accent/50"
              )}
            >
              <div className="flex items-center justify-between">
                <span className={cn("text-xs font-bold uppercase tracking-wide", selected ? "text-primary" : "text-muted-foreground")}>
                  Response {side}
                </span>
                {selected && (
                  <span className="text-xs bg-primary text-primary-foreground rounded-full px-2 py-0.5">
                    Selected
                  </span>
                )}
              </div>
              <p className="text-sm whitespace-pre-wrap line-clamp-6">{text || <span className="italic text-muted-foreground">No response provided</span>}</p>
            </button>
          );
        })}
      </div>

      <div className="space-y-2">
        <Label htmlFor="rationale">
          Rationale <span className="text-muted-foreground font-normal text-xs">(optional)</span>
        </Label>
        <Textarea
          id="rationale"
          value={rationale}
          onChange={(e) => onChange(chosen, e.target.value)}
          placeholder="Why is this response better?"
          className="min-h-[70px]"
        />
      </div>
    </div>
  );
}

export function comparisonValid(chosen: "A" | "B" | null): boolean {
  return chosen !== null;
}
