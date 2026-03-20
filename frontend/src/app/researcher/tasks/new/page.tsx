import { TaskForm } from "@/components/tasks/TaskForm";

export default function NewTaskPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">New Task</h1>
      <TaskForm />
    </div>
  );
}
