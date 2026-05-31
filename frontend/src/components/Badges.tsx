import type { ReactNode } from "react";
import type { ActionType } from "../types";

export function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone =
    value >= 0.9
      ? "bg-emerald-100 text-emerald-700"
      : value >= 0.7
        ? "bg-amber-100 text-amber-700"
        : "bg-rose-100 text-rose-700";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${tone}`}>
      {pct}% sure
    </span>
  );
}

const ACTION_META: Record<ActionType, { label: string; tone: string }> = {
  reply: { label: "Reply", tone: "bg-blue-100 text-blue-700" },
  flag: { label: "Flag for review", tone: "bg-amber-100 text-amber-700" },
  discard: { label: "Archive", tone: "bg-slate-200 text-slate-600" },
  label: { label: "Label", tone: "bg-violet-100 text-violet-700" },
  crm_handoff: { label: "CRM handoff", tone: "bg-fuchsia-100 text-fuchsia-700" },
  exclude: { label: "Excluded (skipped)", tone: "bg-zinc-200 text-zinc-600" },
};

export function ActionChip({ action, sendMode }: { action: ActionType; sendMode?: string }) {
  const meta = ACTION_META[action];
  const suffix = action === "reply" && sendMode ? ` · ${sendMode}` : "";
  return (
    <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${meta.tone}`}>
      {meta.label}
      {suffix}
    </span>
  );
}

export function Pill({ children, tone = "bg-slate-100 text-slate-600" }: { children: ReactNode; tone?: string }) {
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${tone}`}>{children}</span>;
}
