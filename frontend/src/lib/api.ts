// Thin client for the FastAPI backend. All business logic lives on the server.
export type Band = "safer" | "competitive" | "ambitious" | "beyond" | null;

export type Route = {
  quota: string; seat_type: string; gender_pool: string; gender_pool_label?: string; rank_used: number; rank_list: string; band: Band;
  low_closing?: number | null; high_closing?: number | null; latest_year?: number | null; latest_closing?: number | null;
  years_used?: number[]; explanation: string; quota_reason: string;
};
export type Component = { key: string; label: string; weight: number; score: number | null; note: string };
export type Ranking = { framework: string; category: string; year: number; rank: number; score: number | null; verification_status: string; source_name: string; source_url: string };
export type Placement = {
  scope: string; scope_label: string; cohort_label: string; reporting_definition: string; graduation_year: number; eligible_students: number | null;
  graduating_students: number | null; students_placed: number | null; higher_studies_students: number | null; median_salary_inr: number | null;
  average_salary_inr: number | null; verification_status: string; notes: string | null; source_title: string; source_url: string; source_page: number | null;
  total_students: number | null; base_students: number | null; base_label: string | null; salary_basis: string | null;
};
export type BranchOutcome = {
  programme_id: number; programme: string; graduation_year: number; students_placed: number | null; base_students: number | null; base_label: string | null;
  total_students: number | null; median_salary_inr: number | null; average_salary_inr: number | null; salary_basis: string | null; source_title: string; source_url: string;
  source_page: number | null; verification_status: string; notes: string | null;
};
export type Careers = {
  branch_outcomes: BranchOutcome[];
  outcome_mix: { graduation_year: number; graduating_students: number | null; students_placed: number | null; higher_studies_students: number | null; source_title: string; source_url: string }[];
  sectors: { academic_year: string; cohort_label: string; total: number; items: { sector: string; students: number; percent: number }[]; source_title: string; source_url: string; source_page: number | null } | null;
  recruiters: { academic_year: string; count: number; companies: string[]; note: string; source_title: string; source_url: string } | null;
  alumni: { status: string; sample_size: number; minimum: number; founders?: number; occupations?: { label: string; people: number }[]; employers?: { label: string; people: number }[]; caveat: string; source_title: string; source_url: string; retrieved_at: string } | null;
  not_available: string;
};
export type Fee = {
  academic_year: string; seat_type_group: string; annual_complete_inr: number | null; annual_tuition_inr: number | null; annual_hostel_inr: number | null;
  annual_mess_inr: number | null; annual_other_inr: number | null; one_time_inr: number | null; refundable_deposit_inr: number | null;
  payable_at_admission_inr: number | null; verification_status: string; notes: string | null; source_title: string; source_url: string; source_page: number | null;
};
export type Quality = { score: number | null; coverage: number; status: string; components: Component[] };
export type InstitutionRef = { slug: string; short_name: string; official_name?: string; type: string; city: string | null; state: string };

export type Option = {
  programme_id: number; programme: string; degree: string | null; duration_years: number | null; branch_family: string; branch_label: string;
  institution: InstitutionRef; band: Band; best_route: Route; other_routes: Route[]; quality: Quality;
  suitability: { score: number | null; coverage: number; components: Component[] };
  ranking: Ranking | null; placements: Placement[]; fee: Fee | null;
  strengths: string[]; weaknesses: string[]; data_gaps: string[]; why: string[];
};
export type Recommendations = {
  engine_version: string; data_year?: number; history_window?: [number, number]; counts: Record<string, number>;
  excluded?: Record<string, number>; warnings: string[]; options: Option[]; result_hash?: string;
};
export type Meta = {
  states: string[]; branch_families: Record<string, string>; career_options: Record<string, string>; career_mapped: string[];
  default_priorities: Record<string, number>; suitability_labels: Record<string, string>; quality_labels: Record<string, string>;
  quality_weights: Record<string, number>; latest_data_year: number; engine_version: string; institute_types: Record<string, string>;
};
export type Profile = {
  category: string; gender: string; is_pwd: boolean; eligibility_state: string; class12_status: string;
  main: Record<string, number | null>; advanced: Record<string, number | null>; advanced_qualified: boolean;
  preferred_branches: string[]; acceptable_branches: string[]; avoid_branches: string[]; preferred_types: string[];
  preferred_states: string[]; career_goals: string[]; annual_budget_inr: number | null; priorities: Record<string, number>;
};
export type InstitutionListItem = {
  slug: string; short_name: string; official_name: string; type: string; city: string | null; state: string; is_pilot: boolean;
  programme_count: number; ranking: Ranking | null; completeness: { percent: number; fields: Record<string, boolean> };
};
export type ProgrammeSummary = { id: number; name: string; degree: string | null; duration_years: number | null; branch_family: string; branch_label: string; last_seen_year: number | null; currently_offered: boolean };
export type InstitutionDetail = {
  slug: string; short_name: string; official_name: string; type: string; city: string | null; state: string; website: string | null;
  is_pilot: boolean; location_verification: string; aliases: string[]; rankings: Ranking[]; quota_states: Record<string, string[]>;
  institution_placements: Placement[]; fee: Fee | null; programmes: ProgrammeSummary[]; completeness: { percent: number; fields: Record<string, boolean> }; careers: Careers;
};
export type ProgrammeDetail = {
  id: number; name: string; degree: string | null; duration_years: number | null; branch_family: string; branch_label: string; required_paper: string;
  institution: InstitutionRef; available_seats: { seat_type: string; quota: string; gender_pool: string }[];
  placements: Placement[]; ranking: Ranking | null; fee: Fee | null;
};
export type CutoffPoint = {
  year: number; round: number; is_final_round: boolean; quota: string; rank_list: string; opening_rank: number | null; closing_rank: number | null;
  is_preparatory: boolean; raw_closing: string; source_title: string; source_url: string; fetched_at: string;
};
export type ComparisonItem = {
  programme_id: number; programme: string; degree: string | null; duration_years: number | null; branch_label: string; branch_family: string;
  institution: InstitutionRef; reference_cutoff: { year: number; quota: string; closing_rank: number; rank_list: string; source_url: string; source_title: string } | null;
  ranking: Ranking | null; placements: Placement[]; fee: Fee | null; quality: Quality; data_gaps: string[];
  student_route: Route | null; suitability: { score: number | null; coverage: number; components: Component[] } | null; careers: Careers;
};
export type Comparison = { items: ComparisonItem[]; trade_offs: string[]; note: string };
export type DataSource = { key: string; name: string; publisher: string; url: string; tier: string; access_method: string; access_status: string; terms_note: string | null; documents: number; last_checked_at: string | null };
export type Completeness = { institutions: number; programmes: number; cutoff_records: number; cutoff_years: number[]; coverage: Record<string, number>; not_yet_collected: string[] };

