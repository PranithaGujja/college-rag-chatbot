"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Brand } from "@/components/Brand";
import { Chat } from "@/components/Chat";
import { ApiError, api, clearSession, getSession, type ChatMessage, type Role } from "@/lib/api";
import { THEME } from "@/lib/theme";

interface Ready { token: string; name: string; role: Role; history: ChatMessage[] }

export default function Dashboard() {
  const router = useRouter();
  const [state, setState] = useState<Ready | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);

  const expired = useCallback(() => { clearSession(); router.replace("/login?expired=1"); }, [router]);

  useEffect(() => {
    const s = getSession();
    if (!s) { router.replace("/login"); return; }
    (async () => {
      try {
        // The role shown and used comes from the SERVER (/me), never from what is stored in the browser.
        const me = await api.me(s.token);
        if (me.must_change_password) { router.replace("/account"); return; }
        const { messages } = await api.history(s.token);
        setState({ token: s.token, name: me.name, role: me.role, history: messages });
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) expired();
        else setFatal(e instanceof ApiError ? e.message : "Could not load your dashboard.");
      }
    })();
  }, [router, expired]);

  async function logout() {
    if (!state || loggingOut) return;
    setLoggingOut(true);
    try { await api.logout(state.token); } catch { /* token expires on its own anyway */ }
    clearSession();
    router.replace("/");
  }

  if (fatal) {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <div className="max-w-md rounded-2xl border border-red-200 bg-white p-6 text-center shadow-sm">
          <p className="text-sm text-red-800">{fatal}</p>
          <button onClick={() => location.reload()} className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Reload</button>
        </div>
      </main>
    );
  }
  if (!state) {
    return <main className="flex min-h-screen items-center justify-center text-sm text-slate-500" role="status">Loading your dashboard…</main>;
  }

  const t = THEME[state.role];
  return (
    <div className="flex h-dvh flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-3 px-4 py-3">
          <Brand />
          <div className="flex items-center gap-3">
            <div className="hidden text-right leading-tight sm:block">
              <div className="text-sm font-medium text-slate-900">{state.name}</div>
              <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${t.badge}`}>{t.label}</span>
            </div>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold sm:hidden ${t.badge}`}>{t.label}</span>
            <button onClick={logout} disabled={loggingOut} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60">
              {loggingOut ? "…" : "Log out"}
            </button>
          </div>
        </div>
      </header>
      <Chat token={state.token} role={state.role} initial={state.history} onAuthExpired={expired} />
    </div>
  );
}
