"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getCategoricalFrequencies,
  type CategoricalFrequencies,
  type ColumnStatistics,
} from "@/lib/api";
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

const TOP_N_CHOICES = [10, 20, 50] as const;
const CATEGORY_KINDS = ["categorical", "boolean"] as const;

export function CategoricalCard({
  datasetId,
  columns,
}: {
  datasetId: string;
  columns: ColumnStatistics[];
}) {
  const options = columnsOfKinds(columns, [...CATEGORY_KINDS]);
  const [selected, setSelected] = useState<string | undefined>(preferNonIdentifiers(options)[0]?.name);
  const [topN, setTopN] = useState<number>(TOP_N_CHOICES[1]);
  const column = selected ?? preferNonIdentifiers(options)[0]?.name;
  const state = useKeyedFetch(
    column ? `${datasetId}:${column}:${topN}` : null,
    () => getCategoricalFrequencies(datasetId, column ?? "", topN),
  );

  return (
    <ChartCard
      title="Categorical Frequency"
      description="How often each category appears in a text or true/false column. Only the most common categories are drawn; the rest are grouped as Other."
      controls={
        options.length > 0 && (
          <>
            <ColumnSelect
              label="Column"
              value={column ?? ""}
              columns={columns}
              kinds={[...CATEGORY_KINDS]}
              onChange={setSelected}
            />
            <label className="flex items-center gap-2 text-xs text-slate-400">
              <span className="uppercase tracking-wide">Top</span>
              <select
                value={topN}
                onChange={(event) => setTopN(Number(event.target.value))}
                className="rounded border border-slate-700 bg-slate-800 px-2 py-1 text-sm text-slate-200"
              >
                {TOP_N_CHOICES.map((choice) => (
                  <option key={choice} value={choice}>
                    {choice}
                  </option>
                ))}
              </select>
            </label>
          </>
        )
      }
    >
      {options.length === 0 && <NoCompatibleColumns needs="categorical or true/false" />}

      {state.status === "loading" && <ChartLoading />}
      {state.status === "error" && <ChartError message={state.message} />}

      {state.status === "ready" && <FrequencyChart data={state.data} />}
    </ChartCard>
  );
}

function FrequencyChart({ data }: { data: CategoricalFrequencies }) {
  if (data.items.length === 0) {
    return <p className="text-sm text-slate-500">No non-missing values to count.</p>;
  }

  const height = Math.max(200, data.items.length * 28 + 40);

  return (
    <>
      <div style={{ height }} className="w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data.items} layout="vertical" margin={{ left: 8, right: 24 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
            <XAxis
              type="number"
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              label={{ value: "Rows", position: "insideBottom", offset: -2, fill: "#64748b", fontSize: 12 }}
            />
            <YAxis
              type="category"
              dataKey="value"
              width={140}
              tick={{ fill: "#cbd5e1", fontSize: 11 }}
            />
            <Tooltip
              cursor={{ fill: "#1e293b" }}
              contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
              formatter={(value, _name, item) => {
                const payload = item.payload as { percentage: number };
                return [`${value} rows (${payload.percentage}%)`, "Count"];
              }}
            />
            <Bar dataKey="count">
              {data.items.map((item) => (
                <Cell key={item.value} fill={item.is_other ? "#64748b" : "#a78bfa"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <Explanation>
        {data.total_count.toLocaleString()} non-missing values across {data.unique_count.toLocaleString()} distinct categories.
        {data.truncated
          ? ` Showing the top ${data.top_n}; the remaining categories are grouped as Other.`
          : " All categories are shown."}
        {data.missing_count > 0 &&
          ` ${data.missing_count.toLocaleString()} missing values are not counted.`}
      </Explanation>
    </>
  );
}
