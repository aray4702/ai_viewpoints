"use client";

import { useId, useState } from "react";

/** English translation of a non-English quote, hidden until the reader asks for it. */
export function QuoteTranslation({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <>
      {open && (
        <span id={id} lang="en" className="mt-1 block not-italic text-muted">
          <span className="sr-only">Translation: </span>“{text}”
        </span>
      )}
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
        className="mt-1 block text-sm not-italic text-muted underline-offset-2 hover:text-accent hover:underline"
      >
        {open ? "Hide translation" : "Translate"}
      </button>
    </>
  );
}
