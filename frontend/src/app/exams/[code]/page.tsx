"use client";
import { ArrowLeft, ChevronDown, Info } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { type CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Notice, PageHeader, Skeleton, SourceLink } from "@/components/ui";
import { api, num } from "@/lib/api";
import {
  EXAM_ICONS, type ExamAnswers, type ExamMetric, type ExamOption, type ExamRoute, type ExamShortlist, examDefaults, formatFigure,
  loadExamAnswers, POSITION_ORDER, POSITION_STYLE, saveExamAnswers, shortRound,
} from "@/lib/exams";

type ListOrder = "top" | "closest";
const ORDERS: Record<ListOrder, { label: string; note: string }> = {
  top: { label: "Top colleges first", note: "Colleges with a better official NIRF 2025 rank in their field come first, then the most contested seats. Colleges NIRF doesn’t list count as neutral, which doesn’t mean they’re weaker. This isn’t a quality score." },
  closest: { label: "Closest to my figure", note: "Seats whose figures were nearest yours come first." },
};

function PositionBadge({ position, label, hint }: { position: string; label: string; hint: string }) {
  const style = POSITION_STYLE[position] ?? POSITION_STYLE.near;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold" style={{ color: style.color, background: style.bg }} title={hint}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: style.color }} aria-hidden />{label}
    </span>
  );
}

// Each round of the year as a step: filled when that round's figure reached the student.
function RoundLadder({ option, metric, figure }: { option: ExamOption; metric: ExamMetric; figure: number }) {
  const color = (POSITION_STYLE[option.position] ?? POSITION_STYLE.near).color;
  return (
    <div>
      <ol className="flex flex-wrap gap-1.5" aria-label="Figures by round">
        {option.rounds.map((step, i) => (
          <li key={`${step.round}-${i}`} className="min-w-[4.5rem] rounded-lg border px-2 py-1 text-center"
            style={step.reached ? { borderColor: color, background: `color-mix(in srgb, ${color} 12%, transparent)` } : { borderColor: "var(--line)" }}>
            <span className="block text-[11px] text-ink-3">{shortRound(step.round)}</span>
            <span className="tnum block text-sm font-semibold">{step.value == null ? "—" : formatFigure(step.value, metric)}</span>
            <span className="sr-only">{step.reached ? "reached your figure" : "did not reach your figure"}</span>
          </li>
        ))}
      </ol>
      <p className="tnum mt-1.5 text-xs text-ink-3">Your {metric.unit}: {formatFigure(figure, metric)}. {option.rounds.length > 1 ? "Shaded rounds reached it." : "Shaded if it reached it."}</p>
    </div>
  );
}

function headlineFee(option: ExamOption) {
  const first = option.fee?.declared[0];
  return first ? `${first.label}: ${first.value}` : null;
}

