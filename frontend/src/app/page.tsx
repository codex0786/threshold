import { ArrowRight, BadgeCheck, Ban, Check, ChevronDown, FileSearch, GraduationCap, HeartHandshake, Minus, Scale, Stethoscope, UserX, Wrench } from "lucide-react";
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { CutoffTrace, type TracePoint } from "@/components/cutoff-trace";
import { CountUp, Reveal } from "@/components/motion";
import { api, type Completeness, type CutoffPoint, type InstitutionDetail, num } from "@/lib/api";
import type { ExamRoute } from "@/lib/exams";

// Figures come from the API, so the page is rebuilt hourly rather than frozen at build time.
export const revalidate = 3600;

type Trace = { points: TracePoint[]; rankList: string; sourceUrl: string };

async function loadTrace(): Promise<Trace | null> {
  try {
    const inst = await api<InstitutionDetail>("/institutions/nit-tiruchirappalli");
    const id = inst.programmes.find((p) => p.name === "Computer Science and Engineering" && p.currently_offered && p.degree === "Bachelor of Technology")?.id;
    if (id == null) return null;
    const { records } = await api<{ records: CutoffPoint[] }>(`/programmes/${id}/cutoffs?seat_type=OPEN&gender_pool=neutral&quota=OS`);
    const final = records.filter((r) => r.is_final_round && !r.is_preparatory && r.closing_rank != null).sort((a, b) => a.year - b.year);
    if (final.length < 2) return null;
    return {
      points: final.map((r) => ({ year: r.year, closing: r.closing_rank as number })),
      rankList: final[0].rank_list.replace("JEE_ADVANCED:", "JEE Advanced ").replace("JEE_MAIN:", "JEE Main "),
      sourceUrl: final.at(-1)?.source_url ?? "https://josaa.nic.in/or-cr/",
    };
  } catch {
    return null;
  }
}

async function safe<T>(load: () => Promise<T>, fallback: T): Promise<T> {
  try {
    return await load();
  } catch {
    return fallback;
  }
}

const STREAM_ICON: Record<string, typeof Wrench> = { Medical: Stethoscope, Law: Scale, Engineering: Wrench };
const STREAM_TONE: Record<string, string> = { Medical: "var(--ambitious)", Law: "var(--competitive)", Engineering: "var(--teal)" };

// Short exam names for the picker. Routes not listed here use their metric's name.
const EXAM_NAMES: Record<string, string> = { "neet-ug": "NEET UG, All India", "karnataka-neet": "NEET UG, Karnataka", clat: "CLAT", "gate-ccmt": "GATE", "maharashtra-engineering": "MHT-CET" };

type Pick = { href: string; icon: typeof Wrench; tone: string; exam: string; title: string; enter: string; facts: string[] };

function picks(stats: Completeness | null, routes: ExamRoute[]): Pick[] {
  const jee: Pick = {
    href: "/onboarding", icon: GraduationCap, tone: "var(--brand)", exam: "JEE Main and Advanced", title: "IITs, NITs, IIITs and GFTIs (JoSAA)", enter: "Your JEE ranks",
    facts: stats ? [`${stats.cutoff_years[0]}–${String(stats.cutoff_years.at(-1)).slice(2)} cutoffs`, "Admission bands", "Placements and fees"] : ["Admission bands", "Placements and fees"],
  };
  return [jee, ...routes.map((r) => ({
    href: `/exams/${r.code}`, icon: STREAM_ICON[r.stream] ?? Wrench, tone: STREAM_TONE[r.stream] ?? "var(--brand)",
    exam: EXAM_NAMES[r.code] ?? r.metric.label.replace(/ (rank|score|percentile|All India Rank)$/i, ""), title: r.name, enter: `Your ${r.metric.label}`,
    facts: [`${r.document.year}${r.rounds?.length ? `, ${r.rounds.length} rounds` : ""}`, `${num(r.institute_count)} institutes`, ...(r.fee_institute_count ? [`Fees for ${num(r.fee_institute_count)}`] : [])],
  }))];
}

const PRINCIPLES = [
  { icon: FileSearch, title: "Every figure has a source", text: "Each number links to the official document it came from, with its year." },
  { icon: Ban, title: "No made-up chances", text: "We show where past cutoffs fell, never a percentage chance of admission." },
  { icon: BadgeCheck, title: "Gaps stay visible", text: "Where nothing reliable exists, you see “Data not available”, not a guess." },
  { icon: UserX, title: "No sign-up", text: "No name, phone number or email. Your answers stay in this browser." },
];

