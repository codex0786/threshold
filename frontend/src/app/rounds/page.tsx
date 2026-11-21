"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { BandBadge, Notice, PageHeader, Skeleton } from "@/components/ui";
import { track } from "@/lib/analytics";
import { type HigherChoice, num, post, type Profile, type RoundAdvice } from "@/lib/api";
import { loadLists, loadProfile, type SavedList } from "@/lib/store";

const STATUS: Record<HigherChoice["status"], { label: string; tone: string }> = {
  often: { label: "Reached ranks like yours in most recent years", tone: "var(--safer)" },
  sometimes: { label: "Reached ranks like yours in some years", tone: "var(--competitive)" },
  not_seen: { label: "Didn’t reach ranks like yours in recent years", tone: "var(--ink-3)" },
  no_history: { label: "No comparable history", tone: "var(--ink-3)" },
};
const TITLE = { freeze: "Freeze", float: "Float", slide: "Slide" } as const;

function ChoiceRow({ c }: { c: HigherChoice }) {
  const status = STATUS[c.status];
  return (
    <li className="py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium"><span className="tnum text-ink-3">{c.position}.</span> {c.programme} <span className="text-ink-2">at {c.institution}</span></p>
          <p className="text-xs" style={{ color: status.tone }}>{status.label}{c.same_institute ? " · same institute as your seat" : ""}</p>
        </div>
        {c.band && <BandBadge band={c.band} />}
      </div>
      {c.years.length > 0 && (
        <table className="mt-2 w-full max-w-md text-xs">
          <thead><tr className="text-left text-ink-3"><th scope="col" className="font-normal">Year</th><th scope="col" className="text-right font-normal">Closed at this round</th><th scope="col" className="text-right font-normal">Closed at final round</th></tr></thead>
          <tbody className="tnum">
            {c.years.map((y) => (
              <tr key={y.year}>
                <td>{y.year}</td>
                <td className="text-right">{y.closing_at_round != null ? `${num(y.closing_at_round)}${y.round_used != null ? ` (R${y.round_used})` : ""}` : "—"}</td>
                <td className="text-right" style={{ color: y.reached_by_final ? "var(--safer)" : undefined }}>{num(y.final_closing)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {c.rank_used != null && <p className="tnum mt-1 text-xs text-ink-3">Compared with your rank {num(c.rank_used)}{c.route ? ` on ${c.route.seat_type}, ${c.route.quota}, ${c.route.gender_pool === "female" ? "female-only" : "gender-neutral"}` : ""}.</p>}
    </li>
  );
}

export default function RoundsPage() {
  const [profile, setProfile] = useState<Profile | null | undefined>(undefined);
  const [lists, setLists] = useState<SavedList[]>([]);
  const [listIndex, setListIndex] = useState(0);
  const [allotted, setAllotted] = useState<number | null>(null);
  const [round, setRound] = useState(1);
  const [finalRound, setFinalRound] = useState(5);
  const [advice, setAdvice] = useState<RoundAdvice | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const stored = loadLists();
    setProfile(loadProfile());
    setLists(stored);
    const wanted = new URLSearchParams(window.location.search).get("list");
    const index = wanted ? stored.findIndex((l) => l.id === wanted) : -1;
    if (index >= 0) setListIndex(index);
  }, []);

  const list = lists[listIndex];
  const items = useMemo(() => list?.items ?? [], [list]);
  useEffect(() => { setAllotted(null); setAdvice(null); }, [listIndex]);

  const ask = async () => {
    if (!profile || !list || allotted == null) return;
    setBusy(true);
    setError(null);
    try {
      const result = await post<RoundAdvice>("/rounds/advice", { profile, programme_ids: items.map((i) => i.id), allotted_programme_id: allotted, round, final_round: finalRound });
      setAdvice(result);
      track("round_advice_viewed", { round, suggestion: result.suggestion });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (profile === undefined) return <div className="mx-auto max-w-3xl px-4 py-10"><Skeleton /></div>;
  if (profile === null || !items.length) {
    return (
      <div className="mx-auto max-w-xl px-4 py-16 text-center">
        <h1 className="text-3xl">Start with your list</h1>
        <p className="mt-2 text-ink-2">To help with a round, we need your ranks and the choice list you filled on JoSAA, in the same order.</p>
        <Link href={profile ? "/preferences" : "/onboarding"} className="btn btn-primary mt-5">{profile ? "Open my preference list" : "Find my best fit"}</Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <PageHeader title="After a JoSAA round" intro="Got a seat? See how your higher choices moved in past years before you choose Freeze, Float or Slide." />
      <section className="card grid gap-4 p-5 sm:grid-cols-2">
        {lists.length > 1 && (
          <label className="block text-sm sm:col-span-2">
            <span className="font-medium">Your list, in the order you filled it on JoSAA</span>
            <select className="input mt-1 w-full" value={listIndex} onChange={(e) => setListIndex(Number(e.target.value))}>
              {lists.map((l, i) => <option key={l.id} value={i}>{l.name} ({l.items.length})</option>)}
            </select>
          </label>
        )}
        <label className="block text-sm sm:col-span-2">
          <span className="font-medium">The seat you were allotted</span>
          <select className="input mt-1 w-full" value={allotted ?? ""} onChange={(e) => { setAllotted(e.target.value ? Number(e.target.value) : null); setAdvice(null); }}>
            <option value="">Choose from your list</option>
            {items.map((item, i) => <option key={item.id} value={item.id}>{i + 1}. {item.label}</option>)}
          </select>
        </label>
        <label className="block text-sm">
          <span className="font-medium">Round</span>
          <select className="input mt-1 w-full" value={round} onChange={(e) => { setRound(Number(e.target.value)); setAdvice(null); }}>
            {Array.from({ length: finalRound }, (_, i) => i + 1).map((r) => <option key={r} value={r}>Round {r}</option>)}
          </select>
        </label>
        <label className="block text-sm">
          <span className="font-medium">Rounds this year</span>
          <select className="input mt-1 w-full" value={finalRound} onChange={(e) => { const n = Number(e.target.value); setFinalRound(n); setRound(Math.min(round, n)); setAdvice(null); }}>
            {[5, 6, 7].map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <span className="mt-1 block text-xs text-ink-3">JoSAA 2026 had 5 rounds. Check the current schedule.</span>
        </label>
        <div className="sm:col-span-2">
          <button type="button" className="btn btn-primary" disabled={allotted == null || busy} onClick={ask}>{busy ? "Checking…" : "Check my higher choices"}</button>
        </div>
      </section>
      {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}

      {advice && (
        <div className="rise mt-6 space-y-4" aria-live="polite">
          <section className="card p-5">
            <p className="text-sm text-ink-3">Round {advice.round} of {advice.final_round}: {advice.allotted.programme} at {advice.allotted.institution} (your choice {advice.allotted.position})</p>
            <h2 className="mt-1 text-2xl">Past patterns point to <span className="text-brand">{TITLE[advice.suggestion]}</span></h2>
            <p className="mt-2 text-ink-2">{advice.why}</p>
            <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-3">
              {(["freeze", "float", "slide"] as const).map((k) => (
                <div key={k} className={`rounded-xl border p-3 ${advice.suggestion === k ? "border-brand bg-brand-soft" : "border-line"}`}>
                  <dt className="font-medium">{TITLE[k]}</dt>
                  <dd className="mt-0.5 text-xs text-ink-2">{advice.options[k].split(": ")[1]}</dd>
                </div>
              ))}
            </dl>
          </section>
          {advice.higher_choices.length > 0 && (
            <section className="card p-5">
              <h2 className="text-lg">Your higher choices</h2>
              <p className="mt-1 text-sm text-ink-3">Green final-round figures are years when that seat reached your rank.</p>
              <ul className="mt-2 divide-y divide-line">{advice.higher_choices.map((c) => <ChoiceRow key={c.programme_id} c={c} />)}</ul>
            </section>
          )}
          <section className="space-y-2">{advice.cautions.map((c) => <Notice key={c} tone="warn">{c}</Notice>)}</section>
        </div>
      )}
    </div>
  );
}
