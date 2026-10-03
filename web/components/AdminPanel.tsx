"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { PersonDetail, Platform } from "@/lib/types";

const PLATFORMS: { value: Platform; hint: string }[] = [
  { value: "youtube", hint: "@handle" },
  { value: "blog", hint: "feed URL" },
  { value: "podcast", hint: "podcast RSS URL" },
  { value: "arxiv", hint: 'au:"First Last"' },
  { value: "reddit", hint: "username" },
  { value: "x", hint: "handle" },
];

const input =
  "rounded-md border border-border bg-surface px-3 py-1.5 text-sm outline-none focus:border-accent";
const button = "rounded-md bg-fg px-3 py-1.5 text-sm font-medium text-bg hover:opacity-90";

async function send(method: string, url: string, body: unknown): Promise<string | null> {
  const res = await fetch(url, {
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.ok) return null;
  const data = await res.json().catch(() => ({}));
  return typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`;
}

function AddSource({ slug, onDone }: { slug: string; onDone: (err: string | null) => void }) {
  const [platform, setPlatform] = useState<Platform>("youtube");
  const [handle, setHandle] = useState("");
  const [interval, setInterval] = useState(360);
  return (
    <form
      className="mt-3 flex flex-wrap gap-2"
      onSubmit={async (e) => {
        e.preventDefault();
        const err = await send("POST", `/api/people/${slug}/sources`, {
          platform,
          handle: handle.trim(),
          poll_interval_min: interval,
        });
        if (!err) setHandle("");
        onDone(err);
      }}
    >
      <select
        aria-label="Platform"
        className={input}
        value={platform}
        onChange={(e) => setPlatform(e.target.value as Platform)}
      >
        {PLATFORMS.map((p) => (
          <option key={p.value} value={p.value}>
            {p.value}
          </option>
        ))}
      </select>
      <input
        aria-label="Handle or URL"
        required
        className={`${input} min-w-48 flex-1`}
        placeholder={PLATFORMS.find((p) => p.value === platform)?.hint}
        value={handle}
        onChange={(e) => setHandle(e.target.value)}
      />
      <input
        aria-label="Poll interval in minutes"
        type="number"
        min={5}
        className={`${input} w-24`}
        value={interval}
        onChange={(e) => setInterval(Number(e.target.value))}
      />
      <button className={button}>Add source</button>
    </form>
  );
}

export function AdminPanel({ people }: { people: PersonDetail[] }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [bio, setBio] = useState("");
  const [domains, setDomains] = useState("");

  const done = (err: string | null) => {
    setError(err);
    if (!err) router.refresh();
  };

  return (
    <div className="flex flex-col gap-6">
      {error && (
        <p role="alert" className="rounded-md bg-rose-100 px-3 py-2 text-sm text-rose-800">
          {error}
        </p>
      )}

      <form
        className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4"
        onSubmit={async (e) => {
          e.preventDefault();
          const slug = name.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
          const err = await send("POST", "/api/people", {
            name: name.trim(),
            slug,
            bio: bio.trim() || null,
            domains: domains.split(",").map((d) => d.trim().toLowerCase()).filter(Boolean),
          });
          if (!err) {
            setName("");
            setBio("");
            setDomains("");
          }
          done(err);
        }}
      >
        <h2 className="font-medium">Add a person</h2>
        <input aria-label="Name" required placeholder="Name" className={input} value={name} onChange={(e) => setName(e.target.value)} />
        <input aria-label="Bio" placeholder="One-line bio" className={input} value={bio} onChange={(e) => setBio(e.target.value)} />
        <input
          aria-label="Domains"
          placeholder="Domains, comma separated (ai, semiconductors, investment)"
          className={input}
          value={domains}
          onChange={(e) => setDomains(e.target.value)}
        />
        <button className={`${button} self-start`}>Add person</button>
      </form>

      {people.map((p) => (
        <section key={p.slug} className="rounded-xl border border-border bg-surface p-4">
          <h2 className="font-medium">
            {p.name}{" "}
            <span className="text-sm font-normal text-muted">
              · {p.viewpoint_count} viewpoints{p.auto_added && " · added as a guest"}
            </span>
          </h2>
          <ul className="mt-2 flex flex-col gap-1 text-sm">
            {p.sources.map((s) => (
              <li key={s.id} className="flex items-center gap-2">
                <span className="w-16 shrink-0 text-muted">{s.platform}</span>
                <span className={`min-w-0 flex-1 truncate ${s.active ? "" : "text-muted line-through"}`}>
                  {s.handle}
                </span>
                <span className="shrink-0 text-xs text-muted">
                  {s.last_polled_at ? `polled ${new Date(s.last_polled_at).toLocaleString()}` : "never polled"}
                </span>
                <button
                  type="button"
                  className="shrink-0 text-xs text-muted underline-offset-2 hover:text-fg hover:underline"
                  onClick={async () =>
                    done(await send("PATCH", `/api/people/${p.slug}/sources/${s.id}`, { active: !s.active }))
                  }
                >
                  {s.active ? "Pause" : "Resume"}
                </button>
              </li>
            ))}
          </ul>
          <AddSource slug={p.slug} onDone={done} />
        </section>
      ))}
    </div>
  );
}
