import { ArrowRight, GraduationCap, Scale, Stethoscope, Wrench } from "lucide-react";
import Link from "next/link";
import { num } from "@/lib/api";
import { byStream, type CatalogEntry, type StreamKey } from "@/lib/exams";

export const STREAM_STYLE: Record<StreamKey, { icon: typeof Wrench; tone: string }> = {
  Engineering: { icon: Wrench, tone: "var(--teal)" },
  Medical: { icon: Stethoscope, tone: "var(--ambitious)" },
  Law: { icon: Scale, tone: "var(--competitive)" },
  Postgraduate: { icon: GraduationCap, tone: "var(--brand)" },
};

function facts(e: CatalogEntry): string[] {
  return [
    e.year,
    e.institutes ? `${num(e.institutes)} institutes` : "",
    e.bands ? "Admission bands" : "Round by round",
  ].filter(Boolean);
}

/** Compact list for the home hero: every exam, grouped by stream, one row each. */
export function ExamPickerRows({ entries }: { entries: CatalogEntry[] }) {
  return (
    <nav aria-label="Choose your exam" className="glass p-2 sm:p-3">
      {byStream(entries).map(({ stream, entries: rows }) => {
        const style = STREAM_STYLE[stream.key];
        return (
          <div key={stream.key} className="py-1">
            <p className="flex items-center gap-1.5 px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-[0.08em] text-ink-3">
              <style.icon size={13} aria-hidden style={{ color: `color-mix(in srgb, ${style.tone} 45%, white)` }} />{stream.label}
            </p>
            <ul>
              {rows.map((e) => (
                <li key={e.code}>
                  <Link href={e.href} className="group flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 transition-colors hover:bg-surface-2 focus-visible:bg-surface-2">
                    <span className="min-w-0">
                      <span className="block font-semibold leading-tight">{e.name}</span>
                      <span className="block truncate text-sm text-ink-2">{e.scope}</span>
                    </span>
                    <span className="flex shrink-0 items-center gap-3">
                      {e.bands && <span className="hidden rounded-full px-2 py-0.5 text-xs font-medium sm:inline" style={{ background: "color-mix(in srgb, var(--safer) 22%, transparent)", color: "#bff5e6" }}>Bands</span>}
                      <ArrowRight size={16} className="text-ink-3 transition-transform group-hover:translate-x-0.5 group-hover:text-ink" aria-hidden />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

/** Cards for the exams hub: grouped by stream, with what each covers. */
export function ExamPickerCards({ entries }: { entries: CatalogEntry[] }) {
  return (
    <div className="space-y-10">
      {byStream(entries).map(({ stream, entries: cards }) => {
        const style = STREAM_STYLE[stream.key];
        return (
          <section key={stream.key} aria-labelledby={`stream-${stream.key}`}>
            <div className="flex items-baseline gap-3">
              <h2 id={`stream-${stream.key}`} className="flex items-center gap-2 text-2xl">
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg" style={{ background: `color-mix(in srgb, ${style.tone} 14%, transparent)`, color: style.tone }}><style.icon size={17} aria-hidden /></span>
                {stream.label}
              </h2>
              <p className="text-sm text-ink-3">{stream.blurb}</p>
            </div>
            <ul className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {cards.map((e) => (
                <li key={e.code}>
                  <Link href={e.href} className="card card-hover group flex h-full flex-col p-5" style={{ borderTop: `3px solid ${style.tone}` }}>
                    <span className="font-display text-lg font-semibold leading-tight group-hover:text-brand">{e.name}</span>
                    <span className="mt-0.5 text-sm text-ink-2">{e.scope}</span>
                    <span className="mt-4 flex flex-wrap gap-1.5">
                      {facts(e).map((f) => <span key={f} className="tnum rounded-full bg-surface-2 px-2.5 py-0.5 text-xs text-ink-2">{f}</span>)}
                    </span>
                    <span className="mt-auto flex items-center justify-between pt-5 text-sm">
                      <span className="text-ink-3">Enter your {e.enter}</span>
                      <span className="inline-flex items-center gap-1 font-semibold text-brand">Start <ArrowRight size={15} className="transition-transform group-hover:translate-x-1" aria-hidden /></span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