export class ApiError extends Error {}

function apiBase(): string {
  if (typeof window !== "undefined") return "";
  return process.env.API_BASE_URL ?? "http://127.0.0.1:8400";
}

function describeError(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d: { msg?: string }) => (d.msg ?? "Invalid input").replace(/^Value error, /, "")).join(" ");
  }
  return "Something went wrong. Please try again.";
}

// Server-rendered pages share one server address, so they reuse answers for an hour rather than
// counting every visitor against the API's rate limit. The data only changes on a new deployment.
function freshness(): RequestInit {
  return typeof window === "undefined" ? ({ next: { revalidate: 3600 } } as RequestInit) : { cache: "no-store" };
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase()}/api/v1${path}`, { ...freshness(), headers: { "Content-Type": "application/json" }, ...init });
  } catch {
    throw new ApiError("The data service could not be reached. Please try again shortly.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(describeError(body.detail));
  }
  return response.json();
}

export const post = <T,>(path: string, body: unknown) => api<T>(path, { method: "POST", body: JSON.stringify(body) });

export const inr = (value: number | null | undefined) =>
  value == null ? "Data not available" : new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);
export const num = (value: number | null | undefined) => (value == null ? "—" : value.toLocaleString("en-IN"));

export type RoiResult = {
  costs: { annual_cost: number; annual_after_scholarship: number; total_cost: number; total_excluding_refundable: number }; funding_gap: number;
  loan: { loan_amount: number; interest_during_moratorium: number; balance_at_repayment: number; monthly_emi: number; total_repaid: number; total_interest: number };
  scenarios: { name: string; annual_ctc: number; monthly_take_home: number; emi_share_of_take_home: number | null; illustrative_payback_years: number | null; emi_warning: boolean }[];
  assumptions: { low_factor: number; high_factor: number; take_home_share: number; repayment_share: number; low_is_assumed: boolean; high_is_assumed: boolean }; warning: string;
};
export type FinancialDefaults = { programme_id: number; programme: string; institution: string; years: number | null; fee: Fee | null; median: Placement | null };
export type PreferenceItem = {
  position: number; programme_id: number; programme?: string; degree?: string | null; branch_label?: string; institution?: { slug: string; short_name: string; type: string; state: string };
  status: string; band: Band; routes?: { seat_type: string; quota: string; gender_pool: string; band: Band; explanation: string; rank_used: number; rank_list: string }[]; issues: string[];
};
export type PreferenceAnalysis = { items: PreferenceItem[]; order_preserved: boolean; advice: string[]; counts: Record<string, number>; rules: string[]; data_year: number };
export type ReportOption = {
  position: number; programme_id: number; programme: string; degree: string | null; duration_years: number | null; branch_plain: string;
  institution: { short_name: string; official_name: string; type: string; city: string | null; state: string };
  admission: { title: string; text: string; band: Band; routes: { seat_type: string; quota: string; rank_used: number; rank_list: string; explanation: string }[]; issues: string[] };
  ranking: Ranking | null; placement_highlight: Placement | null; placements: Placement[]; fee: Fee | null; known_annual: number | null;
  loan: { known_total: number; complete: boolean; terms: RoiResult["loan"]; scenarios: RoiResult["scenarios"] } | null; careers: Careers; risks: string[];
};
export type ParentReport = {
  generated_on: string; data_year: number; student: { category: string; state: string; is_pwd: boolean; main_rank: number | null; main_category_rank: number | null; advanced_rank: number | null; goals: string[]; preferred_branches: string[] };
  options: ReportOption[]; advice: string[]; glossary: [string, string][]; rules: string[]; limits: string[];
};
