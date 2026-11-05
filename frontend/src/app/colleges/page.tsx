"use client";
import { Search } from "lucide-react";
import Link from "next/link";
import { type CSSProperties, useEffect, useState } from "react";
import { Notice, PageHeader, Skeleton, VerificationTag } from "@/components/ui";
import { api, type InstitutionListItem, type Meta, num } from "@/lib/api";

type Page = { items: InstitutionListItem[]; total: number; page: number; page_size: number };

export default function Colleges() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [state, setState] = useState("");
  const [branch, setBranch] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api<Meta>("/meta").then(setMeta).catch((e) => setError(e.message)); }, []);
  useEffect(() => {
    const t = setTimeout(() => { setQuery(q); setPage(1); }, 250);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => {
    const params = new URLSearchParams({ page: String(page) });
    if (query) params.set("q", query);
    if (type) params.set("type", type);
    if (state) params.set("state", state);
    if (branch) params.set("branch", branch);
    let live = true;
    api<Page>(`/institutions?${params}`).then((d) => { if (live) { setData(d); setError(null); } }).catch((e) => { if (live) setError(e.message); });
    return () => { live = false; };
  }, [query, type, state, branch, page]);

  const select = (setter: (v: string) => void) => (e: React.ChangeEvent<HTMLSelectElement>) => { setter(e.target.value); setPage(1); };
  const pages = data ? Math.ceil(data.total / data.page_size) : 1;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader title="Colleges" intro="Institutes in JoSAA counselling, with official cutoff history. Where a NIRF rank is on record, ranked institutes appear first. Having no rank here is a gap in our data, not a judgement." />
      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="relative sm:col-span-2 lg:col-span-1">
          <span className="sr-only">Search by name or city</span>
          <Search size={15} className="absolute left-3 top-3 text-ink-3" aria-hidden />
          <input className="input !pl-8" placeholder="Search name or city" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <label><span className="sr-only">Institution type</span><select className="input" value={type} onChange={select(setType)}><option value="">All types</option>{meta && Object.entries(meta.institute_types).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label><span className="sr-only">State</span><select className="input" value={state} onChange={select(setState)}><option value="">All states</option>{meta?.states.map((s) => <option key={s}>{s}</option>)}</select></label>
        <label><span className="sr-only">Branch</span><select className="input" value={branch} onChange={select(setBranch)}><option value="">All branches</option>{meta && Object.entries(meta.branch_families).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      {!data && !error && <Skeleton lines={5} />}
      {data && <p className="tnum mb-3 text-sm text-ink-3" aria-live="polite">{num(data.total)} institutes</p>}
      {data && data.items.length === 0 && <Notice>No institutes match these filters. Try removing one.</Notice>}
      <ul className="grid gap-3 md:grid-cols-2">
        {data?.items.map((i, index) => (
          <li key={i.slug} className="rise" style={{ "--i": index } as CSSProperties}>
            <Link href={`/colleges/${i.slug}`} className="card card-hover block h-full p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0"><h2 className="text-lg">{i.short_name}</h2><p className="truncate text-sm text-ink-3">{i.official_name}</p></div>
                <span className="shrink-0 rounded-full bg-brand-soft px-2 py-0.5 text-xs font-semibold text-brand">{i.type === "IISC" ? "IISc" : i.type}</span>
              </div>
              <p className="mt-2 text-sm text-ink-2">{i.city ? `${i.city}, ` : ""}{i.state} · {num(i.programme_count)} programmes</p>
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-sm">
                {i.ranking ? <span className="tnum">NIRF #{i.ranking.rank} ({i.ranking.year}) <VerificationTag status={i.ranking.verification_status} /></span> : <span className="text-ink-3">NIRF rank: Data not available</span>}
                <span className="tnum text-xs text-ink-3">Data {i.completeness.percent}% complete</span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
      {data && pages > 1 && (
        <nav className="mt-6 flex items-center justify-center gap-3" aria-label="Pages">
          <button className="btn btn-secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
          <span className="tnum text-sm text-ink-3">Page {page} of {pages}</span>
          <button className="btn btn-secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
        </nav>
      )}
    </div>
  );
}
