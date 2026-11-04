"use client";

import { useState, type ReactNode } from "react";
import { applyCleaning, type CleaningRequest, type TransformationResult } from "@/lib/api";
import { formatNumber } from "@/lib/format";

/**
 * Every cleaning action follows the same path: the user edits inputs, reviews
 * a plain-language description of exactly what will change, then applies it.
 * The panel never sends a request on input change. The review step is keyed
 * to the request itself, so editing any input returns the panel to editing.
 */
export function OperationPanel({
  datasetId,
  title,
  description,
  request,
  preview,
  destructive = false,
  disabledReason,
  highlighted = false,
  onApplied,
  children,
}: {
  datasetId: string;
  title: string;
  description: string;
  request: CleaningRequest | null;
  preview: string;
  destructive?: boolean;
  disabledReason?: string;
  highlighted?: boolean;
  onApplied: () => void;
  children: ReactNode;
}) {
  const requestKey = request ? JSON.stringify(request) : null;
  const [reviewedKey, setReviewedKey] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<TransformationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reviewing = requestKey !== null && reviewedKey === requestKey;

  async function apply() {
    if (!request) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const outcome = await applyCleaning(datasetId, request);
      setResult(outcome);
      setReviewedKey(null);
      onApplied();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The change could not be applied.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section
      className={`rounded-lg border bg-slate-900 p-5 transition-colors ${
        highlighted ? "border-sky-500/70" : "border-slate-800"
      }`}
    >
      <h3 className="font-medium text-slate-100">{title}</h3>
      <p className="mt-1 max-w-3xl text-sm text-slate-500">{description}</p>

      <div className="mt-4 space-y-3">{children}</div>

      {disabledReason && request === null && (
        <p className="mt-4 text-xs text-slate-500">{disabledReason}</p>
      )}

      {request !== null && !reviewing && (
        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            onClick={() => setReviewedKey(requestKey)}
            disabled={submitting}
            className="rounded bg-slate-700 px-3 py-1.5 text-sm text-slate-100 hover:bg-slate-600 disabled:opacity-50"
          >
            Review change
          </button>
        </div>
      )}

      {request !== null && reviewing && (
        <div
          className={`mt-4 rounded border p-4 text-sm ${
            destructive ? "border-red-900 bg-red-950/30" : "border-slate-700 bg-slate-950/50"
          }`}
        >
          <p className="text-slate-200">{preview}</p>
          {destructive && (
            <p className="mt-2 text-xs text-red-300">
              This removes data from the working copy. The original upload file is kept unchanged,
              but there is no undo yet.
            </p>
          )}
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={apply}
              disabled={submitting}
              className={`rounded px-3 py-1.5 text-sm font-medium disabled:opacity-50 ${
                destructive ? "bg-red-600 text-white hover:bg-red-500" : "bg-sky-600 text-white hover:bg-sky-500"
              }`}
            >
              {submitting ? "Applying…" : destructive ? "Confirm and apply" : "Apply"}
            </button>
            <button
              type="button"
              onClick={() => setReviewedKey(null)}
              disabled={submitting}
              className="rounded px-3 py-1.5 text-sm text-slate-400 hover:text-slate-200"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {result && (
        <p className="mt-4 rounded border border-emerald-900 bg-emerald-950/40 px-4 py-3 text-sm text-emerald-300">
          {result.summary} Rows: {formatNumber(result.rows_before)} → {formatNumber(result.rows_after)}.
          Working copy is now version {result.working_version}.
        </p>
      )}

      {error && (
        <p className="mt-4 rounded border border-red-900 bg-red-950/50 px-4 py-3 text-sm text-red-300">
          {error}
        </p>
      )}
    </section>
  );
}
