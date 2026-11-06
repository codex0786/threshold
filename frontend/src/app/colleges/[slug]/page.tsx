import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CareerSections } from "@/components/careers";
import { FeeBlock, NotAvailable, PlacementBlock, RankingLine, Section, VerificationTag } from "@/components/ui";
import { api, ApiError, type InstitutionDetail, num } from "@/lib/api";

const FIELD_LABELS: Record<string, string> = {
  cutoffs: "Official cutoffs", nirf_rank: "NIRF rank", placements: "Placement records", fees: "Fee records",
  website: "Official website", location_confirmed: "State confirmed",
};

export default async function CollegePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const inst = await api<InstitutionDetail>(`/institutions/${slug}`).catch((e: ApiError) => {
    if (e.message.includes("not found")) notFound();
    throw e;
  });
  const current = inst.programmes.filter((p) => p.currently_offered);
  const past = inst.programmes.filter((p) => !p.currently_offered);
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <Link href="/colleges" className="text-sm text-ink-3 hover:text-ink">← All colleges</Link>
      <header className="mb-6 mt-3">
        <h1 className="text-3xl font-bold sm:text-5xl">{inst.short_name}</h1>
        <p className="mt-1 text-ink-2">{inst.official_name}</p>
        <p className="mt-1 text-sm text-ink-3">
          {inst.city ? `${inst.city}, ` : ""}{inst.state} · <VerificationTag status={inst.location_verification} />
          {inst.website && <> · <a href={inst.website} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline underline-offset-2">Official website <ExternalLink size={11} aria-hidden /></a></>}
        </p>
      </header>
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <Section title="Programmes" hint="As listed in JoSAA. Open one to see its cutoff history.">
            <ul className="divide-y divide-line">
              {current.map((p) => (
                <li key={p.id} className="py-2.5">
                  <Link href={`/programmes/${p.id}`} className="block hover:underline">{p.name}</Link>
                  <p className="text-xs text-ink-3">{p.degree}{p.duration_years ? `, ${p.duration_years} years` : ""} · {p.branch_label}</p>
                </li>
              ))}
            </ul>
            {past.length > 0 && (
              <details className="mt-3 text-sm">
                <summary className="cursor-pointer text-ink-2">{num(past.length)} names not listed in the latest year</summary>
                <p className="mt-1 text-xs text-ink-3">These may be discontinued or renamed. We keep their history.</p>
                <ul className="mt-2 space-y-1">{past.map((p) => <li key={p.id}><Link href={`/programmes/${p.id}`} className="hover:underline">{p.name}</Link> <span className="tnum text-xs text-ink-3">(last seen {p.last_seen_year})</span></li>)}</ul>
              </details>
            )}
          </Section>
          <Section title="Institute-wide placements" hint="These cover the whole institute, not a particular branch.">
            <PlacementBlock records={inst.institution_placements} />
          </Section>
          <CareerSections careers={inst.careers} />
          <Section title="History, facilities and research"><NotAvailable /></Section>
        </div>
        <div className="space-y-5">
          <Section title="Ranking">
            {inst.rankings.length ? <div className="space-y-3">{inst.rankings.map((r) => <RankingLine key={r.year} ranking={r} />)}</div> : <NotAvailable />}
          </Section>
          <Section title="Fees"><FeeBlock fee={inst.fee} /></Section>
          {Object.keys(inst.quota_states).length > 0 && (
            <Section title="Home-state seats" hint="Based on the state of your first Class XII attempt.">
              <ul className="space-y-1 text-sm">{Object.entries(inst.quota_states).map(([q, states]) => <li key={q}><span className="font-medium">{q}:</span> {states.join(", ")}</li>)}</ul>
            </Section>
          )}
          <Section title="How complete is this data?">
            <p className="tnum text-2xl">{inst.completeness.percent}%</p>
            <ul className="mt-2 space-y-1 text-sm">
              {Object.entries(inst.completeness.fields).map(([k, ok]) => <li key={k} className="flex justify-between"><span>{FIELD_LABELS[k] ?? k}</span><span className={ok ? "" : "text-ink-3"}>{ok ? "Yes" : "Not yet"}</span></li>)}
            </ul>
          </Section>
          {inst.aliases.length > 0 && <Section title="Also listed as"><ul className="space-y-1 text-sm text-ink-2">{inst.aliases.map((a) => <li key={a}>{a}</li>)}</ul></Section>}
        </div>
      </div>
    </div>
  );
}
