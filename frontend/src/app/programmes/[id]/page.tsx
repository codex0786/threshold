"use client";
import Link from "next/link";
import { use, useEffect, useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CareerSections } from "@/components/careers";
import { CompareToggle } from "@/components/compare-toggle";
import { FeeBlock, NotAvailable, Notice, PlacementBlock, RankingLine, Section, Skeleton, SourceLink } from "@/components/ui";
import { api, type Careers, type CutoffPoint, type InstitutionDetail, num, type ProgrammeDetail } from "@/lib/api";

const QUOTA: Record<string, string> = { AI: "All India", HS: "Home State", OS: "Other State", GO: "Goa", JK: "Jammu & Kashmir", LA: "Ladakh" };

export default function ProgrammePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [programme, setProgramme] = useState<ProgrammeDetail | null>(null);
  const [records, setRecords] = useState<CutoffPoint[] | null>(null);
  const [seat, setSeat] = useState("OPEN");
  const [pool, setPool] = useState("neutral");
  const [quota, setQuota] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [careers, setCareers] = useState<Careers | null>(null);

  useEffect(() => {
    api<ProgrammeDetail>(`/programmes/${id}`).then((p) => {
      setProgramme(p);
      return api<InstitutionDetail>(`/institutions/${p.institution.slug}`).then((inst) => setCareers(inst.careers));
    }).catch((e) => setError(e.message));
  }, [id]);

  const seats = useMemo(() => [...new Set(programme?.available_seats.map((s) => s.seat_type))], [programme]);
  const quotas = useMemo(() => [...new Set(programme?.available_seats.filter((s) => s.seat_type === seat && s.gender_pool === pool).map((s) => s.quota))], [programme, seat, pool]);
  const activeQuota = quotas.includes(quota) ? quota : quotas[0] ?? "";

  useEffect(() => {
    if (!activeQuota) { setRecords([]); return; }
    let live = true;
    api<{ records: CutoffPoint[] }>(`/programmes/${id}/cutoffs?seat_type=${encodeURIComponent(seat)}&gender_pool=${pool}&quota=${activeQuota}`)
      .then((r) => { if (live) setRecords(r.records); }).catch((e) => setError(e.message));
    return () => { live = false; };
  }, [id, seat, pool, activeQuota]);

  const usable = (records ?? []).filter((r) => !r.is_preparatory && r.closing_rank != null);
  const chart = useMemo(() => {
    const years = [...new Set(usable.map((r) => r.year))].sort();
    return years.map((year) => ({
      year: String(year),
      first: usable.find((r) => r.year === year && !r.is_final_round)?.closing_rank ?? null,
      final: usable.find((r) => r.year === year && r.is_final_round)?.closing_rank ?? null,
    }));
  }, [usable]);

  if (error) return <div className="mx-auto max-w-4xl px-4 py-10"><Notice tone="error">{error}</Notice></div>;
  if (!programme) return <div className="mx-auto max-w-4xl px-4 py-10"><Skeleton /></div>;
  const rankList = usable[0]?.rank_list.replace("JEE_ADVANCED:", "JEE Advanced ").replace("JEE_MAIN:", "JEE Main ");
  const hasPrep = (records ?? []).some((r) => r.is_preparatory);

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <Link href={`/colleges/${programme.institution.slug}`} className="text-sm text-ink-3 hover:text-ink">← {programme.institution.short_name}</Link>
      <header className="mb-6 mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold sm:text-5xl">{programme.name}</h1>
          <p className="mt-1 text-ink-2">{programme.institution.short_name} · {programme.degree}{programme.duration_years ? `, ${programme.duration_years} years` : ""}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <CompareToggle id={programme.id} label={`${programme.institution.short_name}: ${programme.name}`} />
          <Link href={`/finance?programme=${programme.id}`} className="btn btn-secondary !px-3 !py-1.5 text-sm">Estimate cost</Link>
        </div>
      </header>

      <div className="space-y-5">
        <Section title="Cutoff history" hint="Past closing ranks are historical facts, not a measure of your chances. A lower number means the seat filled with stronger ranks.">
          <div className="mb-4 grid gap-3 sm:grid-cols-3">
            <label className="text-sm">Seat type<select className="input mt-1" value={seat} onChange={(e) => setSeat(e.target.value)}>{seats.map((s) => <option key={s}>{s}</option>)}</select></label>
            <label className="text-sm">Seat pool<select className="input mt-1" value={pool} onChange={(e) => setPool(e.target.value)}><option value="neutral">Gender-neutral</option><option value="female">Female-only</option></select></label>
            <label className="text-sm">Quota<select className="input mt-1" value={activeQuota} onChange={(e) => setQuota(e.target.value)} disabled={!quotas.length}>{quotas.map((q) => <option key={q} value={q}>{QUOTA[q] ?? q}</option>)}</select></label>
          </div>
          {records === null ? <Skeleton lines={1} /> : usable.length === 0 ? <NotAvailable what="this seat" /> : <>
            <p className="mb-2 text-sm text-ink-3">Ranks shown are on the {rankList} list.</p>
            <div className="h-64" role="img" aria-label={`Closing ranks by year on the ${rankList} list`}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chart} margin={{ left: 8, right: 16, top: 8, bottom: 0 }}>
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="year" stroke="var(--ink-3)" tickLine={false} fontSize={12} />
                  <YAxis reversed stroke="var(--ink-3)" tickLine={false} axisLine={false} fontSize={12} width={56} tickFormatter={(v) => Number(v).toLocaleString("en-IN")} domain={["auto", "auto"]} />
                  <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--ink)" }} formatter={(v) => Number(v).toLocaleString("en-IN")} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line type="linear" dataKey="final" name="Final round" stroke="var(--brand)" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} animationDuration={1200} connectNulls />
                  <Line type="linear" dataKey="first" name="Round 1" stroke="var(--teal)" strokeWidth={1.5} strokeDasharray="4 3" dot={{ r: 2.5 }} animationDuration={1200} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[480px] text-left text-sm">
                <thead><tr className="border-b border-line text-ink-3"><th scope="col" className="py-2 font-normal">Year</th><th scope="col" className="py-2 font-normal">Round</th><th scope="col" className="py-2 text-right font-normal">Opening</th><th scope="col" className="py-2 text-right font-normal">Closing</th><th scope="col" className="py-2 pl-4 font-normal">Source</th></tr></thead>
                <tbody>
                  {[...usable].reverse().map((r) => (
                    <tr key={`${r.year}-${r.round}`} className="border-b border-line last:border-0">
                      <td className="tnum py-2">{r.year}</td><td className="tnum py-2">{r.round}{r.is_final_round ? " (final)" : ""}</td>
                      <td className="tnum py-2 text-right">{num(r.opening_rank)}</td><td className="tnum py-2 text-right font-medium">{num(r.closing_rank)}</td>
                      <td className="py-2 pl-4"><SourceLink href={r.source_url} label="JoSAA" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>}
          {hasPrep && <p className="mt-3 text-sm text-ink-3">Some years list a preparatory-course rank for this seat. Those ranks are on a different list and are left out here.</p>}
        </Section>
        <div className="grid gap-5 md:grid-cols-2">
          <Section title="Placements" hint="Programme-level data where available, and clearly labelled if institute-wide."><PlacementBlock records={programme.placements} /></Section>
          <Section title="Institute ranking" hint="NIRF ranks whole institutes, not branches."><RankingLine ranking={programme.ranking} /></Section>
          <Section title="Fees"><FeeBlock fee={programme.fee} /></Section>
          <Section title="Curriculum and faculty"><NotAvailable /></Section>
        </div>
        {careers && <CareerSections careers={careers} highlight={programme.id} />}
      </div>
    </div>
  );
}
