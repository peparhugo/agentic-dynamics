import matter from "gray-matter";
import type { Frontmatter } from "./types.js";

export interface ParsedDocument {
  frontmatter: Frontmatter;
  body: string;
}

function toDate(value: unknown): Date | null {
  if (value instanceof Date && !isNaN(value.getTime())) return value;
  if (typeof value === "string" || typeof value === "number") {
    const d = new Date(value);
    if (!isNaN(d.getTime())) return d;
  }
  return null;
}

function toTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((t) => String(t).trim()).filter(Boolean);
  }
  if (typeof value === "string") {
    return value
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
  }
  return [];
}

function toBool(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return value.trim().toLowerCase() === "true";
  return false;
}

/**
 * Parse a markdown document with optional YAML frontmatter.
 * Normalizes the well-known fields: title, date, tags, draft.
 * Unknown fields are passed through untouched.
 */
export function parseFrontmatter(raw: string, fallbackTitle = "Untitled"): ParsedDocument {
  const { data, content } = matter(raw);
  const { title, date, tags, draft, ...rest } = data as Record<string, unknown>;
  const frontmatter: Frontmatter = {
    ...rest,
    title: typeof title === "string" && title.trim() ? title.trim() : fallbackTitle,
    date: toDate(date),
    tags: toTags(tags),
    draft: toBool(draft),
  };
  if (typeof data.layout === "string") frontmatter.layout = data.layout;
  return { frontmatter, body: content };
}
