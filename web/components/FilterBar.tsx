"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { feedHref, withoutFilter, type Filters } from "@/lib/url";

export function FilterBar({ filters, base = "/" }: { filters: Filters; base?: string }) {
  const router = useRouter();
  const [q, setQ] = useState(filters.q);
  const active = (["person", "domain", "tag"] as const).flatMap((key) =>
    filters[key].map((value) => ({ key, value })),
  );

  return (
    <div className="mb-6">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          router.push(feedHref({ ...filters, q: q.trim() }, base));
        }}
      >
        <label htmlFor="feed-q" className="sr-only">
          Search viewpoints
        </label>
        <input
          id="feed-q"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search viewpoints, e.g. inference costs"
          className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 outline-none placeholder:text-muted focus:border-accent"
        />
      </form>
      {(active.length > 0 || filters.q) && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">Filtered by</span>
          {active.map(({ key, value }) => (
            <Link
              key={`${key}:${value}`}
              href={feedHref(withoutFilter(filters, key, value), base)}
              className="rounded-full bg-accent-soft px-3 py-0.5 text-accent hover:line-through"
              aria-label={`Remove filter ${key} ${value}`}
            >
              {key === "person" ? "@" : ""}
              {value} ×
            </Link>
          ))}
          <Link href={base} className="text-muted underline-offset-2 hover:underline">
            Clear all
          </Link>
        </div>
      )}
    </div>
  );
}
