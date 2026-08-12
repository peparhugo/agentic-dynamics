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
  if (parsed.data.template !== undefined) {
    data.template = String(parsed.data.template);
  }
  if (parsed.data.layout !== undefined) {
    data.layout = String(parsed.data.layout);
  }

  for (const key of Object.keys(parsed.data)) {
    if (key in data) continue;
    const value = parsed.data[key];
    if (value !== undefined && value !== null) {
      data[key] = value;
    }
  }

  return { data, content: parsed.content };
}
