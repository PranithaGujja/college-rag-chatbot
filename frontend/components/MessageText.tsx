import type { ReactNode } from "react";

// Renders the small subset of formatting the assistant uses (paragraphs, bullets, **bold**)
// as plain React nodes. No HTML injection is possible.
function inline(text: string, keyPrefix: string): ReactNode[] {
  const clean = text.replace(/\s*\[\d{1,2}\]/g, ""); // source markers like [1] are not shown to the user
  return clean.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={key} className="font-semibold text-slate-950">{part.slice(2, -2)}</strong>;
    return <span key={key}>{part}</span>;
  });
}

export function MessageText({ text }: { text: string }) {
  const lines = text.split("\n").map((l) => l.trimEnd()).filter((l) => l.trim() !== "");
  const blocks: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const bullet = /^\s*([-*•])\s+(.*)$/;
    const numbered = /^\s*\d+[.)]\s+(.*)$/;
    if (bullet.test(lines[i])) {
      const items: string[] = [];
      while (i < lines.length && bullet.test(lines[i])) items.push(lines[i++].replace(bullet, "$2"));
      blocks.push(<ul key={`b${i}`} className="my-2 list-disc space-y-1 pl-5">{items.map((t, j) => <li key={j}>{inline(t, `b${i}-${j}`)}</li>)}</ul>);
    } else if (numbered.test(lines[i])) {
      const items: string[] = [];
      while (i < lines.length && numbered.test(lines[i])) items.push(lines[i++].replace(numbered, "$1"));
      blocks.push(<ol key={`n${i}`} className="my-2 list-decimal space-y-1 pl-5">{items.map((t, j) => <li key={j}>{inline(t, `n${i}-${j}`)}</li>)}</ol>);
    } else {
      blocks.push(<p key={`p${i}`} className="my-1.5">{inline(lines[i], `p${i}`)}</p>);
      i++;
    }
  }
  return <div className="text-[15px] leading-relaxed">{blocks}</div>;
}
