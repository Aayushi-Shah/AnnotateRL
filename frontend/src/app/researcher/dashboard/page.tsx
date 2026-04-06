"use client";

import { useQuery } from "@tanstack/react-query";
import { metricsApi } from "@/lib/api";
import { OverviewCards } from "@/components/dashboard/OverviewCards";
import { ThroughputChart } from "@/components/dashboard/ThroughputChart";
import { RewardDistributionChart } from "@/components/dashboard/RewardDistributionChart";
import { IAACard } from "@/components/dashboard/IAACard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardPage() {
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ["metrics", "overview"],
    queryFn: metricsApi.overview,
    refetchInterval: 30_000,
  });

  const { data: throughput, isLoading: throughputLoading } = useQuery({
    queryKey: ["metrics", "throughput", 30],
    queryFn: () => metricsApi.throughput(30),
  });

  const { data: iaaSummary, isLoading: iaaLoading } = useQuery({
    queryKey: ["metrics", "iaa-summary"],
    queryFn: metricsApi.iaaSummary,
    refetchInterval: 60_000,
  });

  const { data: rewardDist, isLoading: rewardLoading } = useQuery({
    queryKey: ["metrics", "reward-distribution"],
    queryFn: metricsApi.rewardDistribution,
  });

  const { data: annotatorData, isLoading: annotatorsLoading } = useQuery({
    queryKey: ["metrics", "annotators"],
    queryFn: metricsApi.annotators,
    refetchInterval: 60_000,
  });

  const { data: calibrationData } = useQuery({
    queryKey: ["metrics", "annotators-calibration"],
    queryFn: metricsApi.annotatorsCalibration,
    refetchInterval: 60_000,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <OverviewCards data={overview} isLoading={overviewLoading} />

      <ThroughputChart data={throughput?.data} isLoading={throughputLoading} days={30} />

      <RewardDistributionChart data={rewardDist} isLoading={rewardLoading} />

      <IAACard data={iaaSummary} isLoading={iaaLoading} />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Annotator Activity</CardTitle>
        </CardHeader>
        <CardContent>
          {annotatorsLoading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="text-left py-2 font-medium">Annotator</th>
                  <th className="text-right py-2 font-medium">Total</th>
                  <th className="text-right py-2 font-medium">Active</th>
                  <th className="text-right py-2 font-medium" title="% agreeing with majority vote on shared tasks">Agreement</th>
                  <th className="text-right py-2 font-medium" title="Score tendency vs task average (rating tasks). + = lenient, − = harsh">Bias</th>
                  <th className="text-right py-2 font-medium">Speed</th>
                </tr>
              </thead>
              <tbody>
                {annotatorData?.annotators?.map((a) => {
                  const cal = calibrationData?.calibration?.[a.id];
                  return (
                    <tr key={a.id} className="border-b border-border last:border-0">
                      <td className="py-2.5">{a.name}</td>
                      <td className="py-2.5 text-right tabular-nums">{a.annotation_count}</td>
                      <td className="py-2.5 text-right tabular-nums">
                        <span className={a.active_assignments > 0 ? "text-green-600 font-medium" : "text-muted-foreground"}>
                          {a.active_assignments}
                        </span>
                      </td>
                      <td className="py-2.5 text-right tabular-nums">
                        {cal?.agreement_rate != null ? (
                          <span className={cal.agreement_rate >= 0.8 ? "text-green-600 font-medium" : cal.agreement_rate >= 0.6 ? "text-amber-600" : "text-red-600"}>
                            {Math.round(cal.agreement_rate * 100)}%
                          </span>
                        ) : <span className="text-muted-foreground">—</span>}
                      </td>
                      <td className="py-2.5 text-right tabular-nums">
                        {cal?.score_bias != null ? (
                          <span className={cal.score_bias > 0.5 ? "text-amber-600" : cal.score_bias < -0.5 ? "text-blue-600" : ""}>
                            {cal.score_bias > 0 ? "+" : ""}{cal.score_bias.toFixed(1)}
                          </span>
                        ) : <span className="text-muted-foreground">—</span>}
                      </td>
                      <td className="py-2.5 text-right tabular-nums text-muted-foreground">
                        {cal?.median_completion_minutes != null
                          ? cal.median_completion_minutes < 60
                            ? `${cal.median_completion_minutes}m`
                            : `${(cal.median_completion_minutes / 60).toFixed(1)}h`
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
