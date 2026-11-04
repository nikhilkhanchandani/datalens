"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { uploadDataset } from "@/lib/api";
import { formatBytes } from "@/lib/format";

const MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024; // keep in sync with backend default

type UploadState =
  | { phase: "idle" }
  | { phase: "uploading"; fileName: string }
  | { phase: "error"; message: string };

function validateFileClientSide(file: File): string | null {
  if (!file.name.toLowerCase().endsWith(".csv")) {
    return "Only .csv files are supported.";
  }
  if (file.size === 0) {
    return "This file is empty.";
  }
  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return `File is too large (${formatBytes(file.size)}). Limit is ${formatBytes(MAX_UPLOAD_SIZE_BYTES)}.`;
  }
  return null;
}

export function UploadForm() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<UploadState>({ phase: "idle" });
  const [isDragging, setIsDragging] = useState(false);

  async function handleFile(file: File) {
    const clientError = validateFileClientSide(file);
    if (clientError) {
      setState({ phase: "error", message: clientError });
      return;
    }

    setState({ phase: "uploading", fileName: file.name });
    try {
      const dataset = await uploadDataset(file);
      router.push(`/datasets/${dataset.id}`);
    } catch (error) {
      setState({
        phase: "error",
        message: error instanceof Error ? error.message : "Upload failed.",
      });
    }
  }

  function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) void handleFile(file);
  }

  function handleInputChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void handleFile(file);
    event.target.value = "";
  }

  const isUploading = state.phase === "uploading";

  return (
    <div className="w-full max-w-xl">
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-8 py-14 text-center transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400 ${
          isDragging
            ? "border-sky-400 bg-sky-950/30"
            : "border-slate-700 bg-slate-900/50 hover:border-slate-600"
        } ${isUploading ? "pointer-events-none opacity-60" : ""}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={handleInputChange}
          disabled={isUploading}
        />

        {isUploading ? (
          <>
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-sky-400" />
            <p className="text-sm text-slate-300">
              Uploading {state.fileName}…
            </p>
          </>
        ) : (
          <>
            <p className="text-base font-medium text-slate-200">
              Drag and drop a CSV file here
            </p>
            <p className="text-sm text-slate-500">or click to browse</p>
          </>
        )}
      </div>

      {state.phase === "error" && (
        <p className="mt-3 rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-300">
          {state.message}
        </p>
      )}
    </div>
  );
}
