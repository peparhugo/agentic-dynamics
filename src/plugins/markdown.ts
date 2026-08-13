import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { BuildPage, Plugin } from '../plugin.js';

function asDate(value: unknown): string | undefined {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? undefined : value.toISOString().slice(0, 10);
  }
  return typeof value === 'string' || typeof value === 'number' ? String(value) : undefined;
}

function asTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function templateName(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  async onFile(page: BuildPage): Promise<void> {
    const parsed = matter(page.source);
    page.data = parsed.data;
    page.title = typeof parsed.data.title === 'string' && parsed.data.title.trim()
      ? parsed.data.title.trim()
      : path.parse(page.sourcePath).name;
    page.date = asDate(parsed.data.date);
    page.tags = asTags(parsed.data.tags);
    page.template = templateName(parsed.data.template);
    page.layout = parsed.data.layout === false ? false : templateName(parsed.data.layout);
    page.html = await marked.parse(parsed.content);
  }
}
