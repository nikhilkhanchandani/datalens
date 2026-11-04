/**
 * Thin client for the DataLens FastAPI backend.
 *
 * All real analysis logic lives in Python — this file only knows how to
 * call the API and should never contain statistics/business logic itself.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface HealthResponse {
  status: string;
  service: string;
  environment: string;
}

export interface DatasetResponse {
  id: string;
  original_filename: string;
  upload_timestamp: string;
  row_count: number;
  column_count: number;
  file_size_bytes: number;
  encoding: string;
  working_version: number;
}

export type ColumnKind = "numeric" | "categorical" | "boolean" | "datetime";

export interface NumericColumnStats {
  count: number;
  mean: number | null;
  median: number | null;
  std: number | null;
  variance: number | null;
  minimum: number | null;
  maximum: number | null;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  range: number | null;
}

export interface TopValue {
  value: string;
  count: number;
}

export interface CategoricalColumnStats {
  unique_count: number;
  most_frequent_value: string | null;
  most_frequent_count: number;
  top_values: TopValue[];
}

export interface ColumnProfile {
  name: string;
  kind: ColumnKind;
  pandas_dtype: string;
  missing_count: number;
  missing_percentage: number;
  unique_count: number;
  sample_values: unknown[];
  numeric_stats: NumericColumnStats | null;
  categorical_stats: CategoricalColumnStats | null;
}

export interface DatasetProfile {
  row_count: number;
  column_count: number;
  duplicate_row_count: number;
  memory_usage_bytes: number;
  columns: ColumnProfile[];
  encoding: string;
}

export type IssueSeverity = "low" | "medium" | "high";

export type IssueType =
  | "missing_values"
  | "blank_strings"
  | "duplicate_rows"
  | "constant_column"
  | "mostly_empty_column"
  | "infinite_values"
  | "mixed_types"
  | "high_cardinality_column"
  | "possible_identifier_column";

export interface QualityIssue {
  type: IssueType;
  column: string | null;
  severity: IssueSeverity;
  affected_rows: number;
  percentage: number;
  message: string;
  suggested_action: string;
}

export interface ScoreBreakdownEntry {
  category: string;
  penalty: number;
  reason: string;
}

export interface QualityReport {
  score: number;
  breakdown: ScoreBreakdownEntry[];
  issues: QualityIssue[];
}

export interface NumericStatistics {
  count: number;
  missing_count: number;
  mean: number | null;
  median: number | null;
  std: number | null;
  variance: number | null;
  minimum: number | null;
  maximum: number | null;
  range: number | null;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  iqr: number | null;
}

export interface CategoricalTopValue {
  value: string;
  count: number;
}

export interface CategoricalStatistics {
  count: number;
  missing_count: number;
  unique_count: number;
  most_frequent_value: string | null;
  most_frequent_count: number;
  top_values: CategoricalTopValue[];
}

export interface BooleanStatistics {
  count: number;
  missing_count: number;
  true_count: number;
  false_count: number;
  true_percentage: number | null;
}

export interface DatetimeStatistics {
  valid_count: number;
  missing_count: number;
  earliest: string | null;
  latest: string | null;
  range_days: number | null;
}

export interface ColumnStatistics {
  name: string;
  kind: ColumnKind;
  numeric: NumericStatistics | null;
  categorical: CategoricalStatistics | null;
  boolean: BooleanStatistics | null;
  datetime: DatetimeStatistics | null;
}

export interface DatasetStatistics {
  row_count: number;
  columns: ColumnStatistics[];
}

interface ApiErrorBody {
  error: string;
  message: string;
}

async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as ApiErrorBody;
    return body.message || `Request failed with status ${response.status}`;
  } catch {
    return `Request failed with status ${response.status}`;
  }
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`);

  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }

  return response.json();
}

export async function uploadDataset(file: File): Promise<DatasetResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/datasets/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.json();
}

export async function getDataset(datasetId: string): Promise<DatasetResponse> {
  const response = await fetch(`${API_BASE_URL}/api/datasets/${datasetId}`);

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.json();
}

export async function getDatasetProfile(
  datasetId: string,
): Promise<DatasetProfile> {
  const response = await fetch(
    `${API_BASE_URL}/api/datasets/${datasetId}/profile`,
  );

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.json();
}

export async function getDatasetQuality(
  datasetId: string,
): Promise<QualityReport> {
  const response = await fetch(
    `${API_BASE_URL}/api/datasets/${datasetId}/quality`,
  );

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.json();
}

export async function getDatasetStatistics(
  datasetId: string,
): Promise<DatasetStatistics> {
  const response = await fetch(
    `${API_BASE_URL}/api/datasets/${datasetId}/statistics`,
  );

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.json();
}

export type CorrelationMethod = "pearson" | "spearman";

export interface ExcludedColumn {
  name: string;
  reason: string;
}

export interface StrongPair {
  x: string;
  y: string;
  r: number;
  direction: "positive" | "negative";
}

export interface CorrelationReport {
  method: CorrelationMethod;
  columns: string[];
  matrix: (number | null)[][];
  excluded_columns: ExcludedColumn[];
  strong_pairs: StrongPair[];
  strong_threshold: number;
  disclaimer: string;
}

export interface HistogramBin {
  start: number;
  end: number;
  count: number;
}

export interface HistogramData {
  column: string;
  bins: HistogramBin[];
  bin_strategy: string;
  total_observations: number;
  missing_count: number;
  infinite_count: number;
  is_constant: boolean;
}

export interface FrequencyItem {
  value: string;
  count: number;
  percentage: number;
  is_other: boolean;
}

export interface CategoricalFrequencies {
  column: string;
  total_count: number;
  missing_count: number;
  unique_count: number;
  top_n: number;
  truncated: boolean;
  items: FrequencyItem[];
}

export interface ScatterPoint {
  x: number;
  y: number;
}

export interface ScatterData {
  x_column: string;
  y_column: string;
  total_points: number;
  returned_points: number;
  sampled: boolean;
  max_points: number;
  pearson_r: number | null;
  points: ScatterPoint[];
}

export interface DistributionSummary {
  column: string;
  count: number;
  missing_count: number;
  minimum: number;
  q1: number;
  median: number;
  q3: number;
  maximum: number;
  iqr: number;
}

export interface TrendPoint {
  period_start: string;
  mean: number;
  minimum: number;
  maximum: number;
  count: number;
}

export interface DatetimeTrend {
  datetime_column: string;
  value_column: string;
  granularity: string;
  total_observations: number;
  points: TrendPoint[];
}

async function fetchAnalysis<T>(
  datasetId: string,
  path: string,
  params: Record<string, string | number | undefined> = {},
): Promise<T> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) query.set(key, String(value));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  const response = await fetch(
    `${API_BASE_URL}/api/datasets/${datasetId}${path}${suffix}`,
  );

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.json();
}

export function getCorrelations(
  datasetId: string,
  method: CorrelationMethod,
): Promise<CorrelationReport> {
  return fetchAnalysis(datasetId, "/correlations", { method });
}

export function getHistogram(
  datasetId: string,
  column: string,
): Promise<HistogramData> {
  return fetchAnalysis(datasetId, "/visualizations/histogram", { column });
}

export function getCategoricalFrequencies(
  datasetId: string,
  column: string,
  topN: number,
): Promise<CategoricalFrequencies> {
  return fetchAnalysis(datasetId, "/visualizations/categorical", {
    column,
    top_n: topN,
  });
}

export function getScatter(
  datasetId: string,
  x: string,
  y: string,
): Promise<ScatterData> {
  return fetchAnalysis(datasetId, "/visualizations/scatter", { x, y });
}

export function getDistributionSummary(
  datasetId: string,
  column: string,
): Promise<DistributionSummary> {
  return fetchAnalysis(datasetId, "/visualizations/distribution", { column });
}

export function getDatetimeTrend(
  datasetId: string,
  datetimeColumn: string,
  valueColumn: string,
): Promise<DatetimeTrend> {
  return fetchAnalysis(datasetId, "/visualizations/datetime-trend", {
    datetime_column: datetimeColumn,
    value_column: valueColumn,
  });
}

export type FillStrategy = "mean" | "median" | "mode" | "custom" | "remove_rows";
export type ConversionTarget = "numeric" | "datetime" | "boolean" | "string";

/** Mirrors the backend's discriminated union on `operation`. */
export type CleaningRequest =
  | { operation: "fill_missing"; column: string; strategy: FillStrategy; value?: number | string | boolean | null }
  | { operation: "remove_duplicates"; subset?: string[] | null }
  | { operation: "normalize_text"; columns: string[]; trim?: boolean; blank_to_missing?: boolean }
  | { operation: "drop_columns"; columns: string[] }
  | { operation: "rename_column"; column: string; new_name: string }
  | { operation: "convert_type"; column: string; target: ConversionTarget };

