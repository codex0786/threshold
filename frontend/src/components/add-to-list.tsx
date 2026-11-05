"use client";
import { Check, ListPlus } from "lucide-react";
import { useState } from "react";
import { addToList, type CompareEntry } from "@/lib/store";

export function AddToList({ entry }: { entry: CompareEntry }) {
  const [added, setAdded] = useState(false);
  return (
    <button type="button" className="btn btn-secondary !px-3 !py-1.5 text-sm" disabled={added} onClick={() => { addToList(entry); setAdded(true); }}>
      {added ? <Check size={14} aria-hidden /> : <ListPlus size={14} aria-hidden />} {added ? "In your list" : "Add to list"}
    </button>
  );
}
