import { ArrowDown, ArrowRight, BadgeCheck, Ban, Check, ChevronDown, FileSearch, Minus, UserX } from "lucide-react";
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { ExamPickerRows } from "@/components/exam-picker";
import { CountUp, Reveal } from "@/components/motion";
import { api, type Completeness } from "@/lib/api";
import { type CatalogEntry, examCatalog, type ExamRoute } from "@/lib/exams";

// Figures come from the API, so the page is rebuilt hourly rather than frozen at build time.
export const revalidate = 3600;

async function safe<T>(load: () => Promise<T>, fallback: T): Promise<T> {
  try {
    return await load();
  } catch {
    return fallback;
  }
}

const PRINCIPLES = [
  { icon: FileSearch, title: "Every figure has a source", text: "Each number links to the official document it came from, with its year." },
  { icon: Ban, title: "No made-up chances", text: "We show where past cutoffs fell, never a percentage chance of admission." },
  { icon: BadgeCheck, title: "Gaps stay visible", text: "Where nothing reliable exists, you see “Data not available”, not a guess." },
  { icon: UserX, title: "No sign-up", text: "No name, phone number or email. Your answers stay in this browser." },
];

const STEPS = [
  { title: "Pick your exam", text: "Engineering, medical, law or postgraduate. Enter your rank or score, your category and the quotas you qualify for." },
  { title: "See what your figure reached", text: "Every seat is compared only with figures from the same list, category and quota, round by round." },
  { title: "Weigh it with your family", text: "NIRF rank, fees, faculty and placements where they exist, each with its source." },
];

type Cell = "yes" | "part" | "no" | string;
const MARK: Record<string, { icon: typeof Check; color: string; label: string }> = {
  yes: { icon: Check, color: "var(--safer)", label: "Yes" },
  part: { icon: Check, color: "var(--competitive)", label: "Some institutes" },
  no: { icon: Minus, color: "var(--ink-3)", label: "Not yet" },
};
function CellView({ value }: { value: Cell }) {
  const mark = MARK[value];
  if (!mark) return <span className="tnum text-sm">{value}</span>;
  return <span className="inline-flex items-center gap-1.5 text-sm" style={{ color: mark.color }}><mark.icon size={15} aria-hidden />{mark.label}</span>;
}

function coverageRows(stats: Completeness | null, routes: ExamRoute[], catalog: CatalogEntry[]): { exam: string; cells: Cell[] }[] {
  const named = (code: string, fallback: string) => {
    const entry = catalog.find((e) => e.code === code);
    return entry ? `${entry.name} · ${entry.scope}` : fallback;
  };
  const jee = stats ? {
    exam: named("jee", "JEE (JoSAA)"),
    cells: [`${stats.cutoff_years[0]}–${stats.cutoff_years.at(-1)}`, "Bands", `${stats.coverage.nirf_rank} of ${stats.institutions}`, `${stats.coverage.fees} of ${stats.institutions}`, `${stats.coverage.placements} of ${stats.institutions}`],
  } : null;
  // Other evidence where placements aren't collected: faculty figures for GATE institutes found in the JoSAA data, and seats for law.
  const outcome = (r: ExamRoute): Cell => r.code === "gate-ccmt" ? "Faculty figures" : r.stream === "Law" ? "Seat counts" : "no";
  const order = catalog.map((e) => e.code);
  return [
    ...(jee ? [jee] : []),
    ...[...routes].sort((a, b) => order.indexOf(a.code) - order.indexOf(b.code)).map((r) => ({
      exam: named(r.code, r.name),
      cells: [
        r.document.year,
        r.history ? `Bands, ${r.history.years[0]}–${r.history.years.at(-1)}` : r.rounds?.length ? `${r.rounds.length} rounds` : "One cut-off",
        r.ranked_institute_count ? `${r.ranked_institute_count} of ${r.institute_count}` : "no",
        r.fee_institute_count ? `${r.fee_institute_count} of ${r.institute_count}` : "no",
        outcome(r),
      ] as Cell[],
    })),
  ];
}

