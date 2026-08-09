import matter from "gray-matter";
import type { Frontmatter } from "./types.js";

const KNOWN_KEYS = new Set(["title", "date", "tags", "draft", "layout"]);

/** Parse a markdown document with optional YAML frontmatter. */
export function parseFrontmatter(src: string): { frontmatter: Frontmatter; body: string } {
  const { data, content } = matter(src);
  return { frontmatter: normalize(data), body: content };
}

export function normalize(data: Record<string, unknown>): Frontmatter {
  const extra: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(data)) {
    if (!KNOWN_KEYS.has(k)) extra[k] = v;
  }
  return {
    title: typeof data.title === "string" ? data.title : "",
    date: coerceDate(data.date),
    tags: coerceTags(data.tags),
    draft: coerceBool(data.draft),
    layout: typeof data.layout === "string" ? data.layout : "default",
    extra,
  };
}

function coerceDate(v: unknown): Date | null {
  if (v instanceof Date) return isNaN(v.getTime()) ? null : v;
  if (typeof v === "string" || typeof v === "number") {
    const d = new Date(v);
    return isNaN(d.getTime()) ? null : d;
  }
  return null;
}

function coerceTags(v: unknown): string[] {
  if (Array.isArray(v)) return v.map(String).map((s) => s.trim()).filter(Boolean);
  if (typeof v === "string") {
    return v.split(",").map((s) => s.trim()).filter(Boolean);
  }
  return [];
}

function coerceBool(v: unknown): boolean {
  if (typeof v === "boolean") return v;
  if (typeof v === "string") return v.toLowerCase() === "true";
  return false;
}
