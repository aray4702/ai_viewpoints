import Link from "next/link";
import { notFound } from "next/navigation";

import { ViewpointCard } from "@/components/ViewpointCard";
import { ApiError, getViewpoint } from "@/lib/api";

export default async function ViewpointPage(props: PageProps<"/v/[id]">) {
  const { id } = await props.params;
  const v = await getViewpoint(id).catch((e) => {
    if (e instanceof ApiError && (e.status === 404 || e.status === 422)) notFound();
    throw e;
  });
  return (
    <>
      <Link href="/" className="mb-4 inline-block text-sm text-muted hover:text-fg">
        ← All viewpoints
      </Link>
      <ViewpointCard v={v} />
      <p className="mt-4 text-sm text-muted">
        More from{" "}
        <Link href={`/people/${v.person.slug}`} className="text-fg hover:text-accent">
          {v.person.name}
        </Link>
      </p>
    </>
  );
}
