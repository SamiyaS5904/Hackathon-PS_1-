"use client";

import { ChevronDown, Download, FileSpreadsheet, FileText, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

const NOUN: Record<string, [string, string]> = {
  section: ["section", "sections"], teacher: ["teacher", "teachers"], venue: ["room", "rooms"],
};

/** Secondary action: Excel / PDF for notice boards. Staff can also download every section, teacher or room. */
export function DownloadMenu({ view, entityId, entityName, canAll }: {
  view: string; entityId: string; entityName: string; canAll: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const get = async (key: string, format: "xlsx" | "pdf", all: boolean) => {
    setBusy(key);
    setError(null);
    try {
      await api.exportTimetable(format, view, all ? undefined : entityId);
      setOpen(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't download the file.");
    } finally {
      setBusy(null);
    }
  };

  const [one, many] = NOUN[view] ?? NOUN.section;
  const items: { key: string; label: string; format: "xlsx" | "pdf"; all: boolean }[] = [
    ...(entityId ? [
      { key: "xlsx-1", label: `${entityName || `This ${one}`}: Excel`, format: "xlsx" as const, all: false },
      { key: "pdf-1", label: `${entityName || `This ${one}`}: PDF`, format: "pdf" as const, all: false },
    ] : []),
    ...(canAll ? [
      { key: "xlsx-all", label: `All ${many}: Excel (one sheet each)`, format: "xlsx" as const, all: true },
      { key: "pdf-all", label: `All ${many}: PDF (one page each)`, format: "pdf" as const, all: true },
    ] : []),
  ];
  if (items.length === 0) return null;

  return (
    <div className="relative no-print" ref={ref}>
      <Button variant="ghost" onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open}>
        <Download size={16} aria-hidden /> Download <ChevronDown size={14} aria-hidden />
      </Button>
      {open && (
        <div role="menu" className="absolute right-0 z-30 mt-1 w-72 rounded-lg border border-border bg-surface p-1 shadow-lg">
          {items.map((i) => (
            <button
              key={i.key}
              role="menuitem"
              type="button"
              disabled={busy !== null}
              onClick={() => get(i.key, i.format, i.all)}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-surface-2 disabled:opacity-60"
            >
              {busy === i.key ? (
                <Loader2 size={16} className="animate-spin" aria-hidden />
              ) : i.format === "xlsx" ? (
                <FileSpreadsheet size={16} className="text-ok" aria-hidden />
              ) : (
                <FileText size={16} className="text-danger" aria-hidden />
              )}
              <span className="truncate">{i.label}</span>
            </button>
          ))}
          {error && <p className="px-3 py-2 text-xs text-danger" role="alert">{error}</p>}
          <p className="border-t border-border px-3 py-2 text-xs text-muted">Weekly timetable. One-day changes show in the app.</p>
        </div>
      )}
    </div>
  );
}
