import type { CSSProperties } from "react";
import { SourceLink } from "@/components/ui";

export type TracePoint = { year: number; closing: number };

const W = 480, H = 210, PAD_X = 34, PAD_TOP = 36, PAD_BOTTOM = 34;

// Real closing ranks drawn on a reversed axis, so higher on the chart means a more competitive seat.
export function CutoffTrace({ points, institute, programme, rankList, quota, sourceUrl }: { points: TracePoint[]; institute: string; programme: string; rankList: string; quota: string; sourceUrl: string }) {
  const ranks = points.map((p) => p.closing);
  const low = Math.min(...ranks), high = Math.max(...ranks);
  const span = high - low || 1;
  const x = (i: number) => PAD_X + (i * (W - PAD_X * 2)) / Math.max(1, points.length - 1);
  const y = (rank: number) => PAD_TOP + ((rank - low) / span) * (H - PAD_TOP - PAD_BOTTOM - 14);
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.closing).toFixed(1)}`).join(" ");
  const area = `${line} L${x(points.length - 1).toFixed(1)} ${H - PAD_BOTTOM} L${x(0).toFixed(1)} ${H - PAD_BOTTOM} Z`;
  const summary = points.map((p) => `${p.year}: ${p.closing.toLocaleString("en-IN")}`).join(", ");
  return (
    <figure className="glass p-5">
      <figcaption>
        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-accent"><span className="pulse-dot inline-block h-2 w-2 rounded-full bg-accent" aria-hidden /> A real record</p>
        <p className="mt-2 font-display text-lg font-semibold leading-snug">{institute}</p>
        <p className="text-sm text-ink-2">{programme}</p>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full" role="img" aria-label={`Final-round closing ranks by year. ${summary}`}>
        <defs>
          <linearGradient id="trace-line" x1="0" x2="1"><stop offset="0" stopColor="#5eead4" /><stop offset="1" stopColor="#fbbf24" /></linearGradient>
          <linearGradient id="trace-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#5eead4" stopOpacity="0.28" /><stop offset="1" stopColor="#5eead4" stopOpacity="0" /></linearGradient>
        </defs>
        <line x1={PAD_X} x2={W - PAD_X} y1={H - PAD_BOTTOM} y2={H - PAD_BOTTOM} stroke="rgb(255 255 255 / 0.2)" />
        <path d={area} fill="url(#trace-fill)" className="fade-late" style={{ "--delay": "1100ms" } as CSSProperties} />
        <path d={line} pathLength={1} fill="none" stroke="url(#trace-line)" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" className="draw" />
        {points.map((p, i) => {
          const delay = { "--delay": `${350 + i * 260}ms` } as CSSProperties;
          return (
            <g key={p.year}>
              <circle cx={x(i)} cy={y(p.closing)} r={4.5} fill="#0d1033" stroke="#fff" strokeWidth={2} className="pop" style={delay} />
              <text x={x(i)} y={y(p.closing) - 12} textAnchor="middle" fontSize={13} fontWeight={600} fill="#fff" className="fade-late tnum" style={delay}>{p.closing.toLocaleString("en-IN")}</text>
              <text x={x(i)} y={H - 12} textAnchor="middle" fontSize={13} fill="rgb(255 255 255 / 0.72)">{p.year}</text>
            </g>
          );
        })}
      </svg>
      <p className="mt-2 text-xs text-ink-2">Final-round closing ranks on the {rankList} list ({quota}, gender-neutral). Higher on the chart means a more competitive seat. Past cutoffs are history, not a forecast.</p>
      <p className="mt-1"><SourceLink href={sourceUrl} label="Source: JoSAA" /></p>
    </figure>
  );
}
