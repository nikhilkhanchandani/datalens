"use client";

import { useState } from "react";
import type {
  CleaningRequest,
  ColumnKind,
  ConversionTarget,
  DatasetProfile,
  FillStrategy,
} from "@/lib/api";
import { OperationPanel } from "./OperationPanel";

/** Where the user arrived from, e.g. a "Fix in Clean tab" button on a quality issue. */
export interface CleanFocus {
  operation: "fill_missing" | "remove_duplicates" | "normalize_text";
  column?: string;
}

const FILL_STRATEGIES: Record<ColumnKind, { value: FillStrategy; label: string }[]> = {
  numeric: [
    { value: "median", label: "Median (robust to extreme values)" },
    { value: "mean", label: "Mean (sensitive to extreme values)" },
    { value: "custom", label: "Custom number" },
    { value: "remove_rows", label: "Remove rows with a missing value" },
  ],
  categorical: [
    { value: "mode", label: "Most common value" },
    { value: "custom", label: "Custom text" },
    { value: "remove_rows", label: "Remove rows with a missing value" },
  ],
  boolean: [
    { value: "mode", label: "Most common value" },
    { value: "custom", label: "Custom true/false" },
    { value: "remove_rows", label: "Remove rows with a missing value" },
  ],
  datetime: [
    { value: "custom", label: "Custom date (YYYY-MM-DD)" },
    { value: "remove_rows", label: "Remove rows with a missing value" },
  ],
};

const TARGET_LABELS: Record<ConversionTarget, string> = {
  numeric: "Number",
  datetime: "Date",
  boolean: "True / false",
  string: "Text",
};

const KIND_OF_TARGET: Record<ConversionTarget, ColumnKind> = {
  numeric: "numeric",
  datetime: "datetime",
  boolean: "boolean",
  string: "categorical",
};

const selectClass = "rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-200";
const inputClass = "rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-200";

export function CleanView({
  datasetId,
  profile,
  focus,
  onApplied,
}: {
  datasetId: string;
  profile: DatasetProfile;
  focus: CleanFocus | null;
  onApplied: () => void;
}) {
  return (
    <div className="w-full max-w-5xl space-y-6">
      <p className="text-sm text-slate-500">
        Nothing changes until you review and confirm an action. Each action applies to the working copy;
        the uploaded file is never modified.
      </p>
      <FillMissingPanel datasetId={datasetId} profile={profile} focus={focus} onApplied={onApplied} />
      <DuplicatesPanel datasetId={datasetId} profile={profile} focus={focus} onApplied={onApplied} />
      <TextPanel datasetId={datasetId} profile={profile} focus={focus} onApplied={onApplied} />
      <ConvertPanel datasetId={datasetId} profile={profile} onApplied={onApplied} />
      <RenamePanel datasetId={datasetId} profile={profile} onApplied={onApplied} />
      <DropPanel datasetId={datasetId} profile={profile} onApplied={onApplied} />
    </div>
  );
}

// --- missing values --------------------------------------------------------