function OptionCard({ option, route, figure, labels, index, gaps }: { option: ExamOption; route: ExamRoute; figure: number; labels: ExamShortlist["positions"]; index: number; gaps: string[] }) {
  const [open, setOpen] = useState(false);
  const style = POSITION_STYLE[option.position] ?? POSITION_STYLE.near;
  const label = labels[option.position] ?? { label: option.position, hint: "" };
  const name = option.institute_short ?? option.institution?.short_name ?? option.institute;
  const fee = headlineFee(option);
  const academics = option.institution?.academics;
  const missing = [
    ...(option.ranking ? [] : [`Not in NIRF 2025’s ${route.stream} list, so ordered as neutral. That doesn’t mean it’s weaker.`]),
    ...(route.stream === "Medical" && !option.fee ? ["No fee document collected for this seat. Check the counselling authority’s fee list."] : []),
    ...gaps,
  ];
  const lastCount = [...option.rounds].reverse().find((s) => s.count != null)?.count;
  return (
    <article className="card card-hover band-card rise p-5 pl-6" style={{ "--band": style.color, "--i": Math.min(index, 10) } as CSSProperties}>
      <div className="flex flex-wrap items-center gap-2">
        <PositionBadge position={option.position} label={label.label} hint={label.hint} />
        {option.female_only && <span className="rounded-full px-2 py-0.5 text-xs font-semibold" style={{ background: "var(--competitive-soft)", color: "var(--competitive)" }}>Female candidates only</span>}
        <span className="text-xs text-ink-3">{[option.institution ? `${option.institution.type} · ${option.institution.state}` : null, option.quota, option.category].filter(Boolean).join(" · ")}</span>
      </div>
      <h2 className="mt-2 text-xl">{option.programme}</h2>
      <p className="text-ink-2">
        {option.institution ? <Link href={`/colleges/${option.institution.slug}`} className="hover:underline">{name}</Link> : name}
        {option.programme_code ? <span className="text-ink-3"> · course code {option.programme_code}</span> : null}
      </p>
      {name !== option.institute && <p className="text-xs text-ink-3">{option.institute.replace(/\s*\(Female Seat only\s*\)/, "")}</p>}

      <div className="mt-4 grid gap-5 md:grid-cols-[1.6fr_1fr_1fr]">
        <div>
          <p className="text-xs text-ink-3">{route.rounds?.length ? `Round by round, ${route.document.year}` : `${route.metric.value_label}, ${route.document.year}`}</p>
          <div className="mt-1.5"><RoundLadder option={option} metric={route.metric} figure={figure} /></div>
        </div>
        <div>
          <p className="text-xs text-ink-3">Standing</p>
          {option.ranking
            ? <><p className="tnum mt-1 font-medium">NIRF {option.ranking.category} #{option.ranking.rank} <span className="font-normal text-ink-3">({option.ranking.year})</span></p><SourceLink href={option.ranking.source_url} label="Official NIRF list" /></>
            : <p className="mt-1 text-sm text-ink-3">Not ranked by NIRF {route.stream === "Engineering" ? "Engineering" : route.stream} 2025</p>}
        </div>
        <div>
          <p className="text-xs text-ink-3">{route.stream === "Medical" ? "Fees" : route.stream === "Law" ? "Seats" : "Faculty (whole institute)"}</p>
          {route.stream === "Medical" && (fee
            ? <><p className="mt-1 text-sm font-medium break-words">{fee}</p><p className="text-xs" style={{ color: option.fee?.status === "official" ? "var(--safer)" : "var(--competitive)" }}>{option.fee?.status === "official" ? "Official, as printed" : "Declared by the college, unverified"}</p></>
            : <p className="mt-1 text-sm text-ink-3">Data not available</p>)}
          {route.stream === "Law" && (option.seats != null ? <p className="tnum mt-1 text-sm font-medium">{num(option.seats)} in this category</p> : <p className="mt-1 text-sm text-ink-3">Data not available</p>)}
          {route.stream === "Engineering" && (academics?.students_per_regular_faculty != null
            ? <p className="tnum mt-1 text-sm">{academics.students_per_regular_faculty} students per regular faculty member{academics.phd_share != null ? `, ${Math.round(academics.phd_share * 100)}% with a doctorate` : ""}</p>
            : <p className="mt-1 text-sm text-ink-3">Data not available</p>)}
          {lastCount != null && <p className="tnum mt-1 text-xs text-ink-3">{num(lastCount)} allotted in the last round shown</p>}
        </div>
      </div>

      <button type="button" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-brand hover:underline" aria-expanded={open} onClick={() => setOpen(!open)}>
        <ChevronDown size={15} className={`chev ${open ? "rotate-180" : ""}`} aria-hidden /> {open ? "Hide" : "Why this option"}
      </button>
      {open && (
        <div className="rise mt-4 grid gap-6 border-t border-line pt-4 md:grid-cols-2">
          <div className="space-y-4">
            <div><h3 className="text-base font-medium">Why it appears</h3><ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-ink-2">{option.why.map((w) => <li key={w}>{w}</li>)}</ul></div>
            <div><h3 className="text-base font-medium">Data gaps</h3><ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-ink-2">{missing.map((w) => <li key={w}>{w}</li>)}</ul></div>
            {option.note && <p className="text-sm text-ink-2">{option.note}</p>}
          </div>
          <div className="space-y-4">
            {option.fee && (
              <div>
                <h3 className="text-base font-medium">{option.fee.title}</h3>
                <p className="mt-1 text-xs text-ink-3">{option.fee.note}</p>
                <dl className="mt-1 space-y-0.5 text-sm">{option.fee.declared.map((f) => <div key={f.label}><dt className="inline text-ink-3">{f.label}: </dt><dd className="inline break-words">{f.value}</dd></div>)}</dl>
                <p className="mt-1"><SourceLink href={option.fee.source_url} label={`Source document, ${option.fee.year}`} /></p>
              </div>
            )}
            {academics && (
              <div>
                <h3 className="text-base font-medium">Faculty (whole institute)</h3>
                <p className="mt-1 text-sm text-ink-2">
                  {academics.faculty_regular != null ? `${num(academics.faculty_regular)} regular faculty. ` : ""}
                  {academics.students_per_regular_faculty != null ? `${academics.students_per_regular_faculty} students per regular faculty member. ` : ""}
                  {academics.phd_share != null ? `${Math.round(academics.phd_share * 100)}% hold a doctorate. ` : ""}
                  Counts people, not how well anyone teaches.
                </p>
                {academics.source && <p className="mt-1"><SourceLink href={academics.source.url} label={`${academics.source.title}, ${academics.source.submission_year}`} /></p>}
                {option.institution && <p className="mt-1 text-sm"><Link className="underline" href={`/colleges/${option.institution.slug}`}>See the institute’s figures</Link></p>}
              </div>
            )}
            <div>
              <h3 className="text-base font-medium">Source</h3>
              {(route.sources ?? [route.document]).slice(0, 4).map((s) => <p key={s.url} className="mt-1"><SourceLink href={s.url} label={s.title} /></p>)}
            </div>
          </div>
        </div>
      )}
    </article>
  );
}

