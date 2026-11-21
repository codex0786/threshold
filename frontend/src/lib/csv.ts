// A tiny CSV writer for downloads. Quotes every field, and neutralises cells a spreadsheet would run as a formula.
export function toCsv(rows: (string | number | null | undefined)[][]): string {
  const cell = (v: string | number | null | undefined) => {
    let text = v == null ? "" : String(v);
    if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
    return `"${text.replace(/"/g, '""')}"`;
  };
  return rows.map((r) => r.map(cell).join(",")).join("\r\n");
}

export function downloadCsv(filename: string, rows: (string | number | null | undefined)[][]) {
  // A byte-order mark lets Excel read Indian institute names and the rupee sign correctly.
  const blob = new Blob(["﻿", toCsv(rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
