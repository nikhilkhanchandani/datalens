"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getHistogram, type ColumnStatistics, type HistogramData } from "@/lib/api";
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

interface BinRow {
  label: string;
  count: number;
}

function toRows(data: HistogramData): BinRow[] {
  return data.bins.map((bin) => ({
    label: `${formatNumber(bin.start)} – ${formatNumber(bin.end)}`,
    count: bin.count,
  }));
}

export function HistogramCard({
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
    () => getHistogram(datasetId, column ?? ""),
  );

  return (
    <ChartCard
      title="Histogram"
      description="How the values of one numeric column are spread across ranges (bins). Taller bars mean more rows fall in that range."
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

      {state.status === "ready" && state.data.total_observations === 0 && (
        <p className="text-sm text-slate-500">No usable numeric values to plot.</p>
      )}

      {state.status === "ready" && state.data.total_observations > 0 && (
        <>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={toRows(state.data)} barCategoryGap={1}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="label"
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  interval="preserveStartEnd"
                  label={{ value: state.data.column, position: "insideBottom", offset: -4, fill: "#64748b", fontSize: 12 }}
                />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} label={{ value: "Rows", angle: -90, position: "insideLeft", fill: "#64748b", fontSize: 12 }} />
                <Tooltip
                  cursor={{ fill: "#1e293b" }}
                  contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
                  formatter={(value) => [`${value} rows`, "Count"]}
                />
                <Bar dataKey="count" fill="#38bdf8" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <Explanation>
            {state.data.total_observations.toLocaleString()} usable values ·{" "}
            {state.data.bins.length} bins ({state.data.bin_strategy}).
            {state.data.missing_count > 0 &&
              ` ${state.data.missing_count.toLocaleString()} missing values excluded.`}
            {state.data.infinite_count > 0 &&
              ` ${state.data.infinite_count.toLocaleString()} infinite values excluded.`}
            {state.data.is_constant &&
              " Every usable value is identical, so all rows fall in one bin."}
          </Explanation>
        </>
      )}
    </ChartCard>
  );
}
