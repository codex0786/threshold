"use client";
import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ResetData } from "@/components/reset-data";
import { loadCompare } from "@/lib/store";

// The site is organised by exam. The top bar stays short; tools that only exist for JoSAA live in the JEE bar below it.
const LINKS = [
  { href: "/exams", label: "Exams" },
  { href: "/methodology", label: "How it works" },
];

// Pages that belong to the JEE (JoSAA) workspace, and the tools shown in its bar.
const JEE_PATHS = ["/onboarding", "/recommendations", "/colleges", "/programmes", "/compare", "/preferences", "/rounds", "/finance", "/report", "/assistant", "/rank-estimator", "/share"];
const JEE_TOOLS = [
  { href: "/recommendations", label: "Shortlist" },
  { href: "/colleges", label: "Colleges" },
  { href: "/compare", label: "Compare" },
  { href: "/preferences", label: "Preference list" },
  { href: "/rounds", label: "After a round" },
  { href: "/finance", label: "Costs" },
  { href: "/report", label: "Parent report" },
  { href: "/assistant", label: "Ask" },
];

function Logo() {
  return (
    <span className="inline-flex items-center gap-2 font-display text-xl font-bold tracking-tight">
      <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden>
        <defs><linearGradient id="logo" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#4f46e5" /><stop offset="1" stopColor="#0d9488" /></linearGradient></defs>
        <rect width="26" height="26" rx="7" fill="url(#logo)" />
        <path d="M8 21V7.5A1.5 1.5 0 0 1 9.5 6h7A1.5 1.5 0 0 1 18 7.5V21" fill="none" stroke="#fff" strokeWidth="2" />
        <path d="M5 21h16" stroke="#fbbf24" strokeWidth="2" strokeLinecap="round" />
        <circle cx="15" cy="14" r="1.3" fill="#fbbf24" />
      </svg>
      Threshold
    </span>
  );
}

const active = (pathname: string, href: string) => pathname === href || pathname.startsWith(`${href}/`);

function JeeBar({ pathname, count }: { pathname: string; count: number }) {
  const bar = useRef<HTMLElement>(null);
  // On narrow screens the bar scrolls; keep the current tool in view.
  useEffect(() => { bar.current?.querySelector('[aria-current="page"]')?.scrollIntoView({ block: "nearest", inline: "center" }); }, [pathname]);
  return (
    <div className="border-t border-line bg-surface/70">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4">
        <Link href="/recommendations" className="shrink-0 py-2 text-xs font-bold uppercase tracking-[0.08em] text-brand">JEE · JoSAA</Link>
        <span className="h-4 w-px shrink-0 bg-line" aria-hidden />
        <nav ref={bar} aria-label="JEE tools" className="-mx-1 flex min-w-0 gap-0.5 overflow-x-auto py-1.5 [mask-image:linear-gradient(to_right,#000_82%,transparent)] [scrollbar-width:none] md:[mask-image:none]">
          {JEE_TOOLS.map((t) => (
            <Link key={t.href} href={t.href} aria-current={active(pathname, t.href) ? "page" : undefined}
              className={`shrink-0 rounded-md px-2.5 py-1 text-sm transition-colors ${active(pathname, t.href) ? "bg-brand-soft font-medium text-brand" : "text-ink-2 hover:bg-surface-2 hover:text-ink"}`}>
              {t.label}{t.href === "/compare" && count > 0 ? <span className="tnum ml-1 opacity-70">({count})</span> : null}
            </Link>
          ))}
        </nav>
      </div>
    </div>
  );
}

export function Nav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(0);
  useEffect(() => {
    const sync = () => setCount(loadCompare().length);
    sync();
    window.addEventListener("threshold-compare", sync);
    return () => window.removeEventListener("threshold-compare", sync);
  }, []);
  useEffect(() => setOpen(false), [pathname]);
  const inJee = JEE_PATHS.some((p) => active(pathname, p));
  const examsActive = active(pathname, "/exams") || inJee;
  const items = LINKS.map((l) => {
    const on = l.href === "/exams" ? examsActive : active(pathname, l.href);
    return (
      <Link key={l.href} href={l.href} aria-current={on ? "page" : undefined}
        className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${on ? "bg-brand-soft text-brand" : "text-ink-2 hover:bg-surface-2 hover:text-ink"}`}>
        {l.label}
      </Link>
    );
  });
  return (
    <header className="no-print sticky top-0 z-20 border-b border-line bg-surface/85 backdrop-blur-lg">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        <Link href="/" aria-label="Threshold home"><Logo /></Link>
        <nav className="hidden items-center gap-1 sm:flex" aria-label="Main">{items}
          <Link href="/#start" className="btn btn-primary ml-2 !py-1.5 text-sm">Choose your exam</Link>
        </nav>
        <button className="btn btn-secondary !p-2 sm:hidden" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>
      {open && (
        <nav className="rise flex flex-col gap-1 border-t border-line px-4 py-3 sm:hidden" aria-label="Mobile">{items}
          <Link href="/#start" className="btn btn-primary mt-1">Choose your exam</Link>
        </nav>
      )}
      {inJee && <JeeBar pathname={pathname} count={count} />}
    </header>
  );
}

export function Footer() {
  return (
    <footer className="no-print border-t border-line bg-surface">
      <div className="mx-auto max-w-6xl px-4 py-8 text-sm text-ink-3">
        <Logo />
        <p className="mt-3 max-w-3xl">Threshold is an independent decision aid and is not affiliated with any counselling authority (JoSAA, CSAB, MCC, KEA, AKTU, the CET Cell, the Consortium of NLUs, CCMT) or any institute. Always confirm details on official counselling websites before making a decision.</p>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
          <Link href="/exams" className="underline underline-offset-2 hover:text-brand">All exams</Link>
          <Link href="/methodology" className="underline underline-offset-2 hover:text-brand">Data sources and methodology</Link>
          <ResetData label="Clear my saved data" className="underline underline-offset-2 hover:text-brand" />
        </div>
      </div>
    </footer>
  );
}
