export type TagKind = "domain" | "topic" | "entity" | "ticker";
export type Platform = "youtube" | "podcast" | "blog" | "arxiv" | "reddit" | "x";

export interface Tag {
  kind: TagKind;
  slug: string;
  name: string;
}

export interface PersonBrief {
  slug: string;
  name: string;
  avatar_url: string | null;
}

export interface Person extends PersonBrief {
  bio: string | null;
  domains: string[];
  auto_added: boolean;
  viewpoint_count: number;
}

export interface Source {
  id: number;
  platform: Platform;
  handle: string;
  poll_interval_min: number;
  last_polled_at: string | null;
  active: boolean;
}

export interface PersonDetail extends Person {
  sources: Source[];
}

export interface Viewpoint {
  id: number;
  claim: string;
  summary: string;
  quote: string;
  quote_timestamp: number | null;
  quote_url: string;
  stance: string | null;
  confidence: number;
  novelty_score: number;
  created_at: string;
  person: PersonBrief;
  via: PersonBrief | null;
  media: { platform: Platform; url: string; title: string | null; published_at: string | null };
  tags: Tag[];
}

export interface ViewpointPage {
  items: Viewpoint[];
  next_cursor: number | null;
}

export interface User {
  id: number;
  email: string | null;
  discord_id: string | null;
  is_admin: boolean;
}
