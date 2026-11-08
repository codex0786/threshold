"use client";
import { Scale, Stethoscope, Wrench } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Notice, PageHeader, Skeleton, SourceLink } from "@/components/ui";
import { api, num } from "@/lib/api";

type Metric = { label: string; unit: string; lower_is_better: boolean; whole_number?: boolean; max?: number; value_label: string; second_label: string | null };
type Doc = { title: string; url: string; year: string; round: string; retrieved: string; status: "official" | "derived" };
type Route = {
  code: string; stream: string; level: string; name: string; authority: string; metric: Metric; document: Doc; limits: string[];
  record_count: number; institute_count: number; categories: string[]; groups: string[]; programmes: string[]; compare_requires_group?: boolean;
};
type Ranking = { category: string; rank: number; year: number; source_url: string };
type DemoRecord = { ranking?: Ranking; standing?: number; institute: string; programme: string; programme_code?: string; group: string | null; category: string; value: number | null; second_value?: number | null; first_value?: number; count?: number; seats?: number; note?: string | null };
type Result = { total: number; matched: number; compared: boolean; missing: string[]; no_figure: DemoRecord[]; records: DemoRecord[] };

const STATUS = {
  official: { label: "Official figure", color: "var(--safer)" },
  derived: { label: "Calculated by us from official allotments", color: "var(--competitive)" },
};
const NOT_COVERED: [string, string][] = [
  ["CAT and IIMs", "Each IIM reportedly sets its own criteria, and official policies are not yet audited. No cutoffs or bands would be shown."],
  ["UGC-NET, JRF and PhD", "A qualification, not college counselling. Rules are not yet confirmed from UGC or NTA."],
  ["AILET", "120 BA LL.B. seats confirmed, but we found no published cut-off to show."],
  ["Maharashtra law and medical", "No public cutoff document found. Medical portals open at a login page."],
  ["Other states and PG exams", "Not yet audited."],
];
type ListOrder = "top" | "closest";
const ORDERS: Record<ListOrder, { label: string; note: string }> = {
  top: { label: "Top colleges first", note: "Colleges with a better official NIRF 2025 rank in their field come first, then the most contested seats. Colleges NIRF doesn’t list count as neutral, which doesn’t mean they’re weaker. This isn’t a quality score." },
  closest: { label: "Closest to my figure", note: "Past figures nearest yours come first." },
};
// The first view shows one clear list (the open category, and for NEET the All India quota and MBBS), not every list mixed.
const OPEN_CATEGORIES = ["Open", "OPEN", "General (General)", "GOPENS"];
function defaultsFor(route: Route) {
  return {
    category: OPEN_CATEGORIES.find((c) => route.categories.includes(c)) ?? "",
    group: route.compare_requires_group ? (route.groups.includes("All India") ? "All India" : route.groups[0] ?? "") : "",
    programme: route.programmes.length > 1 ? (route.programmes.includes("MBBS") ? "MBBS" : route.programmes[0]) : "",
  };
}
const ICONS: Record<string, typeof Wrench> = { Medical: Stethoscope, Law: Scale, Engineering: Wrench };

