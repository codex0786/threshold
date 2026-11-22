"use client";
import { programmeLabel } from "@/lib/programmes";
import { ChevronDown, Wand2 } from "lucide-react";
import { useState } from "react";
import { Notice } from "@/components/ui";
import { sizeBucket, track } from "@/lib/analytics";
import { type BuiltList, num, post, type Profile } from "@/lib/api";
import type { CompareEntry } from "@/lib/store";

// Suggests a starting list from the shortlist. It always becomes a new scenario, so the student's own list is never changed.
export function ListBuilder({ profile, onBuilt }: { profile: Profile; onBuilt: (name: string, items: CompareEntry[], notes: string[]) => void }) {
  const [open, setOpen] = useState(false);
  const [order, setOrder] = useState<"top" | "fit">("top");
  const [size, setSize] = useState(60);
  const [net, setNet] = useState(5);
  const [ambitious, setAmbitious] = useState(true);
  const [past, setPast] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const build = async () => {
    setBusy(true);
    setError(null);
    try {
      const built = await post<BuiltList>("/preference-lists/build", { profile, order, size, safety_net: net, include_ambitious: ambitious, past_safety_net: past });
      if (!built.items.length) { setError(built.notes[0] ?? "No options matched your profile."); return; }
      track("list_built", { order, size: sizeBucket(built.items.length), safety_net: net });
      onBuilt(`Suggested (${order === "top" ? "top institutes" : "my fit"})`, built.items.map((i) => ({ id: i.programme_id, label: `${i.institution}: ${programmeLabel(i.programme, i.degree, i.duration_years)}` })), built.notes);
      setOpen(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card no-print mb-4 p-4" aria-labelledby="builder-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-xl">
          <h2 id="builder-title" className="text-lg">Build a starting list for me</h2>
          <p className="mt-1 text-sm text-ink-2">We take your shortlist in order and keep a safety net of Safer choices at the end. It opens as a new scenario, so your own list stays as it is.</p>
        </div>
        <button type="button" className="btn btn-secondary" aria-expanded={open} onClick={() => setOpen(!open)}>
          <ChevronDown size={15} className={`chev ${open ? "rotate-180" : ""}`} aria-hidden /> {open ? "Hide" : "Set it up"}
        </button>
      </div>
      {open && (
        <div className="rise mt-4 grid gap-4 border-t border-line pt-4 sm:grid-cols-2">
          <fieldset className="text-sm">
            <legend className="font-medium">Order choices by</legend>
            <label className="mt-1 flex items-center gap-2"><input type="radio" name="order" checked={order === "top"} onChange={() => setOrder("top")} /> Top institutes first</label>
            <label className="mt-1 flex items-center gap-2"><input type="radio" name="order" checked={order === "fit"} onChange={() => setOrder("fit")} /> My priorities (fit)</label>
          </fieldset>
          <label className="block text-sm">
            <span className="flex justify-between font-medium"><span>Longest list</span><span className="tnum text-ink-3">{num(size)} choices</span></span>
            <input type="range" min={10} max={150} step={5} value={size} onChange={(e) => setSize(Number(e.target.value))} className="w-full accent-[var(--brand)]" />
          </label>
          <label className="block text-sm">
            <span className="flex justify-between font-medium"><span>Safety net</span><span className="tnum text-ink-3">{net} Safer choices</span></span>
            <input type="range" min={1} max={20} value={net} onChange={(e) => setNet(Number(e.target.value))} className="w-full accent-[var(--brand)]" />
            <span className="text-xs text-ink-3">The list ends once this many Safer choices are in.</span>
          </label>
          <div className="space-y-2 self-center text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" checked={ambitious} onChange={(e) => setAmbitious(e.target.checked)} /> Include Ambitious choices</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={past} onChange={(e) => setPast(e.target.checked)} /> Keep going past the safety net, up to the longest list</label>
          </div>
          <div className="sm:col-span-2">
            {error && <div className="mb-3"><Notice tone="warn">{error}</Notice></div>}
            <button type="button" className="btn btn-primary" onClick={build} disabled={busy}><Wand2 size={15} aria-hidden /> {busy ? "Building…" : "Build the list"}</button>
            <p className="mt-2 text-xs text-ink-3">This is a starting point. Reorder it by what you actually want: JoSAA gives you the highest choice your rank reaches.</p>
          </div>
        </div>
      )}
    </section>
  );
}
