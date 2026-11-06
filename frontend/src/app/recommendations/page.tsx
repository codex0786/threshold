"use client";
import { ChevronDown } from "lucide-react";
import Link from "next/link";
import { type CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AddToList } from "@/components/add-to-list";
import { CompareToggle } from "@/components/compare-toggle";
import { BandBadge, bandMeta, ComponentList, Notice, PageHeader, PlacementBlock, QualityScore, RankGauge, RankingLine, ScoreBar, Skeleton, FeeBlock } from "@/components/ui";
import { api, type CsabLeads, type Meta, num, type Option, post, type Profile, type Recommendations, type Route } from "@/lib/api";
import { loadProfile, saveProfile } from "@/lib/store";

const BANDS = ["all", "safer", "competitive", "ambitious", "limited_history"] as const;
type Filter = (typeof BANDS)[number];
const listName = (l: string) => l.replace("JEE_ADVANCED:", "JEE Advanced ").replace("JEE_MAIN:", "JEE Main ");
const QUOTA: Record<string, string> = { AI: "All India", HS: "Home State", OS: "Other State", GO: "Goa", JK: "Jammu & Kashmir", LA: "Ladakh" };

function RouteLine({ route }: { route: Route }) {
  return <span>{route.seat_type}, {QUOTA[route.quota] ?? route.quota}, {route.gender_pool === "female" ? "female-only" : "gender-neutral"}</span>;
}

