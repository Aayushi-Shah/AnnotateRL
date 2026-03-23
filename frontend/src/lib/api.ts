import { useAuthStore } from "./auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const tryRefresh = async (refreshToken: string): Promise<boolean> => {
  try {
    const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const { access_token } = await res.json();
    useAuthStore.getState().setAccessToken(access_token);
    return true;
  } catch {
    return false;
  }
};

export const apiFetch = async <T,>(path: string, options: RequestInit = {}): Promise<T> => {
  const store = useAuthStore.getState();
  const token = store.accessToken;

  const url = `${API_URL}/api/v1${path}`;

  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  // Attempt token refresh on 401
  if (res.status === 401 && store.refreshToken) {
    const refreshed = await tryRefresh(store.refreshToken);
    if (refreshed) {
      return apiFetch(path, options); // retry once
    }
    store.logout();
    window.location.href = "/login";
    throw new ApiError(401, "Session expired");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? body.message ?? "Request failed");
  }

  if (res.status === 204) return undefined as T;
  return res.json();
};

// ── Auth ─────────────────────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    apiFetch<{ access_token: string; refresh_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => apiFetch<import("./types").User>("/auth/me"),
  logout: (refreshToken: string) =>
    apiFetch("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
};

// ── Tasks ─────────────────────────────────────────────────────────────────────

export const tasksApi = {
  list: (params?: { status?: string; task_type?: string; page?: number; size?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.task_type) q.set("task_type", params.task_type);
    if (params?.page) q.set("page", String(params.page));
    if (params?.size) q.set("size", String(params.size));
    return apiFetch<import("./types").PaginatedResponse<import("./types").Task>>(
      `/tasks?${q}`
    );
  },
  get: (id: string) => apiFetch<import("./types").Task>(`/tasks/${id}`),
  create: (data: unknown) =>
    apiFetch<import("./types").Task>("/tasks", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: unknown) =>
    apiFetch<import("./types").Task>(`/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  delete: (id: string) => apiFetch(`/tasks/${id}`, { method: "DELETE" }),
  publish: (id: string) =>
    apiFetch<import("./types").Task>(`/tasks/${id}/publish`, { method: "POST" }),
};

// ── Queue ─────────────────────────────────────────────────────────────────────

export const queueApi = {
  list: (params?: { task_type?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.task_type) q.set("task_type", params.task_type);
    if (params?.limit) q.set("limit", String(params.limit));
    return apiFetch<import("./types").Task[]>(`/queue?${q}`);
  },
  claim: (taskId: string) =>
    apiFetch<import("./types").TaskAssignment>(`/queue/${taskId}/claim`, { method: "POST" }),
  mine: () => apiFetch<import("./types").TaskAssignment[]>("/queue/mine"),
  abandon: (assignmentId: string) =>
    apiFetch<import("./types").TaskAssignment>(`/queue/${assignmentId}/abandon`, {
      method: "POST",
    }),
};

// ── Annotations ───────────────────────────────────────────────────────────────

export const annotationsApi = {
  submit: (data: {
    assignment_id: string;
    response: string;
    signal_type: string;
    signal_value: Record<string, unknown>;
  }) =>
    apiFetch<import("./types").Annotation>("/annotations", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  list: (params?: { task_id?: string; annotator_id?: string; page?: number }) => {
    const q = new URLSearchParams();
    if (params?.task_id) q.set("task_id", params.task_id);
    if (params?.annotator_id) q.set("annotator_id", params.annotator_id);
    if (params?.page) q.set("page", String(params.page));
    return apiFetch<import("./types").PaginatedResponse<import("./types").Annotation>>(
      `/annotations?${q}`
    );
  },
};

// ── Metrics ───────────────────────────────────────────────────────────────────

export const metricsApi = {
  overview: () => apiFetch<import("./types").MetricsOverview>("/metrics/overview"),
  throughput: (days = 30) =>
    apiFetch<import("./types").ThroughputData>(`/metrics/throughput?days=${days}`),
  annotators: () =>
    apiFetch<{ annotators: import("./types").AnnotatorStat[] }>("/metrics/annotators"),
};

// ── Datasets ──────────────────────────────────────────────────────────────────

export const datasetsApi = {
  list: () => apiFetch<import("./types").Dataset[]>("/datasets"),
  create: (data: unknown) =>
    apiFetch<import("./types").Dataset>("/datasets", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  get: (id: string) => apiFetch<import("./types").Dataset>(`/datasets/${id}`),
  triggerExport: (id: string) =>
    apiFetch<import("./types").DatasetExport>(`/datasets/${id}/export`, { method: "POST" }),
  exports: (id: string) =>
    apiFetch<import("./types").DatasetExport[]>(`/datasets/${id}/exports`),
};

// ── Fine-tuning ──────────────────────────────────────────────────────────────

export const finetuneApi = {
  listJobs: () => apiFetch<import("./types").FineTuningJob[]>("/finetune/jobs"),
  getJob: (id: string) => apiFetch<import("./types").FineTuningJob>(`/finetune/jobs/${id}`),
  triggerManual: (config?: Record<string, unknown>) =>
    apiFetch<import("./types").FineTuningJob>("/finetune/jobs", {
      method: "POST",
      body: JSON.stringify(config ?? {}),
    }),
  listModels: () => apiFetch<import("./types").ModelVersion[]>("/finetune/models"),
  activateModel: (id: string) =>
    apiFetch<import("./types").ModelVersion>(`/finetune/models/${id}/activate`, {
      method: "POST",
    }),
};
