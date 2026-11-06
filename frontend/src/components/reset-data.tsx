"use client";
import { useId, useRef } from "react";
import { clearAllData } from "@/lib/store";

export function ResetData({ label = "Start over", className = "btn btn-secondary" }: { label?: string; className?: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const confirm = () => {
    clearAllData();
    // A full load, so no page keeps showing the cleared answers from memory.
    window.location.assign("/onboarding");
  };
  return (
    <>
      <button type="button" className={className} onClick={() => dialog.current?.showModal()}>{label}</button>
      <dialog ref={dialog} aria-labelledby={titleId} className="card m-auto w-[calc(100%-2rem)] max-w-md p-6 text-ink backdrop:bg-black/50">
        <h2 id={titleId} className="text-xl">Clear all your saved data?</h2>
        <p className="mt-2 text-sm text-ink-2">This removes your ranks, answers, priorities, compare selection and preference lists from this browser. You can’t undo this.</p>
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button type="button" autoFocus className="btn btn-secondary" onClick={() => dialog.current?.close()}>Keep my data</button>
          <button type="button" className="btn" style={{ background: "var(--ambitious)", color: "var(--ambitious-soft)" }} onClick={confirm}>Clear everything</button>
        </div>
      </dialog>
    </>
  );
}
