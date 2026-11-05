import Link from "next/link";
import type { Careers } from "@/lib/api";
import { inr, num } from "@/lib/api";
import { NotAvailable, Section, SourceLink, VerificationTag } from "./ui";

function Bar({ share }: { share: number }) {
  return <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2" aria-hidden><div className="h-full rounded-full bg-brand" style={{ width: `${Math.min(100, Math.max(1, share))}%` }} /></div>;
}

export function CareerSummary({ careers }: { careers: Careers }) {
  const top = careers.sectors?.items.slice(0, 2).map((s) => `${s.sector} ${s.percent}%`).join(", ");
  const latest = careers.outcome_mix.at(-1);
  if (!top && !careers.recruiters && !latest) return <NotAvailable />;
  return (
    <div className="space-y-1 text-sm">
      {latest?.higher_studies_students != null && latest.graduating_students != null && <p className="tnum">{num(latest.higher_studies_students)} of {num(latest.graduating_students)} went to higher studies ({latest.graduation_year}, self-reported)</p>}
      {top && <p>Sectors: {top} ({careers.sectors?.academic_year})</p>}
      {careers.recruiters && <p className="tnum">{num(careers.recruiters.count)} recruiters listed ({careers.recruiters.academic_year})</p>}
    </div>
  );
}

export function CareerSections({ careers, highlight }: { careers: Careers; highlight?: number }) {
  const { branch_outcomes: branches, outcome_mix: mix, sectors, recruiters, alumni } = careers;
  const maxMedian = Math.max(0, ...branches.map((b) => b.median_salary_inr ?? 0));
  const first = branches[0];
  return (
    <>
      <Section title="Branch outcomes" hint={first ? `From the institute’s own report for ${first.graduation_year} graduates. Only compare branches within this table.` : undefined}>
        {!branches.length ? <NotAvailable what="individual branches" /> : (
          <>
            <ul className="space-y-2.5">
              {branches.map((b) => (
                <li key={b.programme_id} className={b.programme_id === highlight ? "rounded-md bg-brand-soft p-2" : ""}>
                  <div className="flex flex-wrap justify-between gap-x-3 text-sm">
                    <Link href={`/programmes/${b.programme_id}`} className={`hover:underline ${b.programme_id === highlight ? "font-medium" : ""}`}>{b.programme}</Link>
                    <span className="tnum text-ink-2">{b.median_salary_inr != null ? `${inr(b.median_salary_inr)} median ${b.salary_basis ?? ""}` : "Median not published"}</span>
                  </div>
                  {b.median_salary_inr != null && <div className="my-1 flex"><Bar share={(100 * b.median_salary_inr) / maxMedian} /></div>}
                  <p className="tnum text-xs text-ink-3">{num(b.students_placed)} placed of {num(b.base_students)} {b.base_label}{b.total_students != null ? `, ${num(b.total_students)} students in total` : ""}</p>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-ink-3">{first.notes}</p>
            <p className="mt-1"><VerificationTag status={first.verification_status} /></p>
            <SourceLink href={first.source_url} label={first.source_page ? `${first.source_title}, page ${first.source_page}` : first.source_title} />
          </>
        )}
      </Section>

      <Section title="What graduates did next" hint="All 4-year UG students at the institute, as reported to NIRF. Students not counted here aren’t necessarily unemployed, because their outcome just isn’t reported.">
        {!mix.length ? <NotAvailable /> : (
          <>
            <ul className="space-y-2">
              {mix.map((m) => {
                const total = m.graduating_students ?? 0;
                const placed = m.students_placed ?? 0;
                const higher = m.higher_studies_students ?? 0;
                return (
                  <li key={m.graduation_year} className="text-sm">
                    <p className="tnum">{m.graduation_year}: {num(placed)} placed, {num(higher)} higher studies, of {num(total)} graduating on time</p>
                    {total > 0 && <div className="mt-1 flex"><Bar share={(100 * Math.min(total, placed + higher)) / total} /></div>}
                  </li>
                );
              })}
            </ul>
            <div className="mt-2"><SourceLink href={mix[0].source_url} label={mix[0].source_title} /></div>
          </>
        )}
      </Section>

      <Section title="Sectors hiring" hint={sectors ? `${sectors.cohort_label}, ${sectors.academic_year}` : undefined}>
        {!sectors ? <NotAvailable /> : (
          <>
            <ul className="space-y-2">
              {sectors.items.map((s) => (
                <li key={s.sector} className="text-sm">
                  <div className="flex justify-between gap-3"><span>{s.sector}</span><span className="tnum text-ink-2">{num(s.students)} ({s.percent}%)</span></div>
                  <div className="mt-1 flex"><Bar share={s.percent} /></div>
                </li>
              ))}
            </ul>
            <div className="mt-2"><SourceLink href={sectors.source_url} label={sectors.source_page ? `${sectors.source_title}, page ${sectors.source_page}` : sectors.source_title} /></div>
          </>
        )}
      </Section>

      <Section title="Recruiters listed" hint={recruiters ? `${num(recruiters.count)} companies, ${recruiters.academic_year}` : undefined}>
        {!recruiters ? <NotAvailable /> : (
          <>
            <p className="text-sm text-ink-2">{recruiters.companies.join(", ")}</p>
            <p className="mt-2 text-xs text-ink-3">{recruiters.note} Read from logos in the report, and unclear logos were left out.</p>
            <SourceLink href={recruiters.source_url} label={recruiters.source_title} />
          </>
        )}
      </Section>

      <Section title="Alumni: a public sample" hint="Not the alumni network.">
        {!alumni ? <NotAvailable /> : alumni.status !== "available" ? (
          <p className="text-sm text-ink-3">Only {num(alumni.sample_size)} documented people were found, and we need at least {alumni.minimum} to show a pattern.</p>
        ) : (
          <>
            <p className="tnum text-sm font-medium">{num(alumni.sample_size)} people documented on Wikidata{alumni.founders ? `, ${num(alumni.founders)} listed as founders of an organisation` : ""}</p>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <div><h3 className="text-sm font-medium">Occupations</h3><ul className="mt-1 space-y-0.5 text-sm text-ink-2">{alumni.occupations?.map((o) => <li key={o.label} className="flex justify-between gap-3"><span>{o.label}</span><span className="tnum">{num(o.people)}</span></li>)}</ul></div>
              <div><h3 className="text-sm font-medium">Employers</h3><ul className="mt-1 space-y-0.5 text-sm text-ink-2">{alumni.employers?.map((o) => <li key={o.label} className="flex justify-between gap-3"><span>{o.label}</span><span className="tnum">{num(o.people)}</span></li>)}</ul></div>
            </div>
            <p className="mt-3 text-xs text-ink-3">{alumni.caveat} Retrieved {alumni.retrieved_at}. Names aren’t stored.</p>
            <SourceLink href={alumni.source_url} label="Wikidata" />
          </>
        )}
      </Section>
    </>
  );
}
