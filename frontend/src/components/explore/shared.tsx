import type { ReactNode } from "react";
import type { ColumnKind, ColumnStatistics } from "@/lib/api";

export function ChartCard({
  title,
  description,
  controls,
  children,
}: {
  title: string;
  description: string;
  controls?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="font-medium text-slate-100">{title}</h3>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">{description}</p>
        </div>
        {controls && <div className="flex flex-wrap gap-2">{controls}</div>}
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

export function ColumnSelect({
  label,
  value,
  columns,
  kinds,
  onChange,
}: {
  label: string;
  value: string;
  columns: ColumnStatistics[];
  kinds: ColumnKind[];
  onChange: (name: string) => void;
}) {
  const options = columns.filter((column) => kinds.includes(column.kind));
  return (
    <label className="flex items-center gap-2 text-xs text-slate-400">
      <span className="uppercase tracking-wide">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={options.length === 0}
        className="rounded border border-slate-700 bg-slate-800 px-2 py-1 text-sm text-slate-200 disabled:opacity-50"
      >
        {options.map((column) => (
          <option key={column.name} value={column.name}>
            {column.name}
          </option>
        ))}
      </select>
    </label>
  );
}

export function NoCompatibleColumns({ needs }: { needs: string }) {
  return (
    <p className="rounded border border-dashed border-slate-700 px-4 py-6 text-center text-sm text-slate-500">
      This chart needs {needs} columns, and this dataset doesn&apos;t have any.
    </p>
  );
}

export function ChartLoading() {
  return <div className="h-64 animate-pulse rounded bg-slate-800/60" />;
}

export function ChartError({ message }: { message: string }) {
  return (
    <p className="rounded border border-red-900 bg-red-950/50 px-4 py-3 text-sm text-red-300">
      {message}
    </p>
  );
}

export function Explanation({ children }: { children: ReactNode }) {
  return (
    <p className="mt-4 rounded bg-slate-950/60 px-3 py-2 text-xs leading-relaxed text-slate-400">
      {children}
    </p>
  );
}

export function columnsOfKinds(
  columns: ColumnStatistics[],
  kinds: ColumnKind[],
): ColumnStatistics[] {
  return columns.filter((column) => kinds.includes(column.kind));
}

const IDENTIFIER_NAME = /(^|_)(id|uuid|key|code)$/i;

/** Columns whose names look like identifiers come last, so charts default to informative columns. */
export function preferNonIdentifiers(columns: ColumnStatistics[]): ColumnStatistics[] {
  return [...columns].sort(
    (a, b) => Number(IDENTIFIER_NAME.test(a.name)) - Number(IDENTIFIER_NAME.test(b.name)),
  );
}
