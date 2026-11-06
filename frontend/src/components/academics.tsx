import { NotAvailable, SourceLink, VerificationTag } from "@/components/ui";
import { num } from "@/lib/api";
import type { Academics } from "@/lib/api";

function money(value: number | null | undefined): string {
  if (value == null) return "Not on record";
  if (value >= 10_000_000) return `₹${(value / 10_000_000).toFixed(2)} crore`;
  return `₹${(value / 100_000).toFixed(2)} lakh`;
}

function Row({ label, value }: { label: string; value: string }) {
  return <div className="flex justify-between gap-3"><dt className="text-ink-2">{label}</dt><dd className="tnum shrink-0 text-right">{value}</dd></div>;
}

function Block({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-base font-medium">{title}</h3>
      <dl className="mt-1 space-y-0.5 text-sm">{children}</dl>
      {note && <p className="mt-1 text-xs text-ink-3">{note}</p>}
    </div>
  );
}

const given = (value: number | null | undefined) => (value == null ? "Not on record" : num(value));

// Teaching, experience, availability, research and resources stay apart, because none stands in for another.
export function AcademicBlock({ academics, compact = false }: { academics: Academics | null | undefined; compact?: boolean }) {
  if (!academics || (!academics.source && !academics.publications)) return <NotAvailable />;
  const { teaching, experience, availability, research, resources, publications, source, scores } = academics;
  const latest = research?.years?.[0];
  const spend = resources?.years?.[0];
  return (
    <div className="space-y-4">
      {source && <p className="text-xs text-ink-3">{academics.scope_note}</p>}
      <div className={compact ? "space-y-4" : "grid gap-5 sm:grid-cols-2"}>
        {teaching && (
          <Block title="Teaching information" note={teaching.note}>
            <Row label="Students" value={given(teaching.students_total)} />
            <Row label="Regular faculty" value={given(teaching.faculty_regular)} />
            <Row label="Students per regular faculty" value={given(teaching.students_per_regular_faculty)} />
          </Block>
        )}
        {experience && (
          <Block title="Faculty experience">
            <Row label="Regular faculty with a doctorate" value={experience.phd_share == null ? "Not on record" : `${Math.round(experience.phd_share * 100)}%`} />
            <Row label="Median experience" value={experience.median_experience_years == null ? "Not on record" : `${experience.median_experience_years} years`} />
            {!compact && <Row label="Professors / associate / assistant" value={`${given(experience.professors)} / ${given(experience.associate_professors)} / ${given(experience.assistant_professors)}`} />}
          </Block>
        )}
        {availability && (
          <Block title="Faculty availability" note={availability.note}>
            <Row label="Currently working, all terms" value={given(availability.faculty_current)} />
            <Row label="Of whom regular" value={given(availability.faculty_regular)} />
          </Block>
        )}
        {latest && (
          <Block title={`Research strength, ${latest.academic_year}`} note={research?.note}>
            <Row label="Sponsored research funding" value={money(latest.sponsored_amount_inr)} />
            <Row label="Sponsored projects" value={given(latest.sponsored_projects)} />
            <Row label="Doctorates awarded" value={given(latest.phd_graduated)} />
            <Row label="Patents granted" value={given(latest.patents_granted)} />
          </Block>
        )}
        {spend && (
          <Block title={`Academic resources, ${spend.academic_year}`} note={resources?.note}>
            <Row label="Library" value={money(spend.library_spend_inr)} />
            <Row label="New equipment" value={money(spend.equipment_spend_inr)} />
          </Block>
        )}
        {publications && (
          <Block title="Publications" note={publications.note}>
            <Row label="Indexed papers" value={given(publications.works_count)} />
            <Row label="Citations" value={given(publications.cited_by_count)} />
            <SourceLink href={publications.source_url} label={publications.source_title} />
          </Block>
        )}
      </div>
      {source?.issues && <p className="text-xs text-ink-3">Not compared with other institutes: {source.issues}.</p>}
      {source && scores?.faculty == null && !source.issues && <p className="text-xs text-ink-3">Shown but not compared: only Engineering submissions with at least 20 regular faculty are compared with each other.</p>}
      {source && (
        <div className="text-xs text-ink-3">
          <VerificationTag status={source.verification_status} />{" "}
          <SourceLink href={source.url} label={`${source.title} (NIRF ${source.submission_year}, ${source.category})`} />
        </div>
      )}
      <p className="text-xs text-ink-3">We hold no department-level faculty data or student feedback, and we don’t rate individual teachers.</p>
    </div>
  );
}
