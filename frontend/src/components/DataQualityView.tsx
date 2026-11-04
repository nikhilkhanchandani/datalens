import type { IssueSeverity, QualityIssue, QualityReport } from "@/lib/api";
import type { CleanFocus } from "./cleaning/CleanView";

const SEVERITY_STYLES: Record<IssueSeverity, string> = {
  high: "bg-red-950 text-red-300 border-red-800",
  medium: "bg-amber-950 text-amber-300 border-amber-800",
  low: "bg-slate-800 text-slate-300 border-slate-700",
};

function scoreColor(score: number): string {
  if (score >= 90) return "text-emerald-400";
  if (score >= 70) return "text-amber-400";
  return "text-red-400";
}

function scoreRingColor(score: number): string {
  if (score >= 90) return "stroke-emerald-400";
  if (score >= 70) return "stroke-amber-400";
  return "stroke-red-400";
}

function ScoreGauge({ score }: { score: number }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - score / 100);

  return (
    <div className="relative h-36 w-36 shrink-0">
      <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
        <circle
          cx="60"
          cy="60"
          r={radius}
          strokeWidth="10"
          className="fill-none stroke-slate-800"
        />
        <circle
          cx="60"
          cy="60"
          r={radius}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={`fill-none transition-[stroke-dashoffset] duration-500 ${scoreRingColor(score)}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-4xl font-semibold ${scoreColor(score)}`}>
          {score}
        </span>
        <span className="text-xs text-slate-500">/ 100</span>
      </div>
    </div>
  );
}

function fixFor(issue: QualityIssue): CleanFocus | null {
  switch (issue.type) {
    case "missing_values":
      return { operation: "fill_missing", column: issue.column ?? undefined };
    case "blank_strings":
      return { operation: "normalize_text", column: issue.column ?? undefined };
    case "duplicate_rows":
      return { operation: "remove_duplicates" };
    default:
      return null;
  }
}

function IssueCard({ issue, onFix }: { issue: QualityIssue; onFix?: (focus: CleanFocus) => void }) {
  const focus = fixFor(issue);
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded border px-2 py-0.5 text-xs font-medium uppercase ${SEVERITY_STYLES[issue.severity]}`}
        >
          {issue.severity}
        </span>
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {issue.type.replace(/_/g, " ")}
        </span>
        {issue.column && (
          <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
            {issue.column}
          </span>
        )}
        <span className="ml-auto text-xs text-slate-500">
          {issue.affected_rows.toLocaleString()} row(s) · {issue.percentage}%
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-200">{issue.message}</p>
      <p className="mt-1 text-sm text-slate-500">
        Suggested action: {issue.suggested_action}
      </p>
      {focus && onFix && (
        <button
          type="button"
          onClick={() => onFix(focus)}
          className="mt-3 text-sm text-sky-400 hover:underline"
        >
          Fix in Clean tab →
        </button>
      )}
    </div>
  );
}

export function DataQualityView({
  report,
  onFix,
}: {
  report: QualityReport;
  onFix?: (focus: CleanFocus) => void;
}) {
  return (
    <div className="w-full max-w-5xl space-y-8">
      <div className="flex flex-col items-center gap-6 rounded-lg border border-slate-800 bg-slate-900 p-6 sm:flex-row">
        <ScoreGauge score={report.score} />
        <div className="flex-1">
          <h2 className="text-lg font-semibold text-slate-100">
            Data Quality Score
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Starts at 100 and loses points per category of detected problem,
            each capped so no single issue can dominate the score.
          </p>
          {report.breakdown.length > 0 ? (
            <ul className="mt-4 space-y-1.5">
              {report.breakdown.map((entry) => (
                <li
                  key={entry.category}
                  className="flex items-center justify-between gap-4 text-sm"
                >
                  <span className="text-slate-400">{entry.reason}</span>
                  <span className="shrink-0 font-mono text-red-400">
                    -{entry.penalty}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-sm text-emerald-400">
              No quality problems detected.
            </p>
          )}
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-slate-100">
          Detected Issues {report.issues.length > 0 && `(${report.issues.length})`}
        </h2>
        {report.issues.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">
            No data quality issues were detected in this dataset.
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {report.issues.map((issue, index) => (
              <IssueCard
                key={`${issue.type}-${issue.column ?? "dataset"}-${index}`}
                issue={issue}
                onFix={onFix}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
