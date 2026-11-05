"use client";
import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { loadCompare } from "@/lib/store";

const LINKS = [
  { href: "/recommendations", label: "My shortlist" },
  { href: "/colleges", label: "Colleges" },
  { href: "/compare", label: "Compare" },
  { href: "/preferences", label: "Preference list" },
  { href: "/finance", label: "Costs" },
  { href: "/report", label: "Parent report" },
  { href: "/methodology", label: "Methodology" },
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
  const items = LINKS.map((l) => (
    <Link key={l.href} href={l.href} aria-current={pathname.startsWith(l.href) ? "page" : undefined}
      className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${pathname.startsWith(l.href) ? "bg-brand-soft text-brand" : "text-ink-2 hover:bg-surface-2 hover:text-ink"}`}>
      {l.label}{l.href === "/compare" && count > 0 ? <span className="tnum ml-1 opacity-70">({count})</span> : null}
    </Link>
  ));
  return (
    <header className="no-print sticky top-0 z-20 border-b border-line bg-surface/85 backdrop-blur-lg">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <Link href="/" aria-label="Threshold home"><Logo /></Link>
        <nav className="hidden items-center gap-0.5 lg:flex" aria-label="Main">{items}
          <Link href="/onboarding" className="btn btn-primary ml-2 !py-1.5 text-sm">Find my best fit</Link>
        </nav>
        <button className="btn btn-secondary !p-2 lg:hidden" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>
      {open && (
        <nav className="rise flex flex-col gap-1 border-t border-line px-4 py-3 lg:hidden" aria-label="Mobile">{items}
          <Link href="/onboarding" className="btn btn-primary mt-1">Find my best fit</Link>
        </nav>
      )}
    </header>
  );
}

export function Footer() {
  return (
    <footer className="no-print border-t border-line bg-surface">
      <div className="mx-auto max-w-6xl px-4 py-8 text-sm text-ink-3">
        <Logo />
        <p className="mt-3 max-w-3xl">Threshold is an independent decision aid and is not affiliated with JoSAA, CSAB, NTA or any institute. Always confirm details on official counselling websites before making a decision.</p>
        <p className="mt-2"><Link href="/methodology" className="underline underline-offset-2 hover:text-brand">Data sources and methodology</Link></p>
      </div>
    </footer>
  );
}
