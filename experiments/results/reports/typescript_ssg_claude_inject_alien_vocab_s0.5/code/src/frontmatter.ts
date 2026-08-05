import matter from 'gray-matter';
import type { Frontmatter } from './types.js';

export interface ParsedDocument {
  frontmatter: Frontmatter;
  body: string;
}

/** Coerce a frontmatter tags value into a clean string array. */
function normalizeTags(raw: unknown): string[] {
  if (raw == null) return [];
  const list = Array.isArray(raw)
    ? raw
    : String(raw)
        .split(',')
        .map((t) => t.trim());
  return [...new Set(list.map((t) => String(t).trim()).filter(Boolean))];
}

/** Coerce a frontmatter date into a Date, or null if absent/invalid. */
function normalizeDate(raw: unknown): Date | null {
  if (raw == null) return null;
  if (raw instanceof Date) return isNaN(raw.getTime()) ? null : raw;
  const d = new Date(String(raw));
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Parse a Markdown document with optional YAML frontmatter.
 * Normalizes the well-known keys (title, date, tags, draft) and passes
 * everything else through.
 */
export function parseFrontmatter(source: string, fallbackTitle = 'Untitled'): ParsedDocument {
  const { data, content } = matter(source);

  const frontmatter: Frontmatter = {
    ...data,
    title: data.title != null ? String(data.title) : fallbackTitle,
    date: normalizeDate(data.date),
    tags: normalizeTags(data.tags),
    draft: data.draft === true || data.draft === 'true',
  };
  if (typeof data.layout === 'string') frontmatter.layout = data.layout;

  return { frontmatter, body: content };
}
