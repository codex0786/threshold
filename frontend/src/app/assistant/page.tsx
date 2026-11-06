"use client";

import { Send } from "lucide-react";
import Link from "next/link";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Notice, PageHeader, SourceLink, VerificationTag } from "@/components/ui";
import { type AssistantAnswer, post, type Profile } from "@/lib/api";
import { loadProfile } from "@/lib/store";

const EXAMPLES = [
  "Should I choose NIT Trichy CSE or NIT Warangal ECE?", "Is an IIT lower branch better than an NIT top branch?",
  "Which colleges have the best placement consistency?", "Which colleges offer the best value under ₹10 lakh?",
  "What if I prioritise higher studies instead of placements?", "What is the difference between float and slide?",
];

type Turn = { question: string; answer: AssistantAnswer };

function AnswerCard({ turn }: { turn: Turn }) {
  const { answer } = turn;
  return (
    <article className="card p-4 sm:p-5">
      <p className="text-sm font-semibold text-ink-2">{turn.question}</p>
      <p className="mt-2 text-lg">{answer.summary}</p>
      {answer.facts.length > 0 && (
        <section className="mt-4">
          <h2 className="text-base font-medium">From our records</h2>
          <ul className="mt-2 divide-y divide-line">
            {answer.facts.map((fact) => (
              <li key={fact.text} className="py-2 text-sm">
                <p>{fact.text}</p>
                {fact.source_url && <div className="mt-0.5 text-xs text-ink-3">{fact.verification_status && <><VerificationTag status={fact.verification_status} />{" "}</>}<SourceLink href={fact.source_url} label={fact.year ? `${fact.source_title}, ${fact.year}` : fact.source_title ?? fact.source_url} /></div>}
              </li>
            ))}
          </ul>
        </section>
      )}
      {answer.reasoning.length > 0 && (
        <section className="mt-4">
          <h2 className="text-base font-medium">General reasoning, not data</h2>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-ink-2">{answer.reasoning.map((r) => <li key={r}>{r}</li>)}</ul>
        </section>
      )}
      {answer.gaps.length > 0 && (
        <section className="mt-4">
          <h2 className="text-base font-medium">What we don’t know</h2>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-ink-3">{answer.gaps.map((g) => <li key={g}>{g}</li>)}</ul>
        </section>
      )}
      {answer.needs_profile && <p className="mt-4 text-sm"><Link href="/onboarding" className="font-semibold text-brand hover:underline">Add your rank and category</Link> to get an answer about your own options.</p>}
    </article>
  );
}

export default function AssistantPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const top = useRef<HTMLDivElement>(null);

  useEffect(() => setProfile(loadProfile()), []);

  async function ask(text: string) {
    const clean = text.trim();
    if (clean.length < 2 || loading) return;
    setLoading(true);
    setError(null);
    try {
      const answer = await post<AssistantAnswer>("/ai/counselling", { question: clean, profile });
      setTurns((current) => [{ question: clean, answer }, ...current]);
      setQuestion("");
      top.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "The question couldn’t be answered. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <PageHeader title="Counselling assistant" intro="Ask about colleges, branches and the JoSAA process. Answers come only from our stored records, with a source for each figure." />
      <Notice>This doesn’t use an AI model. It matches your question to a fixed set of lookups, so it can’t invent figures, but it understands only certain kinds of question. It never picks a college for you. {profile ? "It’s using the rank you entered in this browser." : "Add your rank to get answers about your own options."} Your question isn’t saved.</Notice>
      <form className="mt-5 flex gap-2" onSubmit={(e: FormEvent) => { e.preventDefault(); void ask(question); }}>
        <label htmlFor="question" className="sr-only">Your question</label>
        <input id="question" value={question} maxLength={500} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask a question" className="min-w-0 flex-1 rounded-xl border border-line bg-surface px-3 py-2.5" />
        <button type="submit" disabled={loading || question.trim().length < 2} className="btn btn-primary shrink-0"><Send size={15} aria-hidden /> {loading ? "Looking" : "Ask"}</button>
      </form>
      <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Example questions">
        {EXAMPLES.map((example) => (
          <button key={example} type="button" onClick={() => void ask(example)} disabled={loading} className="rounded-full border border-line bg-surface px-3 py-1.5 text-left text-xs text-ink-2 transition-colors hover:text-ink">{example}</button>
        ))}
      </div>
      {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}
      <div ref={top} className="mt-6 space-y-4" aria-live="polite">
        {turns.map((turn, i) => <AnswerCard key={`${turn.question}-${turns.length - i}`} turn={turn} />)}
      </div>
    </div>
  );
}