export default function ExamsPage() {
  const [routes, setRoutes] = useState<Route[] | null>(null);
  const [selected, setSelected] = useState<Route | null>(null);
  const [value, setValue] = useState("");
  const [category, setCategory] = useState("");
  const [group, setGroup] = useState("");
  const [search, setSearch] = useState("");
  const [programme, setProgramme] = useState("");
  const [order, setOrder] = useState<ListOrder>("top");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sectionRef = useRef<HTMLElement>(null);

  const run = useCallback((route: Route, params: { value: string; category: string; group: string; search: string; programme: string; order: ListOrder }) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, v]) => v));
    setError(null);
    api<Result>(`/exams/${route.code}?${query}`).then(setResult).catch((e) => setError(e.message));
  }, []);

  const choose = useCallback((route: Route) => {
    const start = defaultsFor(route);
    setSelected(route);
    setValue(""); setCategory(start.category); setGroup(start.group); setSearch(""); setProgramme(start.programme); setOrder("top");
    setResult(null);
    run(route, { value: "", search: "", order: "top", ...start });
  }, [run]);
  // The list sits below the exam cards, so bring it into view once the chosen exam has rendered.
  useEffect(() => {
    // "instant": the page scrolls smoothly by default, and that animation is cut short as the results load in.
    if (selected) sectionRef.current?.scrollIntoView({ behavior: "instant", block: "start" });
  }, [selected]);
  useEffect(() => {
    api<{ routes: Route[] }>("/exams").then((d) => {
      setRoutes(d.routes);
      const wanted = d.routes.find((r) => r.code === new URLSearchParams(window.location.search).get("route"));
      if (wanted) choose(wanted);
    }).catch(() => setError("These figures aren't available right now. Please try again shortly."));
  }, [choose]);

  const problem = (() => {
    if (value === "" || !selected) return null;
    const n = Number(value);
    if (!(n > 0)) return "Enter a number above 0.";
    if (selected.metric.whole_number && !Number.isInteger(n)) return `${selected.metric.label} must be a whole number.`;
    if (selected.metric.max != null && n > selected.metric.max) return `${selected.metric.label} can’t be above ${selected.metric.max}.`;
    return null;
  })();

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <PageHeader title="Other exams and colleges" intro="Figures from official documents, each shown with its source. This shows what happened in past admissions. It doesn’t predict admission." />
      <div className="mb-6"><Notice tone="warn">Early coverage. Most routes cover one document, one round or one institute, so this isn’t a full list of options. Check the limits shown for each exam.</Notice></div>
      {error && <div className="mb-4"><Notice tone="error">{error}</Notice></div>}
      {!routes && !error && <Skeleton />}

      {routes && (
        <div className="grid gap-3 sm:grid-cols-2">
          {routes.map((route) => {
            const Icon = ICONS[route.stream] ?? Wrench;
            const on = selected?.code === route.code;
            return (
              <button key={route.code} type="button" aria-pressed={on} onClick={() => choose(route)} className={`card card-hover p-4 text-left ${on ? "!border-brand" : ""}`}>
                <span className="flex items-center gap-2 text-sm text-ink-3"><Icon size={15} aria-hidden /> {route.stream} · {route.level}</span>
                <span className="mt-1 block font-display text-lg font-semibold">{route.name}</span>
                <span className="tnum mt-1 block text-sm text-ink-2">{num(route.record_count)} records from {num(route.institute_count)} {route.institute_count === 1 ? "institute" : "institutes"}</span>
              </button>
            );
          })}
        </div>
      )}

      {selected && (
        <section ref={sectionRef} className="mt-8 scroll-mt-20" aria-label={selected.name}>
          <h2 className="text-2xl">{selected.name}</h2>
          <div className="card mt-3 p-4 text-sm">
            <p className="font-semibold" style={{ color: STATUS[selected.document.status].color }}>{STATUS[selected.document.status].label}</p>
            <p className="mt-1">{selected.authority}. {selected.document.round}, {selected.document.year}.</p>
            <p className="mt-1"><SourceLink href={selected.document.url} label={selected.document.title} /></p>
            <details className="mt-2">
              <summary className="cursor-pointer font-medium text-brand">What this covers, and what it doesn’t ({selected.limits.length})</summary>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-2">{selected.limits.map((l) => <li key={l}>{l}</li>)}</ul>
            </details>
          </div>

          <form className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4" onSubmit={(e) => { e.preventDefault(); if (!problem) run(selected, { value, category, group, search, programme, order }); }}>
            <label className="col-span-2 block text-sm lg:col-span-1">Your {selected.metric.label}
              <input className="input tnum mt-1" inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value.trim())} aria-invalid={Boolean(problem)} />
            </label>
            <label className="block text-sm">Category, as published
              <select className="input mt-1" value={category} onChange={(e) => setCategory(e.target.value)}>
                <option value="">All</option>{selected.categories.map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>
            <label className="block text-sm">Quota, section or round
              <select className="input mt-1" value={group} onChange={(e) => setGroup(e.target.value)}>
                <option value="">All</option>{selected.groups.map((g) => <option key={g}>{g}</option>)}
              </select>
            </label>
            {selected.programmes.length > 1 && (
              <label className="block text-sm">Course
                <select className="input mt-1" value={programme} onChange={(e) => setProgramme(e.target.value)}>
                  <option value="">All</option>{selected.programmes.map((p) => <option key={p}>{p}</option>)}
                </select>
              </label>
            )}
            <label className="col-span-2 block text-sm lg:col-span-1">Institute or course
              <input className="input mt-1" value={search} onChange={(e) => setSearch(e.target.value)} />
            </label>
            <div className="col-span-2 lg:col-span-4"><button type="submit" className="btn btn-primary" disabled={Boolean(problem)}>Show past figures</button></div>
            {problem && <p className="col-span-2 text-sm lg:col-span-4" style={{ color: "var(--ambitious)" }} role="alert">{problem}</p>}
          </form>

          <div className="mt-5">
            <div className="inline-flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1" role="group" aria-label="Sort the list">
              {(Object.keys(ORDERS) as ListOrder[]).map((key) => (
                <button key={key} type="button" aria-pressed={order === key}
                  onClick={() => { setOrder(key); if (!problem) run(selected, { value, category, group, search, programme, order: key }); }}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${order === key ? "bg-brand-soft text-brand" : "text-ink-2 hover:text-ink"}`}>
                  {ORDERS[key].label}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-xs text-ink-3">{ORDERS[order].note}</p>
          </div>

          {result && (
            <div className="mt-4" aria-live="polite">
              <p className="tnum text-sm text-ink-2">{result.compared
                ? `${num(result.matched)} of ${num(result.total)} past figures in ${[group, category].filter(Boolean).join(", ")} closed at or ${selected.metric.lower_is_better ? "beyond" : "below"} your ${selected.metric.unit} of ${value}`
                : `${num(result.total)} past figures${[programme, group, category].some(Boolean) ? ` in ${[programme, group, category].filter(Boolean).join(", ")}` : ""}. Enter your ${selected.metric.unit} to compare`}{result.matched > result.records.length ? `. Showing the first ${result.records.length}.` : "."}</p>
              {value && !result.compared && <div className="mt-3"><Notice tone="warn">Choose your {result.missing.join(" and ")} to compare your {selected.metric.unit}. Categories have separate cut-offs and some quotas have their own eligibility, so we don’t compare across them.</Notice></div>}
              {result.records.length === 0 && <div className="mt-3"><Notice>No past figures match in this sample. That doesn’t mean no option exists, because the sample is small.</Notice></div>}
              <div className="mt-3 space-y-2">
                {result.records.map((r) => (
                  <article key={`${r.institute}|${r.programme_code ?? r.programme}|${r.group}|${r.category}`} className="card p-3">
                    <p className="font-semibold">{r.programme}</p>
                    <p className="text-sm text-ink-2">{r.institute}{r.programme_code ? ` · course code ${r.programme_code}` : ""}</p>
                    <p className="text-xs text-ink-3">{[r.group, r.category].filter(Boolean).join(" · ")}</p>
                    {r.ranking && <p className="mt-1 text-xs"><span className="font-semibold">NIRF {r.ranking.year} {r.ranking.category} rank {r.ranking.rank}</span> <SourceLink href={r.ranking.source_url} label="Official NIRF list" /></p>}
                    <dl className="tnum mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
                      <div><dt className="inline text-ink-3">{selected.metric.value_label}: </dt><dd className="inline font-semibold">{r.value === null ? "Data not available" : num(r.value)}</dd></div>
                      {selected.metric.second_label && <div><dt className="inline text-ink-3">{selected.metric.second_label}: </dt><dd className="inline">{r.second_value == null ? "Data not available" : num(r.second_value)}</dd></div>}
                      {r.seats != null && <div><dt className="inline text-ink-3">Seats: </dt><dd className="inline">{num(r.seats)}</dd></div>}
                      {r.count != null && <div><dt className="inline text-ink-3">Allotments in this round: </dt><dd className="inline">{num(r.count)}</dd></div>}
                    </dl>
                  </article>
                ))}
              </div>
              {result.no_figure.length > 0 && (
                <div className="mt-3 text-sm text-ink-2">No comparable figure for {num(result.no_figure.length)} {result.no_figure.length === 1 ? "entry" : "entries"} in this view, including {[...new Set(result.no_figure.map((r) => r.category))].slice(0, 5).join(", ")}. {result.no_figure[0].note}.</div>
              )}
            </div>
          )}
        </section>
      )}

      <section className="mt-10">
        <h2 className="text-xl">Not covered yet</h2>
        <ul className="mt-2 space-y-2 text-sm">{NOT_COVERED.map(([name, why]) => <li key={name}><span className="font-medium">{name}:</span> <span className="text-ink-2">{why}</span></li>)}</ul>
      </section>
    </div>
  );
}
