// Shared types and helpers for exam routes beyond JEE.
import type { Band } from "@/lib/api";
import { Scale, Stethoscope, Wrench } from "lucide-react";

export type ExamMetric = { label: string; unit: string; lower_is_better: boolean; whole_number?: boolean; max?: number; value_label: string; second_label: string | null };
export type ExamDoc = { title: string; url: string; year: string; round: string; retrieved: string; status: "official" | "derived" };
export type ExamRoute = {
  code: string; stream: string; level: string; name: string; authority: string; metric: ExamMetric; document: ExamDoc; limits: string[];
  record_count: number; institute_count: number; categories: string[]; groups: string[]; programmes: string[]; compare_requires_group?: boolean;
  sources?: { title: string; url: string }[]; asks_gender?: boolean;
  group_requirements?: Record<string, string>; category_states?: Record<string, string>;
  rounds?: string[]; default_group?: string; default_programme?: string;
  quota_categories?: Record<string, string[]>; standing_basis?: string | null; list_tools?: boolean;
  history?: { years: number[]; basis: string; uses?: string | null; margin?: number | null; backtest: Record<string, Record<string, { seats: number; safer: number; competitive: number; ambitious: number }>> } | null;
  quotas?: string[]; quota_requirements?: Record<string, string>; ranked_institute_count?: number; fee_institute_count?: number;
};
export type ExamRanking = { category: string; rank: number; year: number; source_url: string };
export type DeclaredFee = { title: string; note: string; declared: { label: string; value: string }[]; source_url: string; year: string; status: string };

export type RoundStep = { round: string | null; value: number | null; second_value: number | null; count: number | null; reached: boolean };
export type ExamAcademics = { students_per_regular_faculty: number | null; phd_share: number | null; faculty_regular: number | null; source: { title: string; url: string; submission_year: number } | null } | null;
type ProfileSource = { source_title: string; source_url: string; status: string; retrieved?: string; nirf_id?: string | null };
export type OutcomeYear = { academic_year: string; graduating_students: number | null; students_placed: number | null; median_salary_inr: number | null; higher_studies_students: number | null; notes: string[] };
export type ExamProfile = {
  website?: { url: string; note: string | null } & ProfileSource;
  outcomes?: { programme: string; years: OutcomeYear[]; excluded: { academic_year: string; reason: string }[]; note: string; year_note: string | null } & ProfileSource;
  faculty?: {
    regular: number | null; with_phd: number | null; listed: number | null; current: number | null; professors: number | null; associate: number | null; assistant: number | null;
    median_experience_years: number | null; students_total: number | null; phd_students: number | null; students_per_regular_faculty: number | null;
    research_years: Record<string, { sponsored_projects?: number | null; sponsored_amount_inr?: number | null; consultancy_amount_inr?: number | null; phd_graduated?: number | null }>;
    note: string;
  } & ProfileSource;
  alumni?: { sample_size: number; occupations: { label: string; people: number }[]; employers: { label: string; people: number }[]; caveat: string } & ProfileSource;
  fee?: DeclaredFee;
  other_rankings?: { category: string; rank: number; year: number; name: string; source_url: string; note: string }[];
};
export type ExamOption = {
  profile?: ExamProfile | null;
  institute: string; institute_short: string | null; programme: string; programme_code: string | null; quota: string | null; category: string;
  female_only: boolean; seats: number | null; note: string | null; position: string; rounds: RoundStep[]; furthest: number;
  ranking: ExamRanking | null; fee: DeclaredFee | null; standing: number; why: string[];
  history?: { band: Band; explanation: string; years: number[]; closing: Record<string, number>; needs?: string } | null;
  institution?: { slug: string; short_name: string; type: string; state: string; academics: ExamAcademics } | null;
};
export type ExamShortlist = {
  missing: string[]; positions: Record<string, { label: string; hint: string }>; counts: Record<string, number>; options: ExamOption[];
  beyond: number; hidden_female_only: number; limit?: number;
  elsewhere?: { quota: string; programme: string; seats: number }[]; state_categories?: { state: string; category: string; seats: number }[]; standing_basis?: string | null;
};

// The first view shows one clear list: the open category, and the route's own default quota and course.
// KEA's general merit category is GM.
export const OPEN_CATEGORIES = ["Open", "OPEN", "General (General)", "GOPENS", "GM", "OPNO"];
export const EXAM_ICONS: Record<string, typeof Wrench> = { Medical: Stethoscope, Law: Scale, Engineering: Wrench };

