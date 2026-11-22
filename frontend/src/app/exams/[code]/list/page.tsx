"use client";
import { ArrowDown, ArrowLeft, ArrowUp, Download, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BandBadge, Notice, PageHeader, Skeleton, SourceLink } from "@/components/ui";
import { api, num, type Band } from "@/lib/api";
import { downloadCsv } from "@/lib/csv";
import { type ExamRoute, examDefaults, loadExamAnswers } from "@/lib/exams";

type Item = { position: number; institute: string; institute_short: string | null; programme: string; quota: string; category: string; band: Band; closing: Record<string, number>; explanation: string; key: string };
type Built = { items: Item[]; counts: Record<string, number>; stop_reason: string; notes: string[]; data_years: number[] };
type Option = { key: string; name: string; text: string };
type Higher = { position: number; institute: string; programme: string; quota: string; status: string; reached_years: number; years: { year: number; closing_at_round: number | null; final_closing: number | null; reached_by_round_3: boolean }[] };
type Advice = {
  round: number; round_label: string; suggestion: string; why: string; allotted: { position: number; institute: string; programme: string; quota: string };
  options: Option[]; warning: string | null; higher_choices: Higher[]; source: { title: string; url: string }; cautions: string[];
};
const STATUS: Record<string, string> = {
  often: "Reached ranks like yours by Round 3 in most past years",
  sometimes: "Reached ranks like yours by Round 3 in some past years",
  not_seen: "Didn't reach ranks like yours in past years",
  no_history: "No past figures",
};
const ROUNDS: [number, string][] = [[1, "Round 1"], [2, "Round 2"], [3, "Round 3"], [4, "Stray vacancy round"]];
const storeKey = (code: string) => `threshold.examlist.${code}.v1`;

