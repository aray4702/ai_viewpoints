import "server-only";

import { cookies } from "next/headers";

import type { PersonDetail, Person, Tag, User, Viewpoint, ViewpointPage } from "./types";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** Server-side fetch to FastAPI, forwarding the visitor's session cookie. */
async function api<T>(path: string): Promise<T> {
  const cookieHeader = (await cookies()).toString();
  const res = await fetch(`${API_URL}${path}`, {
    headers: cookieHeader ? { cookie: cookieHeader } : {},
    cache: "no-store",
  });
  if (!res.ok) throw new ApiError(res.status, `${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export type FeedParams = {
  person?: string[];
  tag?: string[];
  domain?: string[];
  q?: string;
  cursor?: string;
};

export function feedQuery(p: FeedParams): URLSearchParams {
  const qs = new URLSearchParams();
  for (const key of ["person", "tag", "domain"] as const) {
    for (const v of p[key] ?? []) qs.append(key, v);
  }
  if (p.q) qs.set("q", p.q);
  if (p.cursor) qs.set("cursor", p.cursor);
  return qs;
}

export const getFeed = (p: FeedParams) => api<ViewpointPage>(`/api/viewpoints?${feedQuery(p)}`);
export const getViewpoint = (id: string) => api<Viewpoint>(`/api/viewpoints/${encodeURIComponent(id)}`);
export const search = (q: string) => api<Viewpoint[]>(`/api/search?q=${encodeURIComponent(q)}`);
export const getPeople = () => api<Person[]>("/api/people");
export const getPerson = (slug: string) => api<PersonDetail>(`/api/people/${encodeURIComponent(slug)}`);
export const getTags = () => api<Tag[]>("/api/tags?limit=30");

export async function getMe(): Promise<User | null> {
  try {
    return await api<User>("/api/auth/me");
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return null;
    throw e;
  }
}

/** Normalize a searchParams value to a list. */
export function list(v: string | string[] | undefined): string[] {
  return v === undefined ? [] : Array.isArray(v) ? v : [v];
}
