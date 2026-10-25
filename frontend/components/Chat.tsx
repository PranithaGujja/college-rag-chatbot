"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, type ChatMessage, type Role } from "@/lib/api";
import { THEME } from "@/lib/theme";
import { MessageText } from "./MessageText";

const MAX_CHARS = 500;

export function Chat({ token, role, initial, onAuthExpired }: { token: string; role: Role; initial: ChatMessage[]; onAuthExpired: () => void }) {
  const t = THEME[role];
  const [messages, setMessages] = useState<ChatMessage[]>(initial);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; question: string } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, loading, error]);

  const send = useCallback(async (text?: string) => {
    const question = (text ?? input).trim();
    if (!question || loading) return;
    if (question.length > MAX_CHARS) { setError({ message: `Please keep your question under ${MAX_CHARS} characters.`, question }); return; }
    setMessages((m) => [...m, { role: "user", content: question }]);
    setInput("");
    if (areaRef.current) areaRef.current.style.height = "auto";
    setError(null);
    setLoading(true);
    try {
      const r = await api.ask(token, role, question);
      setMessages((m) => [...m, { role: "assistant", content: r.answer, sources: r.sources, found: r.found }]);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { onAuthExpired(); return; }
      setError({ message: e instanceof ApiError ? e.message : "Something went wrong. Please try again.", question });
    } finally {
      setLoading(false);
    }
  }, [input, loading, token, role, onAuthExpired]);

  function retry() {
    if (!error) return;
    const q = error.question;
    setMessages((m) => (m.length && m[m.length - 1].role === "user" && m[m.length - 1].content === q ? m.slice(0, -1) : m));
    setError(null);
    void send(q);
  }

  async function clearChat() {
    if (!messages.length || !window.confirm("Clear this conversation? This cannot be undone.")) return;
    try { await api.clearHistory(token); setMessages([]); setError(null); }
    catch (e) { if (e instanceof ApiError && e.status === 401) onAuthExpired(); else setError({ message: "Could not clear the chat. Please try again.", question: "" }); }
  }

  const empty = messages.length === 0 && !loading;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto" aria-live="polite">
        <div className="mx-auto w-full max-w-3xl px-4 py-6">
          {empty && (
            <div className="py-6 text-center sm:py-12">
              <div className={`mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br text-2xl text-white ${t.gradient}`} aria-hidden>📘</div>
              <h2 className="text-xl font-semibold text-slate-900 sm:text-2xl">{t.assistant}</h2>
              <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">Ask anything about the {t.handbook}. {t.blurb}</p>
              <p className="mt-6 text-xs font-semibold uppercase tracking-wide text-slate-500">Try asking</p>
              <div className="mt-3 flex flex-wrap justify-center gap-2">
                {t.suggestions.map((s) => (
                  <button key={s} onClick={() => send(s)} className="rounded-full border border-slate-300 bg-white px-3.5 py-2 text-left text-sm text-slate-700 shadow-sm transition hover:border-slate-400 hover:bg-slate-50">{s}</button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-5">
            {messages.map((m, i) =>
              m.role === "user" ? (
                <div key={i} className="flex justify-end">
                  <div className={`max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md px-4 py-2.5 text-[15px] leading-relaxed ${t.userBubble}`}>{m.content}</div>
                </div>
              ) : (
                <div key={i} className="flex justify-start">
                  <div className={`max-w-[92%] rounded-2xl rounded-bl-md border px-4 py-3 shadow-sm sm:max-w-[85%] ${m.found === false ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-white"}`}>
                    <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-slate-500"><span aria-hidden>{m.found === false ? "ℹ️" : "🤖"}</span>Assistant</div>
                    <MessageText text={m.content} />
                  </div>
                </div>
              )
            )}

            {loading && (
              <div className="flex justify-start" role="status" aria-label="Assistant is typing">
                <div className="rounded-2xl rounded-bl-md border border-slate-200 bg-white px-4 py-3 shadow-sm">
                  <div className="flex items-center gap-1.5">
                    {[0, 150, 300].map((d) => <span key={d} className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: `${d}ms` }} />)}
                    <span className="ml-2 text-xs text-slate-500">Searching the {t.handbook}…</span>
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                <p>{error.message}</p>
                {error.question && !error.message.includes("characters") && (
                  <button onClick={retry} className="mt-2 rounded-md bg-red-600 px-3 py-1 text-xs font-semibold text-white hover:bg-red-700">Try again</button>
                )}
              </div>
            )}
          </div>
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)]">
        <div className="mx-auto w-full max-w-3xl px-4 py-3">
          {!empty && (
            <div className="-mx-1 mb-2 flex gap-2 overflow-x-auto px-1 pb-1">
              {t.suggestions.map((s) => (
                <button key={s} disabled={loading} onClick={() => send(s)} className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600 hover:bg-slate-100 disabled:opacity-50">{s}</button>
              ))}
            </div>
          )}
          <div className="flex items-end gap-2">
            <textarea
              ref={areaRef} rows={1} value={input} maxLength={MAX_CHARS + 50} placeholder={`Ask about the ${t.handbook}…`} aria-label="Your question"
              onChange={(e) => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 140) + "px"; }}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }}
              className={`max-h-36 min-h-[44px] flex-1 resize-none rounded-xl border border-slate-300 px-3.5 py-2.5 text-[15px] outline-none focus:ring-2 ${t.ring}`}
            />
            <button
              onClick={() => send()} disabled={loading || !input.trim()}
              className={`h-11 shrink-0 rounded-xl px-5 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-50 ${t.accent} ${t.accentHover}`}
            >
              {loading ? "…" : "Send"}
            </button>
          </div>
          <div className="mt-1.5 flex items-center justify-between text-[11px] text-slate-500">
            <span>Enter to send • Shift+Enter for a new line{input.length > 400 ? ` • ${input.length}/${MAX_CHARS}` : ""}</span>
            <button onClick={clearChat} disabled={!messages.length} className="underline hover:text-slate-800 disabled:no-underline disabled:opacity-40">Clear chat</button>
          </div>
          <p className="mt-1 text-center text-[11px] text-slate-400">AI can make mistakes. Check the cited page for important decisions.</p>
        </div>
      </div>
    </div>
  );
}
