import { Feed } from "@/components/Feed";
import { list } from "@/lib/api";

export default async function Home(props: PageProps<"/">) {
  const sp = await props.searchParams;
  const filters = {
    person: list(sp.person),
    tag: list(sp.tag),
    domain: list(sp.domain),
    q: typeof sp.q === "string" ? sp.q : "",
  };
  const cursor = typeof sp.cursor === "string" ? sp.cursor : undefined;

  return (
    <>
      <section className="mb-8">
        <h1 className="font-serif text-3xl font-semibold tracking-tight sm:text-4xl">
          What people think, with sources.
        </h1>
        <p className="mt-2 text-muted">
          Novel, practical viewpoints mined from the talks, podcasts, posts, and papers of people
          worth listening to. Each comes with the exact quote and a link to the source.
        </p>
      </section>
      <Feed filters={filters} cursor={cursor} />
    </>
  );
}
