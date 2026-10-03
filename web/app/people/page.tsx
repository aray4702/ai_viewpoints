import Link from "next/link";

import { getPeople } from "@/lib/api";

export const metadata = { title: "People" };

export default async function PeoplePage() {
  const people = await getPeople();
  return (
    <>
      <h1 className="mb-6 font-serif text-3xl font-semibold tracking-tight">People</h1>
      <ul className="grid gap-3 sm:grid-cols-2">
        {people.map((p) => (
          <li key={p.slug}>
            <Link
              href={`/people/${p.slug}`}
              className="block h-full rounded-xl border border-border bg-surface p-4 hover:border-accent"
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-medium">{p.name}</span>
                <span className="shrink-0 text-sm text-muted">
                  {p.viewpoint_count} {p.viewpoint_count === 1 ? "viewpoint" : "viewpoints"}
                </span>
              </div>
              {p.bio && <p className="mt-1 text-sm text-muted">{p.bio}</p>}
              {p.auto_added && <p className="mt-1 text-xs text-muted">Guest</p>}
              <div className="mt-2 flex flex-wrap gap-1.5">
                {p.domains.map((d) => (
                  <span key={d} className="rounded-full bg-accent-soft px-2 py-0.5 text-xs text-accent">
                    {d}
                  </span>
                ))}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
