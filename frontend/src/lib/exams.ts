// Shared types and helpers for exam routes beyond JEE.
import { Scale, Stethoscope, Wrench } from "lucide-react";

export type ExamMetric = { label: string; unit: string; lower_is_better: boolean; whole_number?: boolean; max?: number; value_label: string; second_label: string | null };
export type ExamDoc = { title: string; url: string; year: string; round: string; retrieved: string; status: "official" | "derived" };
export type ExamRoute = {
  code: string; stream: string; level: string; name: string; authority: string; metric: ExamMetric; document: ExamDoc; limits: string[];
  record_count: number; institute_count: number; categories: string[]; groups: string[]; programmes: string[]; compare_requires_group?: boolean;
  sources?: { title: string; url: string }[]; asks_gender?: boolean;
  group_requirements?: Record<string, string>; category_states?: Record<string, string>;
  rounds?: string[]; default_group?: string; default_programme?: string;
  quotas?: string[]; quota_requirements?: Record<string, string>; ranked_institute_count?: number; fee_institute_count?: number;
};
export type ExamRanking = { category: string; rank: number; year: number; source_url: string };
export type DeclaredFee = { title: string; note: string; declared: { label: string; value: string }[]; source_url: string; year: string; status: string };

export type RoundStep = { round: string | null; value: number | null; second_value: number | null; count: number | null; reached: boolean };
export type ExamAcademics = { students_per_regular_faculty: number | null; phd_share: number | null; faculty_regular: number | null; source: { title: string; url: string; submission_year: number } | null } | null;
export type ExamOption = {
  institute: string; institute_short: string | null; programme: string; programme_code: string | null; quota: string | null; category: string;
  female_only: boolean; seats: number | null; note: string | null; position: string; rounds: RoundStep[]; furthest: number;
  ranking: ExamRanking | null; fee: DeclaredFee | null; standing: number; why: string[];
  institution?: { slug: string; short_name: string; type: string; state: string; academics: ExamAcademics } | null;
};
export type ExamShortlist = {
  missing: string[]; positions: Record<string, { label: string; hint: string }>; counts: Record<string, number>; options: ExamOption[];
  beyond: number; hidden_female_only: number; limit?: number; route_gaps?: string[];
};

// The first view shows one clear list: the open category, and the route's own default quota and course.
// KEA's general merit category is GM.
export const OPEN_CATEGORIES = ["Open", "OPEN", "General (General)", "GOPENS", "GM"];
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
  if (/stray/i.test(round)) return "Stray";
  const n = round.match(/Round (\d)/);
  return n ? `R${n[1]}${/provisional/i.test(round) ? " (prov.)" : ""}` : round;
}

export function formatFigure(value: number, metric: ExamMetric): string {
  if (metric.whole_number || Number.isInteger(value)) return value.toLocaleString("en-IN");
  return String(value);
}

export type ExamAnswers = { value: string; category: string; quota: string; programme: string; gender: string; domicile: string };
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