function OptionCard({ option, index }: { option: Option; index: number }) {
  const [open, setOpen] = useState(false);
  const route = option.best_route;
  const band = bandMeta(option.band ?? "limited_history");
  return (
    <article className="card card-hover band-card rise p-5 pl-6" style={{ "--band": band.color, "--i": index } as CSSProperties}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2"><BandBadge band={option.band} /><span className="text-xs text-ink-3">{option.institution.type} · {option.institution.state}</span></div>
          <h2 className="mt-2 text-xl"><Link href={`/programmes/${option.programme_id}`} className="hover:underline">{option.programme}</Link></h2>
          <p className="text-ink-2"><Link href={`/colleges/${option.institution.slug}`} className="hover:underline">{option.institution.short_name}</Link>{option.degree ? ` · ${option.degree}` : ""}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <CompareToggle id={option.programme_id} label={`${option.institution.short_name}: ${option.programme}`} />
          <AddToList entry={{ id: option.programme_id, label: `${option.institution.short_name}: ${option.programme}` }} />
        </div>
      </div>

      <div className="mt-4 grid gap-5 sm:grid-cols-3">
        <div>
          <p className="text-xs text-ink-3">Past closing ranks ({route.years_used?.[0]}–{route.years_used?.at(-1)})</p>
          <p className="tnum mt-1 font-medium">{route.low_closing != null ? `${num(route.low_closing)} to ${num(route.high_closing)}` : num(route.latest_closing)}</p>
          {route.low_closing != null && route.high_closing != null && <RankGauge rank={route.rank_used} low={route.low_closing} high={route.high_closing} color={band.color} />}
          <p className="tnum text-xs text-ink-3">Your {listName(route.rank_list)} rank: {num(route.rank_used)}</p>
          <p className="text-xs text-ink-3"><RouteLine route={route} /></p>
          {route.seats != null && route.seats > 0 && <p className="tnum text-xs text-ink-3">{num(route.seats)} {route.seats === 1 ? "seat" : "seats"} in this category, {num(option.total_seats ?? route.seats)} in all, in 2026</p>}
        </div>
        <div>
          <p className="text-xs text-ink-3">Fit with your priorities</p>
          <div className="mt-1.5"><ScoreBar value={option.suitability.score} label="Suitability" /></div>
          <p className="mt-1 text-xs text-ink-3">{Math.round(option.suitability.coverage * 100)}% of this is based on known information</p>
        </div>
        <div>
          <p className="text-xs text-ink-3">Quality</p>
          <p className="mt-1 text-sm font-medium">{option.quality.score ?? "Not scored yet"}</p>
          <p className="text-xs text-ink-3">{Math.round(option.quality.coverage * 100)}% evidence, 50% needed</p>
        </div>
      </div>

      {option.institution.campus_note && <p className="mt-3 text-xs text-ink-3">{option.institution.campus_note}</p>}
      {(option.earlier_names?.length ?? 0) > 0 && <p className="mt-3 text-xs text-ink-3">Past cutoffs include its earlier name: {option.earlier_names?.map((e) => `${e.name} (until ${e.until})`).join(", ")}. We joined these by comparing JoSAA’s lists, and the institute hasn’t confirmed it.</p>}

      <button type="button" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-brand hover:underline" aria-expanded={open} onClick={() => setOpen(!open)}>
        <ChevronDown size={15} className={`chev ${open ? "rotate-180" : ""}`} aria-hidden /> {open ? "Hide" : "Why this option"}
      </button>

      {open && (
        <div className="rise mt-4 grid gap-6 border-t border-line pt-4 md:grid-cols-2">
          <div className="space-y-4">
            <div><h3 className="text-base font-medium">Why it appears</h3><ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-ink-2">{option.why.map((w) => <li key={w}>{w}</li>)}</ul></div>
            {option.strengths.length > 0 && <div><h3 className="text-base font-medium">Strongest points</h3><ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-ink-2">{option.strengths.map((w) => <li key={w}>{w}</li>)}</ul></div>}
            {option.weaknesses.length > 0 && <div><h3 className="text-base font-medium">Weaknesses</h3><ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-ink-2">{option.weaknesses.map((w) => <li key={w}>{w}</li>)}</ul></div>}
            <div><h3 className="text-base font-medium">Data gaps</h3><ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-ink-2">{option.data_gaps.map((w) => <li key={w}>{w}</li>)}</ul></div>
            {option.other_routes.length > 0 && <div><h3 className="text-base font-medium">Other seats you could compete for</h3><ul className="mt-1 space-y-1 text-sm text-ink-2">{option.other_routes.map((r) => <li key={`${r.quota}${r.seat_type}${r.gender_pool}`}><RouteLine route={r} />: {bandMeta(r.band).label}</li>)}</ul></div>}
          </div>
          <div className="space-y-4">
            <div><h3 className="text-base font-medium">How your fit was worked out</h3><div className="mt-2"><ComponentList components={option.suitability.components} /></div></div>
            <div><h3 className="text-base font-medium">Quality</h3><div className="mt-1"><QualityScore quality={option.quality} /></div></div>
            <div><h3 className="text-base font-medium">Ranking</h3><div className="mt-1 text-sm"><RankingLine ranking={option.ranking} /></div></div>
            {option.academics && <div><h3 className="text-base font-medium">Faculty and research (whole institute)</h3><p className="mt-1 text-sm text-ink-2">{option.academics.students_per_regular_faculty != null ? `${option.academics.students_per_regular_faculty} students per regular faculty member. ` : ""}{option.academics.phd_share != null ? `${Math.round(option.academics.phd_share * 100)}% of regular faculty hold a doctorate. ` : ""}<Link className="underline" href={`/colleges/${option.institution.slug}`}>See the institute’s figures</Link></p></div>}
            <div><h3 className="text-base font-medium">Placements</h3><div className="mt-1"><PlacementBlock records={option.placements} /></div></div>
            <div><h3 className="text-base font-medium">Fees</h3><div className="mt-1"><FeeBlock fee={option.fee} /></div></div>
          </div>
        </div>
      )}
    </article>
  );
}

function CsabPanel({ csab }: { csab: CsabLeads }) {
  const [open, setOpen] = useState(false);
  if (csab.count === 0) return null;
  return (
    <section className="card mt-6 p-4" aria-labelledby="csab-title">
      <h2 id="csab-title" className="text-lg">Also worth checking: CSAB special rounds</h2>
      <p className="mt-1 text-sm text-ink-2">{num(csab.count)} programmes closed at or beyond your rank of {num(csab.rank_used)} in 2026.</p>
      <p className="mt-1 text-xs text-ink-3">{csab.note}</p>
      <button type="button" className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-brand hover:underline" aria-expanded={open} onClick={() => setOpen(!open)}>
        <ChevronDown size={15} className={`chev ${open ? "rotate-180" : ""}`} aria-hidden /> {open ? "Hide" : `Show ${csab.count > csab.options.length ? `the first ${num(csab.options.length)}` : "them"}`}
      </button>
      {open && (
        <ul className="rise mt-3 divide-y divide-line">
          {csab.options.map((o) => (
            <li key={o.programme_id} className="py-2 text-sm">
              <div className="flex flex-wrap justify-between gap-x-4">
                <span className="font-medium">{o.institution.short_name}: {o.programme}</span>
                <span className="tnum text-ink-2">closed at {num(o.closing_rank)}</span>
              </div>
              <p className="text-xs text-ink-3">Round {o.round} · {o.quota} quota · {o.seat_type} · {o.gender_pool_label} · <a className="underline" href={o.source_url} target="_blank" rel="noreferrer">source</a></p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function BandMix({ counts }: { counts: Record<string, number> }) {
  const parts = (["safer", "competitive", "ambitious", "limited_history"] as const).map((b) => ({ band: b, count: counts[b] ?? 0 })).filter((p) => p.count > 0);
  const total = parts.reduce((sum, p) => sum + p.count, 0);
  if (!total) return null;
  return (
    <div className="mb-5" role="img" aria-label={parts.map((p) => `${bandMeta(p.band).label}: ${p.count}`).join(", ")}>
      <div className="grow-x flex h-3 gap-0.5 overflow-hidden rounded-full">
        {parts.map((p) => <div key={p.band} className="transition-[flex-grow] duration-500" style={{ flexGrow: p.count, background: bandMeta(p.band).color === "var(--ink-2)" ? "var(--ink-3)" : bandMeta(p.band).color }} />)}
      </div>
    </div>
  );
}

export default function RecommendationsPage() {
  const [profile, setProfile] = useState<Profile | null | undefined>(undefined);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [result, setResult] = useState<Recommendations | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [showPriorities, setShowPriorities] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const run = useCallback(async (p: Profile) => {
    setLoading(true);
    setError(null);
    try {
      setResult(await post<Recommendations>("/recommendations/generate", { profile: p }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const stored = loadProfile();
    setProfile(stored);
    api<Meta>("/meta").then(setMeta).catch((e) => setError(e.message));
    if (stored) run(stored);
  }, [run]);

  const changePriority = (key: string, value: number) => {
    if (!profile) return;
    const next = { ...profile, priorities: { ...profile.priorities, [key]: value } };
    setProfile(next);
    saveProfile(next);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => run(next), 300);
  };

  const shown = useMemo(() => (result?.options ?? []).filter((o) => filter === "all" || (o.band ?? "limited_history") === filter), [result, filter]);

  if (profile === undefined) return <div className="mx-auto max-w-6xl px-4 py-10"><Skeleton /></div>;
  if (profile === null) {
    return (
      <div className="mx-auto max-w-xl px-4 py-16 text-center">
        <h1 className="text-4xl font-bold">Your shortlist starts with your rank</h1>
        <p className="mt-2 text-ink-2">Answer a few questions, and we’ll compare your rank with official past cutoffs.</p>
        <Link href="/onboarding" className="btn btn-primary mt-5">Find my best fit</Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader title="Your shortlist" intro={result?.data_year ? `Compared with official JoSAA final-round closing ranks from ${result.history_window?.[0]} to ${result.history_window?.[1]}.` : undefined}>
        <Link href="/onboarding" className="btn btn-secondary">Edit my answers</Link>
      </PageHeader>
      {error && <div className="mb-4"><Notice tone="error">{error}</Notice></div>}

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <button type="button" className="btn btn-secondary w-full lg:hidden" aria-expanded={showPriorities} onClick={() => setShowPriorities(!showPriorities)}>
            <ChevronDown size={15} className={showPriorities ? "rotate-180" : ""} aria-hidden /> {showPriorities ? "Hide priorities" : "Adjust what matters to you"}
          </button>
          <section className={`card p-4 ${showPriorities ? "" : "hidden lg:block"}`}>
            <h2 className="text-lg">What matters to you</h2>
            <p className="mt-0.5 text-xs text-ink-3">Drag to change your priorities. Your admission bands stay the same, because they depend only on past cutoffs.</p>
            <div className="mt-3 space-y-3">
              {meta && Object.entries(meta.suitability_labels).map(([key, label]) => (
                <label key={key} className="block text-sm">
                  <span className="flex justify-between"><span>{label}</span><span className="tnum text-ink-3">{profile.priorities[key] ?? meta.default_priorities[key] ?? 0}</span></span>
                  <input type="range" min={0} max={100} step={5} className="w-full accent-[var(--brand)]" value={profile.priorities[key] ?? meta.default_priorities[key] ?? 0} onChange={(e) => changePriority(key, Number(e.target.value))} />
                </label>
              ))}
            </div>
            <p className="mt-2 text-xs text-ink-3">Where an institute publishes no comparable placement data, it counts as neutral. That doesn’t mean its outcomes are average, and it may flatter institutes that publish nothing. Affordability is rarely scored, because few institutes publish a full yearly cost. How contested a seat is comes from past closing ranks: it shows what earlier candidates chose, not how good the seat is, so lower it if you’d rather not follow the crowd.</p>
          </section>
          <section className={`space-y-2 text-sm text-ink-2 ${showPriorities ? "" : "hidden lg:block"}`}>
            {result?.warnings.map((w) => <p key={w} className="text-xs text-ink-3">{w}</p>)}
          </section>
        </aside>

        <div aria-live="polite">
          {result && <p className="mb-3 text-xs text-ink-3 lg:hidden">{result.warnings[0]}</p>}
          {result && (
            <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Filter by admission band">
              {BANDS.map((b) => {
                const count = b === "all" ? Object.values(result.counts).reduce((a, c) => a + c, 0) : result.counts[b] ?? 0;
                return (
                  <button key={b} type="button" aria-pressed={filter === b} onClick={() => setFilter(b)}
                    className={`tnum rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${filter === b ? "border-brand bg-brand text-brand-ink" : "border-line bg-surface text-ink-2"}`}>
                    {b === "all" ? "All" : bandMeta(b).label} ({num(count)})
                  </button>
                );
              })}
            </div>
          )}
          {result && <BandMix counts={result.counts} />}
          {result?.excluded && (result.excluded.beyond_range > 0 || result.excluded.avoided_branch > 0 || result.excluded.no_latest_cutoff > 0) && (
            <p className="mb-3 text-sm text-ink-3">Not shown: {num(result.excluded.beyond_range)} options more than 20% beyond recent closing ranks, {num(result.excluded.avoided_branch)} in branches you chose to avoid and {num(result.excluded.no_latest_cutoff)} missing from the {result.data_year} seat matrix, so not offered this year{(result.excluded.no_seat_in_category ?? 0) > 0 ? `, and ${num(result.excluded.no_seat_in_category)} with no ${result.data_year} seat in your category` : ""}. Each band shows its 25 best matches for you, and options with limited history come last.</p>
          )}
          {loading && !result && <Skeleton lines={4} />}
          <div className={`space-y-4 transition-opacity ${loading ? "opacity-60" : ""}`}>
            {shown.map((o, i) => <OptionCard key={o.programme_id} option={o} index={i} />)}
          </div>
          {result?.csab && <CsabPanel csab={result.csab} />}
          {result && shown.length === 0 && !loading && (
            <div className="space-y-3">
              {result.options.length === 0 && result.warnings.filter((w) => w.includes("no options")).map((w) => <Notice key={w} tone="warn">{w}</Notice>)}
              <Notice>{result.options.length === 0
                ? "No JoSAA programme has closed within 20% of your rank in recent years. Check that your ranks and Class XII state are correct. State counselling isn't covered here, and it may still have options."
                : "No options in this view. Try another band, or check that your ranks and Class XII state are correct."}</Notice>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
