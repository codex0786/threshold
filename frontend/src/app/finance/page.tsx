"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { Notice, PageHeader, Section, SourceLink } from "@/components/ui";
import { api, type FinancialDefaults, inr, post, type RoiResult } from "@/lib/api";

type Fields = Record<string, string>;
const BLANK: Fields = {
  annual_tuition_inr: "", annual_hostel_inr: "", annual_mess_inr: "", annual_other_inr: "", one_time_inr: "", refundable_deposit_inr: "", annual_living_inr: "", annual_scholarship_inr: "",
  years: "4", family_contribution_inr: "", loan_amount_inr: "", interest_rate_percent: "9", repayment_years: "10", moratorium_months: "60", median_ctc_inr: "", low_ctc_inr: "", high_ctc_inr: "", take_home_percent: "70",
};
const COST: [string, string][] = [["annual_tuition_inr", "Tuition a year"], ["annual_hostel_inr", "Hostel a year"], ["annual_mess_inr", "Mess a year"], ["annual_other_inr", "Other charges a year"], ["annual_living_inr", "Living expenses a year"], ["annual_scholarship_inr", "Scholarship a year"], ["one_time_inr", "One-time charges"], ["refundable_deposit_inr", "Refundable deposits"]];
const LOAN: [string, string][] = [["family_contribution_inr", "Family contribution"], ["loan_amount_inr", "Loan amount (blank uses what’s left)"], ["interest_rate_percent", "Interest rate, %"], ["repayment_years", "Repayment years"], ["moratorium_months", "Months before repayment starts"]];
const SALARY: [string, string][] = [["median_ctc_inr", "Base: median CTC a year"], ["low_ctc_inr", "Low (blank is 70% of base)"], ["high_ctc_inr", "High (blank is 130% of base)"], ["take_home_percent", "Take-home share of CTC, %"]];

function Inputs({ items, values, set, missing }: { items: [string, string][]; values: Fields; set: (k: string, v: string) => void; missing?: Set<string> }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {items.map(([key, label]) => (
        <label key={key} className="text-sm">
          {label}
          <input className="input tnum mt-1" inputMode="decimal" value={values[key]} onChange={(e) => set(key, e.target.value.replace(/[^\d.]/g, ""))} placeholder={missing?.has(key) ? "Not published. Enter your own" : ""} />
        </label>
      ))}
    </div>
  );
}

