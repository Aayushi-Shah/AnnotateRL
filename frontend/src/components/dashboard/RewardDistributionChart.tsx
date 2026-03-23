"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { RewardDistribution } from "@/lib/types";

interface Props {
  data: RewardDistribution | undefined;
  isLoading: boolean;
}

const SIGNAL_LABELS: Record<string, string> = {
  rating: "Rating (1–5)",
  binary: "Binary (Accept/Reject)",
  comparison: "Comparison (A vs B)",
};

const KEY_ORDER: Record<string, string[]> = {
  rating: ["1", "2", "3", "4", "5"],
  binary: ["accept", "reject"],
  comparison: ["A", "B"],
};

function SignalChart({ signalType, counts }: { signalType: string; counts: Record<string, number> }) {
  const order = KEY_ORDER[signalType];
  const data = (order ?? Object.keys(counts).sort()).map((key) => ({
    label: key,
    count: counts[key] ?? 0,
  }));

  return (
    <div>
      <p className="text-xs text-muted-foreground mb-2 font-medium">
        {SIGNAL_LABELS[signalType] ?? signalType}
      </p>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} barSize={28}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 12 }} allowDecimals={false} axisLine={false} tickLine={false} width={28} />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "6px",
              fontSize: "12px",
            }}
            cursor={{ fill: "hsl(var(--muted))" }}
          />
          <Bar dataKey="count" name="Count" fill="hsl(var(--primary))" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RewardDistributionChart({ data, isLoading }: Props) {
  const entries = data ? Object.entries(data.distribution).filter(([, counts]) => Object.keys(counts).length > 0) : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Reward Signal Distribution</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-44 w-full" />)}
          </div>
        ) : entries.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6 text-center">
            No signal data yet. Complete some annotations to see the distribution.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {entries.map(([signalType, counts]) => (
              <SignalChart key={signalType} signalType={signalType} counts={counts} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
