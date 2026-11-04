"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import {
  getDataset,
  getDatasetProfile,
  getDatasetQuality,
  getDatasetStatistics,
  type DatasetProfile,
  type DatasetResponse,
  type DatasetStatistics,
  type QualityReport,
} from "@/lib/api";
import { DatasetProfileView } from "@/components/DatasetProfileView";
import { DataQualityView } from "@/components/DataQualityView";
import { StatisticsView } from "@/components/StatisticsView";
import { ExploreView } from "@/components/ExploreView";
import { CleanView, type CleanFocus } from "@/components/cleaning/CleanView";
import { CompareView } from "@/components/compare/CompareView";

type LoadState =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | {
      phase: "ready";
      dataset: DatasetResponse;
      profile: DatasetProfile;
      quality: QualityReport;
      statistics: DatasetStatistics;
    };

type Tab = "profile" | "quality" | "statistics" | "explore" | "clean" | "compare";

const TABS: { id: Tab; label: string }[] = [
  { id: "profile", label: "Profile" },
  { id: "quality", label: "Data Quality" },
  { id: "statistics", label: "Statistics" },
  { id: "explore", label: "Explore" },
  { id: "clean", label: "Clean" },
  { id: "compare", label: "Compare & Export" },
];

export default function DatasetPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [state, setState] = useState<LoadState>({ phase: "loading" });
  const [activeTab, setActiveTab] = useState<Tab>("profile");
  const [cleanFocus, setCleanFocus] = useState<CleanFocus | null>(null);

  // Every analysis is re-fetched from the server after a cleaning step, so the
  // page never shows numbers computed from an earlier version of the data.
  // Bumping `reloadCount` re-runs the fetch below.
  const [reloadCount, setReloadCount] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.all([
      getDataset(id),
      getDatasetProfile(id),
      getDatasetQuality(id),
      getDatasetStatistics(id),
    ])
      .then(([dataset, profile, quality, statistics]) => {
        if (active) setState({ phase: "ready", dataset, profile, quality, statistics });
      })
      .catch((error: unknown) => {
        if (active) {
          setState({
            phase: "error",
            message: error instanceof Error ? error.message : "Failed to load dataset.",
          });
        }
      });
    return () => {
      active = false;
    };
  }, [id, reloadCount]);

  function openClean(focus: CleanFocus) {
    setCleanFocus(focus);
    setActiveTab("clean");
  }

  return (
    <main className="flex min-h-screen flex-col items-center gap-6 bg-slate-950 px-4 py-16 text-slate-100">
      <div className="flex w-full max-w-5xl flex-col gap-4">
        <Link href="/" className="self-start text-sm text-sky-400 hover:underline">
          ← Upload another dataset
        </Link>

        {state.phase === "ready" && (
          <>
            <div role="tablist" aria-label="Dataset sections" className="flex gap-1 overflow-x-auto border-b border-slate-800">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`whitespace-nowrap px-4 py-2 text-sm font-medium transition-colors focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400 ${
                    activeTab === tab.id
                      ? "border-b-2 border-sky-400 text-sky-400"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {tab.label}
                  {tab.id === "quality" && ` (${state.quality.score})`}
                </button>
              ))}
            </div>
            {state.dataset.working_version > 0 && (
              <p className="rounded border border-amber-900 bg-amber-950/40 px-4 py-2 text-xs text-amber-300">
                Analysis is on the cleaned working copy (version {state.dataset.working_version}).
                The uploaded file, {state.dataset.original_filename}, is unchanged.
              </p>
            )}
          </>
        )}
      </div>

      {state.phase === "loading" && (
        <div className="w-full max-w-5xl animate-pulse space-y-4">
          <div className="h-8 w-64 rounded bg-slate-800" />
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-20 rounded-lg bg-slate-900" />
            ))}
          </div>
          <div className="h-64 rounded-lg bg-slate-900" />
        </div>
      )}

      {state.phase === "error" && (
        <p className="rounded-lg border border-red-900 bg-red-950/50 px-4 py-3 text-sm text-red-300">
          {state.message}
        </p>
      )}

      {state.phase === "ready" && activeTab === "profile" && (
        <DatasetProfileView dataset={state.dataset} profile={state.profile} />
      )}
      {state.phase === "ready" && activeTab === "quality" && (
        <DataQualityView report={state.quality} onFix={openClean} />
      )}
      {state.phase === "ready" && activeTab === "statistics" && (
        <StatisticsView statistics={state.statistics} />
      )}
      {state.phase === "ready" && activeTab === "explore" && (
        <ExploreView datasetId={id} columns={state.statistics.columns} />
      )}
      {state.phase === "ready" && activeTab === "clean" && (
        <CleanView
          datasetId={id}
          profile={state.profile}
          focus={cleanFocus}
          onApplied={() => setReloadCount((count) => count + 1)}
        />
      )}
      {state.phase === "ready" && activeTab === "compare" && (
        <CompareView datasetId={id} workingVersion={state.dataset.working_version} />
      )}
    </main>
  );
}