function FillMissingPanel({
  datasetId,
  profile,
  focus,
  onApplied,
}: {
  datasetId: string;
  profile: DatasetProfile;
  focus: CleanFocus | null;
  onApplied: () => void;
}) {
  const defaultColumn =
    (focus?.operation === "fill_missing" && focus.column) ||
    profile.columns.find((c) => c.missing_count > 0)?.name ||
    profile.columns[0]?.name ||
    "";
  const [columnName, setColumnName] = useState(defaultColumn);
  const column = profile.columns.find((c) => c.name === columnName);
  const strategies = column ? FILL_STRATEGIES[column.kind] : [];
  const [strategy, setStrategy] = useState<FillStrategy>("median");
  const activeStrategy = strategies.some((s) => s.value === strategy) ? strategy : strategies[0]?.value;
  const [customText, setCustomText] = useState("");

  const missing = column?.missing_count ?? 0;
  let request: CleaningRequest | null = null;
  let disabledReason: string | undefined;
  let value: number | string | boolean | undefined;

  if (!column) {
    disabledReason = "This dataset has no columns.";
  } else if (missing === 0) {
    disabledReason = `'${column.name}' has no missing values.`;
  } else if (activeStrategy === "custom") {
    if (column.kind === "numeric") {
      const parsed = Number(customText);
      if (customText.trim() === "" || !Number.isFinite(parsed)) {
        disabledReason = "Enter a number to fill with.";
      } else {
        value = parsed;
      }
    } else if (column.kind === "boolean") {
      value = customText === "true";
      if (customText === "") disabledReason = "Choose true or false.";
    } else if (customText.trim() === "") {
      disabledReason = "Enter a value to fill with.";
    } else {
      value = customText;
    }
  }

  if (column && missing > 0 && activeStrategy && !disabledReason) {
    request = {
      operation: "fill_missing",
      column: column.name,
      strategy: activeStrategy,
      ...(activeStrategy === "custom" ? { value } : {}),
    };
  }

  const preview = describeFill(column?.name ?? "", missing, activeStrategy, value);

  return (
    <OperationPanel
      datasetId={datasetId}
      title="Fill missing values"
      description="Replace blank cells in one column with a value you choose, or remove the rows that have a blank. The strategy options depend on the column's type."
      request={request}
      preview={preview}
      destructive={activeStrategy === "remove_rows"}
      disabledReason={disabledReason}
      highlighted={focus?.operation === "fill_missing"}
      onApplied={onApplied}
    >
      <div className="flex flex-wrap gap-3">
        <label className="flex items-center gap-2 text-xs text-slate-400">
          <span className="uppercase tracking-wide">Column</span>
          <select
            value={columnName}
            onChange={(event) => {
              setColumnName(event.target.value);
              setCustomText("");
            }}
            className={selectClass}
          >
            {profile.columns.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name} ({c.missing_count} missing)
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-xs text-slate-400">
          <span className="uppercase tracking-wide">Strategy</span>
          <select
            value={activeStrategy ?? ""}
            onChange={(event) => setStrategy(event.target.value as FillStrategy)}
            className={selectClass}
          >
            {strategies.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        {activeStrategy === "custom" && column?.kind === "boolean" && (
          <label className="flex items-center gap-2 text-xs text-slate-400">
            <span className="uppercase tracking-wide">Value</span>
            <select value={customText} onChange={(e) => setCustomText(e.target.value)} className={selectClass}>
              <option value="">Choose…</option>
              <option value="true">true</option>
              <option value="false">false</option>
            </select>
          </label>
        )}
        {activeStrategy === "custom" && column?.kind !== "boolean" && (
          <label className="flex items-center gap-2 text-xs text-slate-400">
            <span className="uppercase tracking-wide">Value</span>
            <input
              type={column?.kind === "numeric" ? "number" : "text"}
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              placeholder={column?.kind === "datetime" ? "2024-01-31" : ""}
              className={inputClass}
            />
          </label>
        )}
      </div>
    </OperationPanel>
  );
}

function describeFill(column: string, missing: number, strategy: FillStrategy | undefined, value: unknown): string {
  if (!column || missing === 0 || !strategy) return "";
  const cells = `${missing.toLocaleString()} missing value(s) in '${column}'`;
  switch (strategy) {
    case "mean":
      return `Fill ${cells} with the column's mean.`;
    case "median":
      return `Fill ${cells} with the column's median.`;
    case "mode":
      return `Fill ${cells} with the most common value.`;
    case "custom":
      return `Fill ${cells} with "${String(value)}".`;
    case "remove_rows":
      return `Delete the ${missing.toLocaleString()} row(s) where '${column}' is missing. Other values in those rows are lost.`;
  }
}

// --- duplicates ------------------------------------------------------------

function DuplicatesPanel({
  datasetId,
  profile,
  focus,
  onApplied,
}: {
  datasetId: string;
  profile: DatasetProfile;
  focus: CleanFocus | null;
  onApplied: () => void;
}) {
  const [scope, setScope] = useState<"all" | "subset">("all");
  const [subset, setSubset] = useState<string[]>([]);
  const duplicates = profile.duplicate_row_count;

  let request: CleaningRequest | null = null;
  let disabledReason: string | undefined;
  if (scope === "all") {
    if (duplicates === 0) disabledReason = "No duplicate rows were found in this dataset.";
    else request = { operation: "remove_duplicates", subset: null };
  } else if (subset.length === 0) {
    disabledReason = "Choose the columns that must match for two rows to count as duplicates.";
  } else {
    request = { operation: "remove_duplicates", subset };
  }

  const preview =
    scope === "all"
      ? `Remove ${duplicates.toLocaleString()} row(s) that exactly match an earlier row, keeping the first occurrence.`
      : `Remove rows that match an earlier row on ${subset.join(", ")}, keeping the first occurrence. Other columns may differ.`;

  return (
    <OperationPanel
      datasetId={datasetId}
      title="Remove duplicate rows"
      description="Keeps the first occurrence of each repeated row. By default two rows are duplicates only when every column matches."
      request={request}
      preview={preview}
      destructive
      disabledReason={disabledReason}
      highlighted={focus?.operation === "remove_duplicates"}
      onApplied={onApplied}
    >
      <div className="flex flex-wrap gap-4 text-sm text-slate-300">
        <label className="flex items-center gap-2">
          <input type="radio" checked={scope === "all"} onChange={() => setScope("all")} />
          Every column must match ({duplicates.toLocaleString()} found)
        </label>
        <label className="flex items-center gap-2">
          <input type="radio" checked={scope === "subset"} onChange={() => setScope("subset")} />
          Only these columns must match
        </label>
      </div>
      {scope === "subset" && (
        <CheckboxGroup
          options={profile.columns.map((c) => c.name)}
          selected={subset}
          onChange={setSubset}
        />
      )}
    </OperationPanel>
  );
}

// --- text normalization ----------------------------------------------------

function TextPanel({
  datasetId,
  profile,
  focus,
  onApplied,
}: {
  datasetId: string;
  profile: DatasetProfile;
  focus: CleanFocus | null;
  onApplied: () => void;
}) {
  const textColumns = profile.columns.filter((c) => c.kind === "categorical").map((c) => c.name);
  const [selected, setSelected] = useState<string[]>(() =>
    focus?.operation === "normalize_text" && focus.column ? [focus.column] : [],
  );
  const [trim, setTrim] = useState(true);
  const [blankToMissing, setBlankToMissing] = useState(true);

  let request: CleaningRequest | null = null;
  let disabledReason: string | undefined;
  if (textColumns.length === 0) disabledReason = "This dataset has no text columns to clean.";
  else if (selected.length === 0) disabledReason = "Choose at least one text column.";
  else if (!trim && !blankToMissing) disabledReason = "Choose trimming, blank-to-missing, or both.";
  else request = { operation: "normalize_text", columns: selected, trim, blank_to_missing: blankToMissing };

  const actions = [trim && "remove spaces at the start and end", blankToMissing && "turn whitespace-only cells into missing values"]
    .filter(Boolean)
    .join(" and ");

  return (
    <OperationPanel
      datasetId={datasetId}
      title="Trim and normalize text"
      description="Only text columns are offered. Numeric and date columns are never altered by this action."
      request={request}
      preview={`In ${selected.join(", ") || "the chosen columns"}: ${actions || "nothing"}. Only cells that actually change are counted.`}
      disabledReason={disabledReason}
      highlighted={focus?.operation === "normalize_text"}
      onApplied={onApplied}
    >
      <CheckboxGroup options={textColumns} selected={selected} onChange={setSelected} />
      <div className="flex gap-4 text-sm text-slate-300">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={trim} onChange={(e) => setTrim(e.target.checked)} />
          Trim leading and trailing spaces
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={blankToMissing} onChange={(e) => setBlankToMissing(e.target.checked)} />
          Turn blank cells into missing values
        </label>
      </div>
    </OperationPanel>
  );
}

// --- type conversion -------------------------------------------------------

function ConvertPanel({
  datasetId,
  profile,
  onApplied,
}: {
  datasetId: string;
  profile: DatasetProfile;
  onApplied: () => void;
}) {
  const [columnName, setColumnName] = useState(profile.columns[0]?.name ?? "");
  const column = profile.columns.find((c) => c.name === columnName);
  const targets = (Object.keys(TARGET_LABELS) as ConversionTarget[]).filter(
    (t) => column === undefined || KIND_OF_TARGET[t] !== column.kind,
  );
  const [target, setTarget] = useState<ConversionTarget | "">("");
  const chosenTarget = targets.find((t) => t === target) ?? targets[0];

  const request: CleaningRequest | null =
    column && chosenTarget ? { operation: "convert_type", column: column.name, target: chosenTarget } : null;

  return (
    <OperationPanel
      datasetId={datasetId}
      title="Convert column type"
      description="Change a column's type when it is stored in the wrong form, such as numbers saved as text. If any value can't be converted, nothing changes and the count of failures is reported."
      request={request}
      preview={
        column && chosenTarget
          ? `Convert every value in '${column.name}' to ${TARGET_LABELS[chosenTarget].toLowerCase()}. If any value can't be converted, the change is cancelled.`
          : ""
      }
      disabledReason={column ? undefined : "This dataset has no columns."}
      onApplied={onApplied}
    >
      <div className="flex flex-wrap gap-3">
        <label className="flex items-center gap-2 text-xs text-slate-400">
          <span className="uppercase tracking-wide">Column</span>
          <select value={columnName} onChange={(e) => setColumnName(e.target.value)} className={selectClass}>
            {profile.columns.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name} (currently {c.kind})
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-xs text-slate-400">
          <span className="uppercase tracking-wide">Convert to</span>
          <select
            value={chosenTarget ?? ""}
            onChange={(e) => setTarget(e.target.value as ConversionTarget)}
            className={selectClass}
          >
            {targets.map((t) => (
              <option key={t} value={t}>
                {TARGET_LABELS[t]}
              </option>
            ))}
          </select>
        </label>
      </div>
    </OperationPanel>
  );
}

// --- rename ----------------------------------------------------------------

function RenamePanel({
  datasetId,
  profile,
  onApplied,
}: {
  datasetId: string;
  profile: DatasetProfile;
  onApplied: () => void;
}) {
  const [columnName, setColumnName] = useState(profile.columns[0]?.name ?? "");
  const [newName, setNewName] = useState("");
  const trimmed = newName.trim();
  const taken = profile.columns.some((c) => c.name === trimmed && c.name !== columnName);

  let request: CleaningRequest | null = null;
  let disabledReason: string | undefined;
  if (trimmed === "") disabledReason = "Enter a new name.";
  else if (taken) disabledReason = `Another column is already named '${trimmed}'.`;
  else if (trimmed === columnName) disabledReason = "The new name matches the current name.";
  else request = { operation: "rename_column", column: columnName, new_name: trimmed };

  return (
    <OperationPanel
      datasetId={datasetId}
      title="Rename a column"
      description="Changes the column header only. The values stay exactly as they are."
      request={request}
      preview={request ? `Rename '${columnName}' to '${trimmed}'. No data changes.` : ""}
      disabledReason={disabledReason}
      onApplied={onApplied}
    >
      <div className="flex flex-wrap gap-3">
        <label className="flex items-center gap-2 text-xs text-slate-400">
          <span className="uppercase tracking-wide">Column</span>
          <select value={columnName} onChange={(e) => setColumnName(e.target.value)} className={selectClass}>
            {profile.columns.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-xs text-slate-400">
          <span className="uppercase tracking-wide">New name</span>
          <input value={newName} onChange={(e) => setNewName(e.target.value)} className={inputClass} />
        </label>
      </div>
    </OperationPanel>
  );
}

// --- drop columns ----------------------------------------------------------

function DropPanel({
  datasetId,
  profile,
  onApplied,
}: {
  datasetId: string;
  profile: DatasetProfile;
  onApplied: () => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const allSelected = profile.columns.length > 0 && selected.length >= profile.columns.length;

  let request: CleaningRequest | null = null;
  let disabledReason: string | undefined;
  if (selected.length === 0) disabledReason = "Choose the columns to remove.";
  else if (allSelected) disabledReason = "At least one column must remain.";
  else request = { operation: "drop_columns", columns: selected };

  return (
    <OperationPanel
      datasetId={datasetId}
      title="Drop columns"
      description="Removes columns you choose from the working copy. DataLens never removes a column on its own, even one flagged as an identifier or mostly empty."
      request={request}
      preview={`Remove ${selected.join(", ")} from every row of the working copy.`}
      destructive
      disabledReason={disabledReason}
      onApplied={onApplied}
    >
      <CheckboxGroup
        options={profile.columns.map((c) => c.name)}
        selected={selected}
        onChange={setSelected}
      />
    </OperationPanel>
  );
}

// --- shared ----------------------------------------------------------------

function CheckboxGroup({
  options,
  selected,
  onChange,
}: {
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  if (options.length === 0) {
    return <p className="text-sm text-slate-500">No columns of this type.</p>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((name) => {
        const checked = selected.includes(name);
        return (
          <label
            key={name}
            className={`flex cursor-pointer items-center gap-2 rounded border px-2.5 py-1 text-sm ${
              checked ? "border-sky-500/60 bg-sky-500/10 text-sky-200" : "border-slate-700 text-slate-400"
            }`}
          >
            <input
              type="checkbox"
              className="sr-only"
              checked={checked}
              onChange={() =>
                onChange(checked ? selected.filter((n) => n !== name) : [...selected, name])
              }
            />
            {name}
          </label>
        );
      })}
    </div>
  );
}
