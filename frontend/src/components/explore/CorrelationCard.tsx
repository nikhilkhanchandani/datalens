"use client";

import { useState } from "react";
import {
  getCorrelations,
  type CorrelationMethod,
  type CorrelationReport,
} from "@/lib/api";
import { useKeyedFetch } from "@/hooks/useKeyedFetch";
import { ChartCard, ChartError, ChartLoading, Explanation } from "./shared";

const METHODS: { id: CorrelationMethod; label: string }[] = [
  { id: "pearson", label: "Pearson" },
  { id: "spearman", label: "Spearman" },
];

export function CorrelationCard({ datasetId }: { datasetId: string }) {
  const [method, setMethod] = useState<CorrelationMethod>("pearson");
  const state = useKeyedFetch(`${datasetId}:${method}`, () =>
    getCorrelations(datasetId, method),
  );

  return (
    <ChartCard
      title="Correlation Heatmap"
      description="How strongly each pair of numeric columns moves together. +1 means they rise together perfectly, −1 means one rises as the other falls, and 0 means no linear link."
      controls={
        <div className="flex overflow-hidden rounded border border-slate-700 text-xs">
          {METHODS.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => setMethod(option.id)}
              className={`px-3 py-1.5 transition-colors ${
                method === option.id
                  ? "bg-sky-500/20 text-sky-300"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      }
    >
      {state.status === "loading" && <ChartLoading />}
      {state.status === "error" && (
        <ChartError message={state.message} />
      )}
      {state.status === "ready" && <Heatmap report={state.data} />}
    </ChartCard>
  );
}

function cellColor(value: number | null): string {
  if (value === null) return "transparent";
  const alpha = Math.min(Math.abs(value), 1) * 0.85;
  return value >= 0
    ? `rgba(56, 189, 248, ${alpha})`
    : `rgba(248, 113, 113, ${alpha})`;
}

function Heatmap({ report }: { report: CorrelationReport }) {
  const methodLabel = report.method === "pearson" ? "Pearson" : "Spearman";

  return (
    <>
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-1 text-xs">
          <thead>
            <tr>
              <th className="p-1" />
              {report.columns.map((column) => (
                <th key={column} className="max-w-[7rem] truncate p-1 text-left font-medium text-slate-400" title={column}>
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {report.columns.map((rowName, rowIndex) => (
              <tr key={rowName}>
                <th className="max-w-[9rem] truncate p-1 text-right font-medium text-slate-400" title={rowName}>
                  {rowName}
                </th>
                {report.matrix[rowIndex].map((value, colIndex) => (
                  <td
                    key={`${rowName}-${report.columns[colIndex]}`}
                    className="h-12 w-20 rounded text-center font-mono text-slate-100"
                    style={{ background: cellColor(value) }}
                    title={`${rowName} vs ${report.columns[colIndex]}: ${value === null ? "undefined" : value.toFixed(3)} (${methodLabel})`}
                  >
                    {value === null ? "—" : value.toFixed(2)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center gap-3 text-xs text-slate-500">
        <span>−1</span>
        <div
          className="h-2 w-48 rounded"
          style={{ background: "linear-gradient(to right, rgba(248,113,113,0.85), transparent, rgba(56,189,248,0.85))" }}
        />
        <span>+1</span>
      </div>

      {report.strong_pairs.length > 0 && (
        <div className="mt-5">
          <h4 className="text-sm font-medium text-slate-300">
            Strong relationships (|{methodLabel} r| ≥ {report.strong_threshold})
          </h4>
          <ul className="mt-2 space-y-1 text-sm text-slate-400">
            {report.strong_pairs.map((pair) => (
              <li key={`${pair.x}-${pair.y}`}>
                {pair.x} ↔ {pair.y}:{" "}
                <span className={pair.direction === "positive" ? "text-sky-300" : "text-red-300"}>
                  {pair.r > 0 ? "+" : ""}
                  {pair.r.toFixed(2)} ({pair.direction})
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.excluded_columns.length > 0 && (
        <p className="mt-4 text-xs text-slate-500">
          Not included:{" "}
          {report.excluded_columns.map((e) => `${e.name} (${e.reason})`).join("; ")}.
        </p>
      )}

      <Explanation>
        {methodLabel} measures {report.method === "pearson"
          ? "linear association between the raw values."
          : "how consistently one column rises or falls with another, using ranks, so it also catches curved but consistent relationships."}{" "}
        Each cell uses only the rows where both columns have values. {report.disclaimer}
      </Explanation>
    </>
  );
}
