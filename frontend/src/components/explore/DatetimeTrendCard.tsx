"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getDatetimeTrend,
  type ColumnStatistics,
  type DatetimeTrend,
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

export function DatetimeTrendCard({
  datasetId,
  columns,
}: {
  datasetId: string;
  columns: ColumnStatistics[];
}) {
  const timeOptions = columnsOfKinds(columns, ["datetime"]);
  const valueOptions = columnsOfKinds(columns, ["numeric"]);
  const [timeSelected, setTimeSelected] = useState<string | undefined>(preferNonIdentifiers(timeOptions)[0]?.name);
  const [valueSelected, setValueSelected] = useState<string | undefined>(preferNonIdentifiers(valueOptions)[0]?.name);
  const timeColumn = timeSelected ?? preferNonIdentifiers(timeOptions)[0]?.name;
  const valueColumn = valueSelected ?? preferNonIdentifiers(valueOptions)[0]?.name;
  const ready = timeColumn !== undefined && valueColumn !== undefined;

  const state = useKeyedFetch(
    ready ? `${datasetId}:${timeColumn}:${valueColumn}` : null,
    () => getDatetimeTrend(datasetId, timeColumn ?? "", valueColumn ?? ""),
  );

  const hasBoth = timeOptions.length > 0 && valueOptions.length > 0;

  return (
    <ChartCard
      title="Datetime Trend"
      description="The average of a numeric column for each calendar period (day, week, month, quarter, or year) across a date column. Dashed lines mark the lowest and highest value in each period."
      controls={
        hasBoth && (
          <>
            <ColumnSelect label="Date" value={timeColumn ?? ""} columns={columns} kinds={["datetime"]} onChange={setTimeSelected} />
            <ColumnSelect label="Value" value={valueColumn ?? ""} columns={columns} kinds={["numeric"]} onChange={setValueSelected} />
          </>
        )
      }
    >
      {!hasBoth && (
        <NoCompatibleColumns needs="a date column plus a numeric column" />
      )}
      {hasBoth && state.status === "loading" && <ChartLoading />}
      {hasBoth && state.status === "error" && <ChartError message={state.message} />}
      {hasBoth && state.status === "ready" && <Trend data={state.data} />}
    </ChartCard>
  );
}

function Trend({ data }: { data: DatetimeTrend }) {
  if (data.points.length === 0) {
    return <p className="text-sm text-slate-500">No rows have both a date and a value.</p>;
  }

  const rows = data.points.map((point) => ({
    period: point.period_start.slice(0, 10),
    mean: point.mean,
    minimum: point.minimum,
    maximum: point.maximum,
    count: point.count,
  }));

  return (
    <>
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="period" tick={{ fill: "#94a3b8", fontSize: 11 }} minTickGap={24} />
            <YAxis
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              label={{ value: data.value_column, angle: -90, position: "insideLeft", fill: "#64748b", fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
              formatter={(value, name) => [formatNumber(Number(value)), String(name)]}
              labelFormatter={(label) => `${label} (${data.granularity})`}
            />
            <Line type="monotone" dataKey="mean" name="Average" stroke="#fb923c" strokeWidth={2} dot={rows.length <= 60} />
            <Line type="monotone" dataKey="maximum" name="Maximum" stroke="#fb923c" strokeOpacity={0.35} strokeDasharray="4 4" dot={false} />
            <Line type="monotone" dataKey="minimum" name="Minimum" stroke="#fb923c" strokeOpacity={0.35} strokeDasharray="4 4" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Explanation>
        {data.total_observations.toLocaleString()} rows with a valid date and value, grouped by {data.granularity}.
        Python picks the finest period that keeps the chart readable, so long date ranges group into larger
        periods automatically. Each period&apos;s average is computed from every row in it, not from a sample.
      </Explanation>
    </>
  );
}