export interface TransformationResult {
  operation: string;
  column: string | null;
  strategy: string | null;
  columns: string[];
  affected_rows: number;
  rows_before: number;
  rows_after: number;
  summary: string;
  working_version: number;
}

/** Applies one explicit cleaning step. The server validates everything and returns the reason on failure. */
export async function applyCleaning(
  datasetId: string,
  request: CleaningRequest,
): Promise<TransformationResult> {
  const response = await fetch(`${API_BASE_URL}/api/datasets/${datasetId}/clean`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.json();
}

export interface DatasetMetrics {
  row_count: number;
  column_count: number;
  missing_values: number;
  duplicate_rows: number;
  quality_score: number;
}

export interface MetricChanges {
  row_count: number;
  column_count: number;
  missing_values: number;
  duplicate_rows: number;
  quality_score: number;
}

export interface ColumnRename {
  from_name: string;
  to_name: string;
}

export interface OperationTotals {
  transformation_count: number;
  rows_removed: number;
  duplicate_rows_removed: number;
  values_filled: number;
  text_rows_changed: number;
  columns_dropped: string[];
  columns_renamed: ColumnRename[];
}

export interface ComparisonResponse {
  working_version: number;
  original: DatasetMetrics;
  current: DatasetMetrics;
  changes: MetricChanges;
  operations: OperationTotals;
}

export interface TransformationRecord {
  id: number;
  operation: string;
  column: string | null;
  parameters: Record<string, unknown>;
  affected_rows: number;
  rows_before: number;
  rows_after: number;
  resulting_version: number;
  timestamp: string;
  description: string;
}

export async function getDatasetComparison(
  datasetId: string,
): Promise<ComparisonResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/datasets/${datasetId}/comparison`,
  );

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.json();
}

export async function getDatasetTransformations(
  datasetId: string,
): Promise<TransformationRecord[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/datasets/${datasetId}/transformations`,
  );

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.json();
}

/** Link target for the export download. The server sets Content-Disposition, so a plain link is enough. */
export function datasetExportUrl(datasetId: string): string {
  return `${API_BASE_URL}/api/datasets/${datasetId}/export`;
}
