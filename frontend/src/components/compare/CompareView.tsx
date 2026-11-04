import {
  datasetExportUrl,
  getDatasetComparison,
  getDatasetTransformations,
  type ComparisonResponse,
  type TransformationRecord,
} from "@/lib/api";
import { useKeyedFetch } from "@/hooks/useKeyedFetch";
import { formatDateTime, formatNumber } from "@/lib/format";

interface CompareViewProps {
  datasetId: string;
  workingVersion: number;
}

/** Operations whose stored affected_rows doesn't count rows changed by value. */
const ROW_COUNT_NOT_MEANINGFUL = new Set(["drop_columns", "rename_column"]);

function formatSigned(value: number): string {
  if (value === 0) return "0";
  return `${value > 0 ? "+" : ""}${formatNumber(value)}`;
}

function scoreChangeColor(change: number): string {
  if (change > 0) return "text-emerald-400";
  if (change < 0) return "text-red-400";
  return "text-slate-400";
}

export function CompareView({ datasetId, workingVersion }: CompareViewProps) {
  // Both requests depend on the working version, so a cleaning step refetches them.
  const key = `${datasetId}:${workingVersion}`;
  const comparison = useKeyedFetch(key, () => getDatasetComparison(datasetId));
  const history = useKeyedFetch(key, () => getDatasetTransformations(datasetId));

  return (
    <div className="flex w-full max-w-5xl flex-col gap-6">
      <ExportBar datasetId={datasetId} workingVersion={workingVersion} />

      {comparison.status === "loading" && (
        <p className="text-sm text-slate-500">Comparing the original with the current version…</p>
      )}
      {comparison.status === "error" && <ErrorBox message={comparison.message} />}
      {comparison.status === "ready" && <ComparisonTable data={comparison.data} />}

      {comparison.status === "ready" && <OperationTotals data={comparison.data} />}

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Transformation history
        </h2>
        {history.status === "loading" && <p className="text-sm text-slate-500">Loading history…</p>}
        {history.status === "error" && <ErrorBox message={history.message} />}
        {history.status === "ready" && <HistoryList entries={history.data} />}
      </section>
    </div>
  );
}

function ExportBar({ datasetId, workingVersion }: { datasetId: string; workingVersion: number }) {
  const changed = workingVersion > 0;
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-slate-800 bg-slate-900 p-4 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-slate-400">
        {changed
          ? "Export downloads the current cleaned version. The uploaded file is not changed."
          : "No changes have been applied yet, so this download is the original upload."}
      </p>
      <a
        href={datasetExportUrl(datasetId)}
        className="shrink-0 rounded bg-sky-500 px-4 py-2 text-center text-sm font-medium text-slate-950 hover:bg-sky-400"
      >
        {changed ? "Export cleaned CSV" : "Download original CSV"}
      </a>
    </div>
  );
}

function ComparisonTable({ data }: { data: ComparisonResponse }) {
  const rows: {
    label: string;
    original: number;
    current: number;
    change: number;
    isScore?: boolean;
  }[] = [
    { label: "Rows", original: data.original.row_count, current: data.current.row_count, change: data.changes.row_count },
    { label: "Columns", original: data.original.column_count, current: data.current.column_count, change: data.changes.column_count },
    { label: "Missing values", original: data.original.missing_values, current: data.current.missing_values, change: data.changes.missing_values },
    { label: "Duplicate rows", original: data.original.duplicate_rows, current: data.current.duplicate_rows, change: data.changes.duplicate_rows },
    { label: "Quality score", original: data.original.quality_score, current: data.current.quality_score, change: data.changes.quality_score, isScore: true },
  ];

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full text-sm">
        <thead className="bg-slate-900 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3 font-medium">Metric</th>
            <th className="px-4 py-3 text-right font-medium">Original</th>
            <th className="px-4 py-3 text-right font-medium">Current</th>
            <th className="px-4 py-3 text-right font-medium">Change</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {rows.map((row) => (
            <tr key={row.label}>
              <td className="px-4 py-3 text-slate-300">{row.label}</td>
              <td className="px-4 py-3 text-right tabular-nums text-slate-400">{formatNumber(row.original)}</td>
              <td className="px-4 py-3 text-right tabular-nums text-slate-100">{formatNumber(row.current)}</td>
              <td
                className={`px-4 py-3 text-right tabular-nums font-medium ${
                  row.isScore ? scoreChangeColor(row.change) : "text-slate-300"
                }`}
              >
                {formatSigned(row.change)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-slate-800 bg-slate-900/60 px-4 py-2 text-xs text-slate-500">
        Counts show how the data changed; a lower count is not automatically better. Only the
        quality score is colored, because a higher score means fewer detected problems.
      </p>
    </div>
  );
}

function OperationTotals({ data }: { data: ComparisonResponse }) {
  const ops = data.operations;
  if (ops.transformation_count === 0) {
    return <p className="text-sm text-slate-500">No transformations have been applied.</p>;
  }

  const stats = [
    { label: "Transformations", value: formatNumber(ops.transformation_count) },
    { label: "Rows removed", value: formatNumber(ops.rows_removed) },
    { label: "Duplicates removed", value: formatNumber(ops.duplicate_rows_removed) },
    { label: "Values filled", value: formatNumber(ops.values_filled) },
    { label: "Text rows changed", value: formatNumber(ops.text_rows_changed) },
  ];

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
        Changes applied
      </h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-lg border border-slate-800 bg-slate-900 p-3">
            <p className="text-xs text-slate-500">{stat.label}</p>
            <p className="mt-1 text-lg font-semibold tabular-nums text-slate-100">{stat.value}</p>
          </div>
        ))}
      </div>
      {(ops.columns_dropped.length > 0 || ops.columns_renamed.length > 0) && (
        <ul className="list-inside list-disc text-sm text-slate-400">
          {ops.columns_dropped.map((name) => (
            <li key={`drop-${name}`}>Dropped column &ldquo;{name}&rdquo;</li>
          ))}
          {ops.columns_renamed.map((rename) => (
            <li key={`rename-${rename.from_name}`}>
              Renamed &ldquo;{rename.from_name}&rdquo; to &ldquo;{rename.to_name}&rdquo;
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function HistoryList({ entries }: { entries: TransformationRecord[] }) {
  if (entries.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        Nothing has been applied yet. Each cleaning step you apply appears here in order.
      </p>
    );
  }

  return (
    <ol className="flex flex-col gap-2">
      {entries.map((entry) => (
        <li
          key={entry.id}
          className="flex flex-col gap-1 rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <span className="text-sm text-slate-200">{entry.description}</span>
          <span className="flex flex-wrap gap-x-3 text-xs text-slate-500">
            <span>Version {entry.resulting_version}</span>
            <span className="tabular-nums">
              {formatNumber(entry.rows_before)} → {formatNumber(entry.rows_after)} rows
            </span>
            {!ROW_COUNT_NOT_MEANINGFUL.has(entry.operation) && (
              <span className="tabular-nums">{formatNumber(entry.affected_rows)} affected</span>
            )}
            <span>{formatDateTime(entry.timestamp)}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <p className="rounded-lg border border-red-900 bg-red-950/50 px-4 py-3 text-sm text-red-300">
      {message}
    </p>
  );
}
