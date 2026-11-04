/**
 * Pure display-formatting helpers. These only reformat numbers already
 * computed by the backend — they must never derive new statistics.
 */

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";

  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const value = bytes / 1024 ** exponent;

  return `${exponent === 0 ? value : value.toFixed(1)} ${units[exponent]}`;
}

export function formatNumber(value: number | null): string {
  if (value === null) return "—";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(
    value,
  );
}

export function formatDateTime(isoString: string): string {
  return new Date(isoString).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
