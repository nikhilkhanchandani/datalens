"use client";

import { useState } from "react";
import {
  getDistributionSummary,
  type ColumnStatistics,
  type DistributionSummary,
} from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { useKeyedFetch } from "@/hooks/useKeyedFetch";
import {
  ChartCard,
  ChartError,
  ChartLoading,
  ColumnSelect,
  Explanation,
  NoCompatibleColumns,
  columnsOfKinds,
  preferNonIdentifiers,
} from "./shared";

const WIDTH = 640;
const HEIGHT = 120;
const PADDING = 32;

export function DistributionCard({
  datasetId,
  columns,
}: {
  datasetId: string;
  columns: ColumnStatistics[];
}) {
  const options = columnsOfKinds(columns, ["numeric"]);
  const [selected, setSelected] = useState<string | undefined>(preferNonIdentifiers(options)[0]?.name);
  const column = selected ?? preferNonIdentifiers(options)[0]?.name;
  const state = useKeyedFetch(
    column ? `${datasetId}:${column}` : null,
    () => getDistributionSummary(datasetId, column ?? ""),
  );

  return (
    <ChartCard
      title="Distribution Summary (Box Plot)"
      description="The middle half of values sits inside the box (from Q1 to Q3); the line inside it marks the median; the whiskers reach the smallest and largest values."
      controls={
        options.length > 0 && (
          <ColumnSelect
            label="Column"
            value={column ?? ""}
            columns={columns}
            kinds={["numeric"]}
            onChange={setSelected}
          />
        )
      }
    >
      {options.length === 0 && <NoCompatibleColumns needs="numeric" />}
      {state.status === "loading" && <ChartLoading />}
      {state.status === "error" && <ChartError message={state.message} />}
      {state.status === "ready" && <BoxPlot summary={state.data} />}
    </ChartCard>
  );
}

function BoxPlot({ summary }: { summary: DistributionSummary }) {
  const span = summary.maximum - summary.minimum;
  const scale = (value: number) =>
    span === 0
      ? WIDTH / 2
      : PADDING + ((value - summary.minimum) / span) * (WIDTH - 2 * PADDING);

  const midY = HEIGHT / 2;
  const boxHeight = 44;
  const x = {
    min: scale(summary.minimum),
    q1: scale(summary.q1),
    median: scale(summary.median),
    q3: scale(summary.q3),
    max: scale(summary.maximum),
  };

  return (
    <>
      <div className="w-full overflow-x-auto">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="w-full min-w-[480px]"
          role="img"
          aria-label={`Box plot of ${summary.column}`}
        >
          <line x1={x.min} x2={x.max} y1={midY} y2={midY} stroke="#64748b" strokeWidth={2} />
          <line x1={x.min} x2={x.min} y1={midY - 16} y2={midY + 16} stroke="#64748b" strokeWidth={2} />
          <line x1={x.max} x2={x.max} y1={midY - 16} y2={midY + 16} stroke="#64748b" strokeWidth={2} />
          <rect
            x={x.q1}
            y={midY - boxHeight / 2}
            width={Math.max(x.q3 - x.q1, 1)}
            height={boxHeight}
            fill="#0ea5e9"
            fillOpacity={0.25}
            stroke="#38bdf8"
            strokeWidth={2}
          >
            <title>{`Q1 ${formatNumber(summary.q1)} · Q3 ${formatNumber(summary.q3)}`}</title>
          </rect>
          <line x1={x.median} x2={x.median} y1={midY - boxHeight / 2} y2={midY + boxHeight / 2} stroke="#f8fafc" strokeWidth={3} />
          <text x={x.min} y={HEIGHT - 8} textAnchor="middle" fill="#94a3b8" fontSize={11}>
            min {formatNumber(summary.minimum)}
          </text>
          <text x={x.max} y={HEIGHT - 8} textAnchor="middle" fill="#94a3b8" fontSize={11}>
            max {formatNumber(summary.maximum)}
          </text>
          <text x={x.median} y={midY - boxHeight / 2 - 6} textAnchor="middle" fill="#e2e8f0" fontSize={11}>
            median {formatNumber(summary.median)}
          </text>
        </svg>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-6">
        <Stat label="Min" value={summary.minimum} />
        <Stat label="Q1" value={summary.q1} />
        <Stat label="Median" value={summary.median} />
        <Stat label="Q3" value={summary.q3} />
        <Stat label="Max" value={summary.maximum} />
        <Stat label="IQR (Q3 − Q1)" value={summary.iqr} />
      </dl>

      <Explanation>
        Based on {summary.count.toLocaleString()} usable values
        {summary.missing_count > 0 && `; ${summary.missing_count.toLocaleString()} missing values excluded`}.
        IQR (interquartile range) is the width of the box: the spread of the middle 50% of values.
        Quartiles are computed by Python with linear interpolation.
      </Explanation>
    </>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-slate-200">{formatNumber(value)}</dd>
    </div>
  );
}
