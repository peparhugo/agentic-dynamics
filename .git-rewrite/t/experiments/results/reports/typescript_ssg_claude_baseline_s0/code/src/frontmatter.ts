import matter from "gray-matter";
import type { PageMeta } from "./types.js";

const KNOWN_KEYS = new Set(["title", "date", "tags", "draft", "layout"]);

function normalizeDate(value: unknown): Date | null {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (typeof value === "string" || typeof value === "number") {
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  return null;
}

function normalizeTags(value: unknown): string[] {
  let raw: unknown[];
  if (Array.isArray(value)) raw = value;
  else if (typeof value === "string") raw = value.split(",");
  else return [];
  const seen = new Set<string>();
  for (const item of raw) {
    const tag = String(item).trim();
    if (tag) seen.add(tag);
  }
  return [...seen];
}

function normalizeDraft(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return value.trim().toLowerCase() === "true";
  return false;
}

export function titleFromSlug(slug: string): string {
  const last = slug.split("/").pop() ?? slug;
  return last
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

/**
 * Parse a markdown document with optional YAML frontmatter.
 * Returns normalized metadata and the markdown body.
 */
export function parseFrontmatter(
  raw: string,
  fallbackTitle = "Untitled"
): { meta: PageMeta; body: string } {
  const { data, content } = matter(raw);

  const extra: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(data)) {
    if (!KNOWN_KEYS.has(key)) extra[key] = value;
  }

  const meta: PageMeta = {
    title:
      typeof data.title === "string" && data.title.trim()
        ? data.title.trim()
        : fallbackTitle,
    date: normalizeDate(data.date),
    tags: normalizeTags(data.tags),
    draft: normalizeDraft(data.draft),
    layout:
      typeof data.layout === "string" && data.layout.trim()
        ? data.layout.trim()
        : "default",
    extra,
  };

  return { meta, body: content };
}