const STEPS = [
  { title: "Pick your exam", text: "JEE, NEET, CLAT, GATE or MHT-CET. Enter your rank or score, category and quota." },
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

function coverageRows(stats: Completeness | null, routes: ExamRoute[]): { exam: string; cells: Cell[] }[] {
  const jee = stats ? {
    exam: "JEE (JoSAA)",
    cells: [`${stats.cutoff_years[0]}–${stats.cutoff_years.at(-1)}`, "Bands", `${stats.coverage.nirf_rank} of ${stats.institutions}`, `${stats.coverage.fees} of ${stats.institutions}`, `${stats.coverage.placements} of ${stats.institutions}`],
  } : null;
  // Other evidence where placements aren't collected: faculty figures for GATE institutes found in the JoSAA data, and seats for law.
  const outcome = (r: ExamRoute): Cell => r.code === "gate-ccmt" ? "Faculty figures" : r.stream === "Law" ? "Seat counts" : "no";
  return [
    ...(jee ? [jee] : []),
    ...routes.map((r) => ({
      exam: r.name,
      cells: [
        r.document.year,
        r.rounds?.length ? `${r.rounds.length} rounds` : "One cut-off",
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
  { q: "Why does JEE have bands but NEET, CLAT and GATE don’t?", a: "Bands need at least two years of cutoffs for the same seat. For the other exams we have one recent year, so each seat shows the round in which it reached your figure instead." },
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
  const [stats, routes, trace] = await Promise.all([
    safe(() => api<Completeness>("/data/completeness"), null),
    safe(async () => (await api<{ routes: ExamRoute[] }>("/exams")).routes, [] as ExamRoute[]),
    loadTrace(),
  ]);
  const options = picks(stats, routes);
  const rows = coverageRows(stats, routes);
  const records = (stats?.cutoff_records ?? 0) + routes.reduce((sum, r) => sum + r.record_count, 0);
  return (
    <div>
      <section className="hero">
        <span className="orb" style={{ width: 420, height: 420, background: "#4f46e5", top: -140, left: -80 }} aria-hidden />
        <span className="orb" style={{ width: 360, height: 360, background: "#0d9488", bottom: -160, right: "8%", animationDelay: "-6s" }} aria-hidden />
        <span className="orb" style={{ width: 240, height: 240, background: "#d97706", top: 40, right: -60, animationDelay: "-11s", opacity: 0.35 }} aria-hidden />
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 pb-14 pt-12 sm:pt-16 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <p className="rise text-sm font-semibold text-ink-2" style={{ "--i": 0 } as CSSProperties}>For JEE, NEET, CLAT, GATE and MHT-CET aspirants, and their families</p>
            <h1 className="rise mt-3 text-4xl font-bold leading-[1.05] sm:text-6xl" style={{ "--i": 1 } as CSSProperties}>Your Rank Opens Doors. Make Sure You Choose the <span className="gradient-text">Right One.</span></h1>
            <p className="rise mt-5 max-w-xl text-lg text-ink-2" style={{ "--i": 2 } as CSSProperties}>Enter your rank or score and see which seats it reached in past counselling, with the official source beside every figure.</p>
            <div className="rise mt-7 flex flex-wrap gap-3" style={{ "--i": 3 } as CSSProperties}>
              <a href="#start" className="btn btn-glow !px-5 !py-3">Choose your exam <ArrowRight size={17} aria-hidden /></a>
              <Link href="/colleges" className="btn btn-ghost !px-5 !py-3">Explore colleges</Link>
            </div>
            {records > 0 && (
              <dl className="rise mt-10 grid max-w-xl grid-cols-3 gap-5 border-t border-line pt-6" style={{ "--i": 4 } as CSSProperties}>
                <div><dt className="text-sm text-ink-3">Cutoff records from official documents</dt><dd className="mt-1 font-display text-2xl font-semibold sm:text-3xl"><CountUp value={records} /></dd></div>
                <div><dt className="text-sm text-ink-3">Exams covered</dt><dd className="mt-1 font-display text-2xl font-semibold sm:text-3xl"><CountUp value={options.length} /></dd></div>
                <div><dt className="text-sm text-ink-3">Sign-up needed</dt><dd className="mt-1 font-display text-2xl font-semibold sm:text-3xl">None</dd></div>
              </dl>
            )}
          </div>
          {trace && (
            <div className="rise" style={{ "--i": 3 } as CSSProperties}>
              <CutoffTrace points={trace.points} institute="NIT Tiruchirappalli" programme="Computer Science and Engineering" rankList={trace.rankList} quota="Other State, OPEN" sourceUrl={trace.sourceUrl} />
            </div>
          )}
        </div>
      </section>

      <section id="start" className="mx-auto max-w-6xl scroll-mt-20 px-4 pt-14" aria-labelledby="start-title">
        <SectionHead id="start-title" eyebrow="Start here" title="Which exam did you take?" intro="Pick one to build your shortlist. It takes about a minute, and you can switch exams any time." />
        <ul className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {options.map((o, i) => (
            <li key={o.href}>
              <Reveal delay={i * 70} className="h-full">
                <Link href={o.href} className="card card-hover group flex h-full flex-col p-5" style={{ borderTop: `3px solid ${o.tone}` }}>
                  <span className="flex items-center gap-3">
                    <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ background: `color-mix(in srgb, ${o.tone} 14%, transparent)`, color: o.tone }}><o.icon size={20} aria-hidden /></span>
                    <span className="min-w-0">
                      <span className="block font-display text-lg font-semibold leading-tight group-hover:text-brand">{o.exam}</span>
                      <span className="block text-sm text-ink-2">{o.title}</span>
                    </span>
                  </span>
                  <span className="mt-4 flex flex-wrap gap-1.5">
                    {o.facts.map((f) => <span key={f} className="tnum rounded-full bg-surface-2 px-2.5 py-0.5 text-xs text-ink-2">{f}</span>)}
                  </span>
                  <span className="mt-auto flex items-center justify-between pt-5 text-sm">
                    <span className="text-ink-3">{o.enter}</span>
                    <span className="inline-flex items-center gap-1 font-semibold text-brand">Start <ArrowRight size={15} className="transition-transform group-hover:translate-x-1" aria-hidden /></span>
                  </span>
                </Link>
              </Reveal>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-sm text-ink-3">Not listed? CAT, AILET, other state quotas and PG exams aren’t covered yet. <Link href="/exams" className="underline underline-offset-2 hover:text-brand">See what’s missing and why</Link>.</p>
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
                    {["Exam", "Cutoff years", "Detail", "NIRF rank", "Fees", "Placements or other evidence"].map((h) => <th key={h} scope="col" className="p-4 font-medium">{h}</th>)}
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
            <p className="mt-3 text-sm text-ink-3">Counts are institutes with a figure we can source. NIRF ranks are from official NIRF lists. MCC’s fees are as the colleges declared them and aren’t verified. Karnataka’s are KEA’s, as printed. <Link href="/methodology" className="underline underline-offset-2 hover:text-brand">Read the methodology</Link></p>
          </Reveal>
        </section>
      )}

      <section className="border-y border-line bg-surface">
        <div className="mx-auto grid max-w-6xl gap-5 px-4 py-16 md:grid-cols-2">
          {[
            { icon: GraduationCap, tone: "var(--brand)", title: "For students", text: "You’ve worked for years for this rank. See every seat it reached, sorted the way you choose, and why each one is there.", href: "#start", cta: "Build my shortlist" },
            { icon: HeartHandshake, tone: "var(--competitive)", title: "For parents", text: "Fees, costs with a loan, and a plain-language report you can read together. For JEE today, with more exams to follow.", href: "/report", cta: "See the parent report" },
          ].map((a, i) => (
            <Reveal key={a.title} delay={i * 120}>
              <div className="card h-full p-6">
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl" style={{ background: `color-mix(in srgb, ${a.tone} 14%, transparent)`, color: a.tone }}><a.icon size={22} aria-hidden /></span>
                <h3 className="mt-4 text-2xl">{a.title}</h3>
                <p className="mt-1 text-ink-2">{a.text}</p>
                <Link href={a.href} className="mt-4 inline-flex items-center gap-1 font-semibold text-brand hover:underline">{a.cta} <ArrowRight size={15} aria-hidden /></Link>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

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
