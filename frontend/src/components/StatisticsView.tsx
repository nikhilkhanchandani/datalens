import type { ColumnKind, ColumnStatistics, DatasetStatistics } from "@/lib/api";
import { formatNumber } from "@/lib/format";

const KIND_STYLES: Record<ColumnKind, string> = {
  numeric: "bg-sky-950 text-sky-300 border-sky-800",
  categorical: "bg-violet-950 text-violet-300 border-violet-800",
  boolean: "bg-amber-950 text-amber-300 border-amber-800",
  datetime: "bg-emerald-950 text-emerald-300 border-emerald-800",
};

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-sm text-slate-200">{value}</p>
    </div>
  );
}

function NumericStatsGrid({ column }: { column: ColumnStatistics }) {
  const s = column.numeric!;
  return (
    <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
      <Stat label="Count" value={formatNumber(s.count)} />
      <Stat label="Missing" value={formatNumber(s.missing_count)} />
      <Stat label="Mean" value={formatNumber(s.mean)} />
      <Stat label="Median" value={formatNumber(s.median)} />
      <Stat label="Std Dev" value={formatNumber(s.std)} />
      <Stat label="Variance" value={formatNumber(s.variance)} />
      <Stat label="Minimum" value={formatNumber(s.minimum)} />
      <Stat label="Maximum" value={formatNumber(s.maximum)} />
      <Stat label="Range" value={formatNumber(s.range)} />
      <Stat label="P25" value={formatNumber(s.p25)} />
      <Stat label="P50 (Median)" value={formatNumber(s.p50)} />
      <Stat label="P75" value={formatNumber(s.p75)} />
      <Stat label="IQR" value={formatNumber(s.iqr)} />
    </div>
  );
}

function CategoricalStatsGrid({ column }: { column: ColumnStatistics }) {
  const s = column.categorical!;
  return (
    <div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        <Stat label="Count" value={formatNumber(s.count)} />
        <Stat label="Missing" value={formatNumber(s.missing_count)} />
        <Stat label="Unique" value={formatNumber(s.unique_count)} />
        <Stat
          label="Most Frequent"
          value={
            s.most_frequent_value !== null
              ? `${s.most_frequent_value} (${s.most_frequent_count})`
              : "—"
          }
        />
      </div>
      {s.top_values.length > 0 && (
        <div className="mt-4">
          <p className="text-xs uppercase tracking-wide text-slate-500">
            Top Values
          </p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {s.top_values.map((tv) => (
              <li
                key={tv.value}
                className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-300"
              >
                {tv.value} <span className="text-slate-500">× {tv.count}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function BooleanStatsGrid({ column }: { column: ColumnStatistics }) {
  const s = column.boolean!;
  return (
    <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
      <Stat label="Count" value={formatNumber(s.count)} />
      <Stat label="Missing" value={formatNumber(s.missing_count)} />
      <Stat label="True" value={formatNumber(s.true_count)} />
      <Stat label="False" value={formatNumber(s.false_count)} />
      <Stat
        label="True %"
        value={s.true_percentage !== null ? `${s.true_percentage}%` : "—"}
      />
    </div>
  );
}

function DatetimeStatsGrid({ column }: { column: ColumnStatistics }) {
  const s = column.datetime!;
  return (
    <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
      <Stat label="Valid" value={formatNumber(s.valid_count)} />
      <Stat label="Missing" value={formatNumber(s.missing_count)} />
      <Stat label="Earliest" value={s.earliest ?? "—"} />
      <Stat label="Latest" value={s.latest ?? "—"} />
      <Stat
        label="Range"
        value={s.range_days !== null ? `${s.range_days} day(s)` : "—"}
      />
    </div>
  );
}

function ColumnStatisticsCard({ column }: { column: ColumnStatistics }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="mb-4 flex items-center gap-2">
        <h3 className="font-medium text-slate-100">{column.name}</h3>
        <span
          className={`rounded border px-2 py-0.5 text-xs font-medium ${KIND_STYLES[column.kind]}`}
        >
          {column.kind}
        </span>
      </div>
      {column.kind === "numeric" && <NumericStatsGrid column={column} />}
      {column.kind === "categorical" && <CategoricalStatsGrid column={column} />}
      {column.kind === "boolean" && <BooleanStatsGrid column={column} />}
      {column.kind === "datetime" && <DatetimeStatsGrid column={column} />}
    </div>
  );
}

export function StatisticsView({ statistics }: { statistics: DatasetStatistics }) {
  return (
    <div className="w-full max-w-5xl space-y-4">
      <p className="text-sm text-slate-500">
        {statistics.row_count.toLocaleString()} rows ·{" "}
        {statistics.columns.length} columns
      </p>
      {statistics.columns.map((column) => (
        <ColumnStatisticsCard key={column.name} column={column} />
      ))}
    </div>
  );
}
