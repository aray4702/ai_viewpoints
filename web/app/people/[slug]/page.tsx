import { notFound } from "next/navigation";

import { Feed } from "@/components/Feed";
import { ApiError, getPerson, list } from "@/lib/api";

const PLATFORM_LABEL: Record<string, string> = {
  youtube: "YouTube",
  podcast: "Podcast",
  blog: "Blog",
  arxiv: "arXiv",
  reddit: "Reddit",
  x: "X",
};

function sourceHref(platform: string, handle: string): string | null {
  if (handle.startsWith("http")) return handle;
  if (platform === "youtube") return `https://www.youtube.com/${handle}`;
  if (platform === "x") return `https://x.com/${handle}`;
  if (platform === "reddit") return `https://www.reddit.com/user/${handle}`;
  return null;
}

export default async function PersonPage(props: PageProps<"/people/[slug]">) {
  const { slug } = await props.params;
  const sp = await props.searchParams;
  const person = await getPerson(slug).catch((e) => {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  });
  const filters = { person: [slug], tag: list(sp.tag), domain: list(sp.domain), q: "" };

  return (
    <>
      <section className="mb-8">
        <h1 className="font-serif text-3xl font-semibold tracking-tight">{person.name}</h1>
        {person.bio && <p className="mt-2 text-muted">{person.bio}</p>}
        {person.auto_added && (
          <p className="mt-2 text-sm text-muted">
            Added automatically after appearing as a guest. Their viewpoints come from other
            people&apos;s shows and posts.
          </p>
        )}
        <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {person.sources
            .filter((s) => s.active)
            .map((s) => {
              const href = sourceHref(s.platform, s.handle);
              const label = PLATFORM_LABEL[s.platform] ?? s.platform;
              return (
                <li key={s.id} className="text-muted">
                  {href ? (
                    <a href={href} target="_blank" rel="noreferrer" className="hover:text-accent">
                      {label} ↗
                    </a>
                  ) : (
                    label
                  )}
                </li>
              );
            })}
        </ul>
      </section>
      <Feed
        filters={filters}
        cursor={typeof sp.cursor === "string" ? sp.cursor : undefined}
        base={`/people/${slug}`}
        showFilterBar={filters.tag.length + filters.domain.length > 0}
      />
    </>
  );
}
