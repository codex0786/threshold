"use client";
// A share link carries a student's answers and one preference list inside the URL's #fragment.
// Browsers never send the fragment to a server, so nothing is stored anywhere and no account is needed.
import { z } from "zod";
import type { Profile } from "./api";
import type { CompareEntry } from "./store";

const MAX_ITEMS = 300;
const MAX_ENCODED = 60_000;
const VERSION = 1;

const ranks = z.record(z.string(), z.number().int().positive().nullable());
const strings = z.array(z.string().max(80)).max(60);
const profileSchema = z.object({
  category: z.string().max(20), gender: z.string().max(20), is_pwd: z.boolean(),
  eligibility_state: z.string().max(80), class12_status: z.string().max(30),
  main: ranks, advanced: ranks, advanced_qualified: z.boolean(),
  preferred_branches: strings, acceptable_branches: strings, avoid_branches: strings,
  preferred_types: strings, preferred_states: strings, career_goals: strings,
  annual_budget_inr: z.number().nonnegative().nullable(),
  priorities: z.record(z.string(), z.number().min(0).max(100)),
});
const entrySchema = z.object({ id: z.number().int().positive(), label: z.string().max(200) });
const payloadSchema = z.object({
  v: z.literal(VERSION),
  profile: profileSchema,
  list: z.object({ name: z.string().max(60), items: z.array(entrySchema).max(MAX_ITEMS) }).nullable(),
});

export type SharePayload = { v: typeof VERSION; profile: Profile; list: { name: string; items: CompareEntry[] } | null };

function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function fromBase64Url(text: string): Uint8Array {
  const b64 = text.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((text.length + 3) % 4);
  const binary = atob(b64);
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

async function pipe(bytes: Uint8Array, stream: CompressionStream | DecompressionStream): Promise<Uint8Array> {
  const out = new Blob([bytes as BlobPart]).stream().pipeThrough(stream);
  return new Uint8Array(await new Response(out).arrayBuffer());
}
const canCompress = () => typeof CompressionStream !== "undefined" && typeof DecompressionStream !== "undefined";

// "z" = deflate-raw then base64url; "j" = plain JSON in base64url for browsers without compression streams.
export async function encodeShare(payload: SharePayload): Promise<string> {
  const json = new TextEncoder().encode(JSON.stringify(payload));
  if (canCompress()) return `z${toBase64Url(await pipe(json, new CompressionStream("deflate-raw")))}`;
  return `j${toBase64Url(json)}`;
}

export async function decodeShare(encoded: string): Promise<SharePayload | null> {
  if (!encoded || encoded.length > MAX_ENCODED) return null;
  try {
    const kind = encoded[0];
    let bytes = fromBase64Url(encoded.slice(1));
    if (kind === "z") {
      if (!canCompress()) return null;
      bytes = await pipe(bytes, new DecompressionStream("deflate-raw"));
    } else if (kind !== "j") return null;
    if (bytes.length > 400_000) return null;
    const parsed = payloadSchema.safeParse(JSON.parse(new TextDecoder().decode(bytes)));
    return parsed.success ? (parsed.data as SharePayload) : null;
  } catch {
    return null;
  }
}

export async function buildShareUrl(payload: SharePayload): Promise<string> {
  return `${window.location.origin}/share#d=${await encodeShare(payload)}`;
}

export function readShareFragment(): string {
  const match = window.location.hash.match(/[#&]d=([^&]+)/);
  return match ? match[1] : "";
}
