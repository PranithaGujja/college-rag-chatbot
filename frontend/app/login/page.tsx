"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AuthShell } from "@/components/AuthShell";
import { ApiError, api, getSession, saveSession, type Role } from "@/lib/api";
import { RESET_CONTACT } from "@/lib/brand";
import { THEME } from "@/lib/theme";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const role: Role = params.get("as") === "faculty" ? "faculty" : "student";
  const other: Role = role === "student" ? "faculty" : "student";
  const t = THEME[role];

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [slow, setSlow] = useState(false);
  const [ready, setReady] = useState(false); // the button stays disabled until the page's JavaScript has loaded
  const [signupOpen, setSignupOpen] = useState(false);
  const [forgot, setForgot] = useState(false);
  const [error, setError] = useState<string | null>(params.get("expired") ? "Your session has ended. Please log in again." : null);

  useEffect(() => {
    setReady(true);
    api.config().then((c) => setSignupOpen(!!c.signup?.[role])).catch(() => setSignupOpen(false));
    if (getSession()) router.replace("/dashboard");
  }, [router, role]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(null);
    if (!username.trim() || !password) { setError("Please enter your ID and password."); return; }
    setBusy(true);
    const slowTimer = setTimeout(() => setSlow(true), 5000);
    try {
      const res = await api.login(username.trim(), password, role);
      saveSession({ token: res.access_token, user: res.user });
      router.replace(res.user.must_change_password ? "/account" : "/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      setBusy(false);
    } finally {
      clearTimeout(slowTimer);
      setSlow(false);
    }
  }

  return (
    <AuthShell>
      <form onSubmit={submit} className="w-full rounded-2xl border border-slate-200 bg-white p-6 text-slate-900 shadow-xl sm:p-8" noValidate>
        <span className={`mb-3 inline-block rounded-full px-3 py-1 text-xs font-semibold ${t.badge}`}>{t.label} Login</span>
        <h1 className="text-2xl font-bold text-slate-900">Welcome back</h1>
        <p className="mt-1 text-sm text-slate-600">Sign in to open the {t.assistant}.</p>

        {error && <div role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800">{error}</div>}

        <label htmlFor="username" className="mt-5 block text-sm font-medium text-slate-700">{t.label} ID</label>
        <input id="username" autoComplete="username" autoCapitalize="none" value={username} onChange={(e) => setUsername(e.target.value)}
          className={`mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:ring-2 ${t.ring}`} />

        <label htmlFor="password" className="mt-4 block text-sm font-medium text-slate-700">Password</label>
        <div className="relative mt-1">
          <input id="password" type={show ? "text" : "password"} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)}
            className={`w-full rounded-lg border border-slate-300 px-3 py-2.5 pr-16 text-sm outline-none focus:ring-2 ${t.ring}`} />
          <button type="button" onClick={() => setShow((s) => !s)} className="absolute inset-y-0 right-0 px-3 text-xs font-medium text-slate-500 hover:text-slate-800">{show ? "Hide" : "Show"}</button>
        </div>

        <div className="mt-2 text-right">
          <button type="button" onClick={() => setForgot((f) => !f)} aria-expanded={forgot} className="text-xs font-medium text-slate-600 underline hover:text-slate-900">Forgot password?</button>
        </div>
        {forgot && (
          <div className={`mt-2 rounded-lg border px-3 py-3 text-sm text-slate-700 ${t.soft}`}>
            <p className="font-medium text-slate-900">Reset your password</p>
            <p className="mt-1">For your security, passwords are reset by your college office. Contact them with your college ID. They will give you a temporary password, and you will choose a new one when you sign in.</p>
            {RESET_CONTACT && <p className="mt-2 font-medium">{RESET_CONTACT}</p>}
          </div>
        )}

        <button type="submit" disabled={busy || !ready}
          className={`mt-6 w-full rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-60 ${t.accent} ${t.accentHover}`}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        {slow && <p className="mt-3 text-center text-xs text-slate-500">Waking up the server. This can take up to a minute on the free plan…</p>}

        <p className="mt-5 text-center text-xs text-slate-500">First time? Use the temporary password from your college office. You will then choose your own.</p>
        {signupOpen && (
          <p className="mt-4 text-center text-sm text-slate-600">
            No login yet? <Link href={`/register?as=${role}`} className="font-semibold text-slate-900 underline">Create an account</Link>
          </p>
        )}
        <p className="mt-2 text-center text-sm text-slate-500">
          Not a {role}? <Link href={`/login?as=${other}`} className="font-medium text-slate-800 underline">Use the {THEME[other].label} Login</Link>
        </p>
      </form>
    </AuthShell>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
