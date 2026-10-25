"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AuthShell } from "@/components/AuthShell";
import { ApiError, api, getSession, saveSession, type Role } from "@/lib/api";
import { THEME } from "@/lib/theme";

function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const role: Role = params.get("as") === "faculty" ? "faculty" : "student";
  const t = THEME[role];
  const idLabel = role === "student" ? "Student ID / Roll number" : "Employee ID";

  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [code, setCode] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setReady(true);
    api.wake();
    if (getSession()) router.replace("/dashboard");
  }, [router]);

  function validate(): string | null {
    if (name.trim().length < 2) return "Please enter your full name.";
    if (!/^[A-Za-z0-9._@-]{3,40}$/.test(username.trim())) return `${idLabel} must be 3-40 characters: letters, numbers and . _ @ - only (no spaces).`;
    if (password.length < 8) return "Password must be at least 8 characters.";
    if (new TextEncoder().encode(password).length > 72) return "Password is too long (maximum 72 characters).";
    if (password !== confirm) return "The two passwords do not match.";
    if (!code.trim()) return `Please enter the ${role} access code from your college office.`;
    return null;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    const problem = validate();
    if (problem) { setError(problem); return; }
    setError(null);
    setBusy(true);
    try {
      const res = await api.register({ name: name.trim(), username: username.trim(), password, portal: role, access_code: code.trim() });
      saveSession({ token: res.access_token, user: res.user });
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      setBusy(false);
    }
  }

  const input = `mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:ring-2 ${t.ring}`;
  return (
    <AuthShell>
      <form onSubmit={submit} className="w-full rounded-2xl border border-slate-200 bg-white p-6 text-slate-900 shadow-xl sm:p-8" noValidate>
        <span className={`mb-3 inline-block rounded-full px-3 py-1 text-xs font-semibold ${t.badge}`}>{t.label} Sign up</span>
        <h1 className="text-2xl font-bold">Create your account</h1>
        <p className="mt-1 text-sm text-slate-600">You will get access to the {t.handbook} only.</p>

        {error && <div role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800">{error}</div>}

        <label htmlFor="name" className="mt-5 block text-sm font-medium text-slate-700">Full name</label>
        <input id="name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} className={input} />

        <label htmlFor="username" className="mt-4 block text-sm font-medium text-slate-700">{idLabel}</label>
        <input id="username" autoComplete="username" autoCapitalize="none" value={username} onChange={(e) => setUsername(e.target.value)} maxLength={40} className={input} />

        <label htmlFor="password" className="mt-4 block text-sm font-medium text-slate-700">Password <span className="font-normal text-slate-500">(at least 8 characters)</span></label>
        <div className="relative">
          <input id="password" type={show ? "text" : "password"} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} className={`${input} pr-16`} />
          <button type="button" onClick={() => setShow((s) => !s)} className="absolute inset-y-0 right-0 mt-1 px-3 text-xs font-medium text-slate-500 hover:text-slate-800">{show ? "Hide" : "Show"}</button>
        </div>

        <label htmlFor="confirm" className="mt-4 block text-sm font-medium text-slate-700">Confirm password</label>
        <input id="confirm" type={show ? "text" : "password"} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className={input} />

        <label htmlFor="code" className="mt-4 block text-sm font-medium text-slate-700">{t.label} access code</label>
        <input id="code" autoComplete="off" autoCapitalize="none" value={code} onChange={(e) => setCode(e.target.value)} className={input} />
        <p className="mt-1 text-xs text-slate-500">Get this code from your college office. It makes sure only {role === "student" ? "students" : "faculty"} can sign up here.</p>

        <button type="submit" disabled={busy || !ready}
          className={`mt-6 w-full rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-60 ${t.accent} ${t.accentHover}`}>
          {busy ? "Creating account…" : "Create account"}
        </button>

        <p className="mt-6 text-center text-sm text-slate-600">
          Already registered? <Link href={`/login?as=${role}`} className="font-semibold text-slate-900 underline">Log in</Link>
        </p>
      </form>
    </AuthShell>
  );
}

export default function RegisterPage() {
  return <Suspense><RegisterForm /></Suspense>;
}