function Calculator() {
  const params = useSearchParams();
  const programme = params.get("programme");
  const [values, setValues] = useState<Fields>(BLANK);
  const [defaults, setDefaults] = useState<FinancialDefaults | null>(null);
  const [result, setResult] = useState<RoiResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const set = useCallback((k: string, v: string) => setValues((c) => ({ ...c, [k]: v })), []);

  useEffect(() => {
    if (!programme) return;
    api<FinancialDefaults>(`/financial/defaults/${programme}`).then((d) => {
      setDefaults(d);
      setValues((c) => ({
        ...c, years: String(d.years ?? 4), annual_tuition_inr: String(d.fee?.annual_tuition_inr ?? ""), annual_hostel_inr: String(d.fee?.annual_hostel_inr ?? ""),
        annual_mess_inr: String(d.fee?.annual_mess_inr ?? ""), annual_other_inr: String(d.fee?.annual_other_inr ?? ""), one_time_inr: String(d.fee?.one_time_inr ?? ""),
        refundable_deposit_inr: String(d.fee?.refundable_deposit_inr ?? ""), median_ctc_inr: String(d.median?.median_salary_inr ?? ""),
      }));
    }).catch((e) => setError(e.message));
  }, [programme]);

  useEffect(() => {
    const timer = setTimeout(() => {
      const n = (k: string) => (values[k] === "" ? undefined : Number(values[k]));
      const body = {
        annual_tuition_inr: n("annual_tuition_inr") ?? 0, annual_hostel_inr: n("annual_hostel_inr") ?? 0, annual_mess_inr: n("annual_mess_inr") ?? 0, annual_other_inr: n("annual_other_inr") ?? 0,
        annual_living_inr: n("annual_living_inr") ?? 0, annual_scholarship_inr: n("annual_scholarship_inr") ?? 0, one_time_inr: n("one_time_inr") ?? 0, refundable_deposit_inr: n("refundable_deposit_inr") ?? 0,
        years: n("years") ?? 4, family_contribution_inr: n("family_contribution_inr") ?? 0, loan_amount_inr: n("loan_amount_inr"), interest_rate_percent: n("interest_rate_percent") ?? 0,
        repayment_years: n("repayment_years") ?? 10, moratorium_months: n("moratorium_months") ?? 0, median_ctc_inr: n("median_ctc_inr"), low_ctc_inr: n("low_ctc_inr"), high_ctc_inr: n("high_ctc_inr"),
        take_home_share: (n("take_home_percent") ?? 70) / 100,
      };
      post<RoiResult>("/financial/roi", body).then((r) => { setResult(r); setError(null); }).catch((e) => setError(e.message));
    }, 250);
    return () => clearTimeout(timer);
  }, [values]);

  const missing = new Set(defaults ? COST.map(([k]) => k).filter((k) => k !== "annual_living_inr" && k !== "annual_scholarship_inr" && values[k] === "") : []);
  const salarySource = defaults?.median;
  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <PageHeader title="Cost and loan estimate" intro={defaults ? `${defaults.programme} at ${defaults.institution}. Published figures are filled in, and you can change anything.` : "Enter your costs, or open this page from a programme to fill in what’s published."} />
      {error && <div className="mb-4"><Notice tone="error">{error}</Notice></div>}
      {defaults && missing.size > 0 && <div className="mb-4"><Notice tone="warn">Some costs aren’t published in our sources, so we’ve left them blank instead of guessing. The total will be too low until you add them.</Notice></div>}
      <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
        <div className="space-y-5">
          <Section title="Costs">
            <label className="mb-3 block text-sm">Years of study<input className="input tnum mt-1 sm:w-40" inputMode="numeric" value={values.years} onChange={(e) => set("years", e.target.value.replace(/\D/g, ""))} /></label>
            <Inputs items={COST} values={values} set={set} missing={missing} />
            {defaults?.fee && <div className="mt-3 text-xs text-ink-3"><p>Filled for: {defaults.fee.seat_type_group}, {defaults.fee.academic_year}. {defaults.fee.notes}</p><SourceLink href={defaults.fee.source_url} label={defaults.fee.source_title} /></div>}
          </Section>
          <Section title="Funding"><Inputs items={LOAN} values={values} set={set} /></Section>
          <Section title="Salary scenarios" hint="We use a median, never the highest package.">
            <Inputs items={SALARY} values={values} set={set} />
            {salarySource && <div className="mt-3 text-xs text-ink-3"><p>Base is {salarySource.scope === "programme" ? "this branch’s" : "the institute-wide"} self-reported median for {salarySource.graduation_year}, and {salarySource.scope === "programme" ? "only covers placed students" : "isn’t specific to this branch"}.</p><SourceLink href={salarySource.source_url} label={salarySource.source_title} /></div>}
          </Section>
        </div>
        <div className="space-y-5 lg:sticky lg:top-20 lg:self-start" aria-live="polite">
          {result && <>
            <Section title="Total cost">
              <p className="tnum text-2xl">{inr(result.costs.total_cost)}</p>
              <p className="tnum text-sm text-ink-2">{inr(result.costs.annual_after_scholarship)} a year, plus one-time charges and deposits</p>
            </Section>
            <Section title="Loan">
              <dl className="tnum space-y-1 text-sm">
                {[["Loan amount", result.loan.loan_amount], ["Interest before repayment", result.loan.interest_during_moratorium], ["Monthly EMI", result.loan.monthly_emi], ["Total interest", result.loan.total_interest], ["Total repaid", result.loan.total_repaid]].map(([l, v]) => <div key={l as string} className="flex justify-between gap-3"><dt className="text-ink-2">{l}</dt><dd className="font-medium">{inr(v as number)}</dd></div>)}
              </dl>
            </Section>
            <Section title="If salary after graduation is…">
              {!result.scenarios.length ? <p className="text-sm text-ink-3">Add a median salary to see scenarios.</p> : (
                <ul className="space-y-3">
                  {result.scenarios.map((s) => (
                    <li key={s.name} className="text-sm">
                      <p className="font-medium">{s.name}: {inr(s.annual_ctc)} CTC{(s.name === "Low" && result.assumptions.low_is_assumed) || (s.name === "High" && result.assumptions.high_is_assumed) ? " (assumed)" : ""}</p>
                      <p className="tnum text-ink-2">About {inr(s.monthly_take_home)} a month in hand. EMI takes {s.emi_share_of_take_home}%.</p>
                      <p className="tnum text-ink-2">Illustrative payback: {s.illustrative_payback_years} years</p>
                      {s.emi_warning && <p className="text-xs" style={{ color: "var(--ambitious)" }}>This EMI is above {Math.round(result.assumptions.repayment_share * 100)}% of take-home pay, which could be hard to sustain.</p>}
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-3 text-xs text-ink-3">Payback assumes {Math.round(result.assumptions.repayment_share * 100)}% of take-home pay goes to the education cost and loan. {result.warning}</p>
            </Section>
          </>}
        </div>
      </div>
    </div>
  );
}

export default function FinancePage() {
  return <Suspense fallback={null}><Calculator /></Suspense>;
}
