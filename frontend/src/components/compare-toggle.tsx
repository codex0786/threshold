"use client";
import { Check, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { loadCompare, toggleCompare } from "@/lib/store";

export function CompareToggle({ id, label }: { id: number; label: string }) {
  const [selected, setSelected] = useState(false);
  const [full, setFull] = useState(false);
  useEffect(() => {
    const sync = () => {
      const list = loadCompare();
      setSelected(list.some((e) => e.id === id));
      setFull(list.length >= 4);
    };
    sync();
    window.addEventListener("threshold-compare", sync);
    return () => window.removeEventListener("threshold-compare", sync);
  }, [id]);
  return (
    <button type="button" className="btn btn-secondary !px-3 !py-1.5 text-sm" aria-pressed={selected} disabled={!selected && full}
      title={!selected && full ? "You can compare up to four options" : undefined} onClick={() => toggleCompare({ id, label })}>
      {selected ? <Check size={14} aria-hidden /> : <Plus size={14} aria-hidden />}
      {selected ? "Added to compare" : "Compare"}
    </button>
  );
}
