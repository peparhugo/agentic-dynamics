import matter from "gray-matter";
import type { Frontmatter } from "./types.js";

export interface ParsedDocument {
  frontmatter: Frontmatter;
  body: string;
}

function toDate(value: unknown): Date | null {
  if (value instanceof Date) return isNaN(value.getTime()) ? null : value;
  if (typeof value === "string" || typeof value === "number") {
    const d = new Date(value);
    return isNaN(d.getTime()) ? null : d;
  }
  return null;
}

function toTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).map((t) => t.trim()).filter(Boolean);
  if (typeof value === "string") {
    return value.split(",").map((t) => t.trim()).filter(Boolean);
  }
  return [];
}

/**
 * Parse a Markdown document with optional YAML frontmatter.
 * Normalizes the well-known keys: title, date, tags, draft, layout.
 * Unknown keys are preserved verbatim.
 */
export function parseDocument(raw: string, fallbackTitle = "Untitled"): ParsedDocument {
  const { data, content } = matter(raw);
  const frontmatter: Frontmatter = {
    ...data,
    title: typeof data.title === "string" && data.title.trim() ? data.title.trim() : fallbackTitle,
    date: toDate(data.date),
    tags: toTags(data.tags),
    draft: data.draft === true,
    layout: typeof data.layout === "string" && data.layout.trim() ? data.layout.trim() : "default",
  };
  return { frontmatter, body: content };
}
