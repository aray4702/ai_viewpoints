import Link from "next/link";

import { QuoteActions } from "@/components/QuoteActions";
import { ShowSummary } from "@/components/ShowSummary";
import type { Viewpoint } from "@/lib/types";
import { actionClass } from "@/lib/styles";
import { EMPTY, feedHref, withFilter, type Filters } from "@/lib/url";

const PLATFORM_LABEL: Record<string, string> = {
  youtube: "YouTube",
  podcast: "Podcast",
  blog: "Blog",
  arxiv: "arXiv",
  reddit: "Reddit",
  x: "X",
};

const STANCE_STYLE: Record<string, string> = {
  bullish: "text-emerald-700 dark:text-emerald-400",
  positive: "text-emerald-700 dark:text-emerald-400",
  bearish: "text-rose-700 dark:text-rose-400",
  negative: "text-rose-700 dark:text-rose-400",
  prediction: "text-accent",
};

function fmtTs(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

/** What the source link says: "▶ Watch at 3:06", "▶ Listen at 1:02:10", "Read the source ↗". */
function sourceLabel(v: Viewpoint): string {
  const at = v.quote_timestamp !== null ? ` at ${fmtTs(v.quote_timestamp)}` : "";
  switch (v.media.platform) {
    case "youtube":
      return at ? `▶ Watch${at}` : "▶ Watch on YouTube";
    case "podcast":
      return at ? `▶ Listen${at}` : "▶ Listen to the episode";
    case "arxiv":
      return "Read the paper ↗";
    default:
      return "Read the source ↗";
  }
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function ViewpointCard({ v, filters = EMPTY }: { v: Viewpoint; filters?: Filters }) {
  const tags = [...v.tags].sort((a, b) => a.kind.localeCompare(b.kind));
  return (
    <article className="rounded-xl border border-border bg-surface p-5 sm:p-6">
      <header className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
        <Link href={`/people/${v.person.slug}`} className="font-medium text-fg hover:text-accent">
          {v.person.name}
        </Link>
        <span aria-hidden>·</span>
        <span>
          {PLATFORM_LABEL[v.media.platform] ?? v.media.platform}
          {v.via && (
            <>
              {" via "}
              <Link href={`/people/${v.via.slug}`} className="hover:text-accent">
                {v.via.name}
              </Link>
            </>
          )}
        </span>
        <span aria-hidden>·</span>
        <time dateTime={v.media.published_at ?? v.created_at}>
          {fmtDate(v.media.published_at ?? v.created_at)}
        </time>
        {v.stance && v.stance !== "neutral" && (
          <span className={`ml-auto text-xs font-medium uppercase tracking-wide ${STANCE_STYLE[v.stance] ?? ""}`}>
            {v.stance}
          </span>
        )}
      </header>

      <h2 className="text-[17px] font-semibold leading-snug sm:text-lg">
        <Link href={`/v/${v.id}`} className="hover:text-accent">
          {v.claim}
        </Link>
      </h2>
      <ShowSummary text={v.summary} />

      <blockquote className="mt-4 border-l-2 border-accent pl-4 text-[15px] italic leading-relaxed">
        “{v.quote}”
        <QuoteActions translation={v.quote_translation}>
          <a
            href={v.quote_url}
            target="_blank"
            rel="noreferrer"
            title={v.media.title ?? undefined}
            aria-label={`${sourceLabel(v)}: ${v.media.title ?? "source"} (opens in a new tab)`}
            className={actionClass}
          >
            {sourceLabel(v)}
          </a>
        </QuoteActions>
      </blockquote>

      {tags.length > 0 && (
        <ul className="mt-4 flex flex-wrap gap-1.5">
          {tags.map((t) => (
            <li key={`${t.kind}:${t.slug}`}>
              <Link
                href={feedHref(withFilter(filters, t.kind === "domain" ? "domain" : "tag", t.slug))}
                className={`inline-block rounded-full px-2.5 py-0.5 text-xs hover:bg-accent-soft hover:text-accent ${
                  t.kind === "domain" ? "bg-accent-soft text-accent" : "bg-chip text-muted"
                }`}
              >
                {t.kind === "ticker" ? `$${t.name}` : t.name}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
