import { ArrowRight, CircleDashed } from "lucide-react";
import Link from "next/link";
import { ExamPickerCards } from "@/components/exam-picker";
import { Reveal } from "@/components/motion";
import { PageHeader } from "@/components/ui";
import { api, type Completeness } from "@/lib/api";
import { examCatalog, type ExamRoute } from "@/lib/exams";

// Figures come from the API, so the page is rebuilt hourly rather than frozen at build time.
export const revalidate = 3600;

export const metadata = { title: "Exams · Threshold" };

const NOT_COVERED: [string, string][] = [
  ["CAT and IIMs", "Each IIM sets its own shortlisting criteria, and we haven't audited them, so there are no cut-offs to show."],
  ["CUET UG", "Admission runs through each university's own process. Not audited yet."],
  ["NEET PG", "Planned. MCC's PG allotment lists are next on our list."],
  ["AILET", "120 BA LL.B. seats are confirmed, but we found no published cut-off to show."],
  ["Other state counselling", "Tamil Nadu labels every 2026 list provisional, so none is shown. Other states aren't audited yet."],
  ["UGC-NET, JRF and PhD", "A qualification rather than college counselling. Rules aren't confirmed from UGC or NTA yet."],
];

async function safe<T>(load: () => Promise<T>, fallback: T): Promise<T> {
  try {
    return await load();
  } catch {
    return fallback;
  }
}

export default async function ExamsPage() {
  const [stats, routes] = await Promise.all([
    safe(() => api<Completeness>("/data/completeness"), null),
    safe(async () => (await api<{ routes: ExamRoute[] }>("/exams")).routes, [] as ExamRoute[]),
  ]);
  const catalog = examCatalog(routes, stats ? { years: stats.cutoff_years, institutes: stats.institutions } : null);
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader title="Choose your exam" intro="Each exam has its own counselling, categories and quotas, so each gets its own shortlist. Pick the one you took; you can switch any time." />
      <ExamPickerCards entries={catalog} />

      <Reveal>
        <section className="mt-14 rounded-2xl border border-dashed border-line p-6" aria-labelledby="not-covered">
          <h2 id="not-covered" className="flex items-center gap-2 text-xl"><CircleDashed size={18} className="text-ink-3" aria-hidden /> Not covered yet</h2>
          <p className="mt-1 text-sm text-ink-2">We add an exam only when there's an official source we can read and check. Here's what's missing, and why.</p>
          <dl className="mt-4 grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
            {NOT_COVERED.map(([name, why]) => (
              <div key={name}><dt className="font-semibold">{name}</dt><dd className="text-ink-2">{why}</dd></div>
            ))}
          </dl>
          <Link href="/methodology" className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-brand hover:underline">How we choose and check sources <ArrowRight size={14} aria-hidden /></Link>
        </section>
      </Reveal>
    </div>
  );
}
