"use client";
// Per-browser convenience storage. The profile stays on this device until the student asks for results.
import type { Profile } from "./api";

const PROFILE_KEY = "threshold.profile.v1";
const DRAFT_KEY = "threshold.onboarding.v1";
const COMPARE_KEY = "threshold.compare.v1";

function read<T>(key: string): T | null {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}
function write(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage can be blocked. The page still works for the current visit.
  }
}

export const loadProfile = () => read<Profile>(PROFILE_KEY);
export const saveProfile = (p: Profile) => write(PROFILE_KEY, p);
export const loadDraft = <T,>() => read<T>(DRAFT_KEY);
export const saveDraft = (d: unknown) => write(DRAFT_KEY, d);

// Removes everything Threshold keeps in this browser: answers, ranks, priorities, compare selection and lists.
export function clearAllData() {
  try {
    for (const key of Object.keys(window.localStorage)) {
      if (key.startsWith("threshold.")) window.localStorage.removeItem(key);
    }
  } catch {
    // Storage can be blocked, in which case nothing was saved.
  }
  window.dispatchEvent(new Event("threshold-compare"));
}

export type CompareEntry = { id: number; label: string };
export const loadCompare = () => read<CompareEntry[]>(COMPARE_KEY) ?? [];
export function toggleCompare(entry: CompareEntry): CompareEntry[] {
  const current = loadCompare();
  const next = current.some((e) => e.id === entry.id)
    ? current.filter((e) => e.id !== entry.id)
    : current.length >= 4 ? current : [...current, entry];
  write(COMPARE_KEY, next);
  window.dispatchEvent(new Event("threshold-compare"));
  return next;
}
export function clearCompare() {
  write(COMPARE_KEY, []);
  window.dispatchEvent(new Event("threshold-compare"));
}

export type SavedList = { id: string; name: string; items: CompareEntry[] };
const LISTS_KEY = "threshold.lists.v1";
export function loadLists(): SavedList[] {
  const lists = read<SavedList[]>(LISTS_KEY);
  return lists?.length ? lists : [{ id: "default", name: "My list", items: [] }];
}
export const saveLists = (lists: SavedList[]) => write(LISTS_KEY, lists);
export function addToList(entry: CompareEntry) {
  const lists = loadLists();
  if (!lists[0].items.some((e) => e.id === entry.id)) lists[0].items.push(entry);
  saveLists(lists);
}
