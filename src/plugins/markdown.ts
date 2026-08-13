import path from 'node:path';
import { createHash } from 'node:crypto';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Plugin } from '../plugin';

function normalizeDate(value: unknown): string | undefined {
  if (value instanceof Date && !Number.isNaN(value.valueOf())) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';
  private cache = new Map<string, { data: Record<string, unknown>; date?: string; tags: string[]; content: string }>();

  async onFile(page: import('../plugin').PluginPage): Promise<void> {
    const key = createHash('sha256').update(page.source).digest('hex');
    const cached = this.cache.get(key);
    if (cached) {
      page.data = cached.data;
      page.title = typeof cached.data.title === 'string'
        ? cached.data.title
        : path.basename(page.filePath, path.extname(page.filePath));
      page.date = cached.date;
      page.tags = [...cached.tags];
      page.content = cached.content;
      page.output = page.content;
      return;
    }
    const parsed = matter(page.source);
    page.data = parsed.data;
    page.title = typeof parsed.data.title === 'string'
      ? parsed.data.title
      : path.basename(page.filePath, path.extname(page.filePath));
    page.date = normalizeDate(parsed.data.date);
    page.tags = normalizeTags(parsed.data.tags);
    page.content = await marked.parse(parsed.content);
    page.output = page.content;
    this.cache.set(key, {
      data: page.data,
      date: page.date,
      tags: [...page.tags],
      content: page.content
    });
  }
}
