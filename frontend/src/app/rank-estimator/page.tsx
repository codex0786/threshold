"use client";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Notice, PageHeader } from "@/components/ui";
import { track } from "@/lib/analytics";
import { num, post, type RankEstimate } from "@/lib/api";
import { loadDraft, saveDraft } from "@/lib/store";

const YEARS = [2027, 2026, 2025, 2024];

export default function RankEstimatorPage() {
  const router = useRouter();
  const [percentile, setPercentile] = useState("");
  const [year, setYear] = useState(2027);
  const [result, setResult] = useState<RankEstimate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const value = Number(percentile);
  const valid = percentile.trim() !== "" && Number.isFinite(value) && value >= 0 && value <= 100;

  const estimate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) { setError("Enter your percentile as a number from 0 to 100, for example 97.8541236."); return; }
    setError(null);
    setLoading(true);
    try {
      setResult(await post<RankEstimate>("/estimates/rank", { percentile: value, exam_year: year }));
      track("rank_estimated", { year });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const useEstimate = () => {
    if (!result) return;
    const middle = Math.round((result.rank_low + result.rank_high) / 2);
    const draft = loadDraft<{ values: Record<string, unknown>; step: number }>();
    saveDraft({ values: { ...(draft?.values ?? {}), main_crl: String(middle) }, step: draft?.step ?? 0 });
    track("rank_estimate_used");
    router.push("/onboarding");
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <PageHeader title="From percentile to rank" intro="Have your JEE Main percentile but not your rank yet? Get a rank range from NTA’s own published figures." />
      <form onSubmit={estimate} className="card grid gap-4 p-5 sm:grid-cols-[1fr_160px_auto] sm:items-end">
        <label className="block text-sm">
          <span className="font-medium">Your JEE Main percentile (NTA score)</span>
          <input className="input tnum mt-1 w-full" inputMode="decimal" placeholder="e.g. 97.8541236" value={percentile} onChange={(e) => setPercentile(e.target.value)} aria-describedby="percentile-hint" />
          <span id="percentile-hint" className="mt-1 block text-xs text-ink-3">If you sat both sessions, use the higher one.</span>
        </label>
        <label className="block text-sm">
          <span className="font-medium">Exam year</span>
          <select className="input mt-1 w-full" value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
        <button type="submit" className="btn btn-primary" disabled={loading}>{loading ? "Working it out…" : "Estimate my rank"}</button>
      </form>
      {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}

      {result && (
        <section className="card rise mt-6 p-5" aria-live="polite">
          <p className="text-sm text-ink-3">Estimated JEE Main Common Rank List (CRL) rank for {result.percentile} percentile in {result.exam_year}</p>
          <p className="tnum mt-1 text-4xl font-bold">{num(result.rank_low)} to {num(result.rank_high)}</p>
          <p className="mt-2 text-sm text-ink-2">{result.candidates_note}</p>
          {result.warnings.map((w) => <div key={w} className="mt-3"><Notice tone="warn">{w}</Notice></div>)}
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" className="btn btn-primary" onClick={useEstimate}>Use {num(Math.round((result.rank_low + result.rank_high) / 2))} to preview my options <ArrowRight size={15} aria-hidden /></button>
          </div>
          <p className="mt-2 text-xs text-ink-3">The shortlist will treat this as your rank. Replace it with your real CRL rank, and add your category rank, once NTA publishes them.</p>
          <h2 className="mt-6 text-lg">How this works</h2>
          <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm text-ink-2">{result.method.map((m) => <li key={m}>{m}</li>)}</ul>
          <p className="mt-3 text-xs text-ink-3">
            Figures from NTA press releases, read through these copies: {result.sources.map((s, i) => <span key={s.year}>{i > 0 && ", "}<a className="underline" href={s.url} target="_blank" rel="noreferrer">{s.year}</a></span>)}. Method version {result.version}.
          </p>
        </section>
      )}
      <p className="mt-6 text-sm text-ink-3">Already have your rank? <Link href="/onboarding" className="underline">Go straight to your shortlist</Link>.</p>
    </div>
  );
}
