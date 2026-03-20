import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function timeUntil(iso: string): string {
  const diff = new Date(iso).getTime() - Date.now();
  if (diff <= 0) return "Expired";
  const h = Math.floor(diff / 3_600_000);
  const m = Math.floor((diff % 3_600_000) / 60_000);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export function isExpired(iso: string): boolean {
  return new Date(iso).getTime() < Date.now();
}

export const TASK_TYPE_LABELS: Record<string, string> = {
  coding: "Coding",
  reasoning: "Reasoning",
  comparison: "Comparison",
  correction: "Correction",
};

export const TASK_TYPE_COLORS: Record<string, string> = {
  coding: "bg-blue-100 text-blue-800",
  reasoning: "bg-purple-100 text-purple-800",
  comparison: "bg-amber-100 text-amber-800",
  correction: "bg-green-100 text-green-800",
};
