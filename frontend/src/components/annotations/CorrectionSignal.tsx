"use client";

import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

interface Props {
  original: string;
  edited: string;
  onChange: (edited: string) => void;
}

export function CorrectionSignal({ original, edited, onChange }: Props) {
  const isChanged = edited.trim() !== original.trim();

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label htmlFor="correction">
          Edit the response below <span className="text-destructive">*</span>
        </Label>
        {isChanged ? (
          <span className="text-xs text-green-600 font-medium">Modified</span>
        ) : (
          <span className="text-xs text-amber-600 font-medium">Unchanged — make at least one correction</span>
        )}
      </div>
      <Textarea
        id="correction"
        value={edited}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-[180px] font-mono text-sm"
      />
      <p className="text-xs text-muted-foreground">
        Fix factual errors, improve clarity, or correct the reasoning. Your edits are the training signal.
      </p>
    </div>
  );
}

export function correctionValid(original: string, edited: string): boolean {
  return edited.trim().length > 0 && edited.trim() !== original.trim();
}
