import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { MetricsOverview } from "@/lib/types";
import { CheckCircle2, Clock, Users, MessageSquare } from "lucide-react";

interface Props {
  data: MetricsOverview | undefined;
  isLoading: boolean;
}

export function OverviewCards({ data, isLoading }: Props) {
  const cards = [
    {
      label: "Total Annotations",
      value: data?.total_annotations ?? 0,
      icon: MessageSquare,
      color: "text-blue-600",
    },
    {
      label: "Available Tasks",
      value: data?.tasks?.available ?? 0,
      icon: Clock,
      color: "text-amber-600",
    },
    {
      label: "Completed Tasks",
      value: data?.tasks?.completed ?? 0,
      icon: CheckCircle2,
      color: "text-green-600",
    },
    {
      label: "Active Annotators",
      value: `${data?.active_annotators ?? 0} / ${data?.total_annotators ?? 0}`,
      icon: Users,
      color: "text-purple-600",
    },
  ];

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
      {cards.map(({ label, value, icon: Icon, color }) => (
        <Card key={label}>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
            <Icon className={`h-4 w-4 ${color}`} />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{value}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
