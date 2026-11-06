"use client";
import { useState } from "react";
import { num, type Profile } from "@/lib/api";
import { loadDraft, saveDraft } from "@/lib/store";

type Exam = "main" | "advanced";
type Values = Record<Exam, Record<string, string>>;

const EXAMS: { exam: Exam; name: string; draftPrefix: string }[] = [
  { exam: "main", name: "JEE Main", draftPrefix: "main" },
  { exam: "advanced", name: "JEE Advanced", draftPrefix: "adv" },
];
const DRAFT_SUFFIX: Record<string, string> = { crl: "crl", category_rank: "category", crl_pwd: "crl_pwd", category_pwd_rank: "category_pwd" };

// Only the rank lists this student's category and PwD status use.
function rankKeys(profile: Profile): [string, string][] {
  const hasCategory = profile.category !== "GEN";
  const keys: [string, string][] = [["crl", "CRL"]];
  if (hasCategory) keys.push(["category_rank", `${profile.category} category`]);
  if (profile.is_pwd) keys.push(["crl_pwd", "CRL-PwD"]);
  if (profile.is_pwd && hasCategory) keys.push(["category_pwd_rank", `${profile.category}-PwD`]);
  return keys;
}

function toValues(profile: Profile): Values {
  const pick = (ranks: Record<string, number | null>) => Object.fromEntries(rankKeys(profile).map(([k]) => [k, ranks[k] ? String(ranks[k]) : ""]));
  return { main: pick(profile.main), advanced: pick(profile.advanced) };
}

function toRanks(entered: Record<string, string>) {
  return Object.fromEntries(Object.entries(entered).map(([k, v]) => [k, v ? Number(v) : null]));
}

// Keeps "Edit my answers" showing the same ranks as the shortlist.
function syncDraft(values: Values, qualified: boolean) {
  const draft = loadDraft<{ values: Record<string, unknown>; step: number }>();
  if (!draft) return;
  const next: Record<string, unknown> = { ...draft.values, advanced_qualified: qualified };
  for (const { exam, draftPrefix } of EXAMS) {
    for (const [key, value] of Object.entries(values[exam])) next[`${draftPrefix}_${DRAFT_SUFFIX[key]}`] = value;
  }
  saveDraft({ ...draft, values: next });
}

export function RankEditor({ profile, onChange }: { profile: Profile; onChange: (next: Profile) => void }) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Values>(() => toValues(profile));
  const [qualified, setQualified] = useState(profile.advanced_qualified);
  const [error, setError] = useState<string | null>(null);
  const keys = rankKeys(profile);

  const start = () => {
    setValues(toValues(profile));
    setQualified(profile.advanced_qualified);
    setError(null);
    setOpen(true);
  };
  const set = (exam: Exam, key: string, value: string) => setValues({ ...values, [exam]: { ...values[exam], [key]: value.trim() } });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const entered = (exam: Exam) => Object.values(values[exam]).filter(Boolean);
    const used = qualified ? [...entered("main"), ...entered("advanced")] : entered("main");
    if (used.some((v) => !/^\d+$/.test(v) || Number(v) < 1)) return setError("Ranks must be whole numbers above 0.");
    if (qualified && !entered("advanced").length) return setError("Enter at least one JEE Advanced rank, or untick JEE Advanced.");
    if (!qualified && !entered("main").length) return setError("Enter at least one JEE Main rank.");
    syncDraft(values, qualified);
    onChange({ ...profile, main: toRanks(values.main), advanced: qualified ? toRanks(values.advanced) : {}, advanced_qualified: qualified });
    setOpen(false);
  };

  const summary = EXAMS.flatMap(({ exam, name }) => (exam === "advanced" && !profile.advanced_qualified ? [] : keys.flatMap(([key, label]) => {
    const rank = profile[exam][key];
    return rank ? [`${name} ${label} ${num(rank)}`] : [];
  })));

  if (!open) {
    return (
      <section className="card mb-6 flex flex-wrap items-center justify-between gap-3 p-4" aria-label="Your ranks">
        <p className="tnum text-sm"><span className="text-ink-3">Your ranks: </span><span className="font-medium">{summary.join(" · ")}</span></p>
        <button type="button" className="btn btn-secondary !py-1.5 text-sm" onClick={start}>Change rank</button>
      </section>
    );
  }
  return (
    <form className="card mb-6 space-y-4 p-4" aria-label="Change your ranks" onSubmit={submit} noValidate>
      {EXAMS.filter(({ exam }) => exam === "main" || qualified).map(({ exam, name }) => (
        <fieldset key={exam}>
          <legend className="text-sm font-semibold">{name}</legend>
          <div className="mt-1 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {keys.map(([key, label]) => (
              <label key={key} className="block text-sm">
                <span>{label} rank</span>
                <input className="input tnum mt-1" inputMode="numeric" value={values[exam][key]} onChange={(e) => set(exam, key, e.target.value)} />
              </label>
            ))}
          </div>
        </fieldset>
      ))}
      <label className="flex items-start gap-2.5"><input type="checkbox" className="mt-1" checked={qualified} onChange={(e) => setQualified(e.target.checked)} /><span className="text-sm">I qualified JEE Advanced</span></label>
      {error && <p className="text-sm" style={{ color: "var(--ambitious)" }} role="alert">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <button type="submit" className="btn btn-primary">Update my shortlist</button>
        <button type="button" className="btn btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </form>
  );
}
