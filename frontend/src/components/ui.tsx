import { ExternalLink, Info } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import type { Band, Component, Fee, Placement, Quality, Ranking } from "@/lib/api";
import { inr, num } from "@/lib/api";

const BAND_STYLE: Record<string, { label: string; color: string; bg: string; hint: string }> = {
  safer: { label: "Safer historical range", color: "var(--safer)", bg: "var(--safer-soft)", hint: "At least 10% inside every recent closing rank" },
  competitive: { label: "Competitive", color: "var(--competitive)", bg: "var(--competitive-soft)", hint: "Close to or within recent closing ranks" },
  ambitious: { label: "Ambitious", color: "var(--ambitious)", bg: "var(--ambitious-soft)", hint: "Up to 20% beyond recent closing ranks" },
  beyond: { label: "Beyond recent range", color: "var(--ink-2)", bg: "var(--neutral-soft)", hint: "More than 20% beyond recent closing ranks" },
  limited_history: { label: "Limited history", color: "var(--ink-2)", bg: "var(--neutral-soft)", hint: "Too few recent years to place in a band, so treat this with extra care" },
};

export const bandMeta = (band: Band | "limited_history") => BAND_STYLE[band ?? "limited_history"];

export function BandBadge({ band }: { band: Band | "limited_history" }) {
  const style = bandMeta(band);
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold" style={{ color: style.color, background: style.bg }} title={style.hint}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: style.color }} aria-hidden />{style.label}
    </span>
  );
}

const VERIFY: Record<string, { label: string; tone: string }> = {
  official: { label: "Official source", tone: "var(--safer)" },
  verified: { label: "Independently verified", tone: "var(--safer)" },
  secondary_unverified: { label: "Secondary source, unverified", tone: "var(--competitive)" },
  manual_unverified: { label: "Entered by hand, unverified", tone: "var(--competitive)" },
  outdated: { label: "Outdated", tone: "var(--ambitious)" },
  test_fixture: { label: "TEST FIXTURE, not real data", tone: "var(--ambitious)" },
};

export function VerificationTag({ status }: { status: string }) {
  const meta = VERIFY[status] ?? { label: status, tone: "var(--ink-2)" };
  return <span className="text-xs font-medium" style={{ color: meta.tone }}>{meta.label}</span>;
}

export function NotAvailable({ what }: { what?: string }) {
  return <span className="text-sm text-ink-3">Data not available{what ? ` for ${what}` : ""}</span>;
}

export function SourceLink({ href, label }: { href: string; label: string }) {
  if (!href.startsWith("http")) return <span className="text-xs text-ink-3">{label}</span>;
  return (
    <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-ink-2 underline decoration-line underline-offset-2 hover:text-ink">
      {label} <ExternalLink size={11} aria-hidden />
    </a>
  );
}

export function RankingLine({ ranking }: { ranking: Ranking | null }) {
  if (!ranking) return <NotAvailable />;
  return (
    <div>
      <p className="tnum font-medium">NIRF {ranking.category} #{ranking.rank} <span className="font-normal text-ink-3">({ranking.year})</span></p>
      <p className="mt-0.5"><VerificationTag status={ranking.verification_status} /></p>
      <SourceLink href={ranking.source_url} label={ranking.source_name} />
    </div>
  );
}

