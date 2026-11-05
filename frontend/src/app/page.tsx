import { ArrowRight, Check, ChevronDown, Clock, GraduationCap, HeartHandshake, Scale, ShieldCheck, Sparkles, Target } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";
import { CutoffTrace, type TracePoint } from "@/components/cutoff-trace";
import { CountUp, Reveal } from "@/components/motion";
import { SourceLink } from "@/components/ui";
import { api, type Comparison, type Completeness, type CutoffPoint, type InstitutionDetail, num, post } from "@/lib/api";

// Figures come from the API, so the page is rebuilt hourly rather than frozen at build time.
export const revalidate = 3600;

async function findProgramme(slug: string, name: string): Promise<number | null> {
  const inst = await api<InstitutionDetail>(`/institutions/${slug}`);
  return inst.programmes.find((p) => p.name === name && p.currently_offered && p.degree === "Bachelor of Technology")?.id ?? null;
}

type Trace = { points: TracePoint[]; rankList: string; sourceUrl: string };

async function loadTrace(programmeId: number | null): Promise<Trace | null> {
  if (programmeId == null) return null;
  const { records } = await api<{ records: CutoffPoint[] }>(`/programmes/${programmeId}/cutoffs?seat_type=OPEN&gender_pool=neutral&quota=OS`);
  const final = records.filter((r) => r.is_final_round && !r.is_preparatory && r.closing_rank != null).sort((a, b) => a.year - b.year);
  if (final.length < 2) return null;
  return {
    points: final.map((r) => ({ year: r.year, closing: r.closing_rank as number })),
    rankList: final[0].rank_list.replace("JEE_ADVANCED:", "JEE Advanced ").replace("JEE_MAIN:", "JEE Main "),
    sourceUrl: final.at(-1)?.source_url ?? "https://josaa.nic.in/or-cr/",
  };
}

async function loadPreview(): Promise<{ stats: Completeness; comparison: Comparison | null; trace: Trace | null } | null> {
  try {
    const stats = await api<Completeness>("/data/completeness");
    const ids = await Promise.all([
      findProgramme("iit-patna", "Civil Engineering"),
      findProgramme("nit-tiruchirappalli", "Computer Science and Engineering"),
      findProgramme("iiit-allahabad", "Electronics and Communication Engineering"),
    ]);
    const found = ids.filter((id): id is number => id != null);
    const [comparison, trace] = await Promise.all([
      found.length >= 2 ? post<Comparison>("/comparisons", { programme_ids: found }) : null,
      loadTrace(ids[1]),
    ]);
    return { stats, comparison, trace };
  } catch {
    return null;
  }
}

const AUDIENCES = [
  {
    icon: GraduationCap, tone: "var(--brand)", soft: "var(--brand-soft)", title: "For students", intro: "You’ve worked for years for this rank. Use it on a choice you understand.",
    items: [
      { q: "Which seats does my rank line up with?", href: "/onboarding" },
      { q: "Which branches lead where I want to go?", href: "/colleges" },
      { q: "What order should my JoSAA list follow?", href: "/preferences" },
    ],
  },
  {
    icon: HeartHandshake, tone: "var(--competitive)", soft: "var(--accent-soft)", title: "For parents", intro: "It’s a big family decision. You should be able to see the facts behind it, in plain language.",
    items: [
      { q: "What might it really cost us, loan included?", href: "/finance" },
      { q: "What do graduates do after college?", href: "/colleges" },
      { q: "Can we get it all explained in one report?", href: "/report" },
    ],
  },
];

const STEPS = [
  { title: "Tell us your ranks and goals", text: "Enter each rank on its own list, your Class XII state, and what you want from college. No name or phone number needed." },
  { title: "See where past cutoffs place you", text: "Each seat is compared only with cutoffs from the same rank list, quota and seat pool." },
  { title: "Weigh the options your way", text: "Change what matters to you, and watch the shortlist reorder with reasons you can check." },
];

const ANSWERS = [
  { icon: Target, q: "Can I get in?", a: "An admission band, from past cutoffs on your exact rank list.", tone: "var(--teal)" },
  { icon: ShieldCheck, q: "Is it good?", a: "A quality score, withheld until enough evidence exists.", tone: "var(--brand)" },
  { icon: Sparkles, q: "Is it right for me?", a: "A suitability score, driven by the priorities you set.", tone: "var(--accent)" },
];