const FAQ = [
  { q: "Is this a guarantee of admission?", a: "No. We show how your rank or score compares with past cutoffs. Cutoffs change every year, and only the counselling authority allots seats." },
  { q: "Why is there no percentage chance?", a: "Results for individual applicants aren’t public, so a percentage couldn’t be properly tested. We’d rather show the past cutoffs than an unsupported number." },
  { q: "Why do some exams show bands and others don’t?", a: "A band (Safer, Competitive, Ambitious) needs at least two years of cutoffs for the same seat. Where we have only one recent year, such as CLAT and UPTAC, each seat shows the round in which it reached your figure instead." },
  { q: "Why do some options say “Data not available”?", a: "We only show placement, fee and faculty figures that have a source we can point to. A gap is more useful to you than a guess." },
  { q: "Can colleges pay to rank higher?", a: "No. Paid partnerships must never affect the order of results, and the method is published." },
];

function SectionHead({ eyebrow, title, intro, id }: { eyebrow: string; title: string; intro?: ReactNode; id?: string }) {
  return (
    <Reveal>
      <p className="eyebrow">{eyebrow}</p>
      <h2 id={id} className="mt-2 max-w-3xl text-3xl sm:text-4xl">{title}</h2>
      {intro && <p className="mt-2 max-w-2xl text-ink-2">{intro}</p>}
    </Reveal>
  );
}

