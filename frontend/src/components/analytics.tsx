"use client";
import { Analytics, type BeforeSendEvent } from "@vercel/analytics/next";

// Only the path is counted. Query strings and the share link's #fragment, which holds a student's ranks, are removed first.
function stripUrl(event: BeforeSendEvent): BeforeSendEvent {
  try {
    const url = new URL(event.url);
    return { ...event, url: `${url.origin}${url.pathname}` };
  } catch {
    return event;
  }
}

export function UsageCounts() {
  return <Analytics beforeSend={stripUrl} />;
}
