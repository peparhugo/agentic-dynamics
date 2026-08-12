import matter from 'gray-matter';
import { marked } from 'marked';
import path from 'node:path';
import type { Page } from '../index';
import { Plugin } from '../plugin';

function normaliseTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function normaliseDate(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return String(value);
}

export async function parseMarkdown(source: string, sourcePath = 'page.md'): Promise<Page> {
  const parsed = matter(source);
  const name = path.basename(sourcePath, path.extname(sourcePath));
  const title = typeof parsed.data.title === 'string' && parsed.data.title.trim()
    ? parsed.data.title.trim() : name.replace(/[-_]+/g, ' ');
  return {
    title, date: normaliseDate(parsed.data.date), tags: normaliseTags(parsed.data.tags),
    slug: `${name}.html`, html: await marked.parse(parsed.content), sourcePath,
    template: typeof parsed.data.template === 'string' ? parsed.data.template : undefined,
    layout: typeof parsed.data.layout === 'string' ? parsed.data.layout : undefined,
    data: parsed.data as Record<string, unknown>
  };
}

/** Built-in Markdown support. Parsing is exposed here so the core remains format-agnostic. */
export class MarkdownPlugin implements Plugin {
  parse = parseMarkdown;
}