function PositionMix({ counts, labels }: { counts: Record<string, number>; labels: ExamShortlist["positions"] }) {
  const parts = POSITION_ORDER.map((p) => ({ p, count: counts[p] ?? 0 })).filter((x) => x.count > 0);
  if (!parts.length) return null;
  return (
    <div className="mb-5" role="img" aria-label={parts.map((x) => `${labels[x.p]?.label}: ${x.count}`).join(", ")}>
      <div className="grow-x flex h-3 gap-0.5 overflow-hidden rounded-full">
        {parts.map((x) => <div key={x.p} style={{ flexGrow: x.count, background: POSITION_STYLE[x.p].color === "var(--ink-2)" ? "var(--ink-3)" : POSITION_STYLE[x.p].color }} />)}
      </div>
    </div>
  );
}

export default function ExamShortlistPage() {
  const { code } = useParams<{ code: string }>();
  const [route, setRoute] = useState<ExamRoute | null | undefined>(undefined);
  const [answers, setAnswers] = useState<ExamAnswers>({ value: "", category: "", quota: "", programme: "", gender: "", domicile: "" });
  const [result, setResult] = useState<ExamShortlist | null>(null);
  const [asked, setAsked] = useState<number | null>(null);
  const [order, setOrder] = useState<ListOrder>("top");
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const latest = useRef(0);
  const resultsRef = useRef<HTMLDivElement>(null);
  // On a phone the results sit below the form, so bring them into view once a student asks for them.
  const reveal = useRef(false);

  const run = useCallback(async (r: ExamRoute, a: ExamAnswers, listOrder: ListOrder) => {
    const figure = Number(a.value.replace(/[,\s]/g, ""));
    const params = new URLSearchParams(Object.entries({ value: String(figure), category: a.category, quota: a.quota, programme: a.programme, gender: a.gender, order: listOrder }).filter(([, v]) => v));
    const request = ++latest.current;
    setLoading(true);
    setError(null);
    try {
      const next = await api<ExamShortlist>(`/exams/${r.code}/shortlist?${params}`);
      if (request === latest.current) {
        setResult(next); setAsked(figure); setFilter("all");
        if (reveal.current && window.matchMedia("(max-width: 1023px)").matches) requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: "instant", block: "start" }));
        reveal.current = false;
      }
    } catch (e) {
      if (request === latest.current) setError((e as Error).message);
    } finally {
      if (request === latest.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    api<{ routes: ExamRoute[] }>("/exams").then((d) => {
      const found = d.routes.find((r) => r.code === code) ?? null;
      setRoute(found);
      if (!found) return;
      const saved = loadExamAnswers(found.code);
      const start = { value: "", gender: "", domicile: "", ...examDefaults(found), ...saved };
      setAnswers(start);
      if (saved?.value) run(found, start, "top");
    }).catch(() => setError("These figures aren’t available right now. Please try again shortly."));
  }, [code, run]);

  const figure = answers.value.replace(/[,\s]/g, "");
  const problem = (() => {
    if (!route || figure === "") return null;
    const n = Number(figure);
    if (!(n > 0)) return "Enter a number above 0.";
    if (route.metric.whole_number && !Number.isInteger(n)) return `${route.metric.label} must be a whole number.`;
    if (route.metric.max != null && n > route.metric.max) return `${route.metric.label} can’t be above ${route.metric.max}.`;
    return null;
  })();
  const set = (patch: Partial<ExamAnswers>) => setAnswers((a) => ({ ...a, ...patch }));
  const submit = () => {
    if (!route || problem || figure === "") return;
    saveExamAnswers(route.code, answers);
    reveal.current = true;
    run(route, answers, order);
  };
  const shown = useMemo(() => (result?.options ?? []).filter((o) => filter === "all" || o.position === filter), [result, filter]);

  if (route === undefined) return <div className="mx-auto max-w-6xl px-4 py-10">{error ? <Notice tone="error">{error}</Notice> : <Skeleton />}</div>;
  if (route === null) return <div className="mx-auto max-w-xl px-4 py-16 text-center"><h1 className="text-3xl font-bold">Exam not found</h1><Link href="/exams" className="btn btn-primary mt-5">See covered exams</Link></div>;

  const Icon = EXAM_ICONS[route.stream];
  const categories = route.categories.filter((c) => !route.category_states?.[c] || route.category_states[c] === answers.domicile || c === answers.category);
  const total = result ? Object.values(result.counts).reduce((a, c) => a + c, 0) : 0;
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <Link href="/exams" className="mb-3 inline-flex items-center gap-1 text-sm text-ink-2 hover:text-brand"><ArrowLeft size={15} aria-hidden /> All exams</Link>
      <PageHeader title={`Your ${route.name} shortlist`} intro={route.rounds?.length
        ? <>Compared with {route.authority}’s {route.document.year} figures, round by round. One year of figures can’t support admission bands, so each seat shows the round in which it reached your {route.metric.unit}.</>
        : <>Compared with {route.authority}’s {route.document.year} cut-offs. One year of figures can’t support admission bands, so each seat shows whether its cut-off reached your {route.metric.unit}.</>} />

      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <form className="card space-y-3 p-4" onSubmit={(e) => { e.preventDefault(); submit(); }}>
            <h2 className="flex items-center gap-2 text-lg">{Icon && <Icon size={17} className="text-brand" aria-hidden />} Your details</h2>
            <label className="block text-sm">Your {route.metric.label}
              <input className="input tnum mt-1" inputMode="decimal" value={answers.value} onChange={(e) => set({ value: e.target.value.trim() })} aria-invalid={Boolean(problem)} placeholder={route.metric.lower_is_better ? "e.g. 25,000" : route.metric.max === 100 ? "e.g. 95.5" : "e.g. 600"} />
            </label>
            {problem && <p className="text-sm" style={{ color: "var(--ambitious)" }} role="alert">{problem}</p>}
            {route.category_states && (
              <label className="block text-sm">Your domicile state
                <select className="input mt-1" value={answers.domicile} onChange={(e) => set({ domicile: e.target.value })}>
                  <option value="">Not chosen</option>{[...new Set(Object.values(route.category_states))].sort().map((s) => <option key={s}>{s}</option>)}
                </select>
              </label>
            )}
            <label className="block text-sm">Category, as published
              <select className="input mt-1" value={answers.category} onChange={(e) => set({ category: e.target.value })}>
                <option value="">Choose</option>{categories.map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>
            {(route.quotas?.length ?? 0) > 1 && (
              <label className="block text-sm">Quota or section
                <select className="input mt-1" value={answers.quota} onChange={(e) => set({ quota: e.target.value })}>
                  {!route.compare_requires_group && <option value="">All</option>}
                  {route.quotas?.map((q) => <option key={q} value={q}>{q}{route.quota_requirements?.[q] ? ` (${route.quota_requirements[q]} only)` : ""}</option>)}
                </select>
                {route.quota_requirements?.[answers.quota] && <span className="mt-1 block text-xs" style={{ color: "var(--competitive)" }}>Only for: {route.quota_requirements[answers.quota]}. Check you qualify under the authority’s rules.</span>}
              </label>
            )}
            {route.programmes.length > 1 && (
              <label className="block text-sm">Course
                <select className="input mt-1" value={answers.programme} onChange={(e) => set({ programme: e.target.value })}>
                  <option value="">All</option>{route.programmes.map((p) => <option key={p}>{p}</option>)}
                </select>
              </label>
            )}
            {route.asks_gender && (
              <label className="block text-sm">Gender, for seat eligibility
                <select className="input mt-1" value={answers.gender} onChange={(e) => set({ gender: e.target.value })}>
                  <option value="">Not chosen</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option>
                </select>
              </label>
            )}
            <button type="submit" className="btn btn-primary w-full" disabled={Boolean(problem) || figure === "" || !answers.category}>Show my shortlist</button>
            <p className="text-xs text-ink-3">Saved only in this browser. We don’t ask for your name or contact details.</p>
          </form>
          <details className="card p-4 text-sm">
            <summary className="flex cursor-pointer items-center justify-between gap-2 font-medium"><span className="inline-flex items-center gap-1.5"><Info size={15} aria-hidden /> What this covers ({route.limits.length})</span><ChevronDown size={16} className="chev" aria-hidden /></summary>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-2">{route.limits.map((l) => <li key={l}>{l}</li>)}</ul>
            <p className="mt-2"><Link href={`/exams?route=${route.code}`} className="text-brand underline">See every past figure for this exam</Link></p>
          </details>
        </aside>

        <div ref={resultsRef} className="scroll-mt-20" aria-live="polite">
          {error && <div className="mb-4"><Notice tone="error">{error}</Notice></div>}
          {!result && !loading && (
            <div className="card p-8 text-center">
              <p className="font-display text-xl font-semibold">Enter your {route.metric.label} to see your shortlist</p>
              <p className="mx-auto mt-2 max-w-md text-sm text-ink-2">We start with the {[answers.category, answers.quota, answers.programme].filter(Boolean).join(", ") || "open"} list. Change any answer on the left.</p>
            </div>
          )}
          {loading && !result && <Skeleton lines={4} />}
          {result && asked != null && (
            <>
              <div className="mb-4">
                <div className="inline-flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1" role="group" aria-label="Sort the list">
                  {(Object.keys(ORDERS) as ListOrder[]).map((k) => (
                    <button key={k} type="button" aria-pressed={order === k} onClick={() => { setOrder(k); run(route, answers, k); }}
                      className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${order === k ? "bg-brand-soft text-brand" : "text-ink-2 hover:text-ink"}`}>{ORDERS[k].label}</button>
                  ))}
                </div>
                <p className="mt-1.5 text-xs text-ink-3">{ORDERS[order].note}</p>
              </div>
              <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Filter by round reached">
                {["all", ...POSITION_ORDER.filter((p) => result.counts[p])].map((p) => (
                  <button key={p} type="button" aria-pressed={filter === p} onClick={() => setFilter(p)} title={result.positions[p]?.hint}
                    className={`tnum rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${filter === p ? "border-brand bg-brand text-brand-ink" : "border-line bg-surface text-ink-2"}`}>
                    {p === "all" ? "All" : result.positions[p].label} ({num(p === "all" ? total : result.counts[p])})
                  </button>
                ))}
              </div>
              <PositionMix counts={result.counts} labels={result.positions} />
              <p className="mb-3 text-sm text-ink-3">
                {result.beyond > 0 ? `Not shown: ${num(result.beyond)} ${result.beyond === 1 ? "seat" : "seats"} in this list that didn’t reach your ${route.metric.unit}${route.rounds?.length ? " in any round" : ""}${route.metric.lower_is_better ? " or come within 20% of it" : ""}. ` : ""}
                {result.hidden_female_only > 0 ? `Seats only female candidates may hold are hidden, because you chose ${answers.gender}. ` : ""}
                {result.limit && Object.values(result.counts).some((c) => c > (result.limit ?? 0)) ? `Each group shows its first ${result.limit} in this order.` : ""}
              </p>
              {!answers.gender && route.asks_gender && result.options.some((o) => o.female_only) && <p className="mb-3 text-xs text-ink-3">Some seats are for female candidates only, and are labelled. Choose your gender to see only seats you can hold.</p>}
              <div className={`space-y-4 transition-opacity ${loading ? "opacity-60" : ""}`}>
                {shown.map((o, i) => <OptionCard key={`${o.institute}|${o.programme_code ?? o.programme}|${o.quota}`} option={o} route={route} figure={asked} labels={result.positions} index={i} gaps={result.route_gaps ?? []} />)}
              </div>
              {total === 0 && (
                <Notice>Nothing in this list reached or came within reach of your {route.metric.unit} in {route.document.year}. Try another quota or course, or check your figure. This covers one year and one counselling authority, so other options may still exist.</Notice>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
