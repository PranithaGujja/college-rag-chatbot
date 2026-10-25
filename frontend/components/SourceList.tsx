"use client";

import { useState } from "react";
import type { Source } from "@/lib/api";

export function SourceList({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!sources.length) return null;
  return (
    <div className="mt-3 border-t border-slate-200 pt-3">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Source{sources.length > 1 ? "s" : ""}</div>
      <ul className="space-y-2">
        {sources.map((s) => (
          <li key={s.ref} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <div className="flex items-start gap-2">
              <span className="mt-0.5 text-base" aria-hidden>📄</span>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-slate-900">
                  <span className="mr-1.5 rounded bg-slate-200 px-1 text-[10px] font-semibold text-slate-700">{s.ref}</span>
                  {s.handbook}
                </div>
                <div className="text-xs text-slate-600">
                  {s.page}{s.section ? <> • {s.section}</> : null}
                </div>
                <button
                  type="button" onClick={() => setOpen(open === s.ref ? null : s.ref)}
                  className="mt-1 text-xs font-medium text-slate-500 underline hover:text-slate-800"
                  aria-expanded={open === s.ref}
                >
                  {open === s.ref ? "Hide excerpt" : "Show excerpt"}
                </button>
                {open === s.ref && <p className="mt-1.5 whitespace-pre-line rounded bg-white p-2 text-xs leading-relaxed text-slate-700">{s.excerpt}</p>}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
