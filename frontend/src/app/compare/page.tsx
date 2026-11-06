"use client";
import { X } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useEffect, useState } from "react";
import { AcademicBlock } from "@/components/academics";
import { CareerSummary } from "@/components/careers";
import { BandBadge, FeeBlock, NotAvailable, Notice, PageHeader, PlacementBlock, QualityScore, RankingLine, ScoreBar, Skeleton } from "@/components/ui";
import { type Comparison, type ComparisonItem, num, post } from "@/lib/api";
import { clearCompare, type CompareEntry, loadCompare, loadProfile, toggleCompare } from "@/lib/store";

const listName = (l: string) => l.replace("JEE_ADVANCED:", "JEE Advanced ").replace("JEE_MAIN:", "JEE Main ");

const ROWS: { label: string; render: (i: ComparisonItem) => ReactNode; onlyWithProfile?: boolean }[] = [
  { label: "Your admission band", onlyWithProfile: true, render: (i) => i.student_route ? <div><BandBadge band={i.student_route.band} /><p className="mt-1 text-xs text-ink-3">{i.student_route.explanation}</p></div> : <span className="text-sm text-ink-3">No seat matches your ranks and quota</span> },
  { label: "Fit with your priorities", onlyWithProfile: true, render: (i) => i.suitability ? <ScoreBar value={i.suitability.score} label="Suitability" /> : <NotAvailable /> },
  { label: "Reference closing rank", render: (i) => i.reference_cutoff ? <div><p className="tnum font-medium">{num(i.reference_cutoff.closing_rank)}</p><p className="text-xs text-ink-3">{listName(i.reference_cutoff.rank_list)}, {i.reference_cutoff.quota}, {i.reference_cutoff.year} final round</p></div> : <NotAvailable /> },
  { label: "Institutional reputation", render: (i) => <RankingLine ranking={i.ranking} /> },
  { label: "Programme quality", render: (i) => <QualityScore quality={i.quality} /> },
  { label: "Placement outcomes", render: (i) => <PlacementBlock records={i.placements} /> },
  { label: "Fees", render: (i) => <FeeBlock fee={i.fee} /> },
  { label: "Faculty and academics (whole institute)", render: (i) => <AcademicBlock academics={i.academics} compact /> },
  { label: "Curriculum", render: () => <NotAvailable /> },
  { label: "Where graduates go", render: (i) => <CareerSummary careers={i.careers} /> },
  { label: "Documented alumni sample", render: (i) => i.careers.alumni?.status === "available" ? <div><p className="tnum font-medium">{num(i.careers.alumni.sample_size)} people on Wikidata</p><p className="text-xs text-ink-3">Top occupations: {i.careers.alumni.occupations?.slice(0, 3).map((o) => o.label).join(", ")}. A sample of notable people, not the alumni network.</p></div> : <NotAvailable /> },
  { label: "Student experience", render: () => <NotAvailable /> },
  { label: "Data gaps", render: (i) => <ul className="list-disc space-y-1 pl-4 text-xs text-ink-2">{i.data_gaps.map((g) => <li key={g}>{g}</li>)}</ul> },
];

export default function ComparePage() {
  const [entries, setEntries] = useState<CompareEntry[] | null>(null);
  const [data, setData] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => setEntries(loadCompare());
    sync();
    window.addEventListener("threshold-compare", sync);
    return () => window.removeEventListener("threshold-compare", sync);
  }, []);

  const ids = entries?.map((e) => e.id).join(",");
  useEffect(() => {
    if (!entries || entries.length < 2) { setData(null); return; }
    let live = true;
    setError(null);
    post<Comparison>("/comparisons", { programme_ids: entries.map((e) => e.id), profile: loadProfile() })
      .then((d) => { if (live) setData(d); }).catch((e) => { if (live) setError(e.message); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids]);

  if (entries === null) return <div className="mx-auto max-w-6xl px-4 py-10"><Skeleton /></div>;
  if (entries.length < 2) {
    return (
      <div className="mx-auto max-w-xl px-4 py-16 text-center">
        <h1 className="text-3xl">Compare up to four options</h1>
        <p className="mt-2 text-ink-2">{entries.length === 1 ? `You’ve added ${entries[0].label}. Add at least one more to compare.` : "Add at least two programmes from your shortlist or a college page."}</p>
        <div className="mt-5 flex justify-center gap-3"><Link href="/recommendations" className="btn btn-primary">My shortlist</Link><Link href="/colleges" className="btn btn-secondary">Browse colleges</Link></div>
      </div>
    );
  }
  const hasProfile = data?.items.some((i) => i.suitability);
  const rows = ROWS.filter((r) => !r.onlyWithProfile || hasProfile);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader title="Compare" intro="We set out the differences for you to weigh, and we don’t pick a winner."><button className="btn btn-secondary" onClick={clearCompare}>Clear all</button></PageHeader>
      {error && <Notice tone="error">{error}</Notice>}
      {!data && !error && <Skeleton />}
      {data && <>
        <section className="card mb-5 p-5">
          <h2 className="text-xl">Trade-offs to consider</h2>
          <ul className="mt-2 list-disc space-y-1.5 pl-5 text-ink-2">{data.trade_offs.map((t) => <li key={t}>{t}</li>)}</ul>
        </section>
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left align-top">
            <thead>
              <tr className="border-b border-line">
                <th scope="col" className="w-40 p-4 text-sm font-normal text-ink-3">Option</th>
                {data.items.map((i) => (
                  <th scope="col" key={i.programme_id} className="p-4 align-top font-normal">
                    <div className="flex items-start justify-between gap-2">
                      <div><Link href={`/programmes/${i.programme_id}`} className="font-medium hover:underline">{i.programme}</Link><p className="text-sm text-ink-2">{i.institution.short_name}</p></div>
                      <button aria-label={`Remove ${i.programme} at ${i.institution.short_name}`} className="text-ink-3 hover:text-ink" onClick={() => toggleCompare({ id: i.programme_id, label: "" })}><X size={15} /></button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.label} className="border-b border-line last:border-0">
                  <th scope="row" className="p-4 align-top text-sm font-normal text-ink-3">{row.label}</th>
                  {data.items.map((i) => <td key={i.programme_id} className="p-4 align-top text-sm">{row.render(i)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-sm text-ink-3">{data.note}</p>
      </>}
    </div>
  );
}
