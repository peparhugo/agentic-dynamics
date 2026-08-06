import matter from 'gray-matter';
import path from 'node:path';
import type { Frontmatter } from './types.js';

export interface ParsedDocument {
  frontmatter: Frontmatter;
  body: string;
}

function toDate(value: unknown): Date | null {
  if (value instanceof Date) return isNaN(value.getTime()) ? null : value;
  if (typeof value === 'string' || typeof value === 'number') {
    const d = new Date(value);
    return isNaN(d.getTime()) ? null : d;
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

/** Derive a human-readable title from a file name: "my-first-post.md" -> "My First Post". */
export function titleFromFilename(filePath: string): string {
  const base = path.basename(filePath, path.extname(filePath));
  return base
    .replace(/[-_]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Parse a markdown document with optional YAML frontmatter and normalize
 * the well-known fields (title, date, tags, draft, layout, slug).
 */
export function parseDocument(raw: string, sourcePath = 'untitled.md'): ParsedDocument {
  const { data, content } = matter(raw);

  const frontmatter: Frontmatter = {
    ...data,
    title: typeof data.title === 'string' && data.title.trim() !== ''
      ? data.title.trim()
      : titleFromFilename(sourcePath),
    date: toDate(data.date),
    tags: toTags(data.tags),
    draft: data.draft === true || data.draft === 'true',
    layout: typeof data.layout === 'string' && data.layout.trim() !== ''
      ? data.layout.trim()
      : 'default',
    slug: typeof data.slug === 'string' && data.slug.trim() !== '' ? slugify(data.slug) : undefined,
    description: typeof data.description === 'string' ? data.description : undefined,
  };

  return { frontmatter, body: content };
}

/** Convert an arbitrary string into a URL-safe slug. */
export function slugify(input: string): string {
  return input
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}
