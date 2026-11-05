import { Notice, PageHeader, Section, SourceLink } from "@/components/ui";
import { api, type Completeness, type DataSource, type Meta, num } from "@/lib/api";

// Figures come from the API, so the page is rebuilt hourly rather than frozen at build time.
export const revalidate = 3600;

const STATUS: Record<string, string> = { available: "In use", planned: "Planned", manual_only: "Manual import only", blocked: "Blocked" };

export default async function Methodology() {
  const [meta, completeness, sources] = await Promise.all([
    api<Meta>("/meta"), api<Completeness>("/data/completeness"), api<{ sources: DataSource[] }>("/data/sources"),
  ]);
  const coverage: [string, number][] = [
    ["Official cutoffs", completeness.coverage.cutoffs], ["NIRF rank (secondary source)", completeness.coverage.nirf_rank],
    ["Placement records (self-reported, institute-wide)", completeness.coverage.placements], ["Fee records (official circulars)", completeness.coverage.fees],
    ["Location verified", completeness.coverage.location_verified],
  ];
  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <PageHeader title="Data and methodology" intro="How the results are made, what they can’t tell you, and where each piece of data comes from." />
      <div className="space-y-5">
        <Section title="Three separate answers">
          <dl className="space-y-3">
            <div><dt className="font-medium">Admission band</dt><dd className="text-ink-2">Compares your rank with final-round closing ranks from the latest three years, on the same rank list, quota, seat type and pool. Safer means at least 10% inside every one of those closing ranks. Competitive means up to the highest of them. Ambitious means up to 20% beyond it. It needs at least two years of history.</dd></div>
            <div><dt className="font-medium">Quality score</dt><dd className="text-ink-2">Combines the evidence below using starting weights we chose, which are product assumptions and not scientific findings. We withhold the score until at least 50% of the evidence by weight is available. <strong className="font-medium text-ink">At present, no option reaches that level.</strong> Placement figures are institute-wide, so they count for only half their weight here.</dd></div>
            <div><dt className="font-medium">Suitability score</dt><dd className="text-ink-2">Reflects your own priorities. Where we have no information on something, it counts as a neutral 50 for that option.</dd></div>
            <div><dt className="font-medium">Placements within suitability</dt><dd className="text-ink-2">Each institute’s self-reported median salary is compared with other institutes for the same graduating year, using only Engineering submissions to NIRF. The highest package is never used. These figures cover whole institutes, not branches, so every branch of an institute gets the same placement score, and that can hide large differences between branches. Five-year programmes and classes of fewer than 100 graduates aren’t scored. <strong className="font-medium text-ink">Institutes that publish data tend to attract stronger ranks than those that don’t, and an institute that publishes nothing gets a neutral score. So an institute that reports modest results can rank below one that reports nothing. Treat this part of the score with care.</strong></dd></div>
          </dl>
        </Section>
        <Section title="Starting quality weights">
          <ul className="grid gap-x-8 gap-y-1 sm:grid-cols-2">
            {Object.entries(meta.quality_weights).map(([k, w]) => <li key={k} className="flex justify-between text-sm"><span>{meta.quality_labels[k]}</span><span className="tnum text-ink-3">{w}%</span></li>)}
          </ul>
        </Section>
        <Section title="What the bands can’t tell you">
          <Notice tone="warn">A band is not a chance of admission. We show no percentages, because results for individual applicants are not public and a percentage could not be properly tested.</Notice>
          <p className="mt-3 text-ink-2">We did test how stable the bands were. Using three earlier years to set the band edges, a rank at the outer edge of Safer would still have been within the next year’s closing rank for 91% to 94% of seats in 2024, 2025 and 2026. At the outer edge of Ambitious, the figure was 6% to 10%. This measures how seats behaved overall, not your own odds, and future years may differ.</p>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-ink-2">
            <li>This covers JoSAA only. CSAB special rounds and state counselling are not included.</li>
            <li>The latest year’s final round is the last one published when we collected the data.</li>
            <li>Programme-specific medical and other restrictions are not checked. See the JoSAA annexures.</li>
            <li>Seat counts are not yet considered.</li>
          </ul>
        </Section>
        <Section title="Current coverage" hint={`Out of ${num(completeness.institutions)} institutes, ${num(completeness.programmes)} programme names and ${num(completeness.cutoff_records)} cutoff records.`}>
          <ul className="space-y-1">{coverage.map(([label, n]) => <li key={label} className="flex justify-between text-sm"><span>{label}</span><span className="tnum text-ink-2">{num(n)} institutes</span></li>)}</ul>
          <p className="mt-3 text-sm text-ink-3">Not yet collected: {completeness.not_yet_collected.join(", ")}.</p>
        </Section>
        <Section title="Sources">
          <ul className="divide-y divide-line">
            {sources.sources.map((s) => (
              <li key={s.key} className="py-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2"><h3 className="font-medium">{s.name}</h3><span className="text-xs text-ink-3">{STATUS[s.access_status] ?? s.access_status}</span></div>
                <p className="text-sm text-ink-2">{s.publisher} · {s.access_method}</p>
                {s.terms_note && <p className="text-xs text-ink-3">{s.terms_note}</p>}
                <SourceLink href={s.url} label={s.url.replace(/^https?:\/\//, "")} />
              </li>
            ))}
          </ul>
        </Section>
      </div>
    </div>
  );
}
