import { ViewpointCard } from "@/components/ViewpointCard";
import { search } from "@/lib/api";

export const metadata = { title: "Search" };

export default async function SearchPage(props: PageProps<"/search">) {
  const sp = await props.searchParams;
  const q = typeof sp.q === "string" ? sp.q.trim() : "";
  const results = q ? await search(q) : [];

  return (
    <>
      <h1 className="mb-4 font-serif text-3xl font-semibold tracking-tight">Search</h1>
      <form action="/search" className="mb-6">
        <label htmlFor="search-q" className="sr-only">
          Search
        </label>
        <input
          id="search-q"
          name="q"
          defaultValue={q}
          autoFocus
          placeholder="Ask about an idea, e.g. will GPU prices fall?"
          className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 outline-none placeholder:text-muted focus:border-accent"
        />
      </form>
      {q && results.length === 0 && <p className="text-muted">No viewpoints found for “{q}”.</p>}
      <div className="flex flex-col gap-4">
        {results.map((v) => (
          <ViewpointCard key={v.id} v={v} />
        ))}
      </div>
    </>
  );
}
