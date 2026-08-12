import matter from 'gray-matter';
import { marked } from 'marked';
import { Page } from './types';

export interface ParsedDoc {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  content: string;
}

export function slugify(filename: string): string {
  return filename.replace(/\.md$/i, '').replace(/\.markdown$/i, '');
}

function normalizeTags(tags: unknown): string[] {
  if (Array.isArray(tags)) {
    return tags.map(String).filter((t) => t.trim() !== '');
  }
  if (typeof tags === 'string' && tags.trim() !== '') {
    return tags
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t !== '');
  }
  return [];
}

function normalizeDate(date: unknown): string | undefined {
  if (date instanceof Date && !Number.isNaN(date.getTime())) {
    return date.toISOString();
  }
  if (typeof date === 'string' && date.trim() !== '') {
    return date;
  }
  if (typeof date === 'number') {
    return new Date(date).toISOString();
  }
  return undefined;
}

export function parseMarkdown(slug: string, raw: string): ParsedDoc {
  const { data, content } = matter(raw);
  const title =
    typeof data.title === 'string' && data.title.trim() !== ''
      ? data.title.trim()
      : slug;

  return {
    slug,
    title,
    date: normalizeDate(data.date),
    tags: normalizeTags(data.tags),
    content: marked.parse(content, { async: false }) as string,
  };
}

export function toPage(doc: ParsedDoc): Page {
  return {
    slug: doc.slug,
    title: doc.title,
    date: doc.date,
    tags: doc.tags,
    content: doc.content,
  };
}
