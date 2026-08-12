import matter from 'gray-matter';
import type { Frontmatter } from './types';

function toDateString(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'number') return new Date(value).toISOString().slice(0, 10);
  return undefined;
}

export function parseFrontmatter(source: string): { data: Frontmatter; content: string } {
  const parsed = matter(source);
  const data: Frontmatter = {};

  if (parsed.data.title !== undefined) {
    data.title = String(parsed.data.title);
  }
  if (parsed.data.date !== undefined) {
    data.date = toDateString(parsed.data.date);
  }
  if (Array.isArray(parsed.data.tags)) {
    data.tags = parsed.data.tags.filter((tag): tag is string | number | boolean => tag !== null && tag !== undefined).map(String);
  }

  return { data, content: parsed.content };
}
