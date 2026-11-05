"use client";
import { Notice } from "@/components/ui";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto max-w-xl px-4 py-16">
      <h1 className="mb-4 text-3xl">This page couldn’t load</h1>
      <Notice tone="error">The data service may be unavailable. Your answers are still saved on this device.</Notice>
      <button className="btn btn-primary mt-4" onClick={reset}>Try again</button>
    </div>
  );
}
