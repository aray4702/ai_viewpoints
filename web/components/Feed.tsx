import Link from "next/link";

import { FilterBar } from "@/components/FilterBar";
import { ViewpointCard } from "@/components/ViewpointCard";
import { getFeed } from "@/lib/api";
import { feedHref, type Filters } from "@/lib/url";

/** Filterable, cursor-paginated viewpoint list. `base` is the page path the filters link to. */
export async function Feed({
  filters,
  cursor,
  base = "/",
  showFilterBar = true,
}: {
  filters: Filters;
  cursor?: string;
  base?: string;
  showFilterBar?: boolean;
}) {
  const page = await getFeed({ ...filters, cursor });
  const next = page.next_cursor
    ? `${feedHref(filters, base)}${feedHref(filters, base).includes("?") ? "&" : "?"}cursor=${page.next_cursor}`
    : null;

  return (
    <>
      {showFilterBar && <FilterBar key={JSON.stringify(filters)} filters={filters} base={base} />}
      {page.items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-10 text-center text-muted">
          No viewpoints match yet. New ones arrive as sources publish.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {page.items.map((v) => (
            <ViewpointCard key={v.id} v={v} filters={filters} />
          ))}
        </div>
      )}
      <div className="mt-8 flex justify-between text-sm">
        {cursor ? (
          <Link href={feedHref(filters, base)} className="text-muted hover:text-fg">
            ← Newest
          </Link>
        ) : (
          <span />
        )}
        {next && (
          <Link href={next} className="text-muted hover:text-fg">
            Older →
          </Link>
        )}
      </div>
    </>
  );
}
