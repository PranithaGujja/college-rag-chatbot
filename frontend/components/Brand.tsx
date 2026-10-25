import { COLLEGE_INITIALS, COLLEGE_NAME, PORTAL_NAME } from "@/lib/brand";

export function LogoMark({ className = "h-10 w-10", light = false }: { className?: string; light?: boolean }) {
  // Placeholder logo. Swap for: <img src="/logo.png" alt="" className={className} />
  return (
    <div
      className={`${className} flex shrink-0 items-center justify-center rounded-xl text-xs font-bold tracking-wide ${light ? "bg-cyan-400 text-slate-950" : "bg-slate-900 text-white"}`}
      aria-hidden
    >
      {COLLEGE_INITIALS}
    </div>
  );
}

export function Brand({ light = false }: { light?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <LogoMark light={light} />
      <div className="leading-tight">
        <div className={`text-sm font-semibold ${light ? "text-white" : "text-slate-900"}`}>{COLLEGE_NAME}</div>
        <div className={`text-xs ${light ? "text-slate-400" : "text-slate-500"}`}>{PORTAL_NAME}</div>
      </div>
    </div>
  );
}
