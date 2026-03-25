"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { IAASummary } from "@/lib/types";

interface Props {
  data: IAASummary | undefined;
  isLoading: boolean;
}

function kappaColor(k: number) {
  if (k >= 0.6) return "text-green-600";
  if (k >= 0.4) return "text-amber-600";
  return "text-red-600";
}

function kappaLabel(k: number) {
  if (k >= 0.8) return "almost perfect";
  if (k >= 0.6) return "substantial";
  if (k >= 0.4) return "moderate";
  if (k >= 0.2) return "fair";
  return "poor";
}

export function IAACard({ data, isLoading }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Inter-Annotator Agreement</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : !data || data.tasks_evaluated === 0 ? (
          <p className="text-sm text-muted-foreground py-2">
            No multi-annotator tasks completed yet. IAA is computed for tasks with multiple raters.
          </p>
        ) : (
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground text-xs mb-1">Tasks evaluated</p>
              <p className="text-2xl font-bold">{data.tasks_evaluated}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs mb-1">Avg κ (Cohen&apos;s Kappa)</p>
              {data.avg_kappa !== null ? (
                <p className={`text-2xl font-bold ${kappaColor(data.avg_kappa)}`}>
                  {data.avg_kappa.toFixed(2)}
                  <span className="text-xs font-normal ml-1 text-muted-foreground">
                    {kappaLabel(data.avg_kappa)}
                  </span>
                </p>
              ) : (
                <p className="text-muted-foreground">—</p>
              )}
            </div>
            <div>
              <p className="text-muted-foreground text-xs mb-1">High agreement (κ ≥ 0.6)</p>
              {data.avg_kappa !== null ? (
                <p className="text-2xl font-bold text-green-600">{data.high_agreement_count}</p>
              ) : (
                <p className="text-xs text-muted-foreground pt-1">κ applies to<br />binary/comparison</p>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
