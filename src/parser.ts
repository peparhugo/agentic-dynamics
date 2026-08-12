import matter from 'gray-matter';
import MarkdownIt from 'markdown-it';
import type { PageData } from './types';

export interface ParsedMarkdown {
  data: PageData;
  body: string;
}

const markdown = new MarkdownIt({ html: true, linkify: true, typographer: true });

export function normalizeDate(value: unknown): unknown {
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value.toISOString().slice(0, 10);
  }
  return value;
}

export function parseMarkdown(raw: string): ParsedMarkdown {
  const parsed = matter(raw);
  const data: PageData = parsed.data && typeof parsed.data === 'object'
    ? (parsed.data as PageData)
    : {};
  if (data.date !== undefined) {
    data.date = normalizeDate(data.date) as string | undefined;
  }
  return { data, body: parsed.content.trim() };
}

export function renderMarkdown(source: string): string {
  return markdown.render(source);
}
