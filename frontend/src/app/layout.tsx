import type { Metadata } from "next";
import { Bricolage_Grotesque, Public_Sans } from "next/font/google";
import Script from "next/script";
import type { ReactNode } from "react";
import { Footer, Nav } from "@/components/nav";
import "./globals.css";

const body = Public_Sans({ subsets: ["latin"], variable: "--font-body" });
const heading = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-heading" });

export const metadata: Metadata = {
  title: "Threshold: college and branch decisions, with evidence",
  description: "Compare colleges and branches using official JoSAA cutoffs and clearly sourced data.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-IN" className={`${body.variable} ${heading.variable}`} suppressHydrationWarning>
      <body className="flex min-h-screen flex-col">
        {/* Scroll reveals only hide content once we know JavaScript can show it again. */}
        <Script id="js-flag" strategy="beforeInteractive">{"document.documentElement.classList.add('js')"}</Script>
        <Nav />
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