const CAPABILITIES: { title: string; text: string; ready: boolean }[] = [
  { title: "Admission bands", text: "Ambitious, competitive and safer ranges from official JoSAA cutoffs since 2021.", ready: true },
  { title: "College and branch comparison", text: "Up to four options side by side, with trade-offs written out and gaps shown.", ready: true },
  { title: "Personal shortlist", text: "Rule-based and repeatable, with a reason for every result.", ready: true },
  { title: "Placement intelligence", text: "Self-reported, institute-wide outcomes from official NIRF submissions for 59 institutes, with sources. Branch-level data is still being collected.", ready: true },
  { title: "Preference list and parent report", text: "Build a JoSAA list in your own order, with warnings but no automatic changes, and save a report for your family.", ready: true },
  { title: "Faculty and academic quality", text: "Research strength and teaching information will be kept separate. Not collected yet.", ready: false },
  { title: "Alumni and career outcomes", text: "Recruiters, sectors and a labelled sample of documented alumni, where sources exist. It isn’t the full alumni network.", ready: true },
  { title: "Financial ROI", text: "Low, base and high scenarios using median salaries, never the highest package.", ready: true },
  { title: "AI counselling", text: "Will explain stored records with sources, and will not decide rankings. Not built yet.", ready: false },
];

const FAQ = [
  { q: "Is this a guarantee of admission?", a: "No. Bands describe how your rank compares with past closing ranks. Cutoffs change every year, and seats are allotted only by the counselling authority." },
  { q: "Why is there no percentage chance?", a: "Results for individual applicants are not public, so a percentage could not be properly tested. We would rather show the past cutoffs than an unsupported number." },
  { q: "Why do many options say “Data not available”?", a: "We only show placement and fee figures that have a source we can point to. So far that covers a small group of institutes, and a gap is more useful to you than a guess." },
  { q: "Which state counts as my home state?", a: "For JoSAA, it is the state where you first appeared for Class XII, not where you live or were born." },
  { q: "Can colleges pay to rank higher?", a: "No. Paid partnerships must never affect the order of results, and the scoring method is published." },
];

