import Link from "next/link";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Task } from "@/lib/types";
import { cn, formatDate, TASK_TYPE_COLORS, TASK_TYPE_LABELS } from "@/lib/utils";
import { CheckCircle2, Clock, FileEdit, Loader2 } from "lucide-react";

const STATUS_ICON: Record<string, React.ReactNode> = {
  draft: <FileEdit className="h-3.5 w-3.5" />,
  available: <Clock className="h-3.5 w-3.5" />,
  completed: <CheckCircle2 className="h-3.5 w-3.5" />,
};

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  available: "bg-amber-100 text-amber-700",
  completed: "bg-green-100 text-green-700",
};

interface Props {
  task: Task;
  onPublish?: (id: string) => void;
  publishing?: boolean;
}

export function TaskCard({ task, onPublish, publishing }: Props) {
  const meta = task.metadata as Record<string, string> | null;
  const genStatus = meta?.ai_generation_status;

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-semibold leading-snug line-clamp-2">
            {task.title}
          </CardTitle>
          <span className={cn("shrink-0 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", STATUS_COLORS[task.status])}>
            {STATUS_ICON[task.status]}
            {task.status}
          </span>
        </div>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          <span className={cn("text-xs rounded-full px-2 py-0.5 font-medium", TASK_TYPE_COLORS[task.task_type])}>
            {TASK_TYPE_LABELS[task.task_type]}
          </span>
          {task.priority > 0 && (
            <span className="text-xs text-muted-foreground">P{task.priority}</span>
          )}
          {genStatus === "pending" && (
            <span className="inline-flex items-center gap-1 text-xs text-amber-600">
              <Loader2 className="h-3 w-3 animate-spin" />
              Generating AI response…
            </span>
          )}
          {genStatus === "failed" && (
            <span className="text-xs text-destructive">AI generation failed</span>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1 pb-3">
        <p className="text-xs text-muted-foreground line-clamp-3">{task.prompt}</p>
      </CardContent>
      <CardFooter className="flex items-center justify-between pt-0">
        <div className="text-xs text-muted-foreground">
          {task.annotation_count} / {task.annotations_required} annotations · {formatDate(task.created_at)}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href={`/researcher/tasks/${task.id}`}>View</Link>
          </Button>
          {task.status === "draft" && onPublish && (
            <Button size="sm" onClick={() => onPublish(task.id)} disabled={publishing}>
              Publish
            </Button>
          )}
        </div>
      </CardFooter>
    </Card>
  );
}
