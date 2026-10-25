"use client";

import Link from "next/link";
import { useEffect } from "react";
import { GLOW } from "@/components/AuthShell";
import { Brand } from "@/components/Brand";
import { api } from "@/lib/api";
import { COLLEGE_NAME } from "@/lib/brand";

export default function Landing() {
  // Free-tier servers sleep when idle. Ping once so it is already awake by the time the user logs in.
  useEffect(() => { api.wake(); }, []);

  return (
    <main className="relative flex min-h-screen flex-col overflow-hidden bg-[#050816] text-white">
      <div aria-hidden className="pointer-events-none absolute inset-0" style={GLOW} />

      <header className="relative border-b border-white/10">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Brand light />
          <nav className="flex items-center gap-2 sm:gap-3">
            <Link href="/login?as=student" className="rounded-lg px-3 py-2 text-sm font-medium text-slate-200 hover:text-white">Student Login</Link>
            <Link href="/login?as=faculty" className="rounded-lg bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-300">Faculty Login</Link>
          </nav>
        </div>
      </header>

      <section className="relative flex flex-1 items-center justify-center px-6 py-16 text-center">
        <div className="mx-auto max-w-3xl">
          <p className="mx-auto mb-7 inline-flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-1.5 text-sm text-cyan-200">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-300" aria-hidden />
            {COLLEGE_NAME} Handbook Assistant
          </p>
          <h1 className="text-4xl font-extrabold leading-tight tracking-tight sm:text-6xl">
            Your handbook,
            <span className="block text-cyan-300">answered instantly.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-slate-400 sm:text-lg">
            Ask a question in plain English and get a clear answer from the official Student or Faculty Handbook, with the exact page shown.
          </p>
          <div className="mt-10 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
            <Link href="/login?as=student" className="rounded-xl bg-cyan-400 px-8 py-3.5 text-base font-semibold text-slate-950 transition hover:bg-cyan-300">Student Login</Link>
            <Link href="/login?as=faculty" className="rounded-xl border border-white/25 px-8 py-3.5 text-base font-semibold text-white transition hover:bg-white/10">Faculty Login</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
