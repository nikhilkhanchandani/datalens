import type { ColumnProfile, DatasetProfile, DatasetResponse } from "@/lib/api";
import { formatBytes, formatDateTime, formatNumber } from "@/lib/format";

const KIND_STYLES: Record<ColumnProfile["kind"], string> = {
  numeric: "bg-sky-950 text-sky-300 border-sky-800",
  categorical: "bg-violet-950 text-violet-300 border-violet-800",
  boolean: "bg-amber-950 text-amber-300 border-amber-800",
  datetime: "bg-emerald-950 text-emerald-300 border-emerald-800",
};

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-100">{value}</p>
    </div>
  );
}

function KindBadge({ kind }: { kind: ColumnProfile["kind"] }) {
  return (
    <span
      className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${KIND_STYLES[kind]}`}
    >
      {kind}
    </span>
  );
}

function ColumnStatsSummary({ column }: { column: ColumnProfile }) {
  if (column.numeric_stats) {
    const { mean, median, std, minimum, maximum } = column.numeric_stats;
    return (
      <span className="text-slate-400">
        mean {formatNumber(mean)} · median {formatNumber(median)} · std{" "}
        {formatNumber(std)} · range [{formatNumber(minimum)},{" "}
        {formatNumber(maximum)}]
      </span>
    );
  }

  if (column.categorical_stats) {
    const { most_frequent_value, most_frequent_count } = column.categorical_stats;
    return (
      <span className="text-slate-400">
        most frequent: {most_frequent_value ?? "—"} ({most_frequent_count})
      </span>
    );
  }

  return <span className="text-slate-600">—</span>;
}

export function DatasetProfileView({
  dataset,
  profile,
}: {
  dataset: DatasetResponse;
  profile: DatasetProfile;
}) {
  return (
    <div className="w-full max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-100">
          {dataset.original_filename}
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Uploaded {formatDateTime(dataset.upload_timestamp)} ·{" "}
          {formatBytes(dataset.file_size_bytes)} · Encoding: {dataset.encoding}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryCard label="Rows" value={formatNumber(profile.row_count)} />
        <SummaryCard label="Columns" value={formatNumber(profile.column_count)} />
        <SummaryCard
          label="Duplicate Rows"
          value={formatNumber(profile.duplicate_row_count)}
        />
        <SummaryCard
          label="Memory Usage"
          value={formatBytes(profile.memory_usage_bytes)}
        />
      </div>

      <div className="mt-8 overflow-x-auto rounded-lg border border-slate-800">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="bg-slate-900 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Column</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Missing</th>
              <th className="px-4 py-3">Unique</th>
              <th className="px-4 py-3">Statistics</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {profile.columns.map((column) => (
              <tr key={column.name} className="text-slate-300">
                <td className="px-4 py-3 font-medium text-slate-100">
                  {column.name}
                  <div className="font-normal text-xs text-slate-600">
                    {column.pandas_dtype}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <KindBadge kind={column.kind} />
                </td>
                <td className="px-4 py-3">
                  {column.missing_count}{" "}
                  <span className="text-slate-600">
                    ({column.missing_percentage}%)
                  </span>
                </td>
                <td className="px-4 py-3">{column.unique_count}</td>
                <td className="px-4 py-3">
                  <ColumnStatsSummary column={column} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
