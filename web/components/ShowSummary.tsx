"use client";

import { useId, useState } from "react";

import { actionClass } from "@/lib/styles";

/** The viewpoint's summary, hidden until the reader asks for it. */
export function ShowSummary({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
        className={`mt-2 text-sm ${actionClass}`}
      >
        {open ? "Hide summary" : "Show summary"}
      </button>
      {open && (
        <p id={id} className="mt-1 leading-relaxed text-muted">
          {text}
        </p>
      )}
    </>
  );
}
