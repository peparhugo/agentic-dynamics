import matter from 'gray-matter';
import type { Frontmatter } from './types.js';

export interface ParsedDocument {
  frontmatter: Frontmatter;
  body: string;
}

function toDate(value: unknown): Date | null {
  if (value instanceof Date && !isNaN(value.getTime())) return value;
  if (typeof value === 'string' || typeof value === 'number') {
    const d = new Date(value);
    if (!isNaN(d.getTime())) return d;
  }
  return null;
}

function toTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((t) => String(t).trim()).filter(Boolean);
  }
  if (typeof value === 'string') {
    return value
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);
  }
  return [];
}

/**
 * Parse a markdown document with optional YAML frontmatter.
 * Normalizes: title (string), date (Date|null), tags (string[]), draft (boolean).
 * Extra keys are preserved as-is.
 */
export function parseFrontmatter(raw: string, fallbackTitle = 'Untitled'): ParsedDocument {
  const { data, content } = matter(raw);
  const { title, date, tags, draft, ...rest } = data as Record<string, unknown>;

  const frontmatter: Frontmatter = {
    ...rest,
    title: typeof title === 'string' && title.trim() ? title.trim() : fallbackTitle,
    date: toDate(date),
    tags: toTags(tags),
    draft: draft === true || draft === 'true',
  };

  return { frontmatter, body: content };
}

/** Derive a short plain-text excerpt from a markdown body. */
export function makeExcerpt(markdown: string, maxLength = 200): string {
  const text = markdown
    .replace(/```[\s\S]*?```/g, ' ') // fenced code blocks
    .replace(/`[^`]*`/g, ' ') // inline code
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ') // images
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // links -> text
    .replace(/^#{1,6}\s+/gm, '') // headings
    .replace(/[*_>~#-]/g, ' ') // md punctuation
    .replace(/\s+/g, ' ')
    .trim();
  return text.length > maxLength ? text.slice(0, maxLength - 1).trimEnd() + '\u2026' : text;
}
