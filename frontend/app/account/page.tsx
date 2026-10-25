"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Brand } from "@/components/Brand";
import { ApiError, api, clearSession, getSession, saveSession, type Role } from "@/lib/api";
import { THEME } from "@/lib/theme";

// Shown only to people who signed in with a temporary password. Once they have chosen their own,
// this page redirects to the chat and there is no "change password" option anywhere in the app.
export default function AccountPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<Role>("student");
  const [who, setWho] = useState("");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const t = THEME[role];

  useEffect(() => {
    const s = getSession();
    if (!s) { router.replace("/login"); return; }
    (async () => {
      try {
        const me = await api.me(s.token); // the server decides whether a change is required
        if (!me.must_change_password) { router.replace("/dashboard"); return; }
        setToken(s.token); setRole(me.role); setWho(me.username);
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) { clearSession(); router.replace("/login?expired=1"); }
        else setError(e instanceof ApiError ? e.message : "Could not load this page. Please refresh.");
      }
    })();
  }, [router]);

  function validate(): string | null {
    if (!current) return "Please enter your temporary password.";
    if (next.length < 8) return "Your new password must be at least 8 characters.";
    if (new TextEncoder().encode(next).length > 72) return "Your new password is too long (maximum 72 characters).";
    if (next === current) return "Your new password must be different from the temporary one.";
    if (next.trim().toLowerCase() === who.toLowerCase()) return "Your password cannot be the same as your ID.";
    if (next !== confirm) return "The two new passwords do not match.";
    return null;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || !token) return;
    const problem = validate();
    if (problem) { setError(problem); return; }
    setError(null); setBusy(true);
    try {
      const res = await api.changePassword(token, current, next);
      saveSession({ token: res.access_token, user: res.user }); // the server closes the old session
      router.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { clearSession(); router.replace("/login?expired=1"); return; }
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      setBusy(false);
    }
  }

  async function logout() {
    if (token) { try { await api.logout(token); } catch { /* ignore */ } }
    clearSession(); router.replace("/");
  }

  const input = `mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:ring-2 ${t.ring}`;
  return (
    <main className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Brand />
          <button onClick={logout} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">Log out</button>
        </div>
      </header>

      <div className="mx-auto w-full max-w-md px-4 py-10">
        {!token && !error && <p className="text-center text-sm text-slate-500" role="status">Loading…</p>}
        {error && !token && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800">{error}</div>}
        {token && (
          <form onSubmit={submit} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8" noValidate>
            <h1 className="text-2xl font-bold text-slate-900">Set your new password</h1>
            <p className="mt-1 text-sm text-slate-600">You signed in with a temporary password. Please choose your own password to continue.</p>

            {error && <div role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800">{error}</div>}

            <label htmlFor="current" className="mt-5 block text-sm font-medium text-slate-700">Temporary password</label>
            <input id="current" type={show ? "text" : "password"} autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} className={input} />

            <label htmlFor="next" className="mt-4 block text-sm font-medium text-slate-700">New password <span className="font-normal text-slate-500">(at least 8 characters)</span></label>
            <input id="next" type={show ? "text" : "password"} autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} className={input} />

            <label htmlFor="confirm" className="mt-4 block text-sm font-medium text-slate-700">Confirm new password</label>
            <input id="confirm" type={show ? "text" : "password"} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className={input} />

            <label className="mt-3 flex items-center gap-2 text-xs text-slate-600">
              <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} /> Show passwords
            </label>

            <button type="submit" disabled={busy}
              className={`mt-6 w-full rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-60 ${t.accent} ${t.accentHover}`}>
              {busy ? "Saving…" : "Save new password"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
