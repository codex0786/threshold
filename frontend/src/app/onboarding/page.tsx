"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { type FieldPath, useForm } from "react-hook-form";
import { z } from "zod";
import { Notice, PageHeader, Skeleton } from "@/components/ui";
import { api, type Meta, type Profile } from "@/lib/api";
import { loadDraft, saveDraft, saveProfile } from "@/lib/store";

const rank = z.string().refine((v) => v === "" || (/^\d+$/.test(v) && Number(v) > 0), "Enter a whole number above 0, or leave this blank");

const schema = z.object({
  advanced_qualified: z.boolean(),
  category: z.enum(["GEN", "GEN-EWS", "OBC-NCL", "SC", "ST"]),
  gender: z.enum(["female", "male", "other"]), is_pwd: z.boolean(),
  eligibility_state: z.string().min(1, "Choose the state of your first Class XII attempt"),
  class12_status: z.enum(["meets", "does_not_meet", "unknown"]),
  main_crl: rank, main_category: rank, main_crl_pwd: rank, main_category_pwd: rank,
  adv_crl: rank, adv_category: rank, adv_crl_pwd: rank, adv_category_pwd: rank,
  preferred_branches: z.array(z.string()), acceptable_branches: z.array(z.string()), avoid_branches: z.array(z.string()),
  preferred_types: z.array(z.string()), preferred_states: z.array(z.string()), career_goals: z.array(z.string()),
  annual_budget: rank,
}).superRefine((v, ctx) => {
  const main = [v.main_crl, v.main_category, v.main_crl_pwd, v.main_category_pwd].some(Boolean);
  const adv = [v.adv_crl, v.adv_category, v.adv_crl_pwd, v.adv_category_pwd].some(Boolean);
  if (v.advanced_qualified && !adv) ctx.addIssue({ code: "custom", path: ["adv_crl"], message: "Enter at least one JEE Advanced rank" });
  if (!main && !v.advanced_qualified) ctx.addIssue({ code: "custom", path: ["main_crl"], message: "Enter at least one JEE Main rank" });
});
type Form = z.infer<typeof schema>;

const DEFAULTS: Form = {
  advanced_qualified: false, category: "GEN", gender: "male", is_pwd: false, eligibility_state: "", class12_status: "unknown",
  main_crl: "", main_category: "", main_crl_pwd: "", main_category_pwd: "", adv_crl: "", adv_category: "", adv_crl_pwd: "", adv_category_pwd: "",
  preferred_branches: [], acceptable_branches: [], avoid_branches: [], preferred_types: [], preferred_states: [], career_goals: [], annual_budget: "",
};
const STEPS = ["About you", "Your ranks", "Branches and places", "Goals and budget"];
const STEP_FIELDS: FieldPath<Form>[][] = [
  ["category", "gender", "eligibility_state", "class12_status"],
  ["main_crl", "main_category", "main_crl_pwd", "main_category_pwd", "adv_crl", "adv_category", "adv_crl_pwd", "adv_category_pwd"],
  [], ["annual_budget"],
];
const asNumber = (v: string) => (v ? Number(v) : null);

function toProfile(v: Form, meta: Meta): Profile {
  const hasCategory = v.category !== "GEN";
  const adv = v.advanced_qualified;
  return {
    category: v.category, gender: v.gender, is_pwd: v.is_pwd, eligibility_state: v.eligibility_state, class12_status: v.class12_status,
    main: { crl: asNumber(v.main_crl), category_rank: hasCategory ? asNumber(v.main_category) : null, crl_pwd: v.is_pwd ? asNumber(v.main_crl_pwd) : null, category_pwd_rank: v.is_pwd && hasCategory ? asNumber(v.main_category_pwd) : null },
    advanced: adv ? { crl: asNumber(v.adv_crl), category_rank: hasCategory ? asNumber(v.adv_category) : null, crl_pwd: v.is_pwd ? asNumber(v.adv_crl_pwd) : null, category_pwd_rank: v.is_pwd && hasCategory ? asNumber(v.adv_category_pwd) : null } : {},
    advanced_qualified: adv, preferred_branches: v.preferred_branches, acceptable_branches: v.acceptable_branches, avoid_branches: v.avoid_branches,
    preferred_types: v.preferred_types, preferred_states: v.preferred_states, career_goals: v.career_goals,
    annual_budget_inr: asNumber(v.annual_budget), priorities: meta.default_priorities,
  };
}

function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm font-medium">{label}</span>
      {hint && <span className="block text-xs text-ink-3">{hint}</span>}
      <span className="mt-1 block">{children}</span>
      {error && <span className="mt-1 block text-sm" style={{ color: "var(--ambitious)" }} role="alert">{error}</span>}
    </label>
  );
}