export default async function Home() {
  const [stats, routes] = await Promise.all([
    safe(() => api<Completeness>("/data/completeness"), null),
    safe(async () => (await api<{ routes: ExamRoute[] }>("/exams")).routes, [] as ExamRoute[]),
  ]);
  const catalog = examCatalog(routes, stats ? { years: stats.cutoff_years, institutes: stats.institutions } : null);
  const rows = coverageRows(stats, routes, catalog);
  const records = (stats?.cutoff_records ?? 0) + routes.reduce((sum, r) => sum + r.record_count, 0);
  return (
    <div>
      <section className="hero">
        <span className="orb" style={{ width: 420, height: 420, background: "#4f46e5", top: -140, left: -80 }} aria-hidden />
        <span className="orb" style={{ width: 360, height: 360, background: "#0d9488", bottom: -160, right: "8%", animationDelay: "-6s" }} aria-hidden />
        <span className="orb" style={{ width: 240, height: 240, background: "#d97706", top: 40, right: -60, animationDelay: "-11s", opacity: 0.35 }} aria-hidden />
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 pb-14 pt-12 sm:pt-16 lg:grid-cols-[1.05fr_1fr]">
          <div>
            <p className="rise text-sm font-semibold text-ink-2" style={{ "--i": 0 } as CSSProperties}>For engineering, medical, law and postgraduate aspirants, and their families</p>
            <h1 className="rise mt-3 text-4xl font-bold leading-[1.05] sm:text-6xl" style={{ "--i": 1 } as CSSProperties}>Your Rank Opens Doors. Make Sure You Choose the <span className="gradient-text">Right One.</span></h1>
            <p className="rise mt-5 max-w-xl text-lg text-ink-2" style={{ "--i": 2 } as CSSProperties}>Pick your exam, enter your rank or score, and see which seats it reached in past counselling, with the official source beside every figure.</p>
            <div className="rise mt-7 flex flex-wrap gap-3 lg:hidden" style={{ "--i": 3 } as CSSProperties}>
              <a href="#start" className="btn btn-glow !px-5 !py-3">Choose your exam <ArrowDown size={17} aria-hidden /></a>
            </div>
            {records > 0 && (
              <dl className="rise mt-10 grid max-w-xl grid-cols-3 gap-5 border-t border-line pt-6" style={{ "--i": 4 } as CSSProperties}>
                <div><dt className="text-sm text-ink-3">Cutoff records from official documents</dt><dd className="mt-1 font-display text-2xl font-semibold sm:text-3xl"><CountUp value={records} /></dd></div>
                <div><dt className="text-sm text-ink-3">Exams covered</dt><dd className="mt-1 font-display text-2xl font-semibold sm:text-3xl"><CountUp value={catalog.length} /></dd></div>
                <div><dt className="text-sm text-ink-3">Sign-up needed</dt><dd className="mt-1 font-display text-2xl font-semibold sm:text-3xl">None</dd></div>
              </dl>
            )}
          </div>
          <div id="start" className="rise scroll-mt-24" style={{ "--i": 3 } as CSSProperties}>
            <p className="mb-3 flex items-baseline justify-between gap-3 px-1">
              <span className="font-display text-lg font-semibold">Which exam did you take?</span>
              <Link href="/exams" className="text-sm text-ink-2 underline-offset-2 hover:text-ink hover:underline">All exams</Link>
            </p>
            <ExamPickerRows entries={catalog} />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16">
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PRINCIPLES.map((p, i) => (
            <li key={p.title}>
              <Reveal delay={i * 80} className="h-full">
                <div className="h-full rounded-2xl border border-line p-5">
                  <p.icon size={22} className="text-brand" aria-hidden />
                  <h3 className="mt-3 text-lg">{p.title}</h3>
                  <p className="mt-1 text-sm text-ink-2">{p.text}</p>
                </div>
              </Reveal>
            </li>
          ))}
        </ul>
      </section>

      <section className="border-y border-line bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-16">
          <SectionHead eyebrow="How it works" title="From a rank to a decision, in three steps" />
          <ol className="relative mt-10 grid gap-8 md:grid-cols-3">
            <span className="grow-x absolute left-5 right-[30%] top-5 hidden h-0.5 md:block" style={{ background: "linear-gradient(90deg, var(--brand), var(--teal), var(--accent))" }} aria-hidden />
            {STEPS.map((s, i) => (
              <li key={s.title} className="relative">
                <Reveal delay={i * 140}>
                  <span className="tnum relative inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand font-display font-bold text-brand-ink" aria-hidden>{i + 1}</span>
                  <h3 className="mt-4 text-xl"><span className="sr-only">Step {i + 1}: </span>{s.title}</h3>
                  <p className="mt-2 text-ink-2">{s.text}</p>
                </Reveal>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {rows.length > 0 && (
        <section className="mx-auto max-w-6xl px-4 py-16" aria-labelledby="coverage">
          <SectionHead id="coverage" eyebrow="Honest coverage" title="What we have for each exam, and what we don’t" intro="Placements matter for engineering, but not every course publishes comparable outcomes. Where they don’t, we show other evidence, and say so." />
          <Reveal delay={80}>
            <div className="card mt-6 overflow-x-auto">
              <table className="w-full min-w-[720px] text-left">
                <thead>
                  <tr className="border-b border-line text-sm text-ink-3">
                    {["Exam", "Latest year", "Detail", "NIRF rank", "Fees", "Placements or other evidence"].map((h) => <th key={h} scope="col" className="p-4 font-medium">{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.exam} className="border-b border-line last:border-0">
                      <th scope="row" className="p-4 text-sm font-semibold">{row.exam}</th>
                      {row.cells.map((c, i) => <td key={i} className="p-4"><CellView value={c} /></td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-sm text-ink-3">Counts are institutes with a figure we can source. NIRF ranks are from official NIRF lists. MCC’s fees are as the colleges declared them and aren’t verified. Karnataka’s are KEA’s, as printed. Costs, a parent report and preference-list tools are available for JEE today. <Link href="/methodology" className="underline underline-offset-2 hover:text-brand">Read the methodology</Link></p>
          </Reveal>
        </section>
      )}

      <section className="mx-auto max-w-3xl px-4 py-16">
        <Reveal><h2 className="text-3xl sm:text-4xl">Questions</h2></Reveal>
        <Reveal delay={80}>
          <div className="card mt-5 divide-y divide-line px-5">
            {FAQ.map((f) => (
              <details key={f.q} className="py-4">
                <summary className="flex cursor-pointer items-center justify-between gap-3 font-semibold">{f.q}<ChevronDown size={18} className="chev shrink-0 text-ink-3" aria-hidden /></summary>
                <p className="mt-2 text-ink-2">{f.a}</p>
              </details>
            ))}
          </div>
        </Reveal>
      </section>

      <section className="hero no-print">
        <span className="orb" style={{ width: 340, height: 340, background: "#4f46e5", top: -120, right: "10%" }} aria-hidden />
        <div className="mx-auto max-w-3xl px-4 py-16 text-center">
          <Reveal>
            <h2 className="text-3xl font-bold sm:text-4xl">Sit down together. See the evidence. Decide with confidence.</h2>
            <p className="mt-3 text-ink-2">It takes a few minutes. We don’t ask for your name or contact details.</p>
            <a href="#start" className="btn btn-glow mt-6 !px-6 !py-3">Choose your exam <ArrowRight size={17} aria-hidden /></a>
          </Reveal>
        </div>
      </section>
    </div>
  );
}
