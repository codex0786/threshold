"use client";
import { ChevronDown } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { bandMeta } from "@/components/ui";
import { track } from "@/lib/analytics";

// From the backtest in docs/ADMISSION_ENGINE.md (`python -m ingest.backtest`), test years 2024, 2025 and 2026.
// Each figure is the share of seats whose final closing rank in the test year was still at or beyond
// a rank sitting exactly at the band's outer edge. Update these when the backtest is rerun.
const BACKTEST_YEARS = "2024 to 2026";
const BANDS: { band: "safer" | "competitive" | "ambitious"; rule: string; low: number; high: number; plain: string }[] = [
  {
    band: "safer", rule: "Your rank is at least 10% inside every closing rank from the last three years.", low: 91, high: 94,
    plain: "About 9 in 10 seats still closed beyond a rank at the very edge of this band.",
  },
  {
    band: "competitive", rule: "Your rank is within the worst closing rank from the last three years.", low: 36, high: 41,
    plain: "About 4 in 10 seats closed beyond a rank at the very edge. Ranks further inside the band did better.",
  },
  {
    band: "ambitious", rule: "Your rank is up to 20% beyond the worst recent closing rank.", low: 6, high: 10,
    plain: "About 1 in 10 seats closed beyond a rank at the very edge. Worth listing, not worth relying on.",
  },
];

export function BandsExplainer({ page }: { page: "shortlist" | "preferences" }) {
  const [open, setOpen] = useState(false);
  const toggle = () => {
    if (!open) track("bands_explainer_opened", { page });
    setOpen(!open);
  };
  return (
    <section className="card p-4" aria-labelledby="bands-explainer-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl">
          <h2 id="bands-explainer-title" className="text-lg">What the bands mean, and why there’s no percentage</h2>
          <p className="mt-1 text-sm text-ink-2">A band compares your rank with what happened in past years. It isn’t your chance of a seat, because that depends on how thousands of others fill their lists this year.</p>
        </div>
        <button type="button" className="inline-flex items-center gap-1 text-sm font-semibold text-brand hover:underline" aria-expanded={open} aria-controls="bands-explainer-body" onClick={toggle}>
          <ChevronDown size={15} className={`chev ${open ? "rotate-180" : ""}`} aria-hidden /> {open ? "Hide" : "How reliable are they?"}
        </button>
      </div>
      {open && (
        <div id="bands-explainer-body" className="rise mt-4 space-y-4 border-t border-line pt-4">
          <p className="text-sm text-ink-2">We tested each band against the following year, for {BACKTEST_YEARS}: if your rank had been exactly at the band’s outer edge, how often would that seat still have closed at or beyond it?</p>
          <ul className="space-y-4">
            {BANDS.map((b) => {
              const meta = bandMeta(b.band);
              return (
                <li key={b.band} className="grid gap-2 sm:grid-cols-[180px_1fr] sm:gap-4">
                  <div>
                    <p className="font-medium" style={{ color: meta.color }}>{meta.label}</p>
                    <p className="text-xs text-ink-3">{b.rule}</p>
                  </div>
                  <div>
                    <div className="relative h-3 overflow-hidden rounded-full bg-[var(--surface-2)]" role="img" aria-label={`${meta.label}: held for ${b.low}% to ${b.high}% of seats at the band's edge`}>
                      <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${b.low}%`, background: meta.color }} />
                      <div className="absolute inset-y-0 rounded-r-full opacity-40" style={{ left: `${b.low}%`, width: `${b.high - b.low}%`, background: meta.color }} />
                    </div>
                    <p className="tnum mt-1 text-sm"><span className="font-medium">{b.low}% to {b.high}%</span> <span className="text-ink-2">of seats held at the edge.</span></p>
                    <p className="text-xs text-ink-3">{b.plain}</p>
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="space-y-1.5 text-xs text-ink-3">
            <p>These figures are about seats, not about you. They are the worst case for each band: most ranks sit further inside it and did better.</p>
            <p>We don’t turn them into a personal percentage. Results for individual applicants aren’t published, so a number like “87% chance” can’t be checked, and it would look more certain than it is.</p>
            <p>A good list keeps some Safer options below the Ambitious and Competitive ones. <Link href="/methodology" className="underline">See the full method</Link>.</p>
          </div>
        </div>
      )}
    </section>
  );
}
