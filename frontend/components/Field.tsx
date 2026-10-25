"use client";

import { type ComponentProps, useId } from "react";

/** Labelled text input. The label and hint are tied to the input explicitly, so screen readers announce them. */
export function Field({ label, hint, id, ...props }: ComponentProps<"input"> & { label: string; hint?: string }) {
  const auto = useId();
  const inputId = id ?? auto;
  return (
    <div className="block text-sm">
      <label htmlFor={inputId} className="mb-1 block font-medium">{label}</label>
      <input
        {...props}
        id={inputId}
        aria-describedby={hint ? `${inputId}-hint` : undefined}
        className="w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
      />
      {hint && <span id={`${inputId}-hint`} className="mt-1 block text-xs text-muted">{hint}</span>}
    </div>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
      {message}
    </p>
  );
}
