/** Build feed URLs from filter state. Shared by server and client components. */

export type Filters = { person: string[]; tag: string[]; domain: string[]; q: string };

export const EMPTY: Filters = { person: [], tag: [], domain: [], q: "" };

export function feedHref(f: Filters, base = "/"): string {
  const qs = new URLSearchParams();
  for (const key of ["person", "tag", "domain"] as const) for (const v of f[key]) qs.append(key, v);
  if (f.q) qs.set("q", f.q);
  const s = qs.toString();
  return s ? `${base}?${s}` : base;
}

export function withFilter(f: Filters, key: "person" | "tag" | "domain", value: string): Filters {
  return f[key].includes(value) ? f : { ...f, [key]: [...f[key], value] };
}

export function withoutFilter(f: Filters, key: "person" | "tag" | "domain", value: string): Filters {
  return { ...f, [key]: f[key].filter((v) => v !== value) };
}