function Chips({ legend, hint, options, value, onChange, disabled }: { legend: string; hint?: string; options: [string, string][]; value: string[]; onChange: (v: string[]) => void; disabled?: string[] }) {
  return (
    <fieldset>
      <legend className="text-sm font-medium">{legend}</legend>
      {hint && <p className="text-xs text-ink-3">{hint}</p>}
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map(([key, label]) => {
          const on = value.includes(key);
          const off = disabled?.includes(key);
          return (
            <button key={key} type="button" aria-pressed={on} disabled={off} onClick={() => onChange(on ? value.filter((v) => v !== key) : [...value, key])}
              className={`rounded-full border px-3 py-1.5 text-sm disabled:opacity-35 ${on ? "border-brand bg-brand text-brand-ink" : "border-line bg-surface text-ink-2 hover:text-ink"}`}>
              {label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

export default function Onboarding() {
  const router = useRouter();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const form = useForm<Form>({ resolver: zodResolver(schema), defaultValues: DEFAULTS, mode: "onBlur" });
  const { register, watch, setValue, trigger, handleSubmit, reset, formState: { errors } } = form;

  useEffect(() => {
    const draft = loadDraft<{ values: Form; step: number }>();
    if (draft) {
      reset({ ...DEFAULTS, ...draft.values });
      setStep(Math.min(draft.step, STEPS.length - 1));
    }
    api<Meta>("/meta").then(setMeta).catch((e) => setError(e.message));
  }, [reset]);

  const values = watch();
  useEffect(() => {
    const sub = watch((v) => saveDraft({ values: v, step }));
    return () => sub.unsubscribe();
  }, [watch, step]);

  const next = async () => {
    if (await trigger(STEP_FIELDS[step])) {
      setStep(step + 1);
      saveDraft({ values: form.getValues(), step: step + 1 });
      window.scrollTo({ top: 0 });
    }
  };
  const submit = (v: Form) => {
    if (!meta) return;
    saveProfile(toProfile(v, meta));
    router.push("/recommendations");
  };

  if (error) return <div className="mx-auto max-w-2xl px-4 py-10"><Notice tone="error">{error}</Notice></div>;
  if (!meta) return <div className="mx-auto max-w-2xl px-4 py-10"><Skeleton /></div>;

  const hasCategory = values.category !== "GEN";
  const families = Object.entries(meta.branch_families).filter(([k]) => !["OTHER", "ARCH", "PLANNING"].includes(k));
  const rankFields = (prefix: "main" | "adv", name: string) => (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={`${name} Common Rank List (CRL) rank`} error={errors[`${prefix}_crl`]?.message}><input className="input tnum" inputMode="numeric" {...register(`${prefix}_crl`)} /></Field>
      {hasCategory && <Field label={`${name} ${values.category} category rank`} hint="Your rank on the category list. This is not your CRL." error={errors[`${prefix}_category`]?.message}><input className="input tnum" inputMode="numeric" {...register(`${prefix}_category`)} /></Field>}
      {values.is_pwd && <Field label={`${name} CRL-PwD rank`} error={errors[`${prefix}_crl_pwd`]?.message}><input className="input tnum" inputMode="numeric" {...register(`${prefix}_crl_pwd`)} /></Field>}
      {values.is_pwd && hasCategory && <Field label={`${name} ${values.category}-PwD rank`} error={errors[`${prefix}_category_pwd`]?.message}><input className="input tnum" inputMode="numeric" {...register(`${prefix}_category_pwd`)} /></Field>}
    </div>
  );

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <PageHeader title="Find your best-fit options" intro="We don’t ask for your name or contact details. Your answers are saved on this device, so you can come back later." />
      <ol className="mb-6 flex gap-1.5" aria-label={`Step ${step + 1} of ${STEPS.length}: ${STEPS[step]}`}>
        {STEPS.map((s, i) => <li key={s} className={`h-1 flex-1 rounded-full ${i <= step ? "bg-brand" : "bg-surface-2"}`} />)}
      </ol>
      <p className="tnum text-sm text-ink-3">Step {step + 1} of {STEPS.length}</p>
      <h2 className="mb-5 mt-0.5 text-2xl">{STEPS[step]}</h2>

      <form
        onSubmit={(e) => {
          // Pressing Enter in an earlier step moves forward and must not submit early.
          if (step < STEPS.length - 1) { e.preventDefault(); void next(); return; }
          void handleSubmit(submit)(e);
        }}
        className="space-y-6"
      >
        {step === 0 && <>
          <Notice>This version covers Indian nationals in JoSAA counselling. OCI/PIO and foreign candidates have different rules, which aren’t handled yet, so please use the official JoSAA documents.</Notice>
          <Field label="Where did you first appear for Class XII?" hint="This sets your JoSAA home state. It is not where you live or where you were born." error={errors.eligibility_state?.message}>
            <select className="input" {...register("eligibility_state")}>
              <option value="">Choose a state or union territory</option>
              {meta.states.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Category" hint="As on your valid certificate."><select className="input" {...register("category")}>
              <option value="GEN">General</option><option value="GEN-EWS">General-EWS</option><option value="OBC-NCL">OBC-NCL</option><option value="SC">SC</option><option value="ST">ST</option>
            </select></Field>
            <Field label="Seat pool eligibility" hint="Only used to decide which seat pools apply."><select className="input" {...register("gender")}>
              <option value="male">Gender-neutral seats only</option><option value="female">Female (female-only and gender-neutral seats)</option><option value="other">Other (gender-neutral seats)</option>
            </select></Field>
          </div>
          <label className="flex items-start gap-2.5"><input type="checkbox" className="mt-1" {...register("is_pwd")} /><span className="text-sm">I am a Person with Benchmark Disability and hold a valid certificate</span></label>
          <Field label="Do you meet the JoSAA Class XII requirement?" hint={`75% aggregate (65% for SC, ST and PwD), or the top 20 percentile of your board.`}>
            <select className="input" {...register("class12_status")}>
              <option value="unknown">Not sure yet</option><option value="meets">Yes</option><option value="does_not_meet">No</option>
            </select>
          </Field>
        </>}

        {step === 1 && <>
          <Notice>Enter each rank exactly as shown on your scorecard. Your CRL and your category rank are different numbers on different lists, and we compare each only with cutoffs from its own list.</Notice>
          <div className="space-y-3"><h3 className="text-lg">JEE Main</h3><p className="-mt-2 text-sm text-ink-3">Used for NITs, IIITs and other government-funded institutes (Paper 1, B.E./B.Tech).</p>{rankFields("main", "JEE Main")}</div>
          <label className="flex items-start gap-2.5"><input type="checkbox" className="mt-1" {...register("advanced_qualified")} /><span className="text-sm">I qualified JEE Advanced</span></label>
          {values.advanced_qualified && <div className="space-y-3"><h3 className="text-lg">JEE Advanced</h3><p className="-mt-2 text-sm text-ink-3">Used for IITs and IISc.</p>{rankFields("adv", "JEE Advanced")}</div>}
          <p className="text-sm text-ink-3">B.Arch and B.Plan need a separate Paper 2 rank, which this version doesn’t handle, so those programmes won’t appear in your shortlist.</p>
        </>}

        {step === 2 && <>
          <Chips legend="Branches you prefer" options={families} value={values.preferred_branches} disabled={[...values.avoid_branches, ...values.acceptable_branches]} onChange={(v) => setValue("preferred_branches", v, { shouldDirty: true })} />
          <Chips legend="Branches you would accept" options={families} value={values.acceptable_branches} disabled={[...values.avoid_branches, ...values.preferred_branches]} onChange={(v) => setValue("acceptable_branches", v, { shouldDirty: true })} />
          <Chips legend="Branches to avoid" hint="These are removed from your shortlist, and we tell you how many were removed." options={families} value={values.avoid_branches} disabled={[...values.preferred_branches, ...values.acceptable_branches]} onChange={(v) => setValue("avoid_branches", v, { shouldDirty: true })} />
          <Chips legend="Institution types you prefer" options={Object.entries(meta.institute_types)} value={values.preferred_types} onChange={(v) => setValue("preferred_types", v, { shouldDirty: true })} />
          <Chips legend="States you prefer" hint="Optional. Leave empty if location doesn’t matter." options={meta.states.map((s) => [s, s])} value={values.preferred_states} onChange={(v) => setValue("preferred_states", v, { shouldDirty: true })} />
        </>}

        {step === 3 && <>
          <Chips legend="Career directions you’re considering" hint="Links between branches and careers are our general assumptions, and we label them as such. Some goals, such as consulting, finance and government jobs, aren’t tied to a branch, so they don’t affect your score." options={Object.entries(meta.career_options)} value={values.career_goals} onChange={(v) => setValue("career_goals", v, { shouldDirty: true })} />
          <Field label="Annual budget in rupees (optional)" hint="We don’t have verified fee data yet, so this won’t change your results until we do." error={errors.annual_budget?.message}>
            <input className="input tnum" inputMode="numeric" {...register("annual_budget")} />
          </Field>
        </>}

        <div className="flex justify-between gap-3 pt-2">
          {step > 0 ? <button type="button" className="btn btn-secondary" onClick={() => setStep(step - 1)}><ArrowLeft size={16} aria-hidden /> Back</button> : <span />}
          {step < STEPS.length - 1
            ? <button key="continue" type="button" className="btn btn-primary" onClick={next}>Continue <ArrowRight size={16} aria-hidden /></button>
            : <button key="submit" type="submit" className="btn btn-primary">See my shortlist <ArrowRight size={16} aria-hidden /></button>}
        </div>
        {Object.keys(errors).length > 0 && step === STEPS.length - 1 && <Notice tone="error">Some answers need attention in an earlier step. Go back and check your ranks.</Notice>}
      </form>
    </div>
  );
}
