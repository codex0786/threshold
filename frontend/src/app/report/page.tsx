"use client";
import { Printer } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CareerSummary } from "@/components/careers";
import { Notice, Skeleton, SourceLink } from "@/components/ui";
import { inr, num, type ParentReport, post, type Profile } from "@/lib/api";
import { loadLists, loadProfile } from "@/lib/store";

const MAX_OPTIONS = 8;

export default function ReportPage() {
  const [profile, setProfile] = useState<Profile | null | undefined>(undefined);
  const [report, setReport] = useState<ParentReport | null>(null);
  const [empty, setEmpty] = useState(false);
  const [trimmed, setTrimmed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const stored = loadProfile();
    setProfile(stored);
    if (!stored) return;
    const items = loadLists()[0].items;
    if (!items.length) { setEmpty(true); return; }
    setTrimmed(Math.max(0, items.length - MAX_OPTIONS));
    post<ParentReport>("/reports/parent", { profile: stored as Profile, programme_ids: items.slice(0, MAX_OPTIONS).map((i) => i.id) }).then(setReport).catch((e) => setError(e.message));
  }, []);

  if (profile === undefined) return <div className="mx-auto max-w-3xl px-4 py-10"><Skeleton /></div>;
  if (profile === null || empty) return <div className="mx-auto max-w-xl px-4 py-16 text-center"><h1 className="text-3xl">Nothing to report yet</h1><p className="mt-2 text-ink-2">The report covers the choices in your preference list.</p><Link href={profile ? "/recommendations" : "/onboarding"} className="btn btn-primary mt-5">{profile ? "Go to my shortlist" : "Find my best fit"}</Link></div>;
  if (error) return <div className="mx-auto max-w-3xl px-4 py-10"><Notice tone="error">{error}</Notice></div>;
  if (!report) return <div className="mx-auto max-w-3xl px-4 py-10"><Skeleton /></div>;

  const s = report.student;
  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <div className="no-print mb-6 flex justify-end"><button className="btn btn-primary" onClick={() => window.print()}><Printer size={15} aria-hidden /> Save as PDF</button></div>
      <header>
        <p className="text-sm text-ink-3">College decision report · {report.generated_on}</p>
        <h1 className="mt-1 text-3xl font-bold sm:text-5xl">Your child’s college options, explained</h1>
        <p className="mt-3 text-ink-2">This report compares {report.options.length} choice{report.options.length === 1 ? "" : "s"} your child has shortlisted, in the order they chose. It uses official counselling records and figures published by the institutes. Where we don’t have information, we say so.</p>
      </header>
      {trimmed > 0 && <div className="mt-4"><Notice tone="warn">Only the first {MAX_OPTIONS} choices are included. {trimmed} more aren’t covered here.</Notice></div>}

      <section className="mt-8">
        <h2 className="text-2xl">Student profile</h2>
        <dl className="tnum mt-2 grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
          <div className="flex justify-between gap-3"><dt className="text-ink-2">JEE Main rank (all-India list)</dt><dd>{num(s.main_rank)}</dd></div>
          {s.main_category_rank != null && <div className="flex justify-between gap-3"><dt className="text-ink-2">JEE Main category rank</dt><dd>{num(s.main_category_rank)}</dd></div>}
          {s.advanced_rank != null && <div className="flex justify-between gap-3"><dt className="text-ink-2">JEE Advanced rank</dt><dd>{num(s.advanced_rank)}</dd></div>}
          <div className="flex justify-between gap-3"><dt className="text-ink-2">Category</dt><dd>{s.category}{s.is_pwd ? ", PwD" : ""}</dd></div>
          <div className="flex justify-between gap-3"><dt className="text-ink-2">State of first Class XII attempt</dt><dd>{s.state}</dd></div>
        </dl>
      </section>

      {report.advice.length > 0 && (
        <section className="mt-6 space-y-2"><h2 className="text-2xl">Worth discussing together</h2>{report.advice.map((a) => <Notice key={a} tone="warn">{a}</Notice>)}</section>
      )}

      <section className="mt-8 space-y-5">
        <h2 className="text-2xl">The choices</h2>
        {report.options.map((o) => (
          <article key={o.programme_id} className="card p-5">
            <p className="text-sm text-ink-3">Choice {o.position}</p>
            <h3 className="text-xl">{o.programme}</h3>
            <p className="text-ink-2">{o.institution.official_name}{o.institution.city ? `, ${o.institution.city}` : ""}, {o.institution.state}</p>
            <p className="mt-2 text-sm"><span className="font-medium">What it’s about: </span>{o.branch_plain}</p>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <h4 className="text-sm font-medium">Where past cutoffs place this choice</h4>
                <p className="mt-1 text-sm font-medium">{o.admission.title}</p>
                <p className="text-sm text-ink-2">{o.admission.routes[0]?.explanation ?? o.admission.text}</p>
                {o.admission.issues.map((i) => <p key={i} className="mt-1 text-xs" style={{ color: "var(--competitive)" }}>{i}</p>)}
              </div>
              <div>
                <h4 className="text-sm font-medium">Jobs after graduation</h4>
                {o.placement_highlight ? (
                  <>
                    <p className="tnum mt-1 text-sm font-medium">{inr(o.placement_highlight.median_salary_inr)} median {o.placement_highlight.salary_basis === "CTC" ? "CTC" : "salary"}</p>
                    <p className="text-sm text-ink-2">{o.placement_highlight.scope === "programme" ? "For this branch" : "Across all 4-year students at the institute, not this branch"}, {o.placement_highlight.graduation_year} graduates. Reported by the institute.</p>
                    <SourceLink href={o.placement_highlight.source_url} label={o.placement_highlight.source_title} />
                  </>
                ) : <p className="mt-1 text-sm text-ink-3">Data not available</p>}
                <div className="mt-2"><CareerSummary careers={o.careers} /></div>
              </div>
              <div>
                <h4 className="text-sm font-medium">Institute ranking</h4>
                {o.ranking ? <p className="tnum mt-1 text-sm">NIRF Engineering rank {o.ranking.rank} ({o.ranking.year}), from a secondary source awaiting official checks. This ranks the whole institute.</p> : <p className="mt-1 text-sm text-ink-3">Data not available</p>}
              </div>
              <div>
                <h4 className="text-sm font-medium">Cost</h4>
                {o.fee ? (
                  <>
                    {o.fee.payable_at_admission_inr != null && <p className="tnum mt-1 text-sm font-medium">{inr(o.fee.payable_at_admission_inr)} stated for the first payment</p>}
                    {o.known_annual != null && <p className="tnum text-sm text-ink-2">{inr(o.known_annual)} a year in published charges{o.fee.annual_complete_inr == null ? ", which doesn’t cover everything" : ""}</p>}
                    <p className="text-xs text-ink-3">For {o.fee.seat_type_group}, {o.fee.academic_year}.</p>
                    <SourceLink href={o.fee.source_url} label={o.fee.source_title} />
                  </>
                ) : <p className="mt-1 text-sm text-ink-3">Data not available</p>}
              </div>
            </div>

            {o.loan && (
              <div className="mt-4 border-t border-line pt-3">
                <h4 className="text-sm font-medium">If the published charges were fully funded by a loan</h4>
                <p className="tnum mt-1 text-sm text-ink-2">{inr(o.loan.known_total)} borrowed{o.loan.complete ? "" : " (published charges only, so the real amount would be higher)"}: EMI of about {inr(o.loan.terms.monthly_emi)} a month and {inr(o.loan.terms.total_interest)} total interest.</p>
                {o.loan.scenarios.length > 0 && <ul className="tnum mt-1 text-sm text-ink-2">{o.loan.scenarios.map((sc) => <li key={sc.name}>{sc.name === "Base" ? "At the reported median" : `${sc.name} (assumed)`}: EMI would take {sc.emi_share_of_take_home}% of about {inr(sc.monthly_take_home)} monthly take-home pay.</li>)}</ul>}
              </div>
            )}

            {o.risks.length > 0 && (
              <div className="mt-4 border-t border-line pt-3">
                <h4 className="text-sm font-medium">Risks and unknowns</h4>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-ink-2">{o.risks.map((r) => <li key={r}>{r}</li>)}</ul>
              </div>
            )}
          </article>
        ))}
      </section>

      <section className="print-break mt-8"><h2 className="text-2xl">How seats are allotted</h2><ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm text-ink-2">{report.rules.map((r) => <li key={r}>{r}</li>)}</ul></section>
      <section className="mt-8"><h2 className="text-2xl">Terms used</h2><dl className="mt-2 space-y-2 text-sm">{report.glossary.map(([t, d]) => <div key={t}><dt className="font-medium">{t}</dt><dd className="text-ink-2">{d}</dd></div>)}</dl></section>
      <section className="mt-8"><h2 className="text-2xl">Limits of this report</h2><ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm text-ink-2">{report.limits.map((r) => <li key={r}>{r}</li>)}</ul></section>
    </div>
  );
}
