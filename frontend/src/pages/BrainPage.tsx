import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { BrainIndex } from "../types";

interface Selected {
  kind: "voice" | "knowledge" | "guardrails";
  name: string;
}

export default function BrainPage() {
  const [index, setIndex] = useState<BrainIndex>({ voices: [], knowledge: [], guardrails: [] });
  const [selected, setSelected] = useState<Selected | null>(null);
  const [content, setContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    api.brainIndex().then((idx) => {
      setIndex(idx);
      setSelected({ kind: "guardrails", name: "guardrails.md" });
    });
  }, []);

  useEffect(() => {
    if (!selected) return;
    api.getBrainFile(selected.kind, selected.name).then((f) => {
      setContent(f.content);
      setDirty(false);
      setStatus("");
    });
  }, [selected]);

  const save = async () => {
    if (!selected) return;
    await api.saveBrainFile(selected.kind, selected.name, content);
    setDirty(false);
    setStatus("Saved ✓");
  };

  const Item = ({ kind, name }: Selected) => {
    const active = selected?.kind === kind && selected?.name === name;
    return (
      <button
        onClick={() => setSelected({ kind, name })}
        className={`block w-full truncate rounded px-2 py-1.5 text-left text-sm ${
          active ? "bg-ink text-white" : "hover:bg-slate-100"
        }`}
      >
        {name}
      </button>
    );
  };

  return (
    <div className="grid gap-4 md:grid-cols-[220px_1fr]">
      <aside className="space-y-4 rounded-xl border border-slate-200 bg-white p-3">
        <div>
          <div className="mb-1 text-xs font-semibold uppercase text-slate-400">Guardrails</div>
          <Item kind="guardrails" name="guardrails.md" />
        </div>
        <div>
          <div className="mb-1 text-xs font-semibold uppercase text-slate-400">Voices</div>
          {index.voices.map((v) => (
            <Item key={v} kind="voice" name={v} />
          ))}
        </div>
        <div>
          <div className="mb-1 text-xs font-semibold uppercase text-slate-400">Knowledge</div>
          {index.knowledge.map((k) => (
            <Item key={k} kind="knowledge" name={k} />
          ))}
        </div>
      </aside>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        {selected ? (
          <>
            <div className="mb-2 flex items-center justify-between">
              <div className="text-sm font-semibold">
                {selected.kind} · {selected.name}
              </div>
              <div className="flex items-center gap-2">
                {status && <span className="text-xs text-emerald-600">{status}</span>}
                <button
                  onClick={save}
                  disabled={!dirty}
                  className="rounded bg-ink px-4 py-1.5 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-40"
                >
                  Save
                </button>
              </div>
            </div>
            <textarea
              className="h-[60vh] w-full rounded-lg border border-slate-300 p-3 font-mono text-sm focus:border-ink focus:outline-none"
              value={content}
              onChange={(e) => {
                setContent(e.target.value);
                setDirty(true);
              }}
            />
          </>
        ) : (
          <div className="text-slate-400">Select a file to edit.</div>
        )}
      </section>
    </div>
  );
}