// Colours follow the JEE bands, so the order of strength reads the same across the site.
export const POSITION_STYLE: Record<string, { color: string; bg: string }> = {
  first_round: { color: "var(--safer)", bg: "var(--safer-soft)" },
  reached: { color: "var(--safer)", bg: "var(--safer-soft)" },
  later_round: { color: "var(--competitive)", bg: "var(--competitive-soft)" },
  leftover_round: { color: "var(--ambitious)", bg: "var(--ambitious-soft)" },
  near: { color: "var(--ink-2)", bg: "var(--neutral-soft)" },
};
export const POSITION_ORDER = ["first_round", "reached", "later_round", "leftover_round", "near"];

export const baseQuota = (group: string) => (group.includes(" · ") ? group.slice(0, group.lastIndexOf(" · ")) : group);

export function examDefaults(route: ExamRoute) {
  const quotas = route.quotas ?? [];
  const wanted = route.default_group ? baseQuota(route.default_group) : "";
  return {
    category: OPEN_CATEGORIES.find((c) => route.categories.includes(c)) ?? "",
    quota: route.compare_requires_group ? ([wanted, "All India"].find((q) => q && quotas.includes(q)) ?? quotas[0] ?? "") : "",
    programme: [route.default_programme, "MBBS"].find((p) => p && route.programmes.includes(p)) ?? "",
  };
}

// Short round names for the round ladder, such as "R1" or "Stray".
export function shortRound(round: string | null): string {
  if (!round) return "Cut-off";
  const cap = round.match(/CAP Round ([IVX]+)/);
  if (cap) return `CAP ${cap[1]}`;
  const special = round.match(/Special Round (\d)/);
  if (special) return `Special ${special[1]}`;
  if (/spot/i.test(round)) return "Spot";
  if (/special stray/i.test(round)) return "Special stray";
  if (/stray/i.test(round)) return "Stray";
  const n = round.match(/Round (\d)/);
  return n ? `R${n[1]}${/provisional/i.test(round) ? " (prov.)" : ""}` : round;
}

export function formatFigure(value: number, metric: ExamMetric): string {
  if (metric.whole_number || Number.isInteger(value)) return value.toLocaleString("en-IN");
  return String(value);
}

export type ExamAnswers = { value: string; category: string; quota: string; programme: string; gender: string; domicile: string; merit?: string };
const key = (code: string) => `threshold.exam.${code}.v1`;
export function loadExamAnswers(code: string): ExamAnswers | null {
  try {
    const raw = window.localStorage.getItem(key(code));
    return raw ? (JSON.parse(raw) as ExamAnswers) : null;
  } catch {
    return null;
  }
}
export function saveExamAnswers(code: string, answers: ExamAnswers) {
  try {
    window.localStorage.setItem(key(code), JSON.stringify(answers));
  } catch {
    // Storage can be blocked. The page still works for this visit.
  }
}

// Short guides to category codes that aren't self-explanatory, shown under the category menu.
const KEA_GUIDE = "Codes as KEA prints them. GM is General Merit; 1, 2A, 2B, 3A and 3B are Karnataka's backward-class categories, and SC and ST follow the same pattern. The next letter is G (general), K (Kannada medium) or R (rural), and a final H means the Hyderabad-Karnataka (Article 371(J)) quota: 2AKH is 2A, Kannada medium, Hyderabad-Karnataka. Other codes are KEA's special and minority categories; check KEA's information bulletin before choosing one.";

export const CATEGORY_GUIDES: Record<string, string> = {
  "kcet-engineering": KEA_GUIDE,
  uptac: "Codes as UPTAC prints them. The first part is the category: OP open, BC OBC from UP, SC, ST and EWS from UP. The rest is the sub-category: NO none, GL female (given to every female UP candidate), FF dependants of freedom fighters, AF armed forces, PH Divyangjan. TFW is the tuition fee waiver scheme. Pick OPNO if none applies.",
  "karnataka-neet": KEA_GUIDE,
  clat: "National categories apply to everyone. State categories appear once you choose your domicile state, and only universities in that state use them.",
  "maharashtra-engineering": "Codes as the CET Cell prints them: G is general and L is ladies (women only), then the category (OPEN, OBC, SC and so on), then where the seat sits: H home university, O other than home university, S state level. Only codes that exist for the chosen quota are listed.",
};

// Common national categories first, in the order counselling bodies usually list them.
const NATIONAL_ORDER = [/^General\b/, /^Economically Weaker/, /^Other Backward Class \(OBC\)/, /^Scheduled Caste \(SC\)/, /^Scheduled Tribe \(ST\)/, /^Person With Disability \(PWD\)/, /^PWD /, /^Women/];
const nationalRank = (c: string) => { const i = NATIONAL_ORDER.findIndex((r) => r.test(c)); return i < 0 ? NATIONAL_ORDER.length : i; };

