import { FinancialField, JsonField } from "./types";

export function parseJsonColumn<T>(raw: string | null | undefined): T | null {
  if (!raw) return null;
  if (typeof raw === "object") return raw as T;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function normalizeToActual(
  value: number | null | undefined,
  unit_stated?: string
): number | null {
  if (value == null) return null;
  if (!unit_stated) return value;
  const lower = unit_stated.toLowerCase();
  if (lower.includes("billion")) return value * 1_000_000_000;
  if (lower.includes("million")) return value * 1_000_000;
  if (lower.includes("thousand")) return value * 1_000;
  return value;
}

export function formatCurrency(
  value: number | null | undefined,
  currency: string = "SAR"
): string {
  if (value == null) return "N/A";
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(value);
  } catch {
    return `${currency} ${value.toLocaleString()}`;
  }
}

export function formatCompact(value: number | null | undefined): string {
  if (value == null) return "N/A";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000_000) return `${sign}${(abs / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}${(abs / 1_000).toFixed(1)}K`;
  return `${sign}${abs}`;
}

export function getNormalizedRevenue(f: FinancialField | null): number | null {
  if (!f) return null;
  return normalizeToActual(f.value, f.unit_stated);
}

export function getJsonValue<T>(field: JsonField<T> | null): T | null {
  if (!field) return null;
  return field.value;
}

export function getConfidence(
  field: JsonField<unknown> | FinancialField | null
): number {
  if (!field) return 0;
  return field.confidence ?? 0;
}

export function confidenceColor(confidence: number): string {
  if (confidence >= 0.9) return "text-emerald-400";
  if (confidence >= 0.7) return "text-amber-400";
  return "text-red-400";
}

export function confidenceBg(confidence: number): string {
  if (confidence >= 0.9) return "bg-emerald-400/20 text-emerald-400";
  if (confidence >= 0.7) return "bg-amber-400/20 text-amber-400";
  return "bg-red-400/20 text-red-400";
}
