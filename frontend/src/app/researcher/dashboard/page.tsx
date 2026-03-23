"use client";

import { useQuery } from "@tanstack/react-query";
import { metricsApi } from "@/lib/api";
import { OverviewCards } from "@/components/dashboard/OverviewCards";
import { ThroughputChart } from "@/components/dashboard/ThroughputChart";
import { RewardDistributionChart } from "@/components/dashboard/RewardDistributionChart";
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

  const { data: rewardDist, isLoading: rewardLoading } = useQuery({
    queryKey: ["metrics", "reward-distribution"],
    queryFn: metricsApi.rewardDistribution,
  });

  const { data: annotatorData, isLoading: annotatorsLoading } = useQuery({
    queryKey: ["metrics", "annotators"],
    queryFn: metricsApi.annotators,
    refetchInterval: 60_000,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <OverviewCards data={overview} isLoading={overviewLoading} />

      <ThroughputChart data={throughput?.data} isLoading={throughputLoading} days={30} />

      <RewardDistributionChart data={rewardDist} isLoading={rewardLoading} />

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
                </tr>
              </thead>
              <tbody>
                {annotatorData?.annotators?.map((a) => (
                  <tr key={a.id} className="border-b border-border last:border-0">
                    <td className="py-2.5">{a.name}</td>
                    <td className="py-2.5 text-right tabular-nums">{a.annotation_count}</td>
                    <td className="py-2.5 text-right tabular-nums">
                      <span className={a.active_assignments > 0 ? "text-green-600 font-medium" : "text-muted-foreground"}>
                        {a.active_assignments}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