export default async function Home() {
  const preview = await loadPreview();
  const stats = preview?.stats;
  const coverage = stats ? [
    { label: "Official JoSAA cutoffs", value: stats.coverage.cutoffs, color: "var(--teal)" },
    { label: "Placement records, self-reported", value: stats.coverage.placements, color: "var(--brand)" },
    { label: "NIRF rank, from a secondary source", value: stats.coverage.nirf_rank, color: "var(--accent)" },
    { label: "Fee records, from official circulars", value: stats.coverage.fees, color: "var(--ambitious)" },
  ] : [];
  return (
    <div>
      <section className="hero">
        <span className="orb" style={{ width: 420, height: 420, background: "#4f46e5", top: -140, left: -80 }} aria-hidden />
        <span className="orb" style={{ width: 360, height: 360, background: "#0d9488", bottom: -160, right: "8%", animationDelay: "-6s" }} aria-hidden />
        <span className="orb" style={{ width: 240, height: 240, background: "#d97706", top: 40, right: -60, animationDelay: "-11s", opacity: 0.35 }} aria-hidden />
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 pb-16 pt-14 sm:pt-20 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <p className="rise text-sm font-semibold text-ink-2" style={{ "--i": 0 } as CSSProperties}>For JEE aspirants and their families</p>
            <h1 className="rise mt-3 text-4xl font-bold leading-[1.05] sm:text-6xl" style={{ "--i": 1 } as CSSProperties}>Your Rank Opens Doors. Make Sure You Choose the <span className="gradient-text">Right One.</span></h1>
            <p className="rise mt-5 max-w-xl text-lg text-ink-2" style={{ "--i": 2 } as CSSProperties}>Compare colleges, branches, placements, costs and career outcomes. Make your admission decision with evidence, not guesswork.</p>
            <div className="rise mt-7 flex flex-wrap gap-3" style={{ "--i": 3 } as CSSProperties}>
              <Link href="/onboarding" className="btn btn-glow !px-5 !py-3">Find My Best-Fit Colleges <ArrowRight size={17} aria-hidden /></Link>
              <Link href="/colleges" className="btn btn-ghost !px-5 !py-3">Explore Colleges</Link>
            </div>
            {stats && (
              <dl className="rise mt-10 grid max-w-xl grid-cols-3 gap-5 border-t border-line pt-6" style={{ "--i": 4 } as CSSProperties}>
                <div><dt className="text-sm text-ink-3">Official cutoff records</dt><dd className="mt-1 font-display text-2xl font-semibold sm:text-3xl"><CountUp value={stats.cutoff_records} /></dd></div>
                <div><dt className="text-sm text-ink-3">Institutes in JoSAA data</dt><dd className="mt-1 font-display text-2xl font-semibold sm:text-3xl"><CountUp value={stats.institutions} /></dd></div>
                <div><dt className="text-sm text-ink-3">Admission years</dt><dd className="tnum mt-1 whitespace-nowrap font-display text-xl font-semibold sm:text-3xl">{stats.cutoff_years[0]}–{String(stats.cutoff_years.at(-1)).slice(2)}</dd></div>
              </dl>
            )}
          </div>
          {preview?.trace && (
            <div className="rise" style={{ "--i": 3 } as CSSProperties}>
              <CutoffTrace points={preview.trace.points} institute="NIT Tiruchirappalli" programme="Computer Science and Engineering" rankList={preview.trace.rankList} quota="Other State, OPEN" sourceUrl={preview.trace.sourceUrl} />
            </div>
          )}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16">
        <Reveal>
          <p className="eyebrow">Made for the whole family</p>
          <h2 className="mt-2 max-w-2xl text-3xl sm:text-4xl">The questions you’re already asking at the dinner table</h2>
        </Reveal>
        <div className="mt-8 grid gap-5 md:grid-cols-2">
          {AUDIENCES.map((a, i) => (
            <Reveal key={a.title} delay={i * 120}>
              <div className="card card-hover h-full p-6">
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl" style={{ background: a.soft, color: a.tone }}><a.icon size={22} aria-hidden /></span>
                <h3 className="mt-4 text-2xl">{a.title}</h3>
                <p className="mt-1 text-ink-2">{a.intro}</p>
                <ul className="mt-4 divide-y divide-line">
                  {a.items.map((item) => (
                    <li key={item.q}><Link href={item.href} className="group flex items-center justify-between gap-3 py-3 font-medium hover:text-brand">{item.q}<ArrowRight size={16} className="shrink-0 transition-transform group-hover:translate-x-1" aria-hidden /></Link></li>
                  ))}
                </ul>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="border-y border-line bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-16">
          <Reveal><p className="eyebrow">How it works</p><h2 className="mt-2 text-3xl sm:text-4xl">From a rank to a decision, in three steps</h2></Reveal>
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

      <section className="mx-auto max-w-6xl px-4 py-16">
        <Reveal><p className="eyebrow">What makes it different</p><h2 className="mt-2 text-3xl sm:text-4xl">Three separate answers, never one blended score</h2></Reveal>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {ANSWERS.map((a, i) => (
            <Reveal key={a.q} delay={i * 110}>
              <div className="card card-hover h-full p-6" style={{ borderTop: `3px solid ${a.tone}` }}>
                <a.icon size={24} style={{ color: a.tone }} aria-hidden />
                <h3 className="mt-3 text-xl">{a.q}</h3>
                <p className="mt-2 text-ink-2">{a.a}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {stats && (
        <section className="mx-auto max-w-6xl px-4 pb-16">
          <Reveal>
            <div className="card grid gap-8 p-6 sm:p-8 lg:grid-cols-[1fr_1.4fr]">
              <div>
                <p className="eyebrow">Honest coverage</p>
                <h2 className="mt-2 text-3xl">What we have, and what we don’t</h2>
                <p className="mt-3 text-ink-2">Every institute has official cutoffs. The rest is still patchy, and we’d rather show you the gap than fill it with a guess.</p>
                <p className="mt-3 text-sm text-ink-3">Not collected yet: {stats.not_yet_collected.join(", ")}.</p>
              </div>
              <ul className="space-y-4 self-center">
                {coverage.map((c, i) => (
                  <li key={c.label}>
                    <div className="flex justify-between gap-3 text-sm"><span>{c.label}</span><span className="tnum shrink-0 font-semibold">{c.value} of {stats.institutions} institutes</span></div>
                    <div className="mt-1.5 h-2.5 overflow-hidden rounded-full bg-surface-2" role="img" aria-label={`${c.value} of ${stats.institutions} institutes`}>
                      <div className="grow-x h-full rounded-full" style={{ width: `${(c.value / stats.institutions) * 100}%`, background: c.color, "--delay": `${200 + i * 130}ms` } as CSSProperties} />
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
        </section>
      )}

      {preview?.comparison && (
        <section className="border-y border-line bg-surface">
          <div className="mx-auto max-w-6xl px-4 py-16">
            <Reveal>
              <p className="eyebrow"><Scale size={14} className="mr-1 inline" aria-hidden />Side by side</p>
              <h2 className="mt-2 text-3xl sm:text-4xl">An IIT, an NIT and an IIIT, compared</h2>
              <p className="mt-2 max-w-2xl text-ink-2">Real records from our database. The most prestigious name is not automatically the right decision, so the differences are set out for you to weigh.</p>
              <div className="card mt-6 overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead><tr className="border-b border-line text-ink-3">
                    <th scope="col" className="p-4 font-medium">Option</th>
                    <th scope="col" className="p-4 font-medium">Final-round closing rank (OPEN, gender-neutral)</th>
                    <th scope="col" className="p-4 font-medium">Rank list</th>
                    <th scope="col" className="p-4 font-medium">Placements</th>
                  </tr></thead>
                  <tbody>
                    {preview.comparison.items.map((item) => (
                      <tr key={item.programme_id} className="border-b border-line transition-colors last:border-0 hover:bg-surface-2">
                        <td className="p-4"><Link href={`/programmes/${item.programme_id}`} className="font-semibold hover:text-brand">{item.institution.short_name}</Link><p className="text-ink-2">{item.programme}</p></td>
                        <td className="tnum p-4">{item.reference_cutoff ? <><span className="font-semibold">{num(item.reference_cutoff.closing_rank)}</span> <span className="text-ink-3">({item.reference_cutoff.quota}, {item.reference_cutoff.year})</span></> : "Data not available"}</td>
                        <td className="p-4 text-ink-2">{item.reference_cutoff?.rank_list.replace("JEE_ADVANCED:", "JEE Advanced ").replace("JEE_MAIN:", "JEE Main ") ?? "—"}</td>
                        <td className="p-4 text-ink-3">{item.placements.length ? "See comparison" : "Data not available"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-sm text-ink-3">JEE Advanced and JEE Main ranks are on different lists, so these numbers cannot be compared directly. <SourceLink href="https://josaa.nic.in/or-cr/" label="Source: JoSAA" /></p>
            </Reveal>
          </div>
        </section>
      )}

      <section className="mx-auto max-w-6xl px-4 py-16">
        <Reveal><p className="eyebrow">Where it stands</p><h2 className="mt-2 text-3xl sm:text-4xl">What works today, and what doesn’t yet</h2></Reveal>
        <ul className="mt-8 grid gap-4 md:grid-cols-2">
          {CAPABILITIES.map((c, i) => (
            <li key={c.title}>
              <Reveal delay={(i % 2) * 90} className="h-full">
                <div className="card flex h-full gap-3 p-4">
                  <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full" style={{ background: c.ready ? "var(--safer-soft)" : "var(--neutral-soft)", color: c.ready ? "var(--safer)" : "var(--ink-3)" }}>
                    {c.ready ? <Check size={15} aria-label="Available" /> : <Clock size={15} aria-label="In development" />}
                  </span>
                  <div><h3 className="text-lg">{c.title}</h3><p className="text-sm text-ink-2">{c.text}</p></div>
                </div>
              </Reveal>
            </li>
          ))}
        </ul>
      </section>

      <section className="mx-auto max-w-3xl px-4 pb-16">
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
        <p className="mt-5 text-sm text-ink-3"><Link href="/methodology" className="underline underline-offset-2 hover:text-brand">Read the full methodology and source list</Link></p>
      </section>

      <section className="hero no-print">
        <span className="orb" style={{ width: 340, height: 340, background: "#4f46e5", top: -120, right: "10%" }} aria-hidden />
        <div className="mx-auto max-w-3xl px-4 py-16 text-center">
          <Reveal>
            <h2 className="text-3xl font-bold sm:text-4xl">Sit down together. See the evidence. Decide with confidence.</h2>
            <p className="mt-3 text-ink-2">It takes a few minutes. We don’t ask for your name or contact details.</p>
            <Link href="/onboarding" className="btn btn-glow mt-6 !px-6 !py-3">Find My Best-Fit Colleges <ArrowRight size={17} aria-hidden /></Link>
          </Reveal>
        </div>
      </section>
    </div>
  );
}
