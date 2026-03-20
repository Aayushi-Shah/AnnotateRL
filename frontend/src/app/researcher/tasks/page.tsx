"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tasksApi } from "@/lib/api";
import { TaskCard } from "@/components/tasks/TaskCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus } from "lucide-react";

const STATUS_FILTERS = ["all", "draft", "available", "completed"];
const TYPE_FILTERS = ["all", "coding", "reasoning", "comparison", "correction"];

export default function TasksPage() {
  const [status, setStatus] = useState("all");
  const [taskType, setTaskType] = useState("all");
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["tasks", status, taskType],
    queryFn: () =>
      tasksApi.list({
        status: status === "all" ? undefined : status,
        task_type: taskType === "all" ? undefined : taskType,
        size: 50,
      }),
  });

  const { mutate: publish, variables: publishingId } = useMutation({
    mutationFn: tasksApi.publish,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Tasks</h1>
        <Button asChild>
          <Link href="/researcher/tasks/new">
            <Plus className="h-4 w-4 mr-1" />
            New Task
          </Link>
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4">
        <div className="flex gap-1">
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                status === s
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-secondary-foreground hover:bg-secondary/70"
              }`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {TYPE_FILTERS.map((t) => (
            <button
              key={t}
              onClick={() => setTaskType(t)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                taskType === t
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-secondary-foreground hover:bg-secondary/70"
              }`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-48 w-full rounded-lg" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {data?.items?.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onPublish={() => publish(task.id)}
              publishing={publishingId === task.id}
            />
          ))}
          {data?.items?.length === 0 && (
            <p className="col-span-3 text-center py-12 text-muted-foreground">
              No tasks found. Create one to get started.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