/** Categories split into menu groups: national ones first, then one group per state. Routes without state categories get one group. */
export function categoryGroups(route: ExamRoute, categories: string[]): { label: string | null; options: string[] }[] {
  const states = route.category_states;
  if (!states) return [{ label: null, options: categories }];
  const national = categories.filter((c) => !states[c]).sort((a, b) => nationalRank(a) - nationalRank(b) || a.localeCompare(b));
  const byState = new Map<string, string[]>();
  for (const c of categories.filter((c) => states[c])) byState.set(states[c], [...(byState.get(states[c]) ?? []), c]);
  return [
    { label: "National categories", options: national },
    ...[...byState.keys()].sort().map((s) => ({ label: `${s} categories`, options: byState.get(s)!.sort((a, b) => nationalRank(a) - nationalRank(b) || a.localeCompare(b)) })),
  ].filter((g) => g.options.length);
}

/** The category to keep when the quota changes: the current one if that quota has it, else an open category, else the first. */
export function categoryFor(route: ExamRoute, quota: string, current: string): string {
  const allowed = route.quota_categories?.[quota];
  if (!allowed?.length || allowed.includes(current)) return current;
  return OPEN_CATEGORIES.find((c) => allowed.includes(c)) ?? allowed.find((c) => /^GOPEN/.test(c)) ?? allowed[0];
}

// ---- The exam catalog: one place that names, groups and orders every exam, JEE included ----

export type StreamKey = "Engineering" | "Medical" | "Law" | "Postgraduate";
export const STREAMS: { key: StreamKey; label: string; blurb: string }[] = [
  { key: "Engineering", label: "Engineering", blurb: "B.Tech and B.E. after Class 12" },
  { key: "Medical", label: "Medical", blurb: "MBBS, BDS and nursing" },
  { key: "Law", label: "Law", blurb: "Five-year integrated law" },
  { key: "Postgraduate", label: "Postgraduate", blurb: "M.Tech and other PG courses" },
];

// Short names students use for each counselling route. Routes not listed use their metric's name.
export const EXAM_SHORT: Record<string, { name: string; scope: string }> = {
  jee: { name: "JEE Main & Advanced", scope: "IITs, NITs, IIITs and GFTIs (JoSAA)" },
  uptac: { name: "UPTAC", scope: "Uttar Pradesh, AKTU colleges" },
  "kcet-engineering": { name: "KCET", scope: "Karnataka engineering (KEA)" },
  "maharashtra-engineering": { name: "MHT-CET", scope: "Maharashtra engineering (CAP)" },
  "neet-ug": { name: "NEET UG", scope: "All India counselling (MCC)" },
  "karnataka-neet": { name: "NEET UG, Karnataka", scope: "State quota (KEA)" },
  clat: { name: "CLAT", scope: "National Law Universities" },
  "gate-ccmt": { name: "GATE", scope: "NIT M.Tech (CCMT)" },
};

export type CatalogEntry = {
  code: string; href: string; stream: StreamKey; name: string; scope: string; enter: string;
  year: string; institutes: number | null; bands: boolean; rounds: number | null;
};

export function streamOf(route: Pick<ExamRoute, "stream" | "level">): StreamKey {
  if (route.level === "PG") return "Postgraduate";
  return (["Engineering", "Medical", "Law"] as const).find((s) => s === route.stream) ?? "Engineering";
}

/** Every exam we cover, JEE first within engineering, then the rest in a fixed order. */
export function examCatalog(routes: ExamRoute[], jee: { years: number[]; institutes: number } | null): CatalogEntry[] {
  const order = Object.keys(EXAM_SHORT);
  const entries: CatalogEntry[] = routes.map((r) => ({
    code: r.code, href: `/exams/${r.code}`, stream: streamOf(r),
    name: EXAM_SHORT[r.code]?.name ?? r.metric.label.replace(/ (rank|score|percentile|All India Rank).*$/i, ""),
    scope: EXAM_SHORT[r.code]?.scope ?? r.name, enter: r.metric.label,
    year: r.document.year, institutes: r.institute_count, bands: Boolean(r.history), rounds: r.rounds?.length ?? null,
  }));
  entries.push({
    code: "jee", href: "/onboarding", stream: "Engineering", name: EXAM_SHORT.jee.name, scope: EXAM_SHORT.jee.scope, enter: "JEE ranks",
    year: jee ? `${jee.years[0]}–${String(jee.years.at(-1)).slice(2)}` : "", institutes: jee?.institutes ?? null, bands: true, rounds: null,
  });
  return entries.sort((a, b) => (order.indexOf(a.code) + 1 || 99) - (order.indexOf(b.code) + 1 || 99));
}

export function byStream(entries: CatalogEntry[]): { stream: (typeof STREAMS)[number]; entries: CatalogEntry[] }[] {
  return STREAMS.map((stream) => ({ stream, entries: entries.filter((e) => e.stream === stream.key) })).filter((g) => g.entries.length);
}
