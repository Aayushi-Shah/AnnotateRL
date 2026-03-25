export type UserRole = "researcher" | "annotator";
export type TaskType = "coding" | "reasoning" | "comparison" | "correction";
export type TaskStatus = "draft" | "available" | "completed";
export type AssignmentStatus = "in_progress" | "completed" | "expired" | "abandoned";
export type SignalType = "rating" | "comparison" | "correction" | "binary";
export type ExportStatus = "pending" | "running" | "done" | "failed";

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface Task {
  id: string;
  title: string;
  prompt: string;
  context: string | null;
  task_type: TaskType;
  status: TaskStatus;
  priority: number;
  annotations_required: number;
  created_by: string;
  created_at: string;
  updated_at: string | null;
  metadata: Record<string, unknown>;
  annotation_count: number;
}

export interface TaskAssignment {
  id: string;
  task_id: string;
  annotator_id: string;
  status: AssignmentStatus;
  claimed_at: string;
  expires_at: string;
  completed_at: string | null;
}

export interface RatingValue { score: number }
export interface ComparisonValue { chosen: "A" | "B"; rationale?: string }
export interface CorrectionValue { edited: string }
export interface BinaryValue { accept: boolean; justification?: string }
export type SignalValue = RatingValue | ComparisonValue | CorrectionValue | BinaryValue;

export interface Annotation {
  id: string;
  task_id: string;
  assignment_id: string;
  annotator_id: string;
  response: string;
  signal_type: SignalType;
  signal_value: Record<string, unknown>;
  created_at: string;
  updated_at: string | null;
}

export interface Dataset {
  id: string;
  name: string;
  description: string | null;
  filter_config: Record<string, unknown>;
  created_by: string;
  created_at: string;
}

export interface DatasetExport {
  id: string;
  dataset_id: string;
  format: string;
  status: ExportStatus;
  s3_key: string | null;
  row_count: number | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  download_url: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface MetricsOverview {
  tasks: Record<string, number>;
  total_annotations: number;
  active_annotators: number;
  total_annotators: number;
}

export interface ThroughputPoint {
  date: string;
  count: number;
}

export interface ThroughputData {
  days: number;
  data: ThroughputPoint[];
}

export interface AnnotatorStat {
  id: string;
  name: string;
  annotation_count: number;
  active_assignments: number;
}

export interface RewardDistribution {
  distribution: Record<string, Record<string, number>>;
}

export interface TaskIAA {
  task_id: string;
  annotation_count: number;
  annotations_required: number;
  signal_type: string | null;
  agreement: {
    mean?: number; std?: number; within_1_rate?: number;
    percent_agreement?: number; kappa?: number; interpretation?: string;
  } | null;
}

export interface IAASummary {
  tasks_evaluated: number;
  avg_kappa: number | null;
  high_agreement_count: number;
}

export interface TrainingStats {
  total_annotations: number;
  accepted: number;
  negative_examples: number;
  dpo_pairs: number;
  skipped_low_iaa: number;
  skipped_ambiguous: number;
  skipped_correction: number;
}

// Fine-tuning
export type FineTuneJobStatus = "pending" | "preparing_data" | "training" | "completed" | "failed";

export interface FineTuningJob {
  id: string;
  status: FineTuneJobStatus;
  trigger_task_id: string | null;
  training_data_s3_key: string | null;
  training_data_rows: number | null;
  training_stats: TrainingStats | null;
  external_job_id: string | null;
  config: Record<string, unknown>;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ModelVersion {
  id: string;
  version_tag: string;
  base_model: string;
  finetuned_model_id: string | null;
  is_active: boolean;
  training_job_id: string | null;
  created_at: string;
}
