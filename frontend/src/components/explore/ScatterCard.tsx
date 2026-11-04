"use client";

import { useState } from "react";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getScatter, type ColumnStatistics, type ScatterData } from "@/lib/api";
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

export function ScatterCard({
  datasetId,
  columns,
}: {
  datasetId: string;
  columns: ColumnStatistics[];
}) {
  const options = columnsOfKinds(columns, ["numeric"]);
  const [xSelected, setXSelected] = useState<string | undefined>(preferNonIdentifiers(options)[0]?.name);
  const [ySelected, setYSelected] = useState<string | undefined>(preferNonIdentifiers(options)[1]?.name ?? preferNonIdentifiers(options)[0]?.name);
  const x = xSelected ?? preferNonIdentifiers(options)[0]?.name;
  const y = ySelected ?? preferNonIdentifiers(options)[1]?.name ?? preferNonIdentifiers(options)[0]?.name;
  const sameAxis = x !== undefined && x === y;
  const state = useKeyedFetch(
    x && y && !sameAxis ? `${datasetId}:${x}:${y}` : null,
    () => getScatter(datasetId, x ?? "", y ?? ""),
  );

  return (
    <ChartCard
      title="Scatter Plot"
      description="Each dot is one row, placed by its values in two numeric columns. Look for a pattern: points rising together suggest a positive association, falling together a negative one."
      controls={
        options.length > 0 && (
          <>
            <ColumnSelect label="X" value={x ?? ""} columns={columns} kinds={["numeric"]} onChange={setXSelected} />
            <ColumnSelect label="Y" value={y ?? ""} columns={columns} kinds={["numeric"]} onChange={setYSelected} />
          </>
        )
      }
    >
      {options.length === 0 && <NoCompatibleColumns needs="numeric" />}
      {options.length === 1 && (
        <p className="text-sm text-slate-500">A scatter plot needs two different numeric columns.</p>
      )}
      {sameAxis && options.length > 1 && (
        <p className="text-sm text-slate-500">Choose two different columns for X and Y.</p>
      )}

      {!sameAxis && state.status === "loading" && <ChartLoading />}
      {!sameAxis && state.status === "error" && <ChartError message={state.message} />}
      {!sameAxis && state.status === "ready" && <Plot data={state.data} />}
    </ChartCard>
  );
}

function Plot({ data }: { data: ScatterData }) {
  if (data.total_points < 2) {
    return <p className="text-sm text-slate-500">Not enough rows where both columns have values.</p>;
  }

  return (
    <>
      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 16, bottom: 16, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              type="number"
              dataKey="x"
              name={data.x_column}
              domain={["auto", "auto"]}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              label={{ value: data.x_column, position: "insideBottom", offset: -8, fill: "#64748b", fontSize: 12 }}
            />
            <YAxis
              type="number"
              dataKey="y"
              name={data.y_column}
              domain={["auto", "auto"]}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              label={{ value: data.y_column, angle: -90, position: "insideLeft", fill: "#64748b", fontSize: 12 }}
            />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
              formatter={(value, name) => [formatNumber(Number(value)), String(name)]}
            />
            <Scatter data={data.points} fill="#34d399" fillOpacity={0.6} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <Explanation>
        Pearson r = {data.pearson_r === null ? "undefined" : data.pearson_r.toFixed(3)} across all{" "}
        {data.total_points.toLocaleString()} rows where both columns have values. {" "}
        {data.sampled
          ? `Plotting a deterministic sample of ${data.returned_points.toLocaleString()} points (the chart is capped at ${data.max_points.toLocaleString()} so large datasets stay fast). Refreshing returns the same sample. `
          : "All points are plotted. "}
        A strong r describes how closely the columns move together; it does not show that one causes the other.
      </Explanation>
    </>
  );
}
