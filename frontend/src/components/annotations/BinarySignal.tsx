"use client";

import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { Check, X } from "lucide-react";

interface Props {
  accept: boolean | null;
  justification: string;
  onChange: (accept: boolean | null, justification: string) => void;
}

export function BinarySignal({ accept, justification, onChange }: Props) {
  return (
    <div className="space-y-4">
      <Label>Is this response acceptable? <span className="text-destructive">*</span></Label>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => onChange(false, justification)}
          className={cn(
            "flex-1 py-4 rounded-lg border-2 font-semibold text-sm flex items-center justify-center gap-2 transition-all",
            accept === false
              ? "border-destructive bg-destructive text-destructive-foreground"
              : "border-border hover:border-destructive/50 hover:bg-red-50"
          )}
        >
          <X className="h-4 w-4" />
          Reject
        </button>
        <button
          type="button"
          onClick={() => onChange(true, justification)}
          className={cn(
            "flex-1 py-4 rounded-lg border-2 font-semibold text-sm flex items-center justify-center gap-2 transition-all",
            accept === true
              ? "border-green-600 bg-green-600 text-white"
              : "border-border hover:border-green-500/50 hover:bg-green-50"
          )}
        >
          <Check className="h-4 w-4" />
          Accept
        </button>
      </div>

      <div className="space-y-2">
        <Label htmlFor="binary-justification">
          Justification <span className="text-muted-foreground font-normal text-xs">(optional)</span>
        </Label>
        <Textarea
          id="binary-justification"
          value={justification}
          onChange={(e) => onChange(accept, e.target.value)}
          placeholder="Why accept or reject?"
          className="min-h-[70px]"
        />
      </div>
    </div>
  );
}

export function binaryValid(accept: boolean | null): boolean {
  return accept !== null;
}
