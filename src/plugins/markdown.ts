import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Plugin, PluginPage } from '../plugin';

export function normalizeDate(value: unknown): string | undefined {
  if (value instanceof Date && !Number.isNaN(value.valueOf())) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
}

export function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  async onFile(page: PluginPage): Promise<void> {
    const parsed = matter(page.source);
    page.data = parsed.data;
    page.title = typeof parsed.data.title === 'string' && parsed.data.title.trim()
      ? parsed.data.title.trim()
      : path.basename(page.sourcePath, path.extname(page.sourcePath));
    page.date = normalizeDate(parsed.data.date);
    page.tags = normalizeTags(parsed.data.tags);
    page.content = (await marked.parse(parsed.content)).trimEnd();
  }
}
