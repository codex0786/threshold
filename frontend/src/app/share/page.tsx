"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Notice, PageHeader, Skeleton } from "@/components/ui";
import { num } from "@/lib/api";
import { track } from "@/lib/analytics";
import { decodeShare, readShareFragment, type SharePayload } from "@/lib/share";
import { clearDraft, importList, loadProfile, saveProfile } from "@/lib/store";

const PREVIEW = 8;
const GENDER: Record<string, string> = { female: "Female", male: "Male", other: "Other" };
const STATUS: Record<string, string> = { meets: "Meets the Class XII criterion", does_not_meet: "Doesn’t meet the Class XII criterion", unknown: "Class XII criterion not known yet" };

function RankLine({ label, ranks }: { label: string; ranks: Record<string, number | null> }) {
  const entries = Object.entries(ranks).filter(([, v]) => v != null) as [string, number][];
  if (!entries.length) return null;
  const name: Record<string, string> = { crl: "CRL", category_rank: "category", crl_pwd: "CRL-PwD", category_pwd_rank: "category-PwD" };
  return <p><span className="text-ink-3">{label}:</span> <span className="tnum">{entries.map(([k, v]) => `${num(v)} (${name[k] ?? k})`).join(", ")}</span></p>;
}

export default function SharePage() {
  const router = useRouter();
  const [payload, setPayload] = useState<SharePayload | null | undefined>(undefined);
  const [hasOwn, setHasOwn] = useState(false);

  useEffect(() => {
    const fragment = readShareFragment();
    setHasOwn(loadProfile() !== null);
    decodeShare(fragment).then((p) => {
      setPayload(p);
      track("share_link_opened", { valid: p !== null });
    });
  }, []);

  const importIt = () => {
    if (!payload) return;
    saveProfile(payload.profile);
    clearDraft();
    const listId = payload.list?.items.length ? importList(payload.list.name, payload.list.items) : null;
    track("share_link_imported", { has_list: listId !== null });
    // Drop the fragment, so the ranks don't stay in this tab's address bar and history entry.
    window.history.replaceState(null, "", "/share");
    router.push(listId ? `/preferences?list=${encodeURIComponent(listId)}` : "/recommendations");
  };

  if (payload === undefined) return <div className="mx-auto max-w-2xl px-4 py-10"><Skeleton /></div>;
  if (payload === null) {
    return (
      <div className="mx-auto max-w-xl px-4 py-16 text-center">
        <h1 className="text-3xl">This link doesn’t open</h1>
        <p className="mt-2 text-ink-2">It may have been cut short when it was copied. Ask for the link again, and copy all of it.</p>
        <Link href="/" className="btn btn-primary mt-5">Go to Threshold</Link>
      </div>
    );
  }

  const { profile, list } = payload;
  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <PageHeader title="A shortlist was shared with you" intro="Someone sent you their answers and preference list from Threshold. Nothing was uploaded: it all came inside the link." />
      <section className="card p-5">
        <h2 className="text-lg">Their answers</h2>
        <div className="mt-2 space-y-1 text-sm">
          <p><span className="text-ink-3">Category:</span> {profile.category}{profile.is_pwd ? ", PwD" : ""} · {GENDER[profile.gender] ?? profile.gender}</p>
          <p><span className="text-ink-3">Class XII state:</span> {profile.eligibility_state} · {STATUS[profile.class12_status] ?? profile.class12_status}</p>
          <RankLine label="JEE Main" ranks={profile.main} />
          {profile.advanced_qualified && <RankLine label="JEE Advanced" ranks={profile.advanced} />}
          {profile.preferred_branches.length > 0 && <p><span className="text-ink-3">Preferred branches:</span> {profile.preferred_branches.join(", ")}</p>}
        </div>
      </section>

      {list && list.items.length > 0 && (
        <section className="card mt-4 p-5">
          <h2 className="text-lg">{list.name} <span className="tnum text-base font-normal text-ink-3">({num(list.items.length)} {list.items.length === 1 ? "choice" : "choices"})</span></h2>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
            {list.items.slice(0, PREVIEW).map((item) => <li key={item.id}>{item.label}</li>)}
          </ol>
          {list.items.length > PREVIEW && <p className="mt-1 text-xs text-ink-3">and {num(list.items.length - PREVIEW)} more.</p>}
        </section>
      )}

      <div className="mt-5 space-y-3">
        {hasOwn && <Notice tone="warn">Opening this replaces the ranks and answers saved in this browser. Your own lists are kept, and theirs is added beside them.</Notice>}
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn btn-primary" onClick={importIt}>{list?.items.length ? "Open their list here" : "Open their shortlist here"}</button>
          <Link href="/" className="btn btn-secondary">Not now</Link>
        </div>
        <p className="text-xs text-ink-3">Bands and checks are worked out again from current data when you open it, so they may differ slightly from what they saw.</p>
      </div>
    </div>
  );
}
