import type { ColumnStatistics } from "@/lib/api";
import { CorrelationCard } from "./explore/CorrelationCard";
import { CategoricalCard } from "./explore/CategoricalCard";
import { DatetimeTrendCard } from "./explore/DatetimeTrendCard";
import { DistributionCard } from "./explore/DistributionCard";
import { HistogramCard } from "./explore/HistogramCard";
import { ScatterCard } from "./explore/ScatterCard";

const GLOSSARY: { term: string; meaning: string }[] = [
  {
    term: "Pearson correlation (r)",
    meaning:
      "Measures how well a straight line fits two columns, from −1 (perfect inverse line) through 0 (no linear link) to +1 (perfect line).",
  },
  {
    term: "Spearman correlation (ρ)",
    meaning:
      "Pearson correlation computed on ranks. It captures any consistent rising or falling pattern, and is less thrown off by extreme values.",
  },
  {
    term: "Quartiles & IQR",
    meaning:
      "Q1, the median, and Q3 split sorted values into four equal-count groups. The IQR (Q3 − Q1) is the width of the middle half of the data.",
  },
  {
    term: "Histogram bins",
    meaning:
      "The value range is cut into equal-width intervals; each bar counts how many values fall inside its interval.",
  },
  {
    term: "Correlation ≠ causation",
    meaning:
      "Two columns moving together doesn't show that one drives the other. A hidden third factor can produce the same pattern.",
  },
];

export function ExploreView({
  datasetId,
  columns,
}: {
  datasetId: string;
  columns: ColumnStatistics[];
}) {
  return (
    <div className="w-full max-w-5xl space-y-6">
      <details className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm">
        <summary className="cursor-pointer font-medium text-slate-300">
          Statistics glossary
        </summary>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
          {GLOSSARY.map((entry) => (
            <div key={entry.term}>
              <dt className="font-medium text-slate-200">{entry.term}</dt>
              <dd className="mt-1 text-slate-400">{entry.meaning}</dd>
            </div>
          ))}
        </dl>
      </details>

      <CorrelationCard datasetId={datasetId} />
      <HistogramCard datasetId={datasetId} columns={columns} />
      <CategoricalCard datasetId={datasetId} columns={columns} />
      <ScatterCard datasetId={datasetId} columns={columns} />
      <DistributionCard datasetId={datasetId} columns={columns} />
      <DatetimeTrendCard datasetId={datasetId} columns={columns} />
    </div>
  );
}
