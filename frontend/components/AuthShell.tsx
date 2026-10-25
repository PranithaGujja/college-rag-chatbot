import Link from "next/link";
import { Brand } from "./Brand";

// Dark page frame shared by the landing, login and sign-up pages.
export const GLOW = { background: "radial-gradient(60% 50% at 50% 0%, rgba(34,211,238,0.16) 0%, rgba(5,8,22,0) 70%)" };

export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="relative flex min-h-screen flex-col overflow-hidden bg-[#050816] text-white">
      <div aria-hidden className="pointer-events-none absolute inset-0" style={GLOW} />
      <header className="relative border-b border-white/10">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/"><Brand light /></Link>
          <Link href="/" className="text-sm text-slate-300 hover:text-white">← Back to home</Link>
        </div>
      </header>
      <div className="relative mx-auto flex w-full max-w-md flex-1 items-start px-5 pb-16 pt-8 sm:items-center sm:pt-0">{children}</div>
    </main>
  );
}
