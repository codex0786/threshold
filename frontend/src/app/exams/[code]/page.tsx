"use client";
import { ArrowLeft, ChevronDown, ExternalLink, Info } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { type CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BandBadge, Notice, PageHeader, Skeleton, SourceLink } from "@/components/ui";
import { api, inr, num } from "@/lib/api";
import {
  CATEGORY_GUIDES, categoryFor, categoryGroups, EXAM_ICONS, type ExamAnswers, type ExamMetric, type ExamOption, type ExamProfile, type ExamRoute, type ExamShortlist, examDefaults, formatFigure,
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

const lakh = (value: number) => `₹${(value / 100000).toLocaleString("en-IN", { maximumFractionDigits: 2 })} lakh`;

// The latest year that has a median, so the card can show one line of evidence.
function latestOutcome(profile: ExamProfile | null | undefined) {
  return [...(profile?.outcomes?.years ?? [])].reverse().find((y) => y.median_salary_inr != null) ?? profile?.outcomes?.years.at(-1) ?? null;
}

function Outcomes({ outcomes }: { outcomes: NonNullable<ExamProfile["outcomes"]> }) {
  return (
    <div>
      <h3 className="text-base font-medium">Placements and higher studies</h3>
      <p className="mt-0.5 text-xs text-ink-3">{outcomes.note}</p>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[420px] text-left text-sm">
          <thead><tr className="border-b border-line text-xs text-ink-3">
            <th scope="col" className="py-1 pr-3 font-medium">Graduating year</th><th scope="col" className="py-1 pr-3 font-medium">Graduated</th>
            <th scope="col" className="py-1 pr-3 font-medium">Placed</th><th scope="col" className="py-1 pr-3 font-medium">Median salary</th><th scope="col" className="py-1 font-medium">Higher studies</th>
          </tr></thead>
          <tbody className="tnum">
            {outcomes.years.map((y) => (
              <tr key={y.academic_year} className="border-b border-line last:border-0">
                <td className="py-1 pr-3">{y.academic_year}</td><td className="py-1 pr-3">{num(y.graduating_students)}</td><td className="py-1 pr-3">{num(y.students_placed)}</td>
                <td className="py-1 pr-3">{y.median_salary_inr != null ? inr(y.median_salary_inr) : "Not shown"}</td><td className="py-1">{num(y.higher_studies_students)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {outcomes.years.flatMap((y) => y.notes.map((n) => <p key={n} className="mt-1 text-xs text-ink-3">{y.academic_year}: {n}.</p>))}
      {outcomes.excluded.map((e) => <p key={e.academic_year} className="mt-1 text-xs text-ink-3">{e.academic_year} left out: {e.reason}</p>)}
      {outcomes.year_note && <p className="mt-1 text-xs text-ink-3">{outcomes.year_note}</p>}
      <p className="mt-1"><SourceLink href={outcomes.source_url} label={outcomes.source_title} /></p>
    </div>
  );
}

function Faculty({ faculty, medical }: { faculty: NonNullable<ExamProfile["faculty"]>; medical: boolean }) {
  const years = Object.entries(faculty.research_years).filter(([, v]) => v.sponsored_amount_inr != null || v.phd_graduated != null).slice(-3);
  return (
    <div>
      <h3 className="text-base font-medium">Faculty and research</h3>
      <p className="mt-0.5 text-xs text-ink-3">{faculty.note}</p>
      <dl className="tnum mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        {faculty.regular != null && <div><dt className="text-xs text-ink-3">Regular faculty</dt><dd>{num(faculty.regular)}{faculty.current != null && faculty.current > faculty.regular ? ` of ${num(faculty.current)} working` : ""}</dd></div>}
        {!medical && faculty.with_phd != null && faculty.regular ? <div><dt className="text-xs text-ink-3">With a doctorate</dt><dd>{num(faculty.with_phd)} ({Math.round((faculty.with_phd / faculty.regular) * 100)}%)</dd></div> : null}
        {faculty.students_per_regular_faculty != null && <div><dt className="text-xs text-ink-3">Students per regular faculty member</dt><dd>{faculty.students_per_regular_faculty}</dd></div>}
        {faculty.median_experience_years != null && <div><dt className="text-xs text-ink-3">Median experience</dt><dd>{faculty.median_experience_years} years</dd></div>}
        {faculty.professors != null && <div><dt className="text-xs text-ink-3">Professors, associate, assistant</dt><dd>{num(faculty.professors)}, {num(faculty.associate)}, {num(faculty.assistant)}</dd></div>}
        {faculty.phd_students != null && <div><dt className="text-xs text-ink-3">PhD scholars</dt><dd>{num(faculty.phd_students)}</dd></div>}
      </dl>
      {years.length > 0 && (
        <ul className="tnum mt-2 space-y-0.5 text-sm text-ink-2">
          {years.map(([year, v]) => <li key={year}>{year}: {[v.sponsored_amount_inr != null ? `${inr(v.sponsored_amount_inr)} in sponsored research` : null, v.phd_graduated != null ? `${num(v.phd_graduated)} PhDs awarded` : null].filter(Boolean).join(", ")}</li>)}
        </ul>
      )}
      <p className="mt-1"><SourceLink href={faculty.source_url} label={faculty.source_title} /></p>
    </div>
  );
}

function Alumni({ alumni }: { alumni: NonNullable<ExamProfile["alumni"]> }) {
  return (
    <div>
      <h3 className="text-base font-medium">Documented alumni (a sample)</h3>
      <p className="mt-0.5 text-xs text-ink-3">{alumni.caveat}</p>
      <p className="tnum mt-1 text-sm">{num(alumni.sample_size)} people in the sample.{alumni.occupations.length ? ` Commonest occupations: ${alumni.occupations.slice(0, 5).map((o) => `${o.label} (${o.people})`).join(", ")}.` : ""}</p>
      {alumni.employers.length > 0 && <p className="tnum mt-1 text-sm">Employers named: {alumni.employers.slice(0, 5).map((o) => `${o.label} (${o.people})`).join(", ")}.</p>}
      <p className="mt-1"><SourceLink href={alumni.source_url} label={alumni.source_title} /></p>
    </div>
  );
}

function Elsewhere({ items, unit, year, onPick }: { items: { quota: string; programme: string; seats: number }[]; unit: string; year: string; onPick: (quota: string, programme: string) => void }) {
  return (
    <section className="card mt-4 p-4" aria-label="Where your figure reached seats">
      <h3 className="text-base font-medium">Where your {unit} reached seats in {year}</h3>
      <p className="mt-0.5 text-xs text-ink-3">Same category, other quotas and courses. Check you qualify for a quota before relying on it.</p>
      <ul className="mt-3 flex flex-wrap gap-2">
        {items.map((item) => (
          <li key={`${item.quota}|${item.programme}`}>
            <button type="button" onClick={() => onPick(item.quota, item.programme)} className="rounded-full border border-line bg-surface px-3 py-1.5 text-left text-sm hover:border-brand hover:text-brand">
              <span className="font-medium">{item.programme}</span> · {item.quota} <span className="tnum text-ink-3">({item.seats} {item.seats === 1 ? "seat" : "seats"})</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function StateCategories({ items, unit, year, onPick }: { items: { state: string; category: string; seats: number }[]; unit: string; year: string; onPick: (state: string, category: string) => void }) {
  return (
    <section className="card mt-4 p-4" aria-label="State domicile categories that reached your figure">
      <h3 className="text-base font-medium">If you hold a state domicile</h3>
      <p className="mt-0.5 text-xs text-ink-3">Your {unit} reached seats in {year} under these state categories. Only candidates with that state&rsquo;s domicile can use them, at its own university.</p>
      <ul className="mt-3 flex flex-wrap gap-2">
        {items.map((item) => (
          <li key={item.category}>
            <button type="button" onClick={() => onPick(item.state, item.category)} className="rounded-full border border-line bg-surface px-3 py-1.5 text-left text-sm hover:border-brand hover:text-brand">
              <span className="font-medium">{item.state}</span> · {item.category} <span className="tnum text-ink-3">({item.seats} {item.seats === 1 ? "seat" : "seats"})</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function HistoryNote({ history, hasMerit }: { history: NonNullable<ExamRoute["history"]>; hasMerit: boolean }) {
  const weakest = Object.entries(history.backtest).map(([year, groups]) => [year, groups["All seats"]?.safer ?? 100] as const).sort((a, b) => a[1] - b[1])[0];
  const tests = Object.entries(history.backtest).sort(([a], [b]) => a.localeCompare(b));
  const margin = history.margin;
  const figure = margin ? "score" : history.uses === "second_value" ? "merit number" : "rank";
  return (
    <Notice>
      {margin ? (
        <p>
          Each seat also has a band from its closing scores in {history.years.slice(-3).join(", ")}: Safer is at least {margin} points above every recent closing score,
          Competitive is within the recent range, and Ambitious is up to {margin} points below it. {history.basis}
        </p>
      ) : (
        <p>
          Each seat also has a band from its closing {history.uses === "second_value" ? "state merit numbers" : "ranks"} in {history.years.slice(-3).join(", ")}, using the same rule as JEE: Safer is at least 10% inside every recent closing {figure},
          Competitive is within the recent range, and Ambitious is up to 20% beyond it. {history.basis}
        </p>
      )}
      <p className="mt-1">
        How well the rule held when tested on the next year, for a {figure} exactly at the Safer edge:{" "}
        {tests.map(([year, groups]) => {
          const named = Object.keys(groups).find((g) => g !== "All seats" && g !== "Other seats");
          return `${year}: ${groups["All seats"]?.safer}% of seats${named ? ` (${groups[named]?.safer}% for ${named})` : ""}`;
        }).join("; ")}.
        {weakest && weakest[1] < 85 ? ` In ${weakest[0]} many seats closed earlier than in the years before, so treat Safer with more care.` : ""}
        {history.uses === "second_value" && !hasMerit ? " Add your state merit number to see each seat’s band." : ""}
        {" "}This describes past seats, not your chance of admission.
      </p>
    </Notice>
  );
}

function OptionCard({ option, route, figure, labels, index }: { option: ExamOption; route: ExamRoute; figure: number; labels: ExamShortlist["positions"]; index: number }) {
  const [open, setOpen] = useState(false);
  const style = POSITION_STYLE[option.position] ?? POSITION_STYLE.near;
  const label = labels[option.position] ?? { label: option.position, hint: "" };
  const name = option.institute_short ?? option.institution?.short_name ?? option.institute;
  const fee = headlineFee(option);
  const academics = option.institution?.academics;
  const missing = [
    ...(option.ranking ? [] : [`Not in NIRF 2025’s ${route.stream} list, so ordered as neutral. That doesn’t mean it’s weaker.`]),
    ...(route.stream === "Medical" && !option.fee ? ["No fee document collected for this seat. Check the counselling authority’s fee list."] : []),
  ];
  const lastCount = [...option.rounds].reverse().find((s) => s.count != null)?.count;
  const profile = option.profile;
  const outcome = latestOutcome(profile);
  if (!profile?.outcomes) missing.push(route.stream === "Medical" ? "Graduate outcomes, such as postgraduate seats or jobs, aren’t collected for this college." : route.code === "gate-ccmt" ? "M.Tech placement figures aren’t collected yet." : "No placement figures found for this institute.");
  if (!profile?.faculty && !academics) missing.push("No faculty or research figures found for this institute.");
  if (!profile?.website) missing.push("No official website on record yet.");
  if (!profile?.alumni) missing.push("No documented alumni sample of 30 or more people.");
  return (
    <article className="card card-hover band-card rise p-5 pl-6" style={{ "--band": style.color, "--i": Math.min(index, 10) } as CSSProperties}>
      <div className="flex flex-wrap items-center gap-2">
        <PositionBadge position={option.position} label={label.label} hint={label.hint} />
        {option.history && !option.history.needs && <BandBadge band={option.history.band ?? "limited_history"} />}
        {option.female_only && <span className="rounded-full px-2 py-0.5 text-xs font-semibold" style={{ background: "var(--competitive-soft)", color: "var(--competitive)" }}>Female candidates only</span>}
        <span className="text-xs text-ink-3">{[option.institution ? `${option.institution.type} · ${option.institution.state}` : null, option.quota, option.category].filter(Boolean).join(" · ")}</span>
      </div>
      <h2 className="mt-2 text-xl">{option.programme}</h2>
      <p className="text-ink-2">
        {option.institution ? <Link href={`/colleges/${option.institution.slug}`} className="hover:underline">{name}</Link> : name}
        {option.programme_code ? <span className="text-ink-3"> · course code {option.programme_code}</span> : null}
      </p>
      {name !== option.institute && <p className="text-xs text-ink-3">{option.institute.replace(/\s*\(Female Seat only\s*\)/, "")}</p>}
      {profile?.website && (
        <a href={profile.website.url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-sm text-brand hover:underline" title={`Address from: ${profile.website.source_title}`}>
          {profile.website.status === "official" ? "Official website" : "Website, confirmed"} <ExternalLink size={12} aria-hidden />
        </a>
      )}

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
          {(profile?.other_rankings?.length ?? 0) > 0 && (
            <p className="tnum mt-1 text-xs text-ink-2" title={`${profile?.other_rankings?.[0].name}. ${profile?.other_rankings?.[0].note}`}>
              Also NIRF {profile?.other_rankings?.map((r) => `${r.category} #${r.rank}`).join(", ")}
              <span className="text-ink-3"> ({profile?.other_rankings?.[0].name}, whole institution)</span>
            </p>
          )}
        </div>
        <div>
          <p className="text-xs text-ink-3">{route.stream === "Medical" ? "Fees" : route.stream === "Law" ? (outcome ? `Placements, ${outcome.academic_year} graduates` : "Seats") : "Faculty (whole institute)"}</p>
          {route.stream === "Medical" && (fee
            ? <><p className="mt-1 text-sm font-medium break-words">{fee}</p><p className="text-xs" style={{ color: option.fee?.status === "official" ? "var(--safer)" : "var(--competitive)" }}>{option.fee?.status === "official" ? "Official, as printed" : "Declared by the college, unverified"}</p></>
            : <p className="mt-1 text-sm text-ink-3">Data not available</p>)}
          {route.stream === "Law" && (outcome
            ? <><p className="tnum mt-1 text-sm font-medium">{outcome.median_salary_inr != null ? `Median ${lakh(outcome.median_salary_inr)}` : "Median not shown"}</p><p className="tnum text-xs text-ink-3">{num(outcome.students_placed)} of {num(outcome.graduating_students)} placed, {num(outcome.higher_studies_students)} to higher studies. Self-reported to NIRF</p></>
            : option.seats != null ? <p className="tnum mt-1 text-sm font-medium">{num(option.seats)} seats in this category</p> : <p className="mt-1 text-sm text-ink-3">Data not available</p>)}
          {route.stream === "Law" && outcome && option.seats != null && <p className="tnum mt-1 text-xs text-ink-3">{num(option.seats)} seats in this category</p>}
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
            {option.history && (
              <div>
                <h3 className="text-base font-medium">Across recent years</h3>
                <p className="mt-1 text-sm text-ink-2">{option.history.explanation}</p>
                <p className="tnum mt-1 text-xs text-ink-3">{route.history?.margin ? "Lowest score admitted in rounds 1 to 3" : route.history?.uses === "second_value" ? "Worst merit number admitted in CAP rounds I to III" : "Last rank allotted in rounds 1 to 3"}: {Object.entries(option.history.closing).map(([y, r]) => `${y}: ${num(r)}`).join(" · ")}</p>
              </div>
            )}
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
            {profile?.outcomes && <Outcomes outcomes={profile.outcomes} />}
            {profile?.faculty && <Faculty faculty={profile.faculty} medical={route.stream === "Medical"} />}
            {profile?.alumni && <Alumni alumni={profile.alumni} />}
            {!profile?.faculty && academics && (
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
    const merit = (a.merit ?? "").replace(/[,\s]/g, "");
    const params = new URLSearchParams(Object.entries({ value: String(figure), category: a.category, quota: a.quota, programme: a.programme, gender: a.gender, order: listOrder, merit: /^\d+$/.test(merit) && Number(merit) > 0 ? merit : "" }).filter(([, v]) => v));
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
      // Answers saved before categories were matched to quotas may hold a pair that can never match.
      start.category = categoryFor(found, start.quota, start.category);
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
  const forQuota = route.quota_categories?.[answers.quota];
  const categories = route.categories.filter((c) => (!route.category_states?.[c] || route.category_states[c] === answers.domicile || c === answers.category) && (!forQuota || forQuota.includes(c)));
  const total = result ? Object.values(result.counts).reduce((a, c) => a + c, 0) : 0;
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <Link href="/exams" className="mb-3 inline-flex items-center gap-1 text-sm text-ink-2 hover:text-brand"><ArrowLeft size={15} aria-hidden /> All exams</Link>
      <PageHeader title={`Your ${route.name} shortlist`} intro={route.rounds?.length
        ? route.history
          ? <>Compared with {route.authority}’s figures from {route.history.years[0]} to {route.history.years.at(-1)}. Each seat shows a band from the last three years, as on JEE, and the {route.document.year} round in which it reached your {route.metric.unit}.</>
          : <>Compared with {route.authority}’s {route.document.year} figures, round by round. One year of figures can’t support admission bands, so each seat shows the round in which it reached your {route.metric.unit}.</>
        : <>Compared with {route.authority}’s {route.document.year} cut-offs. One year of figures can’t support admission bands, so each seat shows whether its cut-off reached your {route.metric.unit}.</>} />
      {route.list_tools && (
        <div className="mb-6 -mt-2 flex flex-wrap items-center gap-3">
          <Link href={`/exams/${route.code}/list`} className="btn btn-primary">Build my choice list</Link>
          <span className="text-sm text-ink-3">An order for choice filling, and what to do after each round’s allotment.</span>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <form className="card space-y-3 p-4" onSubmit={(e) => { e.preventDefault(); submit(); }}>
            <h2 className="flex items-center gap-2 text-lg">{Icon && <Icon size={17} className="text-brand" aria-hidden />} Your details</h2>
            <label className="block text-sm">Your {route.metric.label}
              <input className="input tnum mt-1" inputMode="decimal" value={answers.value} onChange={(e) => set({ value: e.target.value.trim() })} aria-invalid={Boolean(problem)} placeholder={route.metric.lower_is_better ? "e.g. 25,000" : route.metric.max === 100 ? "e.g. 95.5" : "e.g. 600"} />
            </label>
            {problem && <p className="text-sm" style={{ color: "var(--ambitious)" }} role="alert">{problem}</p>}
            {route.history?.uses === "second_value" && (
              <label className="block text-sm">Your state merit number <span className="text-ink-3">(optional)</span>
                <input className="input tnum mt-1" inputMode="numeric" value={answers.merit ?? ""} onChange={(e) => set({ merit: e.target.value.trim() })} placeholder="e.g. 25,000" />
                <span className="mt-1 block text-xs text-ink-3">From the CET Cell’s merit list. Bands use it, because closing percentiles have risen every year while merit numbers stayed comparable.</span>
              </label>
            )}
            {route.category_states && (
              <label className="block text-sm">Your domicile state
                <select className="input mt-1" value={answers.domicile} onChange={(e) => set({ domicile: e.target.value })}>
                  <option value="">Not chosen</option>{[...new Set(Object.values(route.category_states))].sort().map((s) => <option key={s}>{s}</option>)}
                </select>
              </label>
            )}
            <label className="block text-sm">Category, as published
              <select className="input mt-1" value={answers.category} onChange={(e) => set({ category: e.target.value })}>
                <option value="">Choose</option>
                {categoryGroups(route, categories).map((g) => g.label
                  ? <optgroup key={g.label} label={g.label}>{g.options.map((c) => <option key={c}>{c}</option>)}</optgroup>
                  : g.options.map((c) => <option key={c}>{c}</option>))}
              </select>
            {CATEGORY_GUIDES[route.code] && <span className="mt-1 block text-xs text-ink-3">{CATEGORY_GUIDES[route.code]}</span>}
              </label>
            {(route.quotas?.length ?? 0) > 1 && (
              <label className="block text-sm">Quota or section
                <select className="input mt-1" value={answers.quota} onChange={(e) => set({ quota: e.target.value, category: categoryFor(route, e.target.value, answers.category) })}>
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
                <p className="mt-1.5 text-xs text-ink-3">{order === "top" && route.standing_basis === "contest" ? "The most sought-after seats come first: few colleges here have an NIRF rank, so the order is how high each seat's closing figure was. This isn’t a quality score." : ORDERS[order].note}</p>
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
              {route.history && total > 0 && <HistoryNote history={route.history} hasMerit={/^\d+$/.test((answers.merit ?? "").replace(/[,\s]/g, ""))} />}
              <p className="mb-3 text-sm text-ink-3">
                {result.beyond > 0 ? `Not shown: ${num(result.beyond)} ${result.beyond === 1 ? "seat" : "seats"} in this list that didn’t reach your ${route.metric.unit}${route.rounds?.length ? " in any round" : ""}${route.metric.lower_is_better ? " or come within 20% of it" : route.history?.margin ? ` or come within ${route.history.margin} points of it` : ""}. ` : ""}
                {result.hidden_female_only > 0 ? `Seats only female candidates may hold are hidden, because you chose ${answers.gender}. ` : ""}
                {result.limit && Object.values(result.counts).some((c) => c > (result.limit ?? 0)) ? `Each group shows its first ${result.limit} in this order.` : ""}
              </p>
              {!answers.gender && route.asks_gender && result.options.some((o) => o.female_only) && <p className="mb-3 text-xs text-ink-3">Some seats are for female candidates only, and are labelled. Choose your gender to see only seats you can hold.</p>}
              <div className={`space-y-4 transition-opacity ${loading ? "opacity-60" : ""}`}>
                {shown.map((o, i) => <OptionCard key={`${o.institute}|${o.programme_code ?? o.programme}|${o.quota}`} option={o} route={route} figure={asked} labels={result.positions} index={i} />)}
              </div>
              {total === 0 && (
                <Notice>
                  No seat in {[answers.quota, answers.programme].filter(Boolean).join(", ") || "this list"} reached{route.metric.lower_is_better ? " or came within 20% of" : route.history?.margin ? ` or came within ${route.history.margin} points of` : ""} your {route.metric.unit} in {route.document.year}.
                  {result.elsewhere?.length || result.state_categories?.length ? " Your figure did reach seats in the lists below." : " Check your figure and category. Other counselling routes, such as your state’s, may still have seats."}
                </Notice>
              )}
              {!!result.elsewhere?.length && (
                <Elsewhere items={result.elsewhere} unit={route.metric.unit} year={route.document.year} onPick={(q, p) => {
                  const next = { ...answers, quota: q, programme: route.programmes.includes(p) ? p : "", category: categoryFor(route, q, answers.category) };
                  setAnswers(next); saveExamAnswers(route.code, next); reveal.current = true; run(route, next, order);
                }} />
              )}
              {!!result.state_categories?.length && (
                <StateCategories items={result.state_categories} unit={route.metric.unit} year={route.document.year} onPick={(state, category) => {
                  const next = { ...answers, domicile: state, category };
                  setAnswers(next); saveExamAnswers(route.code, next); reveal.current = true; run(route, next, order);
                }} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
