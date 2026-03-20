"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { queueApi, tasksApi } from "@/lib/api";
import { AnnotationWorkspace } from "@/components/annotations/AnnotationWorkspace";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { useState } from "react";

export default function WorkspacePage() {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const router = useRouter();
  const [submitted, setSubmitted] = useState(false);

  // Get current assignments to find this one
  const { data: assignments, isLoading: assignmentsLoading } = useQuery({
    queryKey: ["my-tasks"],
    queryFn: queueApi.mine,
  });

  const assignment = assignments?.find((a) => a.id === assignmentId);

  const { data: task, isLoading: taskLoading } = useQuery({
    queryKey: ["tasks", assignment?.task_id],
    queryFn: () => tasksApi.get(assignment!.task_id),
    enabled: !!assignment,
  });

  if (submitted) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <CheckCircle2 className="h-12 w-12 text-green-500" />
        <h2 className="text-xl font-semibold">Annotation submitted!</h2>
        <p className="text-muted-foreground">Thank you for your contribution.</p>
        <Button asChild>
          <Link href="/annotator/queue">Back to Queue</Link>
        </Button>
      </div>
    );
  }

  if (assignmentsLoading || taskLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="flex gap-6">
          <Skeleton className="h-96 w-2/5 rounded-lg" />
          <Skeleton className="h-96 flex-1 rounded-lg" />
        </div>
      </div>
    );
  }

  if (!assignment) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-muted-foreground">Assignment not found or already completed.</p>
        <Button asChild variant="outline">
          <Link href="/annotator/queue"><ArrowLeft className="h-4 w-4 mr-1" />Back to Queue</Link>
        </Button>
      </div>
    );
  }

  if (!task) return null;

  return (
    <div className="flex flex-col h-full gap-4">
      <div className="flex items-center gap-3 shrink-0">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/annotator/queue"><ArrowLeft className="h-4 w-4" /></Link>
        </Button>
        <h1 className="text-lg font-semibold truncate flex-1">{task.title}</h1>
      </div>
      <div className="flex-1 min-h-0">
        <AnnotationWorkspace
          task={task}
          assignment={assignment}
          onComplete={() => setSubmitted(true)}
          onAbandon={() => router.replace("/annotator/queue")}
        />
      </div>
    </div>
  );
}