export default function ExamChoiceList() {
  const { code } = useParams<{ code: string }>();
  const [route, setRoute] = useState<ExamRoute | null | undefined>(undefined);
  const [rank, setRank] = useState("");
  const [category, setCategory] = useState("");
  const [quotas, setQuotas] = useState<string[]>([]);
  const [programmes, setProgrammes] = useState<string[]>([]);
  const [pastNet, setPastNet] = useState(false);
  const [built, setBuilt] = useState<Built | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [allotted, setAllotted] = useState(0);
  const [round, setRound] = useState(1);
  const [advice, setAdvice] = useState<Advice | null>(null);

  useEffect(() => {
    api<{ routes: (ExamRoute & { list_tools?: boolean })[] }>("/exams").then((d) => {
      const found = d.routes.find((r) => r.code === code && r.list_tools) ?? null;
      setRoute(found);
      if (!found) return;
      const saved = loadExamAnswers(found.code);
      const defaults = examDefaults(found);
      setRank(saved?.value ?? "");
      setCategory(saved?.category || defaults.category);
      setQuotas([saved?.quota || defaults.quota].filter(Boolean));
      setProgrammes([saved?.programme || defaults.programme].filter(Boolean));
      try {
        const kept = JSON.parse(window.localStorage.getItem(storeKey(found.code)) ?? "null") as Item[] | null;
        if (kept?.length) setItems(kept);
      } catch {
        // Storage can be blocked. The page still works for this visit.
      }
    }).catch(() => setError("These figures aren’t available right now. Please try again shortly."));
  }, [code]);

  const keep = (next: Item[]) => {
    setItems(next);
    setAdvice(null);
    try { window.localStorage.setItem(storeKey(code), JSON.stringify(next)); } catch { /* blocked storage */ }
  };
  const figure = Number(rank.replace(/[,\s]/g, ""));

  const build = async () => {
    if (!route || !(figure > 0) || !category || !quotas.length) return;
    setBusy(true); setError(null);
    try {
      const result = await api<Built>(`/exams/${route.code}/list/build`, { method: "POST", body: JSON.stringify({ value: Math.round(figure), category, quotas, programmes, size: 80, past_safety_net: pastNet }) });
      setBuilt(result); keep(result.items); setAllotted(0);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const ask = async () => {
    if (!route || !items.length) return;
    setBusy(true); setError(null);
    try {
      setAdvice(await api<Advice>(`/exams/${route.code}/list/advice`, { method: "POST", body: JSON.stringify({ value: Math.round(figure), items, allotted_index: allotted, round }) }));
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const move = (i: number, by: number) => {
    const next = [...items];
    const [item] = next.splice(i, 1);
    next.splice(i + by, 0, item);
    keep(next);
  };
  const toggle = (list: string[], value: string, set: (v: string[]) => void) => set(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);

  if (route === undefined) return <div className="mx-auto max-w-5xl px-4 py-10">{error ? <Notice tone="error">{error}</Notice> : <Skeleton />}</div>;
  if (route === null) return <div className="mx-auto max-w-xl px-4 py-16 text-center"><h1 className="text-3xl font-bold">Not available for this exam yet</h1><Link href="/exams" className="btn btn-primary mt-5">See covered exams</Link></div>;
  const allowed = quotas.length === 1 ? route.quota_categories?.[quotas[0]] : undefined;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <Link href={`/exams/${route.code}`} className="mb-3 inline-flex items-center gap-1 text-sm text-ink-2 hover:text-brand"><ArrowLeft size={15} aria-hidden /> Back to the shortlist</Link>
      <PageHeader title={`Your ${route.name} choice list`} intro="A suggested order for MCC choice filling, from your shortlist and four years of allotments, and what to do after each round’s allotment. You decide the final order." />
      {error && <div className="mb-4"><Notice tone="error">{error}</Notice></div>}

      <section className="card space-y-4 p-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">Your {route.metric.label}
            <input className="input tnum mt-1" inputMode="numeric" value={rank} onChange={(e) => setRank(e.target.value.trim())} placeholder="e.g. 25,000" />
          </label>
          <label className="block text-sm">Category, as published
            <select className="input mt-1" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">Choose</option>{route.categories.filter((c) => !allowed || allowed.includes(c)).map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
        </div>
        <fieldset>
          <legend className="text-sm font-medium">Quotas to include</legend>
          <p className="text-xs text-ink-3">Only those you qualify for. Some need proof, such as NRI or minority status.</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {(route.quotas ?? []).map((q) => (
              <button key={q} type="button" aria-pressed={quotas.includes(q)} onClick={() => toggle(quotas, q, setQuotas)}
                className={`rounded-full border px-3 py-1.5 text-sm ${quotas.includes(q) ? "border-brand bg-brand text-brand-ink" : "border-line bg-surface text-ink-2 hover:text-ink"}`}>{q}</button>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend className="text-sm font-medium">Courses</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {route.programmes.map((p) => (
              <button key={p} type="button" aria-pressed={programmes.includes(p)} onClick={() => toggle(programmes, p, setProgrammes)}
                className={`rounded-full border px-3 py-1.5 text-sm ${programmes.includes(p) ? "border-brand bg-brand text-brand-ink" : "border-line bg-surface text-ink-2 hover:text-ink"}`}>{p}</button>
            ))}
          </div>
        </fieldset>
        <label className="flex items-start gap-2.5 text-sm"><input type="checkbox" className="mt-1" checked={pastNet} onChange={(e) => setPastNet(e.target.checked)} />
          <span>Keep going past the safety net <span className="block text-xs text-ink-3">By default the list stops after 5 Safer seats, because seats below them were rarely reached by ranks like yours.</span></span>
        </label>
        <button type="button" className="btn btn-primary" disabled={busy || !(figure > 0) || !category || !quotas.length} onClick={build}>Build my choice list</button>
      </section>

      {built && built.notes.length > 0 && <div className="mt-4 space-y-1">{built.notes.map((n) => <p key={n} className="text-sm text-ink-2">{n}</p>)}</div>}

      {items.length > 0 && (
        <section className="mt-6">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-xl">Your list ({items.length})</h2>
            <button type="button" className="btn inline-flex items-center gap-1.5" onClick={() => downloadCsv(`${route.code}-choice-list.csv`, [["Choice", "College", "Course", "Quota", "Category", "Band", ...built?.data_years.map(String) ?? []], ...items.map((it, i) => [i + 1, it.institute, it.programme, it.quota, it.category, it.band ?? "", ...(built?.data_years ?? []).map((y) => it.closing[String(y)] ?? "")])])}>
              <Download size={15} aria-hidden /> Download CSV
            </button>
          </div>
          <ol className="space-y-2">
            {items.map((it, i) => (
              <li key={`${it.key}|${it.quota}`} className="card flex items-start gap-3 p-3">
                <span className="tnum mt-0.5 w-7 shrink-0 text-right font-semibold text-ink-3">{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2"><BandBadge band={it.band ?? "limited_history"} /><span className="text-xs text-ink-3">{it.quota} · {it.category}</span></div>
                  <p className="mt-1 font-medium">{it.programme} · {it.institute_short ?? it.institute}</p>
                  <p className="tnum text-xs text-ink-3">Last rank allotted in rounds 1 to 3: {Object.entries(it.closing).map(([y, r]) => `${y}: ${num(r)}`).join(" · ")}</p>
                </div>
                <div className="flex shrink-0 gap-1">
                  <button type="button" aria-label={`Move choice ${i + 1} up`} disabled={i === 0} onClick={() => move(i, -1)} className="rounded border border-line p-1 disabled:opacity-30"><ArrowUp size={14} /></button>
                  <button type="button" aria-label={`Move choice ${i + 1} down`} disabled={i === items.length - 1} onClick={() => move(i, 1)} className="rounded border border-line p-1 disabled:opacity-30"><ArrowDown size={14} /></button>
                  <button type="button" aria-label={`Remove choice ${i + 1}`} onClick={() => keep(items.filter((_, j) => j !== i))} className="rounded border border-line p-1"><X size={14} /></button>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {items.length > 0 && (
        <section className="card mt-8 space-y-3 p-4">
          <h2 className="text-xl">After an allotment</h2>
          <p className="text-sm text-ink-2">Tell us which seat you were allotted and in which round. We show what MCC lets you do and how your higher choices moved in past years.</p>
          <div className="grid gap-3 sm:grid-cols-[2fr_1fr_auto] sm:items-end">
            <label className="block text-sm">Allotted seat
              <select className="input mt-1" value={allotted} onChange={(e) => setAllotted(Number(e.target.value))}>
                {items.map((it, i) => <option key={`${it.key}|${it.quota}`} value={i}>{i + 1}. {it.programme} · {it.institute_short ?? it.institute}</option>)}
              </select>
            </label>
            <label className="block text-sm">Round
              <select className="input mt-1" value={round} onChange={(e) => setRound(Number(e.target.value))}>{ROUNDS.map(([n, l]) => <option key={n} value={n}>{l}</option>)}</select>
            </label>
            <button type="button" className="btn btn-primary" disabled={busy} onClick={ask}>Show my options</button>
          </div>
          {advice && (
            <div className="space-y-4 border-t border-line pt-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-ink-3">{advice.round_label}: suggested</p>
                <p className="text-lg font-semibold">{advice.options.find((o) => o.key === advice.suggestion)?.name ?? advice.suggestion}</p>
                <p className="mt-1 text-sm text-ink-2">{advice.why}</p>
              </div>
              {advice.warning && <Notice tone="warn">{advice.warning}</Notice>}
              <div>
                <h3 className="text-base font-medium">What MCC lets you do</h3>
                <ul className="mt-1 space-y-1 text-sm">{advice.options.map((o) => <li key={o.key}><span className="font-medium">{o.name}.</span> <span className="text-ink-2">{o.text}</span></li>)}</ul>
                <p className="mt-1 text-xs"><SourceLink href={advice.source.url} label={advice.source.title} /></p>
              </div>
              {advice.higher_choices.length > 0 && (
                <div>
                  <h3 className="text-base font-medium">Your higher choices in past years</h3>
                  <ul className="mt-1 space-y-1 text-sm">
                    {advice.higher_choices.map((h) => (
                      <li key={h.position}><span className="tnum text-ink-3">{h.position}.</span> {h.programme} · {h.institute} <span className="text-ink-3">({h.quota})</span>: <span className={h.status === "often" ? "font-medium" : "text-ink-2"}>{STATUS[h.status]}</span>
                        {h.years.length > 0 && <span className="tnum block pl-5 text-xs text-ink-3">{h.years.map((y) => `${y.year}: ${y.closing_at_round != null ? num(y.closing_at_round) : "–"} at this round, ${y.final_closing != null ? num(y.final_closing) : "–"} by Round 3`).join(" · ")}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <ul className="list-disc space-y-1 pl-4 text-xs text-ink-3">{advice.cautions.map((c) => <li key={c}>{c}</li>)}</ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
