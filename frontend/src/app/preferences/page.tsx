"use client";
import { ArrowDown, ArrowUp, GripVertical, Plus, Printer, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { BandBadge, Notice, PageHeader, Skeleton } from "@/components/ui";
import { num, post, type PreferenceAnalysis, type PreferenceItem, type Profile } from "@/lib/api";
import { loadLists, loadProfile, type SavedList, saveLists } from "@/lib/store";

const QUOTA: Record<string, string> = { AI: "All India", HS: "Home State", OS: "Other State", GO: "Goa", JK: "Jammu & Kashmir", LA: "Ladakh" };
const TYPES = ["All", "IIT", "IISC", "NIT", "IIIT", "GFTI"];

export default function PreferencesPage() {
  const [profile, setProfile] = useState<Profile | null | undefined>(undefined);
  const [lists, setLists] = useState<SavedList[]>([]);
  const [active, setActive] = useState(0);
  const [analysis, setAnalysis] = useState<PreferenceAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState<number | null>(null);
  const [filter, setFilter] = useState("All");

  useEffect(() => { setProfile(loadProfile()); setLists(loadLists()); }, []);
  const list = lists[active];
  const ids = list?.items.map((i) => i.id).join(",") ?? "";

  const update = useCallback((items: SavedList["items"]) => {
    setLists((current) => {
      const next = current.map((l, i) => (i === active ? { ...l, items } : l));
      saveLists(next);
      return next;
    });
  }, [active]);

  useEffect(() => {
    if (!profile || !ids) { setAnalysis(null); return; }
    let live = true;
    post<PreferenceAnalysis>("/preference-lists/analyse", { profile, programme_ids: ids.split(",").map(Number) })
      .then((a) => { if (live) { setAnalysis(a); setError(null); } }).catch((e) => { if (live) setError(e.message); });
    return () => { live = false; };
  }, [profile, ids]);

  const byId = useMemo(() => new Map(analysis?.items.map((i) => [i.programme_id, i])), [analysis]);
  const move = (from: number, to: number) => {
    if (!list || to < 0 || to >= list.items.length) return;
    const items = [...list.items];
    const [moved] = items.splice(from, 1);
    items.splice(to, 0, moved);
    update(items);
  };
  const addList = () => {
    const next = [...lists, { id: String(Date.now()), name: `Scenario ${lists.length + 1}`, items: list ? [...list.items] : [] }];
    setLists(next); saveLists(next); setActive(next.length - 1);
  };
  const removeList = () => {
    if (lists.length < 2) return;
    const next = lists.filter((_, i) => i !== active);
    setLists(next); saveLists(next); setActive(0);
  };

  if (profile === undefined) return <div className="mx-auto max-w-4xl px-4 py-10"><Skeleton /></div>;
  if (profile === null) return <div className="mx-auto max-w-xl px-4 py-16 text-center"><h1 className="text-3xl">Start with your rank</h1><p className="mt-2 text-ink-2">We need your ranks to check a preference list.</p><Link href="/onboarding" className="btn btn-primary mt-5">Find my best fit</Link></div>;

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <PageHeader title="JoSAA preference list" intro="Put choices in the order you actually want them. We flag problems, but we never change your order.">
        <button className="btn btn-secondary no-print" onClick={() => window.print()} disabled={!list?.items.length}><Printer size={15} aria-hidden /> Save as PDF</button>
      </PageHeader>
      <div className="no-print mb-4 flex flex-wrap items-center gap-2" role="group" aria-label="Saved lists">
        {lists.map((l, i) => <button key={l.id} aria-pressed={i === active} onClick={() => setActive(i)} className={`rounded-full border px-3 py-1.5 text-sm ${i === active ? "border-brand bg-brand text-brand-ink" : "border-line bg-surface text-ink-2"}`}>{l.name} ({l.items.length})</button>)}
        <button className="btn btn-secondary !px-3 !py-1.5 text-sm" onClick={addList}><Plus size={14} aria-hidden /> Copy as new scenario</button>
        {lists.length > 1 && <button className="btn btn-secondary !px-3 !py-1.5 text-sm" onClick={removeList}><Trash2 size={14} aria-hidden /> Delete this list</button>}
      </div>
      {error && <div className="mb-4"><Notice tone="error">{error}</Notice></div>}
      {!list?.items.length ? (
        <Notice>Your list is empty. Open your <Link href="/recommendations" className="underline">shortlist</Link> and choose “Add to list” on the options you want.</Notice>
      ) : (
        <>
          {analysis && (
            <div className="mb-4 space-y-2">
              <p className="tnum text-sm text-ink-3">{num(analysis.counts.safer)} safer, {num(analysis.counts.competitive)} competitive, {num(analysis.counts.ambitious)} ambitious. Based on past cutoffs to {analysis.data_year}.</p>
              {analysis.advice.map((a) => <Notice key={a} tone="warn">{a}</Notice>)}
            </div>
          )}
          <div className="no-print mb-3 flex flex-wrap gap-2" role="group" aria-label="Show institution type">
            {TYPES.map((t) => <button key={t} aria-pressed={filter === t} onClick={() => setFilter(t)} className={`rounded-full border px-3 py-1 text-xs ${filter === t ? "border-brand bg-brand-soft text-ink" : "border-line text-ink-2"}`}>{t === "IISC" ? "IISc" : t}</button>)}
            {filter !== "All" && <span className="self-center text-xs text-ink-3">Only a view. Your full order stays the same.</span>}
          </div>
          <ol className="space-y-2">
            {list.items.map((entry, index) => {
              const item: PreferenceItem | undefined = byId.get(entry.id);
              if (filter !== "All" && item?.institution?.type !== filter) return null;
              const route = item?.routes?.[0];
              return (
                <li key={entry.id} draggable onDragStart={() => setDragging(index)} onDragOver={(e) => e.preventDefault()} onDrop={() => { if (dragging !== null) move(dragging, index); setDragging(null); }} className="card flex items-start gap-3 p-3">
                  <GripVertical size={16} className="no-print mt-1 shrink-0 cursor-grab text-ink-3" aria-hidden />
                  <span className="tnum mt-0.5 w-6 shrink-0 font-medium">{index + 1}</span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium"><Link href={`/programmes/${entry.id}`} className="hover:underline">{item?.programme ?? entry.label}</Link></p>
                    <p className="text-sm text-ink-2">{item?.institution?.short_name}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2"><BandBadge band={item?.band ?? "limited_history"} />{route && <span className="tnum text-xs text-ink-3">{route.seat_type}, {QUOTA[route.quota] ?? route.quota}, {route.gender_pool === "female" ? "female-only" : "gender-neutral"}</span>}</div>
                    {route && <p className="mt-1 text-xs text-ink-3">{route.explanation}</p>}
                    {item?.issues.map((issue) => <p key={issue} className="mt-1 text-xs" style={{ color: "var(--competitive)" }}>{issue}</p>)}
                  </div>
                  <div className="no-print flex shrink-0 gap-1">
                    <button className="btn btn-secondary !p-1.5" aria-label={`Move choice ${index + 1} up`} disabled={index === 0} onClick={() => move(index, index - 1)}><ArrowUp size={14} /></button>
                    <button className="btn btn-secondary !p-1.5" aria-label={`Move choice ${index + 1} down`} disabled={index === list.items.length - 1} onClick={() => move(index, index + 1)}><ArrowDown size={14} /></button>
                    <button className="btn btn-secondary !p-1.5" aria-label={`Remove choice ${index + 1}`} onClick={() => update(list.items.filter((_, i) => i !== index))}><X size={14} /></button>
                  </div>
                </li>
              );
            })}
          </ol>
          {analysis && (
            <section className="card mt-6 p-5">
              <h2 className="text-lg">Your order, past cutoffs and real allotment are different things</h2>
              <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm text-ink-2">{analysis.rules.map((r) => <li key={r}>{r}</li>)}</ul>
            </section>
          )}
          <p className="no-print mt-4 text-sm"><Link href="/report" className="underline underline-offset-2">Create a parent report from this list</Link></p>
        </>
      )}
    </div>
  );
}
