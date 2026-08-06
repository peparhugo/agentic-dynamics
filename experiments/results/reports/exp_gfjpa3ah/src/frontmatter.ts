import matter from 'gray-matter';
import type { Frontmatter } from './types.js';

export interface ParsedDocument {
  frontmatter: Frontmatter;
  body: string;
}

/** Coerce a frontmatter `tags` value into a normalized, deduplicated string array. */
export function normalizeTags(value: unknown): string[] {
  let tags: string[] = [];
  if (Array.isArray(value)) {
    tags = value.map((t) => String(t));
  } else if (typeof value === 'string') {
    tags = value.split(',');
  }
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of tags) {
    const t = raw.trim();
    if (!t) continue;
    const key = t.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(t);
  }
  return out;
}

/** Coerce a frontmatter `date` value (Date | string | number) into a Date, or null if absent/invalid. */
export function normalizeDate(value: unknown): Date | null {
  if (value instanceof Date) return isNaN(value.getTime()) ? null : value;
  if (typeof value === 'string' || typeof value === 'number') {
    const d = new Date(value);
    return isNaN(d.getTime()) ? null : d;
  }
  return null;
}

/** Turn arbitrary text into a URL-safe slug. */
export function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '') // strip diacritics
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/**
 * Parse a Markdown document with optional YAML frontmatter.
 * `fallbackTitle` is used when no `title` key is present (typically the filename).
 */
export function parseDocument(raw: string, fallbackTitle = 'Untitled'): ParsedDocument {
  const { data, content } = matter(raw);

  const frontmatter: Frontmatter = {
    ...data,
    title: typeof data.title === 'string' && data.title.trim() ? data.title.trim() : fallbackTitle,
    date: normalizeDate(data.date),
    tags: normalizeTags(data.tags),
    draft: data.draft === true,
    layout: typeof data.layout === 'string' && data.layout.trim() ? data.layout.trim() : 'default',
    description: typeof data.description === 'string' ? data.description : '',
  };
  if (typeof data.slug === 'string' && data.slug.trim()) {
    frontmatter.slug = slugify(data.slug);
  }

  return { frontmatter, body: content };
}
