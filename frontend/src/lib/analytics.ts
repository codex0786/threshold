"use client";
// Anonymous usage counts through Vercel Web Analytics, which sets no cookies.
// Events carry only coarse, non-identifying properties: never ranks, category, state, gender or list contents.
import { track as vercelTrack } from "@vercel/analytics";

type Events = {
  onboarding_completed: Record<string, never>;
  shortlist_generated: { order: "top" | "fit" };
  list_item_added: Record<string, never>;
  bands_explainer_opened: { page: "shortlist" | "preferences" };
  report_opened: Record<string, never>;
  share_link_created: { has_list: boolean; size: SizeBucket; method: "copy" | "native" };
  share_link_opened: { valid: boolean };
  share_link_imported: { has_list: boolean };
  rank_estimated: { year: number };
  rank_estimate_used: Record<string, never>;
  list_built: { order: "top" | "fit"; size: SizeBucket; safety_net: number };
  list_exported: { size: SizeBucket };
  round_advice_viewed: { round: number; suggestion: "freeze" | "float" | "slide" };
};

export type SizeBucket = "0" | "1-10" | "11-30" | "31-60" | "60+";
export function sizeBucket(n: number): SizeBucket {
  if (n === 0) return "0";
  if (n <= 10) return "1-10";
  if (n <= 30) return "11-30";
  if (n <= 60) return "31-60";
  return "60+";
}

export function track<E extends keyof Events>(event: E, props?: Events[E]) {
  try {
    vercelTrack(event, props as Record<string, string | number | boolean> | undefined);
  } catch {
    // Counting must never break the page.
  }
}
