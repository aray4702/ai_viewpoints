"use client";

import { useState } from "react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setState("sending");
    const res = await fetch("/api/auth/magic-link", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email }),
    });
    setState(res.ok ? "sent" : "error");
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="mb-2 font-serif text-3xl font-semibold tracking-tight">Sign in</h1>
      <p className="mb-6 text-muted">Sign in to subscribe to people and topics.</p>

      {state === "sent" ? (
        <p className="rounded-lg border border-border bg-surface p-4">
          Check <strong>{email}</strong> for a sign-in link. It expires in 15 minutes.
        </p>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-3">
          <label htmlFor="email" className="text-sm font-medium">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-lg border border-border bg-surface px-4 py-2.5 outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={state === "sending"}
            className="rounded-lg bg-fg px-4 py-2.5 font-medium text-bg hover:opacity-90 disabled:opacity-60"
          >
            {state === "sending" ? "Sending…" : "Email me a sign-in link"}
          </button>
          {state === "error" && <p className="text-sm text-rose-600">Something went wrong. Try again.</p>}
        </form>
      )}

      <div className="my-6 flex items-center gap-3 text-xs text-muted">
        <span className="h-px flex-1 bg-border" /> or <span className="h-px flex-1 bg-border" />
      </div>
      <a
        href="/api/auth/discord/login"
        className="block rounded-lg border border-border bg-surface px-4 py-2.5 text-center font-medium hover:border-accent"
      >
        Continue with Discord
      </a>
    </div>
  );
}
