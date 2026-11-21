"use client";
import { Check, Copy, Share2, X } from "lucide-react";
import { useState } from "react";
import { Notice } from "@/components/ui";
import { sizeBucket, track } from "@/lib/analytics";
import { buildShareUrl } from "@/lib/share";
import { loadLists, loadProfile, type SavedList } from "@/lib/store";

// Lets a student send their answers and list to a parent's phone without an account.
export function ShareButton({ list }: { list?: SavedList }) {
  const [url, setUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [count, setCount] = useState(0);

  const open = async () => {
    setError(null);
    setCopied(false);
    const profile = loadProfile();
    if (!profile) { setError("Add your ranks first, then share."); return; }
    const chosen = list ?? loadLists()[0];
    const items = chosen?.items ?? [];
    setCount(items.length);
    try {
      setUrl(await buildShareUrl({ v: 1, profile, list: items.length ? { name: chosen.name, items } : null }));
    } catch {
      setError("This browser couldn’t make a link. Try another browser.");
    }
  };

  const copy = async () => {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      track("share_link_created", { has_list: count > 0, size: sizeBucket(count), method: "copy" });
    } catch {
      setError("Couldn’t copy automatically. Select the link and copy it.");
    }
  };

  const nativeShare = async () => {
    if (!url) return;
    try {
      await navigator.share({ title: "My college shortlist on Threshold", text: "Have a look at my shortlist and preference list.", url });
      track("share_link_created", { has_list: count > 0, size: sizeBucket(count), method: "native" });
    } catch {
      // The person closed the share sheet.
    }
  };

  const canNativeShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  return (
    <div className="no-print">
      <button type="button" className="btn btn-secondary" onClick={open} aria-expanded={url !== null}>
        <Share2 size={15} aria-hidden /> Share with family
      </button>
      {error && !url && <p className="mt-2 text-xs" style={{ color: "var(--ambitious)" }} role="alert">{error}</p>}
      {url && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center" role="dialog" aria-modal="true" aria-labelledby="share-title" onClick={() => setUrl(null)}>
          <div className="card w-full max-w-lg p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-3">
              <h2 id="share-title" className="text-lg">Share your shortlist</h2>
              <button type="button" className="btn btn-secondary !p-1.5" aria-label="Close" onClick={() => setUrl(null)}><X size={14} /></button>
            </div>
            <p className="mt-1 text-sm text-ink-2">
              The link opens your answers{count ? ` and your list of ${count} ${count === 1 ? "choice" : "choices"}` : ""} on another phone or computer. Nothing is uploaded: everything is inside the link itself.
            </p>
            <div className="mt-3"><Notice tone="warn">Anyone with this link can see your ranks, category and list. Send it only to people you trust, such as family or your counsellor.</Notice></div>
            <label className="mt-3 block text-xs text-ink-3" htmlFor="share-url">Link</label>
            <input id="share-url" readOnly value={url} onFocus={(e) => e.currentTarget.select()} className="mt-1 w-full truncate rounded-lg border border-line bg-[var(--surface-2)] px-3 py-2 text-sm" />
            {error && <p className="mt-2 text-xs" style={{ color: "var(--ambitious)" }} role="alert">{error}</p>}
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" className="btn btn-primary" onClick={copy}>{copied ? <Check size={15} aria-hidden /> : <Copy size={15} aria-hidden />} {copied ? "Copied" : "Copy link"}</button>
              {canNativeShare && <button type="button" className="btn btn-secondary" onClick={nativeShare}><Share2 size={15} aria-hidden /> Send…</button>}
            </div>
            <p className="mt-3 text-xs text-ink-3">The link is a snapshot. If you change your list later, share again.</p>
          </div>
        </div>
      )}
    </div>
  );
}
