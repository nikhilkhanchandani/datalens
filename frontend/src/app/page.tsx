"use client";

import { useEffect, useState } from "react";
import { getHealth, type HealthResponse } from "@/lib/api";
import { UploadForm } from "@/components/UploadForm";

type ApiStatus =
  | { state: "loading" }
  | { state: "online"; data: HealthResponse }
  | { state: "offline"; error: string };

export default function Home() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>({ state: "loading" });

  useEffect(() => {
    getHealth()
      .then((data) => setApiStatus({ state: "online", data }))
      .catch((error: Error) =>
        setApiStatus({ state: "offline", error: error.message }),
      );
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-10 bg-slate-950 px-4 py-16 text-slate-100">
      <div className="text-center">
        <h1 className="text-5xl font-semibold tracking-tight">DataLens</h1>
        <p className="mt-3 text-lg text-slate-400">
          Turn raw datasets into actionable insights.
        </p>
      </div>

      <UploadForm />

      <div className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900 px-4 py-2 text-xs text-slate-400">
        <span
          className={`h-2 w-2 rounded-full ${
            apiStatus.state === "online"
              ? "bg-emerald-500"
              : apiStatus.state === "offline"
                ? "bg-red-500"
                : "bg-amber-500"
          }`}
        />
        {apiStatus.state === "loading" && <span>Connecting to API…</span>}
        {apiStatus.state === "online" && (
          <span>
            API online — {apiStatus.data.service} ({apiStatus.data.environment})
          </span>
        )}
        {apiStatus.state === "offline" && (
          <span>API offline — {apiStatus.error}</span>
        )}
      </div>
    </main>
  );
}