function PlacementGroup({ records }: { records: Placement[] }) {
  const first = records[0];
  const nirf = first.reporting_definition.startsWith("nirf_");
  const ctc = first.salary_basis === "CTC";
  const hasHigher = records.some((r) => r.higher_studies_students != null);
  return (
    <div className="text-sm">
      <p className="font-medium">{first.scope_label}</p>
      <p className="text-xs text-ink-3">{first.cohort_label}</p>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[320px] text-left">
          <thead><tr className="border-b border-line text-xs text-ink-3">
            <th scope="col" className="py-1 pr-2 font-normal">Graduated</th>
            <th scope="col" className="py-1 pr-2 text-right font-normal">{ctc ? "Median CTC" : "Median salary"}</th>
            <th scope="col" className="py-1 pr-2 text-right font-normal">Placed</th>
            {hasHigher && <th scope="col" className="py-1 text-right font-normal">Higher studies</th>}
          </tr></thead>
          <tbody>
            {records.map((r) => {
              const base = r.base_students ?? r.graduating_students ?? r.eligible_students;
              return (
                <tr key={r.graduation_year} className="border-b border-line last:border-0">
                  <td className="tnum py-1 pr-2">{r.graduation_year}</td>
                  <td className="tnum py-1 pr-2 text-right font-medium">{r.median_salary_inr == null ? "Not published" : inr(r.median_salary_inr)}</td>
                  <td className="tnum py-1 pr-2 text-right">{r.students_placed == null ? "—" : base == null ? num(r.students_placed) : `${num(r.students_placed)} of ${num(base)}`}</td>
                  {hasHigher && <td className="tnum py-1 text-right">{num(r.higher_studies_students)}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {nirf && <p className="mt-2 text-xs text-ink-3">Self-reported to NIRF and not audited. “Of” counts students who graduated in the minimum time, which is not the number eligible for placement. The median covers placed students only.</p>}
      {first.reporting_definition === "nirf_graduation_outcomes_overall" && <p className="mt-1 text-xs text-ink-3">From the institute’s Overall submission, which may include non-engineering programmes. It isn’t directly comparable with Engineering submissions.</p>}
      {first.base_label && <p className="mt-2 text-xs text-ink-3">“Of” counts {first.base_label}{first.total_students != null ? `. This branch has ${num(first.total_students)} students in total` : ""}. {ctc ? "CTC includes items beyond take-home pay. " : ""}Self-reported by the institute. Definitions differ between institutes.</p>}
      <p className="mt-1"><VerificationTag status={first.verification_status} /></p>
      <SourceLink href={first.source_url} label={first.source_page ? `${first.source_title}, page ${first.source_page}` : first.source_title} />
    </div>
  );
}

export function PlacementBlock({ records }: { records: Placement[] }) {
  if (!records.length) return <NotAvailable />;
  const groups = new Map<string, Placement[]>();
  for (const r of records) {
    const key = `${r.scope}|${r.reporting_definition}|${r.cohort_label}`;
    groups.set(key, [...(groups.get(key) ?? []), r]);
  }
  return <div className="space-y-5">{[...groups.entries()].map(([key, group]) => <PlacementGroup key={key} records={group} />)}</div>;
}

export function FeeBlock({ fee }: { fee: Fee | null }) {
  if (!fee) return <NotAvailable />;
  const lines: [string, number | null][] = [
    ["Tuition a year", fee.annual_tuition_inr], ["Hostel a year", fee.annual_hostel_inr], ["Mess advances a year", fee.annual_mess_inr],
    ["Other yearly charges", fee.annual_other_inr], ["One-time charges", fee.one_time_inr], ["Refundable deposits", fee.refundable_deposit_inr],
  ];
  return (
    <div className="text-sm">
      {fee.payable_at_admission_inr != null && <p className="tnum font-medium">{inr(fee.payable_at_admission_inr)} <span className="font-normal text-ink-2">stated for the first payment</span></p>}
      <p className="text-xs text-ink-3">{fee.academic_year} · {fee.seat_type_group}</p>
      <dl className="mt-2 space-y-0.5">
        {lines.filter(([, v]) => v != null).map(([label, v]) => <div key={label} className="flex justify-between gap-3"><dt className="text-ink-2">{label}</dt><dd className="tnum">{inr(v)}</dd></div>)}
      </dl>
      {fee.annual_complete_inr == null && <p className="mt-2 text-xs text-ink-3">This doesn’t show a full yearly cost, because tuition, hostel and mess aren’t all listed together.</p>}
      {fee.notes && <p className="mt-2 text-xs text-ink-3">{fee.notes}</p>}
      <p className="mt-1"><VerificationTag status={fee.verification_status} /></p>
      <SourceLink href={fee.source_url} label={fee.source_page ? `${fee.source_title}, page ${fee.source_page}` : fee.source_title} />
    </div>
  );
}

// Where a rank sits against past closing ranks. A position on a scale, not a chance of admission.
export function RankGauge({ rank, low, high, color }: { rank: number; low: number; high: number; color: string }) {
  const top = Math.max(rank, high) * 1.15;
  const at = (v: number) => `${(v / top) * 100}%`;
  return (
    <div className="mt-2 pb-1" role="img" aria-label={`Your rank ${rank.toLocaleString("en-IN")}, past closing ranks ${low.toLocaleString("en-IN")} to ${high.toLocaleString("en-IN")}. A lower rank is stronger.`}>
      <div className="relative h-2 rounded-full bg-surface-2">
        <div className="grow-x absolute inset-y-0 rounded-full" style={{ left: at(low), width: `${Math.max(1.5, ((high - low) / top) * 100)}%`, background: "var(--ink-3)" }} />
        <span className="pop absolute top-1/2 -ml-[7px] -mt-[7px] h-3.5 w-3.5 rounded-full border-2 border-surface" style={{ left: at(rank), background: color, "--delay": "420ms" } as CSSProperties} />
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-ink-3"><span>Stronger rank</span><span>Grey: past closing ranks</span></div>
    </div>
  );
}

export function ScoreBar({ value, label }: { value: number | null; label?: string }) {
  return (
    <div className="flex items-center gap-2" role="img" aria-label={value == null ? `${label ?? "Score"}: no data` : `${label ?? "Score"}: ${value} out of 100`}>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
        {value != null && <div className="grow-x h-full rounded-full transition-[width] duration-500" style={{ width: `${Math.max(2, value)}%`, background: "linear-gradient(90deg, var(--brand), var(--teal))" }} />}
      </div>
      <span className="tnum w-14 text-right text-xs text-ink-2">{value == null ? "No data" : Math.round(value)}</span>
    </div>
  );
}

export function QualityScore({ quality }: { quality: Quality }) {
  if (quality.score == null) {
    return (
      <div>
        <p className="font-medium">Not scored yet</p>
        <p className="text-sm text-ink-2">Only {Math.round(quality.coverage * 100)}% of the evidence is available. A score needs at least 50%.</p>
      </div>
    );
  }
  return (
    <div>
      <p className="tnum text-2xl font-medium">{quality.score}<span className="text-sm font-normal text-ink-3"> / 100</span></p>
      <p className="text-sm text-ink-2">Based on {Math.round(quality.coverage * 100)}% of the evidence</p>
    </div>
  );
}

export function ComponentList({ components }: { components: Component[] }) {
  return (
    <ul className="space-y-2.5">
      {components.map((c) => (
        <li key={c.key}>
          <div className="flex justify-between gap-3 text-sm">
            <span>{c.label}</span>
            <span className="tnum shrink-0 text-xs text-ink-3">weight {Math.round(c.weight)}%</span>
          </div>
          <ScoreBar value={c.score} label={c.label} />
          <p className="text-xs text-ink-3">{c.note}</p>
        </li>
      ))}
    </ul>
  );
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warn" | "error" }) {
  const color = tone === "error" ? "var(--ambitious)" : tone === "warn" ? "var(--competitive)" : "var(--ink-2)";
  const bg = tone === "error" ? "var(--ambitious-soft)" : tone === "warn" ? "var(--competitive-soft)" : "var(--surface-2)";
  return (
    <div className="flex gap-2.5 rounded-xl px-3.5 py-3 text-sm" style={{ background: bg, borderLeft: `3px solid ${color}` }} role={tone === "error" ? "alert" : undefined}>
      <Info size={16} className="mt-0.5 shrink-0" style={{ color }} aria-hidden />
      <div className="text-ink">{children}</div>
    </div>
  );
}

export function Section({ title, children, hint }: { title: string; children: ReactNode; hint?: string }) {
  return (
    <section className="card p-5">
      <h2 className="text-lg">{title}</h2>
      {hint && <p className="mt-0.5 text-sm text-ink-3">{hint}</p>}
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function PageHeader({ title, intro, children }: { title: string; intro?: ReactNode; children?: ReactNode }) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-2xl">
        <h1 className="text-3xl font-bold sm:text-5xl">{title}</h1>
        {intro && <p className="mt-3 text-lg text-ink-2">{intro}</p>}
      </div>
      {children}
    </header>
  );
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => <div key={i} className="shimmer h-20 rounded-2xl" />)}
    </div>
  );
}
