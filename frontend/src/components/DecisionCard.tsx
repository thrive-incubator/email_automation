import { useState } from "react";
import type { Decision } from "../types";
import { ActionChip, ConfidenceBadge, Pill } from "./Badges";

interface Props {
  decision: Decision;
  selected: boolean;
  onToggleSelect: () => void;
  draft: string;
  onDraftChange: (v: string) => void;
  saveToKnowledge: string;
  onSaveToKnowledgeChange: (v: string) => void;
  knowledgeFiles: string[];
  onDiscard: () => void;
  result?: { ok: boolean; message: string };
}

export default function DecisionCard({
  decision: d,
  selected,
  onToggleSelect,
  draft,
  onDraftChange,
  saveToKnowledge,
  onSaveToKnowledgeChange,
  knowledgeFiles,
  onDiscard,
  result,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const isReply = d.action_type === "reply";
  const done =
    d.status === "submitted" ||
    d.status === "discarded" ||
    d.status === "excluded";

  return (
    <div
      className={`rounded-xl border bg-white shadow-sm transition ${
        selected ? "border-ink ring-1 ring-ink" : "border-slate-200"
      } ${done ? "opacity-60" : ""}`}
    >
      <div className="flex items-start gap-3 p-4">
        <input
          type="checkbox"
          className="mt-1 h-4 w-4 accent-slate-900"
          checked={selected}
          disabled={done}
          onChange={onToggleSelect}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <ActionChip action={d.action_type} sendMode={d.send_mode} />
            <ConfidenceBadge value={d.confidence} />
            {d.safety_flag && <Pill tone="bg-rose-100 text-rose-700">⚠ safety</Pill>}
            {d.sales_opportunity && (
              <Pill tone="bg-emerald-100 text-emerald-700">$ sales</Pill>
            )}
            {d.matched_rule_name && <Pill>{d.matched_rule_name}</Pill>}
            {done && (
              <Pill tone={result?.ok === false ? "bg-rose-100 text-rose-700" : "bg-slate-200 text-slate-600"}>
                {d.status}
              </Pill>
            )}
          </div>

          <div className="mt-2 truncate text-sm">
            <span className="font-semibold">{d.sender}</span>{" "}
            <span className="text-slate-400">&lt;{d.sender_email}&gt;</span>
          </div>
          <div className="truncate font-medium">{d.subject}</div>
          <div className="mt-1 text-sm text-slate-600">{d.summary}</div>

          <button
            onClick={() => setExpanded((x) => !x)}
            className="mt-2 text-xs font-medium text-blue-600 hover:underline"
          >
            {expanded ? "Hide details" : "Show email + draft"}
          </button>

          {expanded && (
            <div className="mt-3 space-y-3">
              <div className="rounded-lg bg-slate-50 p-3 text-sm">
                <div className="mb-1 text-xs font-semibold uppercase text-slate-400">
                  Original email
                </div>
                <p className="whitespace-pre-wrap text-slate-700">{d.body}</p>
              </div>

              {d.reasoning && (
                <div className="text-xs text-slate-500">
                  <span className="font-semibold">Why:</span> {d.reasoning}
                </div>
              )}

              {isReply && (
                <div>
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase text-slate-400">
                      Proposed reply {d.voice_used ? `· voice: ${d.voice_used}` : ""}
                    </span>
                  </div>
                  <textarea
                    className="h-40 w-full rounded-lg border border-slate-300 p-3 text-sm focus:border-ink focus:outline-none"
                    value={draft}
                    disabled={done}
                    onChange={(e) => onDraftChange(e.target.value)}
                  />
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                    <span>On submit:</span>
                    <Pill tone="bg-blue-100 text-blue-700">
                      {d.send_mode === "send" ? "send reply" : "create draft"}
                    </Pill>
                    <span className="ml-2">Save correction to:</span>
                    <select
                      className="rounded border border-slate-300 px-2 py-1 text-xs"
                      value={saveToKnowledge}
                      disabled={done}
                      onChange={(e) => onSaveToKnowledgeChange(e.target.value)}
                    >
                      <option value="">— don't save —</option>
                      {knowledgeFiles.map((k) => (
                        <option key={k} value={k}>
                          {k}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )}

              {d.action_type === "crm_handoff" && d.handoff_payload && (
                <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                  {JSON.stringify(d.handoff_payload, null, 2)}
                </pre>
              )}

              {result && (
                <div
                  className={`rounded-lg p-2 text-xs ${
                    result.ok ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
                  }`}
                >
                  {result.message}
                </div>
              )}
            </div>
          )}
        </div>

        {!done && (
          <button
            onClick={onDiscard}
            className="rounded-md px-2 py-1 text-xs text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            Discard
          </button>
        )}
      </div>
    </div>
  );
}
