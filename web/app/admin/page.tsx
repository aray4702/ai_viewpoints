import { notFound } from "next/navigation";

import { AdminPanel } from "@/components/AdminPanel";
import { getMe, getPeople, getPerson } from "@/lib/api";

export const metadata = { title: "Admin" };

export default async function AdminPage() {
  const me = await getMe();
  if (!me?.is_admin) notFound();
  const people = await Promise.all((await getPeople()).map((p) => getPerson(p.slug)));
  people.sort((a, b) => a.name.localeCompare(b.name));
  return (
    <>
      <h1 className="mb-6 font-serif text-3xl font-semibold tracking-tight">Tracked people</h1>
      <AdminPanel people={people} />
    </>
  );
}
