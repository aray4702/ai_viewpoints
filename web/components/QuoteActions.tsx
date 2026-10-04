"use client";

import { useId, useState } from "react";

import { actionClass } from "@/lib/styles";

/**
 * The row under a quote: the source link (passed as children) and, for non-English quotes,
 * a Translate button that reveals the English translation above the row.
 */
export function QuoteActions({
  translation,
  children,
}: {
  translation: string | null;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <>
      {translation && open && (
        <span id={id} lang="en" className="mt-1 block not-italic text-muted">
          <span className="sr-only">Translation: </span>“{translation}”
        </span>
      )}
      <span className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm not-italic">
        {children}
        {translation && (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={id}
            onClick={() => setOpen(!open)}
            className={actionClass}
          >
            {open ? "Hide translation" : "Translate"}
          </button>
        )}
      </span>
    </>
  );
}
